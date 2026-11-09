"""TSMP-21 RET-01 (NFR-010): uploads and stored reports are purged 30 days after upload."""

from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from accounts.models import AuditLog, User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone
from evaluations.models import Evaluation, Report
from ingestion import tasks
from ingestion.models import CompatibilityReport, Dataset, ModelArtifact
from ingestion.retention import purge_expired

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def owner():
    return User.objects.create_user(email="retention@pes.edu")


def stored(owner, age_days):
    model = ModelArtifact(owner=owner, original_filename="m.pkl", extension=".pkl",
                          size_bytes=3, sha256="m" * 64)
    model.file.save("m.pkl", ContentFile(b"\x80\x04."), save=False)
    model.save()
    dataset = Dataset(owner=owner, original_filename="d.csv", size_bytes=6, sha256="d" * 64,
                      columns=["a", "y"], row_count=1, target_column="y")
    dataset.file.save("d.csv", ContentFile(b"a,y\n1,2\n"), save=False)
    dataset.save()
    created = timezone.now() - timedelta(days=age_days)
    ModelArtifact.objects.filter(id=model.id).update(created_at=created)
    Dataset.objects.filter(id=dataset.id).update(created_at=created)
    return model, dataset


def evaluation_for(owner, model, dataset, status="SUCCEEDED", age_days=0):
    evaluation = Evaluation.objects.create(
        owner=owner, model_artifact=model, dataset=dataset, status=status,
        task_type="REGRESSION", model_sha256=model.sha256, dataset_sha256=dataset.sha256,
        target_column="y", metrics_json={"mae": 0.5},
    )
    Evaluation.objects.filter(id=evaluation.id).update(
        created_at=timezone.now() - timedelta(days=age_days)
    )
    return evaluation


def test_ret_01_artifacts_older_than_30_days_are_removed_with_files_and_references(owner):
    old_model, old_dataset = stored(owner, 31)
    new_model, new_dataset = stored(owner, 29)
    CompatibilityReport.objects.create(owner=owner, model_artifact=old_model,
                                       dataset=old_dataset, result="PASSED", checks=[])
    history = evaluation_for(owner, old_model, old_dataset, age_days=31)
    report = Report(evaluation=history, format=Report.Format.PDF)
    report.file.save("r.pdf", ContentFile(b"%PDF-1.4"), save=True)
    old_paths = [Path(old_model.file.path), Path(old_dataset.file.path), Path(report.file.path)]
    assert all(path.exists() for path in old_paths)

    counts = purge_expired()

    assert counts == {"models": 1, "datasets": 1, "reports": 1, "artifacts": 0}
    assert not any(path.exists() for path in old_paths)
    assert not ModelArtifact.objects.filter(id=old_model.id).exists()
    assert not Dataset.objects.filter(id=old_dataset.id).exists()
    assert not CompatibilityReport.objects.exists()
    assert not Report.objects.exists()
    # History keeps its snapshot; only the references to deleted uploads are cleared.
    history.refresh_from_db()
    assert history.model_artifact is None and history.dataset is None
    assert history.model_sha256 == "m" * 64 and history.metrics_json == {"mae": 0.5}
    # Younger uploads stay.
    assert Path(new_model.file.path).exists() and Path(new_dataset.file.path).exists()
    assert AuditLog.objects.get(event="RETENTION_PURGE").metadata["models"] == 1


def test_ret_01_inputs_of_queued_or_running_jobs_are_kept_until_the_job_ends(owner):
    model, dataset = stored(owner, 45)
    job = evaluation_for(owner, model, dataset, status="RUNNING")
    assert purge_expired()["models"] == 0
    assert Path(model.file.path).exists()
    Evaluation.objects.filter(id=job.id).update(status="FAILED")
    assert purge_expired() == {"models": 1, "datasets": 1, "reports": 0, "artifacts": 0}


def test_ret_01_nothing_to_purge_writes_no_audit_row(owner):
    stored(owner, 1)
    assert purge_expired() == {"models": 0, "datasets": 0, "reports": 0, "artifacts": 0}
    assert not AuditLog.objects.filter(event="RETENTION_PURGE").exists()


def test_ret_01_retention_period_is_configurable(owner, settings):
    settings.RETENTION_DAYS = 7
    stored(owner, 8)
    assert purge_expired()["models"] == 1


def test_ret_01_task_command_and_hourly_schedule(owner, settings):
    stored(owner, 31)
    out = StringIO()
    call_command("purge_expired", stdout=out)
    assert out.getvalue().strip() == "models=1, datasets=1, reports=0, artifacts=0"
    assert tasks.purge_expired.name == "ingestion.purge_expired"
    assert tasks.purge_expired.run() == {"models": 0, "datasets": 0, "reports": 0, "artifacts": 0}
    schedule = settings.CELERY_BEAT_SCHEDULE["purge-expired-uploads"]
    assert schedule == {"task": "ingestion.purge_expired", "schedule": 3600.0}
    assert settings.RETENTION_DAYS == 30
