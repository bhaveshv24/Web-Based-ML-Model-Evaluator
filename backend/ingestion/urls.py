from django.urls import path

from .views import (
    CompatibilityReportCreateView,
    CompatibilityReportDetailView,
    DatasetDetailView,
    DatasetUploadView,
    ModelDetailView,
    ModelUploadView,
)

urlpatterns = [
    path("models", ModelUploadView.as_view(), name="model-upload"),
    path("models/<uuid:id>", ModelDetailView.as_view(), name="model-detail"),
    path("datasets", DatasetUploadView.as_view(), name="dataset-upload"),
    path("datasets/<uuid:id>", DatasetDetailView.as_view(), name="dataset-detail"),
    path("compatibility-reports", CompatibilityReportCreateView.as_view(), name="compat-create"),
    path(
        "compatibility-reports/<uuid:id>",
        CompatibilityReportDetailView.as_view(),
        name="compat-detail",
    ),
]
