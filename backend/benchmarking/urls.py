from django.urls import path, re_path

from .views import (
    ComparisonCreateView,
    ComparisonDetailView,
    ComparisonReportView,
    EvaluationReportView,
)

UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"

urlpatterns = [
    path("comparisons", ComparisonCreateView.as_view(), name="comparison-create"),
    path("comparisons/<uuid:id>", ComparisonDetailView.as_view(), name="comparison-detail"),
    re_path(
        rf"^comparisons/(?P<id>{UUID})/report\.(?P<extension>json|pdf)$",
        ComparisonReportView.as_view(), name="comparison-report",
    ),
    re_path(
        rf"^evaluations/(?P<id>{UUID})/report\.(?P<extension>json|pdf)$",
        EvaluationReportView.as_view(), name="evaluation-report",
    ),
]
