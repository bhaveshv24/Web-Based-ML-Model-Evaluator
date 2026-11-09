"""NFR-010: purge uploaded bytes and stored reports after 30 days.

Keep evaluation history and its checksum snapshots. Active jobs retain their inputs until they
reach a terminal state; the next daily run then removes the expired files.
"""

from datetime import timedelta

from django.utils import timezone
from ingestion.models import Dataset, ModelArtifact

from .models import Evaluation, EvaluationArtifact, Report

RETENTION_DAYS = 30
ACTIVE = (Evaluation.Status.QUEUED, Evaluation.Status.RUNNING)


def purge_expired(*, now=None) -> dict[str, int]:
    cutoff = (now or timezone.now()) - timedelta(days=RETENTION_DAYS)
    summary = {}
    for label, queryset in (
        ("reports", Report.objects.filter(created_at__lt=cutoff).exclude(
            evaluation__status__in=ACTIVE
        )),
        ("evaluation_artifacts", EvaluationArtifact.objects.filter(
            created_at__lt=cutoff
        ).exclude(evaluation__status__in=ACTIVE)),
        ("models", ModelArtifact.objects.filter(created_at__lt=cutoff).exclude(
            evaluations__status__in=ACTIVE
        )),
        ("datasets", Dataset.objects.filter(created_at__lt=cutoff).exclude(
            evaluations__status__in=ACTIVE
        )),
    ):
        ids = list(queryset.values_list("pk", flat=True))
        if ids:
            queryset.model.objects.filter(pk__in=ids).delete()
        summary[label] = len(ids)
    return summary
