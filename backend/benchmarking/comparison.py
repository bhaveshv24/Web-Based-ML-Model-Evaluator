from __future__ import annotations

from dataclasses import dataclass


class ComparisonError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationResult:
    evaluation_id: str
    dataset_sha256: str
    task_type: str
    metrics: dict[str, float]
    status: str = "SUCCEEDED"


LOWER_IS_BETTER = {"mae", "mse", "rmse"}


def assert_comparable(results: list[EvaluationResult]) -> None:
    if not 2 <= len(results) <= 5:
        raise ComparisonError("A comparison requires 2 to 5 evaluations")
    if any(result.status != "SUCCEEDED" for result in results):
        raise ComparisonError("Every evaluation must be SUCCEEDED")
    if len({result.dataset_sha256 for result in results}) != 1:
        raise ComparisonError("Evaluations use different datasets")
    if len({result.task_type for result in results}) != 1:
        raise ComparisonError("Evaluations use different task types")


def best_per_metric(results: list[EvaluationResult]) -> dict[str, str]:
    assert_comparable(results)
    shared_metrics = set.intersection(*(set(result.metrics) for result in results))
    winners: dict[str, str] = {}
    for metric in sorted(shared_metrics):
        choose = min if metric.lower() in LOWER_IS_BETTER else max
        winners[metric] = choose(results, key=lambda result: result.metrics[metric]).evaluation_id
    return winners
