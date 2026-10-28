"""Hardened per-job execution boundary for untrusted models (M3, MLE-11)."""

from django.conf import settings
from django.utils.module_loading import import_string

from .base import SandboxCancelled, SandboxPolicy, SandboxRequest, SandboxRunner, parse_output
from .workspace import JobWorkspace

__all__ = [
    "JobWorkspace",
    "SandboxCancelled",
    "SandboxPolicy",
    "SandboxRequest",
    "SandboxRunner",
    "get_sandbox_runner",
    "parse_output",
]


def get_sandbox_runner() -> SandboxRunner:
    """Instantiate the configured isolation backend (Docker unless a settings module says
    otherwise, e.g. a test double). There is no silent fallback to unisolated execution."""
    return import_string(settings.SANDBOX_RUNNER_CLASS)()
