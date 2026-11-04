"""Owner-scoped comparisons and downloadable reports (API-18..20)."""

from evaluations.models import Comparison, Evaluation
from evaluations.views import EvaluationNotFinished, OwnedEvaluationMixin
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from .comparison import ComparisonError, EvaluationResult, best_per_metric
from .reports import download, evaluation_data, report_data


class ComparisonInput(serializers.Serializer):
    evaluation_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=2, max_length=5,
    )


def comparison_data(owner, ids):
    evaluations = Evaluation.objects.filter(owner=owner).select_related(
        "owner", "model_artifact", "dataset",
    ).in_bulk(ids)
    if len(evaluations) != len(set(ids)):
        raise NotFound()
    rows = [evaluations[evaluation_id] for evaluation_id in ids]
    try:
        winners = best_per_metric([
            EvaluationResult(
                str(row.id), row.dataset_sha256, row.task_type, row.metrics_json or {}, row.status,
            )
            for row in rows
        ])
    except ComparisonError as exc:
        raise ValidationError({"evaluation_ids": [str(exc)]}) from exc
    return {"evaluations": [evaluation_data(row) for row in rows], "best_per_metric": winners}


class ComparisonCreateView(generics.GenericAPIView):
    serializer_class = ComparisonInput

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["evaluation_ids"]
        data = comparison_data(request.user, ids)
        comparison = Comparison.objects.create(
            owner=request.user, evaluation_ids=[str(evaluation_id) for evaluation_id in ids],
        )
        return Response({"id": comparison.id, **data}, status=status.HTTP_201_CREATED)


class OwnedComparisonMixin:
    lookup_field = "id"

    def get_queryset(self):
        return Comparison.objects.filter(owner=self.request.user)

    def get_data(self, comparison):
        ids = [serializers.UUIDField().to_internal_value(pk) for pk in comparison.evaluation_ids]
        return comparison_data(self.request.user, ids)


class ComparisonDetailView(OwnedComparisonMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        comparison = self.get_object()
        return Response({"id": comparison.id, **self.get_data(comparison)})


class ComparisonReportView(OwnedComparisonMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        comparison = self.get_object()
        data = report_data("comparison", comparison.id, request.user, self.get_data(comparison))
        return download(data, kwargs["extension"])


class EvaluationReportView(OwnedEvaluationMixin, generics.GenericAPIView):
    def get_queryset(self):
        return super().get_queryset().select_related("owner", "model_artifact", "dataset")

    def get(self, request, *args, **kwargs):
        evaluation = self.get_object()
        if evaluation.status != Evaluation.Status.SUCCEEDED:
            raise EvaluationNotFinished()
        data = report_data("evaluation", evaluation.id, request.user, {
            "evaluations": [evaluation_data(evaluation)],
        })
        return download(data, kwargs["extension"])


def dashboard_asset(request, asset="index.html"):
    from pathlib import Path

    from django.http import FileResponse

    content_types = {
        "index.html": "text/html; charset=utf-8",
        "dashboard.css": "text/css; charset=utf-8",
        "dashboard.js": "text/javascript; charset=utf-8",
        "favicon.svg": "image/svg+xml",
    }
    # The URLconf supplies a fixed asset name; the result data is always fetched with JWT.
    directory = Path(__file__).with_name("dashboard")
    response = FileResponse((directory / asset).open("rb"), content_type=content_types[asset])
    response["Content-Security-Policy"] = (
        "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response
