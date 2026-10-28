"""Security audit events for evaluation jobs (SEC-006)."""

from __future__ import annotations

import logging

from accounts.models import AuditLog

from .errors import ErrorCode

logger = logging.getLogger("evaluations.audit")

EVENT_FOR_CODE = {
    ErrorCode.TIMEOUT: "EVALUATION_TIMED_OUT",
    ErrorCode.RESOURCE_EXHAUSTED: "SANDBOX_POLICY_VIOLATION",
    ErrorCode.SANDBOX_POLICY_VIOLATION: "SANDBOX_POLICY_VIOLATION",
    ErrorCode.WORKER_LOST: "EVALUATION_REAPED",
    ErrorCode.QUEUE_EXPIRED: "EVALUATION_REAPED",
}


def record_failure(evaluation_id, owner_id, code: ErrorCode, **metadata) -> None:
    """Write one audit row per failed job. Never raises: auditing must not mask the result."""
    event = EVENT_FOR_CODE.get(code, "EVALUATION_FAILED")
    try:
        AuditLog.objects.create(
            event=event,
            user_id=owner_id,
            metadata={"evaluation_id": str(evaluation_id), "error_code": code.value, **metadata},
        )
    except Exception:
        logger.exception("evaluation=%s audit write failed for %s", evaluation_id, event)
