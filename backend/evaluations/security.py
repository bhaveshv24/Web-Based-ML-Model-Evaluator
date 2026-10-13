from __future__ import annotations

import re


def sanitized_failure(exc: BaseException) -> str:
    """Return an actionable error without a stack trace, server path or secret-like token."""
    name = type(exc).__name__
    raw = str(exc).replace("\n", " ")[:300]
    raw = re.sub(r"(?:[A-Za-z]:)?[/\\](?:[^\s:/\\]+[/\\])+[^\s]+", "[path]", raw)
    raw = re.sub(r"(?i)(password|token|secret)\s*[=:]\s*\S+", r"\1=[redacted]", raw)
    return f"{name}: {raw}" if raw else name
