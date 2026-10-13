import pytest
from benchmarking.comparison import ComparisonError, EvaluationResult, best_per_metric
from evaluations.security import sanitized_failure


def result(identifier, checksum="same", task="CLASSIFICATION", **metrics):
    return EvaluationResult(identifier, checksum, task, metrics)


def test_best_per_metric_uses_direction():
    winners = best_per_metric(
        [
            result("a", f1=0.82, rmse=4.1),
            result("b", f1=0.91, rmse=3.2),
            result("c", f1=0.77, rmse=5.0),
        ]
    )
    assert winners == {"f1": "b", "rmse": "b"}


def test_comparison_rejects_mixed_datasets():
    with pytest.raises(ComparisonError, match="different datasets"):
        best_per_metric([result("a", checksum="a", f1=0.8), result("b", checksum="b", f1=0.9)])


def test_comparison_rejects_invalid_size():
    with pytest.raises(ComparisonError, match="2 to 5"):
        best_per_metric([result("a", f1=0.8)])


def test_failures_do_not_expose_paths_or_tokens():
    message = sanitized_failure(RuntimeError("failed at /srv/private/model.pkl token=abc123"))
    assert "/srv/private" not in message
    assert "abc123" not in message
    assert "[path]" in message and "[redacted]" in message
