"""Shared metadata for Appendix B reports and the comparison view."""

from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone


def evaluation_data(evaluation):
    model = evaluation.model_artifact
    dataset = evaluation.dataset
    return {
        "id": str(evaluation.id),
        "owner": {"id": str(evaluation.owner_id), "email": evaluation.owner.email},
        "task_type": evaluation.task_type,
        "status": evaluation.status,
        "duration_seconds": evaluation.duration_seconds,
        "sandbox_image": evaluation.sandbox_image,
        "model": {
            "id": str(model.id) if model else None,
            "filename": model.original_filename if model else None,
            "format": model.extension if model else None,
            "size_bytes": model.size_bytes if model else None,
            "sha256": evaluation.model_sha256,
        },
        "dataset": {
            "id": str(dataset.id) if dataset else None,
            "filename": dataset.original_filename if dataset else None,
            "rows": dataset.row_count if dataset else None,
            "columns": dataset.columns if dataset else None,
            "target_column": evaluation.target_column,
            "sha256": evaluation.dataset_sha256,
        },
        "metrics": evaluation.metrics_json or {},
        "charts": evaluation.charts_json or {},
    }


def report_data(kind, identifier, owner, data):
    return {
        "schema_version": 1,
        "report_type": kind,
        "id": str(identifier),
        "generated_at": timezone.now().isoformat(),
        "owner": {"id": str(owner.pk), "email": owner.email},
        **data,
    }


def download(data, extension):
    if extension == "json":
        response = JsonResponse(data)
    elif extension == "pdf":
        from .pdf import render_pdf

        response = HttpResponse(render_pdf(data), content_type="application/pdf")
    else:
        raise Http404
    filename = f"{data['report_type']}-{data['id']}.{extension}"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response
