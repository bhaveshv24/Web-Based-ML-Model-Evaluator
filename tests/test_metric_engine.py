"""MLE-10: task detection (FR-015) and the trusted metric engine (FR-017, FR-018).

STP vectors UT-EXE-01..04 and UT-EXE-06 are asserted exactly; the pure-Python engine is
additionally cross-checked against scikit-learn's reference implementations.
"""

import math
import random

import pytest
from evaluations.errors import ErrorCode, EvaluationError
from evaluations.metrics import evaluate
from evaluations.metrics.predictions import validate_payload
from evaluations.metrics.roc import auc, chart_indices, roc_curve
from evaluations.task_detection import (
    TaskDecision,
    TaskDetectionError,
    TaskType,
    canonical_label,
    resolve_task,
)

sklearn_metrics = pytest.importorskip("sklearn.metrics")

CLS = TaskDecision(TaskType.CLASSIFICATION, "detected", "test")
REG = TaskDecision(TaskType.REGRESSION, "detected", "test")


def strings(values):
    return [str(value) for value in values]


# ------------------------------------------------------------------ FR-015 task detection
def test_ut_exe_01_two_hundred_distinct_floats_is_regression():
    labels = strings(round(0.37 * i + 0.01, 4) for i in range(200))
    decision = resolve_task(labels, None, max_classes=100)
    assert decision.task_type == TaskType.REGRESSION and decision.source == "detected"


def test_ut_exe_02_string_labels_are_classification_and_override_is_honoured():
    decision = resolve_task(["a", "b", "c", "a"], None, max_classes=100)
    assert decision.task_type == TaskType.CLASSIFICATION
    assert decision.reason == "3 distinct text label(s)"
    numeric = strings(round(0.37 * i + 0.01, 4) for i in range(200))
    override = resolve_task(numeric[:50], "CLASSIFICATION", max_classes=100)
    assert override.task_type == TaskType.CLASSIFICATION and override.source == "override"


def test_numeric_csv_strings_are_interpreted_as_numbers():
    assert resolve_task(["0", "1", "1.0", "0"], None, max_classes=100).task_type == (
        TaskType.CLASSIFICATION
    )
    assert resolve_task(["1.5", "2.25", "3.75"], "REGRESSION", max_classes=100).task_type == (
        TaskType.REGRESSION
    )


@pytest.mark.parametrize(
    ("labels", "override", "message"),
    [
        ([], None, "no rows"),
        (["a", " ", "b"], None, "missing"),
        (["a", "b"], "REGRESSION", "numeric target"),
        (["1", "2"], "CLUSTERING", "Unknown task type"),
        ([f"id-{i}" for i in range(150)], None, "150 distinct labels"),
        (["nan", "1", "2"], "REGRESSION", "numeric target"),
    ],
)
def test_ambiguous_or_unsupported_targets_are_rejected_explicitly(labels, override, message):
    with pytest.raises(TaskDetectionError, match=message):
        resolve_task(labels, override, max_classes=100)


def test_canonical_labels_unify_numeric_spellings():
    assert canonical_label("1") == canonical_label(1) == canonical_label(1.0) == "1"
    assert canonical_label(" setosa ") == "setosa"
    assert canonical_label(True) == "True"
    assert canonical_label(0.5) == canonical_label("0.50") == "0.5"


# -------------------------------------------------------------- FR-017 / FR-018 metrics
def test_ut_exe_03_classification_vector_through_the_engine():
    result = evaluate(strings([0, 1, 1, 0]), {"predictions": [0, 1, 0, 0]}, CLS)
    metrics = result.metrics
    assert metrics["accuracy"] == 0.75
    assert metrics["per_class"]["1"]["precision"] == 1.0
    assert metrics["per_class"]["1"]["recall"] == 0.5
    assert metrics["per_class"]["1"]["f1"] == pytest.approx(2 / 3)
    assert round(metrics["per_class"]["1"]["f1"], 3) == 0.667
    assert metrics["confusion_matrix"] == [[2, 0], [1, 1]]
    assert metrics["roc_auc"] is None and "probabilities" in metrics["roc_auc_note"]
    assert result.charts["confusion_matrix"] == [[2, 0], [1, 1]]
    assert metrics["task_detection"]["task_type"] == "CLASSIFICATION"


