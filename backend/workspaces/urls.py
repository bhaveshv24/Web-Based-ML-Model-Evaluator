from django.urls import path

from .views import (
    AvailableWorkspaceListView,
    WorkspaceEvaluationListView,
    WorkspaceListCreateView,
    WorkspaceMemberCreateView,
)

urlpatterns = [
    path("workspaces/available", AvailableWorkspaceListView.as_view(), name="workspace-available"),
    path("workspaces", WorkspaceListCreateView.as_view(), name="workspace-list"),
    path(
        "workspaces/<uuid:id>/members",
        WorkspaceMemberCreateView.as_view(),
        name="workspace-member",
    ),
    path(
        "workspaces/<uuid:id>/evaluations",
        WorkspaceEvaluationListView.as_view(),
        name="workspace-evaluations",
    ),
]
