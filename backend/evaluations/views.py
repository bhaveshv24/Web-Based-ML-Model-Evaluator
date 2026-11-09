"""Evaluation history (MLE-03) and the asynchronous job API (MLE-09, API-08..10, 15..17)."""

from collections.abc import Mapping

from django.db import transaction
from django.db.models import F, Q
from django.utils.dateparse import parse_datetime
from ingestion.models import Dataset, ModelArtifact
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.response import Response
from workspaces.models import Workspace

from .models import Evaluation
from .serializers import (
    EvaluationCreateSerializer,
    EvaluationDetailSerializer,
    EvaluationSerializer,
    EvaluationStatusSerializer,
)
from .services import SubmissionError, submit_evaluation


class EvaluationNotFinished(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The evaluation has not succeeded, so no chart data is available."
    default_code = "evaluation_not_finished"


class QueueUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The evaluation could not be scheduled. Please try again."
    default_code = "queue_unavailable"


class EvaluationListView(generics.ListAPIView):
    serializer_class = EvaluationSerializer

    def get_queryset(self):
        queryset = Evaluation.objects.filter(owner=self.request.user)
        status_value = self.request.query_params.get("status")
        task_type = self.request.query_params.get("task_type")

        if status_value:
            if status_value not in Evaluation.Status.values:
                raise ValidationError({"status": ["Unknown evaluation status."]})
            queryset = queryset.filter(status=status_value)
        if task_type:
            if task_type not in Evaluation.TaskType.values:
                raise ValidationError({"task_type": ["Unknown task type."]})
            queryset = queryset.filter(task_type=task_type)

        for parameter, lookup in (("from", "created_at__gte"), ("to", "created_at__lte")):
            raw_value = self.request.query_params.get(parameter)
            if raw_value:
                try:
                    value = parse_datetime(raw_value)
                except ValueError:
                    value = None
                if value is None:
                    raise ValidationError({parameter: ["Use an ISO-8601 date-time."]})
                queryset = queryset.filter(**{lookup: value})
        return queryset

    def post(self, request):
        """API-15: validate, create a QUEUED job, enqueue it and return 202 immediately."""
        if not isinstance(request.data, Mapping):
            raise ValidationError({"non_field_errors": ["Request body must be an object."]})
        serializer = EvaluationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            model = ModelArtifact.objects.get(id=data["model_id"], owner=request.user)
            dataset = Dataset.objects.get(id=data["dataset_id"], owner=request.user)
        except (ModelArtifact.DoesNotExist, Dataset.DoesNotExist) as exc:
            raise NotFound() from exc
        workspace = None
        if data.get("workspace_id"):
            workspace = Workspace.objects.filter(
                Q(evaluator=request.user) | Q(members=request.user), id=data["workspace_id"]
            ).first()
            if workspace is None:
                raise NotFound()
        try:
            submission = submit_evaluation(
                request.user,
                model,
                dataset,
                task_type=data.get("task_type") or None,
                workspace=workspace,
            )
        except SubmissionError as exc:
            raise ValidationError({exc.field: [exc.message]}) from exc
        if not submission.scheduled:
            raise QueueUnavailable()
        evaluation = submission.evaluation
        body = EvaluationStatusSerializer(evaluation).data
        body["status_url"] = f"/api/v1/evaluations/{evaluation.id}/status"
        return Response(
            body,
            status=status.HTTP_202_ACCEPTED,
            headers={"Location": f"/api/v1/evaluations/{evaluation.id}"},
        )


class OwnedEvaluationMixin:
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        visible = Q(owner=user)
        if (
            user.role in {"EVALUATOR", "ADMIN"}
            and self.request.method in {"GET", "HEAD", "OPTIONS"}
        ):
            visible |= Q(workspace__evaluator=user, owner__workspaces__id=F("workspace_id"))
        return Evaluation.objects.filter(visible).distinct()


class EvaluationDetailView(OwnedEvaluationMixin, generics.RetrieveDestroyAPIView):
    serializer_class = EvaluationDetailSerializer

    def perform_destroy(self, instance):
        # Lock inputs in the same order as submission and retention so a new job cannot
        # start between the last-reference check and deletion of its input files.
        with transaction.atomic():
            model = ModelArtifact.objects.select_for_update().filter(
                pk=instance.model_artifact_id, owner=self.request.user
            ).first()
            dataset = Dataset.objects.select_for_update().filter(
                pk=instance.dataset_id, owner=self.request.user
            ).first()
            instance.delete()
            for upload in (model, dataset):
                if upload is not None and not upload.evaluations.exists():
                    upload.delete()


class EvaluationStatusView(OwnedEvaluationMixin, generics.RetrieveAPIView):
    serializer_class = EvaluationStatusSerializer


class EvaluationChartsView(OwnedEvaluationMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        evaluation = self.get_object()
        if evaluation.status != Evaluation.Status.SUCCEEDED:
            raise EvaluationNotFinished()
        return Response(
            {
                "id": str(evaluation.id),
                "task_type": evaluation.task_type,
                "charts": evaluation.charts_json,
            }
        )
