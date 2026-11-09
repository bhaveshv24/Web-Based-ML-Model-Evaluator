"""RET-01: expiry removes stored bytes and references while preserving job history."""

from datetime import timedelta
from pathlib import Path

import pytest
from accounts.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from evaluations.models import Evaluation, EvaluationArtifact, Report
from evaluations.retention import purge_expired
from evaluations.tasks import purge_expired_files
from ingestion.models import Dataset, ModelArtifact

pytestmark = pytest.mark.django_db


def upload_pair(owner, prefix):
    model = ModelArtifact.objects.create(
        owner=owner, original_filename=f"{prefix}.pkl", extension=".pkl",
        size_bytes=2, sha256="a" * 64,
    )
    model.file.save(f"{prefix}.pkl", ContentFile(b"\x80\x04"), save=True)
    dataset = Dataset.objects.create(
        owner=owner, original_filename=f"{prefix}.csv", size_bytes=13,
        sha256="b" * 64, columns=["x", "y"], row_count=1,
        target_column="y", suggested_target="y",
    )
    dataset.file.save(f"{prefix}.csv", ContentFile(b"x,y\n1,2\n"), save=True)
    return model, dataset


def test_ret_01_purges_31_day_files_and_keeps_active_and_new_files(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(email="retention@pes.edu", password="SafePass123!")
    old_model, old_dataset = upload_pair(owner, "old")
    active_model, active_dataset = upload_pair(owner, "active")
    new_model, new_dataset = upload_pair(owner, "new")
    finished = Evaluation.objects.create(
        owner=owner, status=Evaluation.Status.SUCCEEDED, model_artifact=old_model,
        dataset=old_dataset, model_sha256=old_model.sha256, dataset_sha256=old_dataset.sha256,
    )
    Evaluation.objects.create(
        owner=owner, status=Evaluation.Status.RUNNING, model_artifact=active_model,
        dataset=active_dataset,
    )
    old_report = Report.objects.create(evaluation=finished, format=Report.Format.JSON)
    old_report.file.save("old.json", ContentFile(b"{}"), save=True)
    old_artifact = EvaluationArtifact.objects.create(evaluation=finished)
    old_artifact.file.save("old.bin", ContentFile(b"old"), save=True)
    paths = [Path(obj.file.path) for obj in
             (old_model, old_dataset, old_report, old_artifact)]
    now = timezone.now()
    old = now - timedelta(days=31)
    for model, pk in (
        (ModelArtifact, old_model.pk), (Dataset, old_dataset.pk),
        (ModelArtifact, active_model.pk), (Dataset, active_dataset.pk),
        (Report, old_report.pk), (EvaluationArtifact, old_artifact.pk),
    ):
        model.objects.filter(pk=pk).update(created_at=old)

    assert purge_expired(now=now) == {
        "reports": 1, "evaluation_artifacts": 1, "models": 1, "datasets": 1,
    }
    assert not any(path.exists() for path in paths)
    assert ModelArtifact.objects.filter(pk__in=[active_model.pk, new_model.pk]).count() == 2
    assert Dataset.objects.filter(pk__in=[active_dataset.pk, new_dataset.pk]).count() == 2
    finished.refresh_from_db()
    assert finished.model_artifact_id is None and finished.dataset_id is None
    assert finished.model_sha256 == "a" * 64 and finished.dataset_sha256 == "b" * 64
    assert purge_expired_files() == {
        "reports": 0, "evaluation_artifacts": 0, "models": 0, "datasets": 0,
    }


def test_deleted_upload_record_removes_file(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(email="delete@pes.edu", password="SafePass123!")
    model, dataset = upload_pair(owner, "manual")
    paths = [Path(model.file.path), Path(dataset.file.path)]
    model.delete()
    dataset.delete()
    assert not any(path.exists() for path in paths)
