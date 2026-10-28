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
    # Blank until the worker detects it, unless the user supplied an override (FR-015).
    task_type = models.CharField(max_length=20, choices=TaskType.choices, blank=True)
    task_type_overridden = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    metrics_json = models.JSONField(null=True, blank=True)
    charts_json = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    error_message = models.TextField(blank=True)

    # Inputs. Checksums and target are snapshotted so the record stays meaningful (and
    # comparable, BR-02) even if the uploaded artifacts are later deleted.
    model_artifact = models.ForeignKey(
        "ingestion.ModelArtifact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluations",
    )
    dataset = models.ForeignKey(
        "ingestion.Dataset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluations",
    )
    model_sha256 = models.CharField(max_length=64, blank=True)
    dataset_sha256 = models.CharField(max_length=64, blank=True)
    target_column = models.CharField(max_length=255, blank=True)
    sandbox_image = models.CharField(max_length=200, blank=True)

    # Lifecycle bookkeeping. run_token identifies the worker attempt that owns a RUNNING job,
    # so late or duplicate workers cannot overwrite a state they no longer own.
    run_token = models.UUIDField(null=True, blank=True, editable=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    TERMINAL_STATUSES = frozenset({Status.SUCCEEDED, Status.FAILED, Status.TIMED_OUT})

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "started_at"], name="evaluation_status_started")]

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL_STATUSES

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 3)
        return None


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
