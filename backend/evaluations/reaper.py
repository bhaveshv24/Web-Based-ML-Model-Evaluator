"""Recovery for crashed or stuck jobs (NFR-006, REL-01, FR-019).

Runs every minute (Celery beat) and once when a worker starts:

* RUNNING longer than the execution limit + grace -> FAILED (WORKER_LOST). With the default
  120 s + 60 s and a 60 s schedule, no job stays RUNNING for more than about 4 minutes.
  A still-alive worker notices it lost ownership on its next poll and kills its container.
* QUEUED longer than the queue timeout -> FAILED (QUEUE_EXPIRED).
* Sandbox containers whose job is no longer RUNNING are killed and removed.
* Leftover per-job workspaces are deleted.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import audit, services
from .errors import ErrorCode, EvaluationError
from .models import Evaluation
from .sandbox import get_sandbox_runner
from .sandbox.workspace import remove_stale_workspaces

logger = logging.getLogger("evaluations.reaper")


def reap_stale(*, now=None, runner=None) -> dict[str, int]:
    now = now or timezone.now()
    limit = settings.EVALUATION_TIMEOUT_SECONDS + settings.EVALUATION_REAPER_GRACE_SECONDS
    summary = {"running": 0, "queued": 0, "containers": 0, "workspaces": 0}

    stuck = Evaluation.objects.filter(
        status=Evaluation.Status.RUNNING, started_at__lt=now - timedelta(seconds=limit)
    ).values_list("id", "run_token", "owner_id")
    for evaluation_id, token, owner_id in stuck:
        if services.fail(evaluation_id, code=ErrorCode.WORKER_LOST, run_token=token):
            audit.record_failure(evaluation_id, owner_id, ErrorCode.WORKER_LOST)
            summary["running"] += 1

    expired = Evaluation.objects.filter(
        status=Evaluation.Status.QUEUED,
        created_at__lt=now - timedelta(seconds=settings.EVALUATION_QUEUE_TIMEOUT_SECONDS),
    ).values_list("id", "owner_id")
    for evaluation_id, owner_id in expired:
        if services.fail(
            evaluation_id, code=ErrorCode.QUEUE_EXPIRED, current=Evaluation.Status.QUEUED
        ):
            audit.record_failure(evaluation_id, owner_id, ErrorCode.QUEUE_EXPIRED)
            summary["queued"] += 1

    active = {
        str(pk)
        for pk in Evaluation.objects.filter(status=Evaluation.Status.RUNNING).values_list(
            "id", flat=True
        )
    }
    runner = runner or get_sandbox_runner()
    remove_orphans = getattr(runner, "remove_orphans", None)
    if remove_orphans is not None:
        try:
            summary["containers"] = remove_orphans(
                active, min_age_seconds=settings.SANDBOX_INSPECT_TIMEOUT_SECONDS + 60
            )
        except EvaluationError:
            logger.warning("orphan container sweep skipped: sandbox unavailable")
        except Exception:
            logger.exception("orphan container sweep failed")

    summary["workspaces"] = remove_stale_workspaces(
        active, older_than_seconds=limit, now=time.time()
    )
    if any(summary.values()):
        logger.warning("reaper summary %s", summary)
    return summary
