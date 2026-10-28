"""M2 endpoints: model upload, dataset ingestion/target selection, compatibility reports."""

from __future__ import annotations

import hashlib
from pathlib import PurePath

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .compatibility import run_compatibility
from .models import CompatibilityReport, Dataset, ModelArtifact
from .validators import (
    DATASET_LIMIT_BYTES,
    MODEL_LIMIT_BYTES,
    validate_csv_bytes,
    validate_model_upload,
)

SIGNATURE_BYTES = 16


class PayloadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Uploaded file exceeds the allowed size."
    default_code = "payload_too_large"


def _issues_payload(issues) -> list[dict]:
    return [
        {"code": i.code, "message": i.message, "expected": i.expected, "actual": i.actual}
        for i in issues
    ]


def _raise_for_issues(issues, size_codes: set[str]) -> None:
    if not issues:
        return
    if any(issue.code in size_codes for issue in issues):
        raise PayloadTooLarge()
    raise ValidationError({"file": _issues_payload(issues)})


def _uploaded_file(request):
    upload = request.FILES.get("file")
    if upload is None:
        raise ValidationError({"file": ["A file is required."]})
    return upload


def _sha256_of(upload) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def dataset_payload(dataset: Dataset) -> dict:
    return {
        "id": str(dataset.id),
        "original_filename": dataset.original_filename,
        "size_bytes": dataset.size_bytes,
        "sha256": dataset.sha256,
        "columns": dataset.columns,
        "row_count": dataset.row_count,
        "suggested_target": dataset.suggested_target,
        "target_column": dataset.target_column,
        "created_at": dataset.created_at,
    }


def model_payload(model: ModelArtifact) -> dict:
    return {
        "id": str(model.id),
        "original_filename": model.original_filename,
        "extension": model.extension,
        "size_bytes": model.size_bytes,
        "sha256": model.sha256,
        "created_at": model.created_at,
    }


def report_payload(report: CompatibilityReport) -> dict:
    return {
        "id": str(report.id),
        "model_id": str(report.model_artifact_id),
        "dataset_id": str(report.dataset_id),
        "result": report.result,
        "checks": report.checks,
        "created_at": report.created_at,
    }


class ModelUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = _uploaded_file(request)
        # Reject by declared size first so oversize bodies are never read or hashed.
        if upload.size > MODEL_LIMIT_BYTES:
            raise PayloadTooLarge("Model exceeds 100 MB.")
        prefix = upload.read(SIGNATURE_BYTES)
        upload.seek(0)
        _raise_for_issues(validate_model_upload(upload.name, upload.size, prefix), {"MODEL_SIZE"})
        artifact = ModelArtifact(
            owner=request.user,
            original_filename=upload.name[:255],
            extension=PurePath(upload.name).suffix.lower(),
            size_bytes=upload.size,
            sha256=_sha256_of(upload),
        )
        artifact.file.save(upload.name, upload, save=False)
        artifact.save()
        return Response(model_payload(artifact), status=status.HTTP_201_CREATED)


class ModelDetailView(APIView):
    def get(self, request, id):
        artifact = get_object_or_404(ModelArtifact, id=id, owner=request.user)
        return Response(model_payload(artifact))


class DatasetUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = _uploaded_file(request)
        if upload.size > DATASET_LIMIT_BYTES:
            raise PayloadTooLarge("Dataset exceeds 50 MB.")
        content = upload.read()
        target = (request.data.get("target_column") or "").strip() or None
        summary, issues = validate_csv_bytes(content, target_column=target)
        _raise_for_issues(issues, {"DATASET_SIZE"})
        suggested = summary.columns[-1] if summary.columns else ""
        dataset = Dataset(
            owner=request.user,
            original_filename=upload.name[:255],
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            columns=list(summary.columns),
            row_count=summary.rows,
            suggested_target=suggested,
            target_column=summary.suggested_target,
        )
        dataset.file.save(upload.name, ContentFile(content), save=False)
        dataset.save()
        return Response(dataset_payload(dataset), status=status.HTTP_201_CREATED)


class DatasetDetailView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, id):
        dataset = get_object_or_404(Dataset, id=id, owner=request.user)
        return Response(dataset_payload(dataset))

    def patch(self, request, id):
        """Override the suggested target; the whole CSV is re-validated for the new target."""
        dataset = get_object_or_404(Dataset, id=id, owner=request.user)
        target = (request.data.get("target_column") or "").strip()
        if not target:
            raise ValidationError({"target_column": ["This field is required."]})
        with dataset.file.open("rb") as handle:
            content = handle.read()
        _, issues = validate_csv_bytes(content, target_column=target)
        _raise_for_issues(issues, set())
        dataset.target_column = target
        dataset.save(update_fields=["target_column"])
        return Response(dataset_payload(dataset))


class CompatibilityReportCreateView(APIView):
    def post(self, request):
        errors = {}
        for field in ("model_id", "dataset_id"):
            if not request.data.get(field):
                errors[field] = ["This field is required."]
        if errors:
            raise ValidationError(errors)
        try:
            model = ModelArtifact.objects.get(id=request.data["model_id"], owner=request.user)
            dataset = Dataset.objects.get(id=request.data["dataset_id"], owner=request.user)
        except (
            ModelArtifact.DoesNotExist,
            Dataset.DoesNotExist,
            DjangoValidationError,
            ValueError,
            TypeError,
        ) as exc:
            raise NotFound() from exc
        report = run_compatibility(request.user, model, dataset)
        return Response(report_payload(report), status=status.HTTP_201_CREATED)


class CompatibilityReportDetailView(APIView):
    def get(self, request, id):
        report = get_object_or_404(CompatibilityReport, id=id, owner=request.user)
        return Response(report_payload(report))
