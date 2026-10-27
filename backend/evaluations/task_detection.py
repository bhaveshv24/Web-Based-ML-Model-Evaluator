from __future__ import annotations

from enum import StrEnum
from numbers import Real


class TaskType(StrEnum):
    CLASSIFICATION = "CLASSIFICATION"
    REGRESSION = "REGRESSION"


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
