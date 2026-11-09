"""Versioned API routes."""

from accounts.views import AdminAuditListView, AdminUserListView, AdminUserView
from benchmarking.views import dashboard_asset
from django.urls import include, path

urlpatterns = [
    path("results", dashboard_asset),
    path("results/dashboard.js", dashboard_asset, {"asset": "dashboard.js"}),
    path("results/dashboard.css", dashboard_asset, {"asset": "dashboard.css"}),
    path("results/favicon.svg", dashboard_asset, {"asset": "favicon.svg"}),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/admin/users", AdminUserListView.as_view(), name="admin-users"),
    path("api/v1/admin/audit", AdminAuditListView.as_view(), name="admin-audit"),
    path("api/v1/admin/users/<uuid:id>", AdminUserView.as_view(), name="admin-user"),
    path("api/v1/", include("evaluations.urls")),
    path("api/v1/", include("benchmarking.urls")),
    path("api/v1/", include("ingestion.urls")),
    path("api/v1/", include("workspaces.urls")),
]
