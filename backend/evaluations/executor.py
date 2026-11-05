"""Worker-side execution of one evaluation job (SAD Figure 7, steps 6-12).

claim (QUEUED -> RUNNING, exactly once) -> fresh workspace -> split X / y -> detect task ->
sandboxed prediction under a hard deadline -> trusted metrics -> remove container and
workspace -> publish SUCCEEDED, or FAILED / TIMED_OUT with a sanitized message.

Cleanup always happens before the terminal state is written, so a client that sees a
terminal status never races with a still-running container. The terminal write is a
compare-and-set on the attempt's run_token: if the reaper or a delete got there first, this
worker's result is discarded instead of overwriting the newer state.
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from pathlib import Path

from django.conf import settings

from . import audit, services
from .errors import ErrorCode, EvaluationError
from .inputs import prepare_inputs
from .metrics import MetricResult, evaluate
from .models import Evaluation
from .sandbox import (
    JobWorkspace,
    SandboxCancelled,
    SandboxRequest,
    SandboxRunner,
    get_sandbox_runner,
)
from .sandbox.workspace import MODEL_FILENAMES
from .task_detection import TaskDetectionError, resolve_task

logger = logging.getLogger("evaluations.executor")

MAX_INSPECTED_FEATURES = 1000


def _soft_time_limit_type() -> type[BaseException]:
    try:
        from celery.exceptions import SoftTimeLimitExceeded
    except ImportError:  # pragma: no cover
        return TimeoutError
    return SoftTimeLimitExceeded


def _run_job(evaluation_id, token: uuid.UUID, runner: SandboxRunner | None) -> MetricResult:
    evaluation = Evaluation.objects.select_related("model_artifact", "dataset").get(
        id=evaluation_id
    )
    try:
        workspace = JobWorkspace.create(str(evaluation.id))
    except OSError as exc:
        logger.error("evaluation=%s workspace unavailable: %s", evaluation_id, type(exc).__name__)
        raise EvaluationError(ErrorCode.SANDBOX_UNAVAILABLE) from exc
    try:
        inputs = prepare_inputs(evaluation, workspace)
        override = evaluation.task_type if evaluation.task_type_overridden else None
        try:
            decision = resolve_task(
                inputs.labels, override, max_classes=settings.EVALUATION_MAX_CLASSES
            )
        except TaskDetectionError as exc:  # messages are server-written, without data values
            raise EvaluationError(ErrorCode.UNSUPPORTED_TASK, str(exc)) from exc
        runner = runner or get_sandbox_runner()
        payload = runner.run(
            SandboxRequest(
                job_id=str(evaluation.id),
                mode="predict",
                workspace=workspace,
                model_filename=inputs.model_filename,
                timeout_seconds=settings.EVALUATION_TIMEOUT_SECONDS,
                cancel_check=lambda: not services.still_owned(evaluation_id, token),
            )
        )
        return evaluate(inputs.labels, payload, decision)
    finally:
        workspace.cleanup()


def _finite_json(value) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite_json(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite_json(item) for item in value)
    return True


def _record_failure(evaluation_id, token, error: EvaluationError, started: float) -> str | None:
    duration = round(time.monotonic() - started, 3)
    if not services.fail(evaluation_id, code=error.code, detail=error.detail, run_token=token):
        logger.info("evaluation=%s failure not recorded: no longer owned", evaluation_id)
        return None
    owner_id = (
        Evaluation.objects.filter(id=evaluation_id).values_list("owner_id", flat=True).first()
    )
    audit.record_failure(evaluation_id, owner_id, error.code, duration_seconds=duration)
    logger.warning("evaluation=%s failed category=%s", evaluation_id, error.code.value)
    return (
        Evaluation.Status.TIMED_OUT if error.code == ErrorCode.TIMEOUT else Evaluation.Status.FAILED
    )


def execute_evaluation(evaluation_id, *, runner: SandboxRunner | None = None) -> str | None:
    """Run one job end to end. Returns the terminal status written, or None if this call
    did not own the job (duplicate delivery, cancelled, or reaped)."""
    token = services.claim(evaluation_id)
    if token is None:
        logger.info("evaluation=%s not claimable; skipping duplicate delivery", evaluation_id)
        return None
    started = time.monotonic()
    logger.info("evaluation=%s started", evaluation_id)
    try:
        result = _run_job(evaluation_id, token, runner)
    except SandboxCancelled:
        logger.info("evaluation=%s stopped: deleted or reaped while running", evaluation_id)
        return None
    except Evaluation.DoesNotExist:
        return None
    except EvaluationError as error:
        return _record_failure(evaluation_id, token, error, started)
    except _soft_time_limit_type():
        return _record_failure(evaluation_id, token, EvaluationError(ErrorCode.TIMEOUT), started)
    except Exception:
        logger.exception("evaluation=%s unexpected internal error", evaluation_id)
        return _record_failure(
            evaluation_id, token, EvaluationError(ErrorCode.INTERNAL_ERROR), started
        )

    try:
        if not (_finite_json(result.metrics) and _finite_json(result.charts)):
            raise ValueError("non-finite metric value")
        published = services.complete(
            evaluation_id,
            token,
            task_type=result.task_type.value,
            metrics=result.metrics,
            charts=result.charts,
        )
    except Exception:
        logger.exception("evaluation=%s result could not be persisted", evaluation_id)
        return _record_failure(
            evaluation_id, token, EvaluationError(ErrorCode.INTERNAL_ERROR), started
        )
    if not published:
        logger.info("evaluation=%s result discarded: no longer owned", evaluation_id)
        return None
    logger.info("evaluation=%s succeeded in %.2fs", evaluation_id, time.monotonic() - started)
    return Evaluation.Status.SUCCEEDED


def inspect_stored_model(relative_name: str, extension: str, *, runner=None) -> dict | None:
    """Sandboxed model inspection for compatibility checks (SAD 5.1 step 6).

    Returns {"expected_feature_count", "feature_names"} or None when the model cannot be
    inspected safely; callers then fail closed.
    """
    filename = MODEL_FILENAMES.get(extension)
    if filename is None:
        return None
    media_root = Path(settings.MEDIA_ROOT)
    job_id = f"inspect-{uuid.uuid4()}"
    try:
        workspace = JobWorkspace.create(job_id)
    except OSError:
        logger.error("model inspection workspace unavailable")
        return None
    try:
        workspace.stage_copy(
            media_root / relative_name,
            filename,
            allowed_root=media_root / "models",
            max_bytes=100 * 1024 * 1024,
            sha256="",
        )
        payload = (runner or get_sandbox_runner()).run(
            SandboxRequest(
                job_id=job_id,
                mode="inspect",
                workspace=workspace,
                model_filename=filename,
                timeout_seconds=settings.SANDBOX_INSPECT_TIMEOUT_SECONDS,
            )
        )
    except EvaluationError as error:
        logger.warning("model inspection failed category=%s", error.code.value)
        return None
    finally:
        workspace.cleanup()

    count = payload.get("n_features_in")
    names = payload.get("feature_names_in")
    if not isinstance(count, int) or isinstance(count, bool):
        return None
    if not 1 <= count <= MAX_INSPECTED_FEATURES:
        return None
    if names is not None:
        valid = (
            isinstance(names, list)
            and len(names) == count
            and all(isinstance(name, str) and 0 < len(name) <= 255 for name in names)
        )
        if not valid:
            names = None
    return {"expected_feature_count": count, "feature_names": names}
