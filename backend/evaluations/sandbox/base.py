"""Sandbox contracts shared by the worker and the isolation backends (NFR-009)."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from django.conf import settings

from ..errors import ErrorCode, EvaluationError

if TYPE_CHECKING:  # pragma: no cover
    from .workspace import JobWorkspace

RESULT_MARKER = b"@@ML-EVALUATOR-RESULT@@ "
SANDBOX_INPUT_DIR = "/input"


class SandboxCancelled(Exception):
    """The job was deleted or reaped while its sandbox was running; stop without a result."""


@dataclass(frozen=True)
class SandboxPolicy:
    """The approved run policy (SAD 5.1 step 3). Built from settings, never from user input."""

    image: str
    user: str
    memory_bytes: int
    nano_cpus: int
    pids_limit: int
    tmpfs_bytes: int
    max_output_bytes: int
    poll_interval: float
    max_open_files: int = 256

    @classmethod
    def from_settings(cls) -> SandboxPolicy:
        return cls(
            image=settings.SANDBOX_IMAGE,
            user=settings.SANDBOX_USER,
            memory_bytes=settings.SANDBOX_MEMORY_BYTES,
            nano_cpus=settings.SANDBOX_NANO_CPUS,
            pids_limit=settings.SANDBOX_PIDS_LIMIT,
            tmpfs_bytes=settings.SANDBOX_TMPFS_BYTES,
            max_output_bytes=settings.SANDBOX_MAX_OUTPUT_BYTES,
            poll_interval=settings.SANDBOX_POLL_INTERVAL_SECONDS,
        )


@dataclass(frozen=True)
class SandboxRequest:
    job_id: str
    mode: Literal["predict", "inspect"]
    workspace: JobWorkspace
    model_filename: str
    timeout_seconds: float
    cancel_check: Callable[[], bool] | None = None

    def command(self) -> list[str]:
        model = f"{SANDBOX_INPUT_DIR}/{self.model_filename}"
        if self.mode == "inspect":
            return ["inspect", model]
        return ["predict", model, f"{SANDBOX_INPUT_DIR}/X.csv"]


class SandboxRunner(Protocol):
    def run(self, request: SandboxRequest) -> dict:
        """Execute the request in isolation and return the parsed result payload.

        Raises EvaluationError for categorized failures and SandboxCancelled when stopped.
        """


def _reject_constant(_name: str) -> float:
    return math.nan  # NaN/Infinity tokens survive parsing and are rejected by validation


def parse_output(raw: bytes, max_bytes: int) -> dict:
    """Extract the framed JSON result from the sandbox stdout.

    Anything the model prints is ignored; only the last line carrying the marker counts.
    """
    if len(raw) > max_bytes:
        raise EvaluationError(ErrorCode.INVALID_PREDICTIONS, "The sandbox output is too large.")
    line = next(
        (item for item in reversed(raw.splitlines()) if item.startswith(RESULT_MARKER)), None
    )
    if line is None:
        raise EvaluationError(ErrorCode.INVALID_PREDICTIONS, "The sandbox returned no result.")
    try:
        payload = json.loads(line[len(RESULT_MARKER) :], parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise EvaluationError(
            ErrorCode.INVALID_PREDICTIONS, "The sandbox result is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise EvaluationError(ErrorCode.INVALID_PREDICTIONS, "The sandbox result is malformed.")
    return payload
