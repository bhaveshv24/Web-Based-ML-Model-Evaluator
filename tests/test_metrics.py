import math

import pytest
from evaluations.metrics import classification_metrics, regression_metrics
from evaluations.task_detection import TaskType, detect_task_type


def test_task_detection_and_override():
    assert detect_task_type(["a", "b", "c"]) == TaskType.CLASSIFICATION
    assert detect_task_type([1.1, 2.2, 3.7, 4.9]) == TaskType.REGRESSION
    assert detect_task_type([1.1, 2.2], TaskType.CLASSIFICATION) == TaskType.CLASSIFICATION


def test_classification_metrics_match_hand_computation():
    result = classification_metrics([0, 1, 1, 0], [0, 1, 0, 0])
    assert result["accuracy"] == 0.75
    assert result["per_class"]["1"]["precision"] == 1.0
    assert result["per_class"]["1"]["recall"] == 0.5
    assert result["per_class"]["1"]["f1"] == pytest.approx(2 / 3)
    assert result["confusion_matrix"] == [[2, 0], [1, 1]]


def test_regression_metrics_match_stp_vector():
    result = regression_metrics([3, 5, 7], [2, 5, 8])
    assert result["mae"] == pytest.approx(2 / 3)
    assert result["mse"] == pytest.approx(2 / 3)
    assert result["rmse"] == pytest.approx(math.sqrt(2 / 3))
    assert result["r2"] == 0.75


def test_metric_vectors_must_align():
    with pytest.raises(ValueError):
        classification_metrics([1], [])
