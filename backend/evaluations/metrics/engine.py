"""Trusted metric engine (FR-017, FR-018, FR-021, SAD D-03).

Runs in the worker, outside the sandbox. Ground truth comes only from the dataset file the
worker read itself; the model contributes nothing but its validated predictions, so it can
neither see the labels nor report its own metrics. Metric selection is fixed per task here
and is never taken from user or model input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..errors import ErrorCode, EvaluationError
from ..task_detection import TaskDecision, TaskType, canonical_label, parse_number
from .classification import classification_metrics
from .predictions import ValidatedPredictions, validate_payload
from .regression import regression_metrics
from .roc import auc, chart_indices, roc_curve

CHART_POINT_LIMIT = 2000
ROC_POINT_LIMIT = 500
HISTOGRAM_BINS = 20


@dataclass(frozen=True)
class MetricResult:
    task_type: TaskType
    metrics: dict
    charts: dict


def _roc_section(y_true: list[str], predictions: ValidatedPredictions) -> tuple[dict, dict | None]:
    """Return (metric fields, chart data) for ROC-AUC, or a note explaining its absence."""
    if predictions.probabilities is None or predictions.classes is None:
        return {"roc_auc": None, "roc_auc_note": predictions.notes[0]}, None
    classes = predictions.classes
    if not set(y_true) <= set(classes):
        note = "Some true labels are not among the model's classes; ROC-AUC omitted."
        return {"roc_auc": None, "roc_auc_note": note}, None

    # Binary: score of the second class, as scikit-learn orders predict_proba columns.
    targets = [classes[1]] if len(classes) == 2 else list(classes)
    curves: dict[str, dict] = {}
    skipped: list[str] = []
    for label in targets:
        column = classes.index(label)
        y_binary = [1 if value == label else 0 for value in y_true]
        scores = [row[column] for row in predictions.probabilities]
        try:
            fpr, tpr, _ = roc_curve(y_binary, scores)
        except ValueError:
            skipped.append(label)
            continue
        keep = chart_indices(len(fpr), ROC_POINT_LIMIT)
        curves[label] = {
            "auc": auc(fpr, tpr),
            "fpr": [fpr[i] for i in keep],
            "tpr": [tpr[i] for i in keep],
        }

    if not curves:
        note = "ROC-AUC needs both positive and negative samples; it is undefined here."
        return {"roc_auc": None, "roc_auc_note": note}, None
    fields: dict = {
        "roc_auc": sum(curve["auc"] for curve in curves.values()) / len(curves),
        "roc_auc_average": "binary" if len(classes) == 2 else "macro_ovr",
        "roc_auc_note": None,
    }
    if skipped:
        fields["roc_auc_note"] = (
            f"{len(skipped)} class(es) without both positive and negative samples were "
            "excluded from the macro average."
        )
    chart = {"average": fields["roc_auc_average"], "curves": curves}
    return fields, chart


def _classification(y_raw: list[str], predictions: ValidatedPredictions) -> tuple[dict, dict]:
    y_true = [canonical_label(value) for value in y_raw]
    if not set(predictions.values) & set(y_true):
        raise EvaluationError(
            ErrorCode.INVALID_PREDICTIONS,
            "None of the predicted labels match the target labels; check the label encoding.",
        )
    metrics = classification_metrics(y_true, predictions.values)
    roc_fields, roc_chart = _roc_section(y_true, predictions)
    metrics.update(roc_fields)
    metrics["n_samples"] = len(y_true)
    charts = {
        "type": TaskType.CLASSIFICATION.value,
        "labels": metrics["labels"],
        "confusion_matrix": metrics["confusion_matrix"],
        "roc": roc_chart,
    }
    return metrics, charts


def _histogram(values: list[float], bins: int) -> dict:
    low, high = min(values), max(values)
    if low == high:
        return {"edges": [low, high], "counts": [len(values)]}
    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        counts[min(int((value - low) / width), bins - 1)] += 1
    return {"edges": [low + width * i for i in range(bins + 1)], "counts": counts}


def _regression(y_raw: list[str], predictions: ValidatedPredictions) -> tuple[dict, dict]:
    y_true = [parse_number(value.strip()) for value in y_raw]
    if any(value is None for value in y_true):
        raise EvaluationError(ErrorCode.UNSUPPORTED_TASK, "The target column is not numeric.")
    try:
        metrics = regression_metrics(y_true, predictions.values)  # type: ignore[arg-type]
    except OverflowError as exc:
        raise EvaluationError(ErrorCode.INVALID_PREDICTIONS, "Metrics overflowed.") from exc
    if not all(math.isfinite(value) for value in metrics.values()):
        raise EvaluationError(ErrorCode.INVALID_PREDICTIONS, "Metrics overflowed to infinity.")
    metrics["n_samples"] = len(y_true)
    residuals = [a - p for a, p in zip(y_true, predictions.values, strict=True)]  # type: ignore[operator]
    keep = chart_indices(len(y_true), CHART_POINT_LIMIT)
    charts = {
        "type": TaskType.REGRESSION.value,
        "predicted_vs_actual": {
            "actual": [y_true[i] for i in keep],
            "predicted": [predictions.values[i] for i in keep],
            "sampled": len(keep) < len(y_true),
        },
        "residuals": {
            "predicted": [predictions.values[i] for i in keep],
            "residual": [residuals[i] for i in keep],
        },
        "residual_histogram": _histogram(residuals, HISTOGRAM_BINS),
    }
    return metrics, charts


def evaluate(y_raw: list[str], payload: object, decision: TaskDecision) -> MetricResult:
    """Validate sandbox output against trusted labels and compute the fixed metric set."""
    predictions = validate_payload(payload, rows=len(y_raw), task=decision.task_type)
    if decision.task_type == TaskType.CLASSIFICATION:
        metrics, charts = _classification(y_raw, predictions)
    else:
        metrics, charts = _regression(y_raw, predictions)
    metrics["task_detection"] = decision.as_dict()
    return MetricResult(decision.task_type, metrics, charts)
