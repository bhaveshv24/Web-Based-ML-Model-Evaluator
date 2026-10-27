from django.urls import path

from .views import EvaluationDetailView, EvaluationListView

urlpatterns = [
    path("evaluations", EvaluationListView.as_view(), name="evaluation-list"),
    path("evaluations/<uuid:id>", EvaluationDetailView.as_view(), name="evaluation-detail"),
]
