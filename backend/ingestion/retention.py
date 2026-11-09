"""NFR-010 data retention: uploads and stored reports are deleted after RETENTION_DAYS.

Evaluation rows are kept as history. Their model/dataset links become null (on_delete=SET_NULL)
while the recorded checksums, target and metrics stay, so history, comparison guards and
report metadata keep working. Artifacts used by a QUEUED or RUNNING evaluation are skipped and
purged on a later pass, so a running job never loses its inputs.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from accounts.models import AuditLog
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from evaluations.models import Evaluation, EvaluationArtifact, Report

from .models import Dataset, ModelArtifact

logger = logging.getLogger("ingestion.retention")

ACTIVE = (Evaluation.Status.QUEUED, Evaluation.Status.RUNNING)


def _delete_with_file(instance) -> None:
    if instance.file:
        instance.file.delete(save=False)
    instance.delete()


def purge_expired(now=None) -> dict[str, int]:
    """Delete expired uploads and stored evaluation files; return the number of each removed."""
    cutoff = (now or timezone.now()) - timedelta(days=settings.RETENTION_DAYS)
    in_use = Evaluation.objects.filter(status__in=ACTIVE)
    counts = {"models": 0, "datasets": 0, "reports": 0, "artifacts": 0}

    for model in ModelArtifact.objects.filter(created_at__lt=cutoff).exclude(
        id__in=in_use.exclude(model_artifact=None).values("model_artifact")
    ):
        _delete_with_file(model)
        counts["models"] += 1
    for dataset in Dataset.objects.filter(created_at__lt=cutoff).exclude(
        id__in=in_use.exclude(dataset=None).values("dataset")
    ):
        _delete_with_file(dataset)
        counts["datasets"] += 1
    # Stored report/artifact rows have no timestamp of their own; they age with their
    # evaluation. post_delete signals (evaluations/signals.py) remove the files.
    expired = Q(evaluation__created_at__lt=cutoff) & ~Q(evaluation__status__in=ACTIVE)
    for key, queryset in (
        ("reports", Report.objects.filter(expired)),
        ("artifacts", EvaluationArtifact.objects.filter(expired)),
    ):
        for row in queryset:
            row.delete()
            counts[key] += 1

    if any(counts.values()):
        AuditLog.objects.create(
            event="RETENTION_PURGE", metadata={"cutoff": cutoff.isoformat(), **counts}
        )
    logger.info("retention purge before %s removed %s", cutoff.isoformat(), counts)
    return counts
