"""Validation of the prediction payload returned by the sandbox (SAD 5.1 step 4).

The payload is produced by untrusted code, so it is treated as hostile input: the length,
type and finiteness of every value are checked before any metric is computed. Optional
probabilities are dropped (with a note) when malformed instead of failing the job.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Real

from ..errors import ErrorCode, EvaluationError
from ..task_detection import TaskType, canonical_label

MAX_LABEL_LENGTH = 200
PROBABILITY_TOLERANCE = 1e-6
ROW_SUM_TOLERANCE = 1e-3


@dataclass
class ValidatedPredictions:
    values: list  # canonical labels (classification) or floats (regression)
    probabilities: list[list[float]] | None = None
    classes: list[str] | None = None
    notes: list[str] = field(default_factory=list)


def _invalid(detail: str) -> EvaluationError:
    return EvaluationError(ErrorCode.INVALID_PREDICTIONS, detail)


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _scalar_label(value: object, position: int) -> str:
    if isinstance(value, str):
        if len(value) > MAX_LABEL_LENGTH:
            raise _invalid(
                f"Prediction {position + 1} is longer than {MAX_LABEL_LENGTH} characters."
            )
        return canonical_label(value)
    if isinstance(value, bool) or _is_number(value):
        if _is_number(value) and not math.isfinite(float(value)):
            raise _invalid(f"Prediction {position + 1} is not a finite number.")
        return canonical_label(value)
    raise _invalid(f"Prediction {position + 1} is not a scalar label.")


def _validate_probabilities(
    payload: dict, rows: int
) -> tuple[list[list[float]] | None, list[str] | None, str | None]:
    probabilities = payload.get("probabilities")
    classes = payload.get("classes")
    if probabilities is None:
        return None, None, "The model does not provide class probabilities; ROC-AUC omitted."
    if not isinstance(classes, list) or not classes:
        return None, None, "Probabilities were returned without class names; ROC-AUC omitted."
    if not all(isinstance(c, (str, int, float, bool)) for c in classes):
        return None, None, "Class names are not scalar values; ROC-AUC omitted."
    names = [canonical_label(c) for c in classes]
    if len(set(names)) != len(names):
        return None, None, "Class names are not unique; ROC-AUC omitted."
    if not isinstance(probabilities, list) or len(probabilities) != rows:
        return None, None, "Probability rows do not match the dataset rows; ROC-AUC omitted."
    clean: list[list[float]] = []
    for row in probabilities:
        if not isinstance(row, list) or len(row) != len(names):
            return None, None, "Probability rows have the wrong width; ROC-AUC omitted."
        if not all(_is_number(p) and math.isfinite(float(p)) for p in row):
            return None, None, "Probabilities contain non-finite values; ROC-AUC omitted."
        values = [float(p) for p in row]
        if any(p < -PROBABILITY_TOLERANCE or p > 1 + PROBABILITY_TOLERANCE for p in values):
            return None, None, "Probabilities fall outside [0, 1]; ROC-AUC omitted."
        if abs(sum(values) - 1.0) > ROW_SUM_TOLERANCE:
            return None, None, "Probability rows do not sum to 1; ROC-AUC omitted."
        clean.append(values)
    return clean, names, None


def validate_payload(payload: object, *, rows: int, task: TaskType) -> ValidatedPredictions:
    if not isinstance(payload, dict):
        raise _invalid("The sandbox output is not a JSON object.")
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise _invalid("The sandbox output has no prediction list.")
    if len(predictions) != rows:
        raise _invalid(f"Expected {rows} predictions, got {len(predictions)}.")
    if rows == 0:
        raise _invalid("The model returned no predictions.")

    if task == TaskType.REGRESSION:
        values: list[float] = []
        for position, value in enumerate(predictions):
            if not _is_number(value) or not math.isfinite(float(value)):
                raise _invalid(f"Prediction {position + 1} is not a finite number.")
            values.append(float(value))
        return ValidatedPredictions(values)

    labels = [_scalar_label(value, position) for position, value in enumerate(predictions)]
    probabilities, classes, note = _validate_probabilities(payload, rows)
    result = ValidatedPredictions(labels, probabilities, classes)
    if note:
        result.notes.append(note)
    return result
