"""Evaluator-only workspace operations."""

from accounts.permissions import IsEvaluator
from evaluations.models import Evaluation
from rest_framework import generics, status
from rest_framework.response import Response

from .models import Workspace
from .serializers import (
    WorkspaceEvaluationSerializer,
    WorkspaceMemberSerializer,
    WorkspaceSerializer,
)


class WorkspaceListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsEvaluator,)
    serializer_class = WorkspaceSerializer

    def get_queryset(self):
        return Workspace.objects.filter(evaluator=self.request.user).prefetch_related("members")

    def perform_create(self, serializer):
        serializer.save(evaluator=self.request.user)


class OwnedWorkspaceMixin:
    permission_classes = (IsEvaluator,)

    def get_workspace(self):
        return generics.get_object_or_404(
            Workspace,
            id=self.kwargs["id"],
            evaluator=self.request.user,
        )


class WorkspaceMemberCreateView(OwnedWorkspaceMixin, generics.GenericAPIView):
    serializer_class = WorkspaceMemberSerializer

    def post(self, request, *args, **kwargs):
        workspace = self.get_workspace()
        serializer = self.get_serializer(data=request.data, context={"workspace": workspace})
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()
        return Response(self.get_serializer(membership).data, status=status.HTTP_201_CREATED)


class WorkspaceEvaluationListView(OwnedWorkspaceMixin, generics.ListAPIView):
    serializer_class = WorkspaceEvaluationSerializer

    def get_queryset(self):
        workspace = self.get_workspace()
        return Evaluation.objects.filter(
            workspace=workspace,
            owner__workspaces=workspace,
        ).select_related("owner")
