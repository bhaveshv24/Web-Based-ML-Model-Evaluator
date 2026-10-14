from django.urls import path

from .views import WorkspaceEvaluationListView, WorkspaceListCreateView, WorkspaceMemberCreateView

urlpatterns = [
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
