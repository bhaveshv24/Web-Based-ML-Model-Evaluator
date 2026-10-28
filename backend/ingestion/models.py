"""Owned model artifacts, datasets and compatibility reports (M2)."""

import uuid
from pathlib import PurePath

from django.conf import settings
from django.db import models


def model_upload_path(instance, filename: str) -> str:
    """Store under a server-generated UUID so user-supplied names never touch the disk."""
    return f"models/{instance.id}{PurePath(filename).suffix.lower()}"


def dataset_upload_path(instance, filename: str) -> str:
    return f"datasets/{instance.id}.csv"


class ModelArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="model_artifacts"
    )
    original_filename = models.CharField(max_length=255)
    extension = models.CharField(max_length=10)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    file = models.FileField(upload_to=model_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="datasets"
    )
    original_filename = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    columns = models.JSONField()
    row_count = models.PositiveIntegerField()
    suggested_target = models.CharField(max_length=255, blank=True)
    target_column = models.CharField(max_length=255)
    file = models.FileField(upload_to=dataset_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CompatibilityReport(models.Model):
    class Result(models.TextChoices):
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="compatibility_reports"
    )
    model_artifact = models.ForeignKey(
        ModelArtifact, on_delete=models.CASCADE, related_name="compatibility_reports"
    )
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name="compatibility_reports"
    )
    result = models.CharField(max_length=10, choices=Result.choices)
    checks = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
