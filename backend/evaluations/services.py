"""Evaluation job lifecycle (FR-014, FR-019, FR-021, BR-01, BR-04).

Every status change goes through :func:`transition`, which is a single conditional UPDATE
(compare-and-set). Two workers, a worker and the reaper, or a worker and a delete can race,
but only one of them can move a job out of a given state, and terminal states never change.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .errors import ErrorCode, public_message
from .models import Evaluation

logger = logging.getLogger("evaluations.lifecycle")

Status = Evaluation.Status

# One-way transitions (SRS Figure 2). QUEUED -> FAILED is used only when a job can never
# start (the queue is unreachable or the job expired in the queue).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    Status.QUEUED: frozenset({Status.RUNNING, Status.FAILED}),
    Status.RUNNING: frozenset({Status.SUCCEEDED, Status.FAILED, Status.TIMED_OUT}),
    Status.SUCCEEDED: frozenset(),
    Status.FAILED: frozenset(),
    Status.TIMED_OUT: frozenset(),
}


class IllegalTransition(ValueError):
    """Raised for a transition the state model does not allow (UT-EXE-05)."""


def check_transition(current: str, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise IllegalTransition(f"{current} -> {target} is not a legal evaluation transition")


def transition(
    evaluation_id,
    current: str,
    target: str,
    *,
    expected_token: uuid.UUID | None = None,
    **fields,
) -> bool:
    """Atomically move a job from ``current`` to ``target``.

    Returns False (and changes nothing) when the job is no longer in ``current`` or is owned
    by a different worker attempt. Raises IllegalTransition for a disallowed edge.
    """
    check_transition(current, target)
    queryset = Evaluation.objects.filter(id=evaluation_id, status=current)
    if expected_token is not None:
        queryset = queryset.filter(run_token=expected_token)
    updated = queryset.update(status=target, updated_at=timezone.now(), **fields)
    if updated:
        logger.info("evaluation=%s transition %s -> %s", evaluation_id, current, target)
    return bool(updated)


def claim(evaluation_id) -> uuid.UUID | None:
    """QUEUED -> RUNNING for exactly one worker; duplicates deliveries get None."""
    token = uuid.uuid4()
    claimed = transition(
        evaluation_id,
        Status.QUEUED,
        Status.RUNNING,
        run_token=token,
        started_at=timezone.now(),
    )
    return token if claimed else None


def still_owned(evaluation_id, run_token: uuid.UUID) -> bool:
    return Evaluation.objects.filter(
        id=evaluation_id, status=Status.RUNNING, run_token=run_token
    ).exists()


def complete(evaluation_id, run_token: uuid.UUID, *, task_type: str, metrics, charts) -> bool:
    """RUNNING -> SUCCEEDED, publishing metrics and charts in the same UPDATE."""
    return transition(
        evaluation_id,
        Status.RUNNING,
        Status.SUCCEEDED,
        expected_token=run_token,
        task_type=task_type,
        metrics_json=metrics,
        charts_json=charts,
        error_code="",
        error_message="",
        finished_at=timezone.now(),
    )


def fail(
    evaluation_id,
    *,
    code: ErrorCode,
    detail: str = "",
    current: str = Status.RUNNING,
    run_token: uuid.UUID | None = None,
) -> bool:
    """Move a job to FAILED or TIMED_OUT with a sanitized message and no metrics."""
    target = Status.TIMED_OUT if code == ErrorCode.TIMEOUT else Status.FAILED
    return transition(
        evaluation_id,
        current,
        target,
        expected_token=run_token,
        error_code=code.value,
        error_message=public_message(code, detail),
        metrics_json=None,
        charts_json=None,
        finished_at=timezone.now(),
    )


# ------------------------------------------------------------------------------ submission
class SubmissionError(Exception):
    def __init__(self, field: str, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.not_found = not_found


@dataclass(frozen=True)
class Submission:
    evaluation: Evaluation
    scheduled: bool


def _current_features(dataset) -> list[str]:
    return [name for name in dataset.columns if name != dataset.target_column]


def latest_passed_report(owner, model, dataset):
    """BR-01: the newest report for this pair must be PASSED and describe the current target."""
    from ingestion.models import CompatibilityReport

    report = (
        CompatibilityReport.objects.filter(owner=owner, model_artifact=model, dataset=dataset)
        .order_by("-created_at")
        .first()
    )
    if report is None or report.result != CompatibilityReport.Result.PASSED:
        return None
    # The report records the feature list it validated. If the target was overridden after
    # validation, the feature set changed and the pair must be validated again.
    validated = next(
        (check.get("actual") for check in report.checks if check.get("code") == "TARGET_EXCLUDED"),
        None,
    )
    if validated != _current_features(dataset):
        return None
    return report


def enqueue_evaluation(evaluation_id) -> None:
    from .tasks import run_evaluation

    run_evaluation.apply_async(args=[str(evaluation_id)], retry=True)


def submit_evaluation(owner, model, dataset, *, task_type: str | None, workspace=None):
    """Create a QUEUED job for a validated pair and schedule it (FR-014)."""
    if latest_passed_report(owner, model, dataset) is None:
        raise SubmissionError(
            "non_field_errors",
            "The model-dataset pair must pass a compatibility check before evaluation.",
        )
    with transaction.atomic():
        evaluation = Evaluation.objects.create(
            owner=owner,
            workspace=workspace,
            model_artifact=model,
            dataset=dataset,
            model_sha256=model.sha256,
            dataset_sha256=dataset.sha256,
            target_column=dataset.target_column,
            task_type=task_type or "",
            task_type_overridden=bool(task_type),
            sandbox_image=settings.SANDBOX_IMAGE,
        )
    try:
        enqueue_evaluation(evaluation.id)
    except Exception:  # broker down, connection refused, serialization ...
        logger.exception("evaluation=%s could not be enqueued", evaluation.id)
        fail(evaluation.id, code=ErrorCode.QUEUE_UNAVAILABLE, current=Status.QUEUED)
        evaluation.refresh_from_db()
        return Submission(evaluation, scheduled=False)
    return Submission(evaluation, scheduled=True)
