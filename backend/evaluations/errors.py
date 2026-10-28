"""Failure categories and sanitized public messages for evaluation jobs (FR-020, SEC-010).

Public error text is always composed by the server from this catalog. Exception messages,
container output and tracebacks never reach API clients; they stay in operator logs.
"""

from __future__ import annotations

from enum import StrEnum

from .security import sanitized_failure


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_TASK = "UNSUPPORTED_TASK"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    MODEL_EXECUTION_FAILED = "MODEL_EXECUTION_FAILED"
    INVALID_PREDICTIONS = "INVALID_PREDICTIONS"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    SANDBOX_UNAVAILABLE = "SANDBOX_UNAVAILABLE"
    SANDBOX_POLICY_VIOLATION = "SANDBOX_POLICY_VIOLATION"
    WORKER_LOST = "WORKER_LOST"
    QUEUE_UNAVAILABLE = "QUEUE_UNAVAILABLE"
    QUEUE_EXPIRED = "QUEUE_EXPIRED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


PUBLIC_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_INPUT: "The model or dataset could not be prepared for evaluation.",
    ErrorCode.UNSUPPORTED_TASK: "The evaluation task could not be determined for this target.",
    ErrorCode.MODEL_LOAD_FAILED: (
        "The model could not be loaded in the sandbox. Check that it was saved with a "
        "compatible scikit-learn or ONNX version."
    ),
    ErrorCode.MODEL_EXECUTION_FAILED: "The model failed while producing predictions.",
    ErrorCode.INVALID_PREDICTIONS: "The model returned predictions that cannot be evaluated.",
    ErrorCode.RESOURCE_EXHAUSTED: "The model exceeded the sandbox memory or process limits.",
    ErrorCode.TIMEOUT: "The evaluation exceeded the execution time limit and was stopped.",
    ErrorCode.SANDBOX_UNAVAILABLE: "The isolated execution environment is unavailable.",
    ErrorCode.SANDBOX_POLICY_VIOLATION: (
        "The isolated execution environment did not meet the security policy, so the model "
        "was not run."
    ),
    ErrorCode.WORKER_LOST: "The evaluation worker stopped unexpectedly.",
    ErrorCode.QUEUE_UNAVAILABLE: "The evaluation could not be scheduled. Please try again.",
    ErrorCode.QUEUE_EXPIRED: "The evaluation was not started in time and was cancelled.",
    ErrorCode.INTERNAL_ERROR: "The evaluation failed because of an internal error.",
}

# Categories that count as sandbox security events for the audit log (SEC-006).
SECURITY_EVENT_CODES = {
    ErrorCode.TIMEOUT,
    ErrorCode.RESOURCE_EXHAUSTED,
    ErrorCode.SANDBOX_POLICY_VIOLATION,
}


class EvaluationError(Exception):
    """A categorized job failure.

    ``detail`` must be written by server code (counts, column positions, limits) and must not
    contain dataset values, file paths or exception text from untrusted code.
    """

    def __init__(self, code: ErrorCode, detail: str = "") -> None:
        super().__init__(code.value)
        self.code = code
        self.detail = detail

    @property
    def public_message(self) -> str:
        return public_message(self.code, self.detail)


def public_message(code: ErrorCode, detail: str = "") -> str:
    message = PUBLIC_MESSAGES[code]
    if detail:
        # Defence in depth: even server-written detail passes the path/secret scrubber.
        cleaned = sanitized_failure(ValueError(detail)).removeprefix("ValueError: ")
        message = f"{message} {cleaned}"
    return message[:500]
