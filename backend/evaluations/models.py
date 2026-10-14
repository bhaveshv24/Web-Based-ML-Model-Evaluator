"""Evaluation history and owned report/artifact records."""

import uuid

from django.conf import settings
from django.db import models


class Evaluation(models.Model):
    class TaskType(models.TextChoices):
        CLASSIFICATION = "CLASSIFICATION", "Classification"
        REGRESSION = "REGRESSION", "Regression"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        TIMED_OUT = "TIMED_OUT", "Timed out"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="evaluations",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluations",
    )
    task_type = models.CharField(max_length=20, choices=TaskType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    metrics_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class StoredEvaluationFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE)
    file = models.FileField(upload_to="evaluations/%Y/%m/%d")

    class Meta:
        abstract = True


class EvaluationArtifact(StoredEvaluationFile):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="artifacts")


class Report(StoredEvaluationFile):
    class Format(models.TextChoices):
        PDF = "PDF", "PDF"
        JSON = "JSON", "JSON"

    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="reports")
    format = models.CharField(max_length=10, choices=Format.choices)
