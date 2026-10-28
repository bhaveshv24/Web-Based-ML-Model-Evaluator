from django.urls import path

from .views import (
    EvaluationChartsView,
    EvaluationDetailView,
    EvaluationListView,
    EvaluationStatusView,
)

urlpatterns = [
    path("evaluations", EvaluationListView.as_view(), name="evaluation-list"),
    path("evaluations/<uuid:id>", EvaluationDetailView.as_view(), name="evaluation-detail"),
    path("evaluations/<uuid:id>/status", EvaluationStatusView.as_view(), name="evaluation-status"),
    path("evaluations/<uuid:id>/charts", EvaluationChartsView.as_view(), name="evaluation-charts"),
]
