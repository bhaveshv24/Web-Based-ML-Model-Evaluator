"""Celery tasks: run_evaluation, reap_stale_evaluations, inspect_model (SAD 2.1)."""

from __future__ import annotations

import logging

from celery import shared_task
from celery.signals import worker_ready
from django.conf import settings
from django.db import InterfaceError, OperationalError

from . import executor, reaper

logger = logging.getLogger("evaluations.tasks")

# Backstops around the sandbox deadline: the soft limit lets the task record TIMED_OUT and
# clean up; the hard limit kills a wedged worker process, after which the reaper finishes it.
SOFT_LIMIT = settings.EVALUATION_TIMEOUT_SECONDS + 60
HARD_LIMIT = settings.EVALUATION_TIMEOUT_SECONDS + 90


@shared_task(
    name="evaluations.run_evaluation",
    acks_late=True,
    soft_time_limit=SOFT_LIMIT,
    time_limit=HARD_LIMIT,
    ignore_result=True,
    # A transient database error (e.g. while claiming) is retried instead of stranding the
    # job in QUEUED. Safe because claiming is a compare-and-set: at most one attempt runs.
    autoretry_for=(OperationalError, InterfaceError),
    retry_backoff=1,
    retry_backoff_max=30,
    retry_jitter=False,
    max_retries=5,
)
def run_evaluation(evaluation_id: str) -> str | None:
    # Idempotent: a redelivered message finds the job already claimed and does nothing.
    return executor.execute_evaluation(evaluation_id)


@shared_task(name="evaluations.reap_stale_evaluations", ignore_result=True)
def reap_stale_evaluations() -> dict[str, int]:
    return reaper.reap_stale()


@shared_task(
    name="evaluations.inspect_model",
    soft_time_limit=settings.SANDBOX_INSPECT_TIMEOUT_SECONDS + 30,
    time_limit=settings.SANDBOX_INSPECT_TIMEOUT_SECONDS + 45,
)
def inspect_model(relative_name: str, extension: str) -> dict | None:
    return executor.inspect_stored_model(relative_name, extension)


@worker_ready.connect
def _reap_on_startup(**_kwargs) -> None:
    """Recover jobs and containers left behind by a previous worker crash."""
    try:
        reap_stale_evaluations.delay()
    except Exception:  # pragma: no cover - broker hiccup at startup; beat retries later
        logger.exception("startup reap could not be scheduled")
