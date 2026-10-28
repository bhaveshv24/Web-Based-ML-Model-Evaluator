"""Versioned API routes."""

from django.urls import include, path

urlpatterns = [
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("evaluations.urls")),
    path("api/v1/", include("ingestion.urls")),
    path("api/v1/", include("workspaces.urls")),
]