def test_ut_exe_04_regression_vector_through_the_engine():
    result = evaluate(["3", "5", "7"], {"predictions": [2, 5, 8]}, REG)
    metrics = result.metrics
    assert metrics["mae"] == pytest.approx(2 / 3) and round(metrics["mae"], 3) == 0.667
    assert metrics["mse"] == pytest.approx(2 / 3)
    assert round(metrics["rmse"], 3) == 0.816
    assert metrics["r2"] == 0.75
    assert result.charts["predicted_vs_actual"] == {
        "actual": [3.0, 5.0, 7.0],
        "predicted": [2.0, 5.0, 8.0],
        "sampled": False,
    }
    assert result.charts["residuals"]["residual"] == [1.0, 0.0, -1.0]
    assert sum(result.charts["residual_histogram"]["counts"]) == 3


def test_ut_exe_06_roc_auc_reported_with_probabilities():
    y = strings([0, 0, 1, 1])
    payload = {
        "predictions": [0, 0, 1, 1],
        "classes": [0, 1],
        "probabilities": [[0.9, 0.1], [0.6, 0.4], [0.65, 0.35], [0.2, 0.8]],
    }
    metrics = evaluate(y, payload, CLS).metrics
    assert metrics["roc_auc"] == pytest.approx(0.75)
    assert metrics["roc_auc"] == pytest.approx(
        sklearn_metrics.roc_auc_score([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8])
    )
    assert metrics["roc_auc_average"] == "binary" and metrics["roc_auc_note"] is None


def test_classification_matches_scikit_learn_on_random_multiclass_data():
    rng = random.Random(7)
    labels = ["cat", "dog", "owl"]
    y_true = [rng.choice(labels) for _ in range(300)]
    y_pred = [t if rng.random() < 0.6 else rng.choice(labels) for t in y_true]
    probabilities = []
    for truth in y_true:
        raw = [rng.random() + (1.5 if name == truth else 0) for name in labels]
        probabilities.append([value / sum(raw) for value in raw])
    payload = {"predictions": y_pred, "classes": labels, "probabilities": probabilities}
    metrics = evaluate(y_true, payload, CLS).metrics

    assert metrics["accuracy"] == pytest.approx(sklearn_metrics.accuracy_score(y_true, y_pred))
    for average in ("macro", "weighted"):
        assert metrics[f"precision_{average}"] == pytest.approx(
            sklearn_metrics.precision_score(y_true, y_pred, average=average, zero_division=0)
        )
        assert metrics[f"recall_{average}"] == pytest.approx(
            sklearn_metrics.recall_score(y_true, y_pred, average=average, zero_division=0)
        )
        assert metrics[f"f1_{average}"] == pytest.approx(
            sklearn_metrics.f1_score(y_true, y_pred, average=average, zero_division=0)
        )
    assert (
        metrics["confusion_matrix"]
        == sklearn_metrics.confusion_matrix(y_true, y_pred, labels=labels).tolist()
    )
    assert metrics["roc_auc"] == pytest.approx(
        sklearn_metrics.roc_auc_score(
            y_true, probabilities, multi_class="ovr", average="macro", labels=labels
        )
    )
    assert metrics["roc_auc_average"] == "macro_ovr"


def test_regression_matches_scikit_learn():
    rng = random.Random(3)
    y_true = [rng.uniform(-50, 50) for _ in range(500)]
    y_pred = [value + rng.gauss(0, 4) for value in y_true]
    metrics = evaluate(strings(y_true), {"predictions": y_pred}, REG).metrics
    assert metrics["mae"] == pytest.approx(sklearn_metrics.mean_absolute_error(y_true, y_pred))
    assert metrics["mse"] == pytest.approx(sklearn_metrics.mean_squared_error(y_true, y_pred))
    assert metrics["rmse"] == pytest.approx(math.sqrt(metrics["mse"]))
    assert metrics["r2"] == pytest.approx(sklearn_metrics.r2_score(y_true, y_pred))


def test_roc_curve_handles_ties_like_scikit_learn():
    y = [0, 1, 1, 0, 1, 0, 1]
    scores = [0.5, 0.5, 0.9, 0.1, 0.5, 0.5, 0.7]
    fpr, tpr, _ = roc_curve(y, scores)
    ref_fpr, ref_tpr, _ = sklearn_metrics.roc_curve(y, scores, drop_intermediate=False)
    assert fpr == pytest.approx(list(ref_fpr)) and tpr == pytest.approx(list(ref_tpr))
    assert auc(fpr, tpr) == pytest.approx(sklearn_metrics.roc_auc_score(y, scores))
    with pytest.raises(ValueError):
        roc_curve([1, 1], [0.2, 0.3])
    assert chart_indices(10, 4) == [0, 3, 6, 9] and chart_indices(3, 10) == [0, 1, 2]


