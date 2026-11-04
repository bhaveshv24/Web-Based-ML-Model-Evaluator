"""Task-type detection from validated ground-truth labels (FR-015).

Detection only looks at the trusted target column read by the worker. Nothing reported by
the uploaded model influences it; the user may override the result explicitly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real


class TaskType(StrEnum):
    CLASSIFICATION = "CLASSIFICATION"
    REGRESSION = "REGRESSION"


class TaskDetectionError(ValueError):
    """The target cannot be evaluated as the requested or detected task."""


def detect_task_type(values: list[object], override: TaskType | str | None = None) -> TaskType:
    if override is not None:
        return TaskType(override)
    if not values:
        raise ValueError("Target column cannot be empty")
    unique = set(values)
    if any(isinstance(value, str) for value in values):
        return TaskType.CLASSIFICATION
    if not all(isinstance(value, Real) and not isinstance(value, bool) for value in values):
        return TaskType.CLASSIFICATION
    # Integer-like or low-cardinality targets are classes.
    # Continuous, high-cardinality targets are regression.
    integer_like = all(float(value).is_integer() for value in values)
    threshold = max(20, int(len(values) ** 0.5))
    if integer_like and len(unique) <= threshold:
        return TaskType.CLASSIFICATION
    return TaskType.REGRESSION


def parse_number(text: str) -> float | None:
    """Return a finite float for numeric CSV text, otherwise None ('nan'/'inf' are not data)."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def coerce_target_values(raw: list[str]) -> list[float | str]:
    """Turn CSV strings into numbers when the whole column is numeric, else keep strings."""
    numbers = [parse_number(value) for value in raw]
    if all(number is not None for number in numbers):
        return numbers  # type: ignore[return-value]
    return list(raw)


def canonical_label(value: object) -> str:
    """One spelling per class: '1', '1.0' and 1 are the same label; 'setosa' stays as is."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, Real):
        number = float(value)
    elif isinstance(value, str):
        number = parse_number(value.strip())
        if number is None:
            return value.strip()
    else:
        return str(value)
    if not math.isfinite(number):
        return str(number)
    if number.is_integer():
        return str(int(number))
    return repr(number)


@dataclass(frozen=True)
class TaskDecision:
    task_type: TaskType
    source: str  # "override" or "detected"
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"task_type": self.task_type.value, "source": self.source, "reason": self.reason}


def resolve_task(
    raw_labels: list[str], override: TaskType | str | None, *, max_classes: int
) -> TaskDecision:
    """Decide the task for a target column or raise TaskDetectionError with a safe reason."""
    if not raw_labels:
        raise TaskDetectionError("The dataset has no rows to evaluate.")
    missing = sum(1 for value in raw_labels if value.strip() == "")
    if missing:
        raise TaskDetectionError(f"The target column has {missing} missing value(s).")
    if override not in (None, ""):
        try:
            requested = TaskType(override)
        except ValueError as exc:
            raise TaskDetectionError("Unknown task type override.") from exc
    else:
        requested = None

    values = coerce_target_values([value.strip() for value in raw_labels])
    numeric = all(isinstance(value, float) for value in values)
    task = detect_task_type(values, requested)
    source = "override" if requested else "detected"

    if task == TaskType.REGRESSION:
        if not numeric:
            raise TaskDetectionError("Regression requires a numeric target column.")
        reason = "numeric target" if requested else "continuous numeric target"
        return TaskDecision(task, source, reason)

    distinct = len({canonical_label(value) for value in values})
    if distinct > max_classes:
        raise TaskDetectionError(
            f"The target has {distinct} distinct labels; at most {max_classes} classes are "
            "supported. Override the task type to REGRESSION if the target is continuous."
        )
    kind = "numeric" if numeric else "text"
    return TaskDecision(task, source, f"{distinct} distinct {kind} label(s)")