def test_roc_is_omitted_with_a_note_when_undefined():
    single_class = evaluate(
        ["a", "a"],
        {
            "predictions": ["a", "a"],
            "classes": ["a", "b"],
            "probabilities": [[0.7, 0.3], [0.6, 0.4]],
        },
        CLS,
    ).metrics
    assert single_class["roc_auc"] is None and "undefined" in single_class["roc_auc_note"]
    unknown_class = evaluate(
        ["a", "c"],
        {
            "predictions": ["a", "a"],
            "classes": ["a", "b"],
            "probabilities": [[0.7, 0.3], [0.6, 0.4]],
        },
        CLS,
    ).metrics
    assert unknown_class["roc_auc"] is None and "not among" in unknown_class["roc_auc_note"]


# ------------------------------------------------------------- prediction validation
@pytest.mark.parametrize(
    ("payload", "task", "rows"),
    [
        ([1, 2], TaskType.CLASSIFICATION, 2),
        ({"labels": [1, 2]}, TaskType.CLASSIFICATION, 2),
        ({"predictions": [1]}, TaskType.CLASSIFICATION, 2),
        ({"predictions": [1, [2]]}, TaskType.CLASSIFICATION, 2),
        ({"predictions": [1, None]}, TaskType.CLASSIFICATION, 2),
        ({"predictions": [1, {"x": 1}]}, TaskType.CLASSIFICATION, 2),
        ({"predictions": [1, "x" * 201]}, TaskType.CLASSIFICATION, 2),
        ({"predictions": [1, float("nan")]}, TaskType.CLASSIFICATION, 2),
        ({"predictions": [1.0, float("inf")]}, TaskType.REGRESSION, 2),
        ({"predictions": [1.0, "2.0"]}, TaskType.REGRESSION, 2),
        ({"predictions": [1.0, True]}, TaskType.REGRESSION, 2),
        ({"predictions": []}, TaskType.REGRESSION, 0),
    ],
)
def test_invalid_predictions_are_rejected(payload, task, rows):
    with pytest.raises(EvaluationError) as raised:
        validate_payload(payload, rows=rows, task=task)
    assert raised.value.code == ErrorCode.INVALID_PREDICTIONS


@pytest.mark.parametrize(
    ("extra", "note"),
    [
        ({"probabilities": [[0.5, 0.5], [0.5, 0.5]]}, "without class names"),
        ({"classes": [0, 0], "probabilities": [[0.5, 0.5], [0.5, 0.5]]}, "not unique"),
        ({"classes": [0, 1], "probabilities": [[0.5, 0.5]]}, "do not match"),
        ({"classes": [0, 1], "probabilities": [[1.0], [1.0]]}, "wrong width"),
        ({"classes": [0, 1], "probabilities": [[float("nan"), 1], [0.5, 0.5]]}, "non-finite"),
        ({"classes": [0, 1], "probabilities": [[1.5, -0.5], [0.5, 0.5]]}, "outside"),
        ({"classes": [0, 1], "probabilities": [[0.9, 0.9], [0.5, 0.5]]}, "sum to 1"),
        ({"classes": [[0], 1], "probabilities": [[0.5, 0.5], [0.5, 0.5]]}, "not scalar"),
    ],
)
def test_malformed_probabilities_drop_roc_but_keep_the_evaluation(extra, note):
    payload = {"predictions": [0, 1], **extra}
    metrics = evaluate(["0", "1"], payload, CLS).metrics
    assert metrics["accuracy"] == 1.0
    assert metrics["roc_auc"] is None and note in metrics["roc_auc_note"]


def test_disjoint_label_encoding_is_rejected_instead_of_scoring_zero():
    with pytest.raises(EvaluationError) as raised:
        evaluate(["setosa", "virginica"], {"predictions": [0, 1]}, CLS)
    assert raised.value.code == ErrorCode.INVALID_PREDICTIONS


def test_overflowing_regression_metrics_are_rejected():
    with pytest.raises(EvaluationError):
        evaluate(["1", "2"], {"predictions": [1e308, -1e308]}, REG)


def test_large_regression_charts_are_sampled():
    n = 5000
    result = evaluate(strings(range(n)), {"predictions": list(range(n))}, REG)
    assert result.metrics["n_samples"] == n
    assert len(result.charts["predicted_vs_actual"]["actual"]) == 2000
    assert result.charts["predicted_vs_actual"]["sampled"] is True
    assert sum(result.charts["residual_histogram"]["counts"]) == n
