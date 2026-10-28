"""ROC curve and area under it (FR-017, UT-EXE-06).

Pure Python so the metric service stays testable without NumPy (NFR-009). Ties in the score
are handled the same way as scikit-learn's ``roc_curve(drop_intermediate=False)``.
"""

from __future__ import annotations

from collections.abc import Sequence


def roc_curve(
    y_binary: Sequence[int], scores: Sequence[float]
) -> tuple[list[float], list[float], list[float]]:
    if len(y_binary) != len(scores) or not y_binary:
        raise ValueError("Labels and scores must have the same non-zero length")
    positives = sum(1 for value in y_binary if value)
    negatives = len(y_binary) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("ROC needs at least one positive and one negative sample")

    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    fpr, tpr, thresholds = [0.0], [0.0], [float("inf")]
    true_pos = false_pos = 0
    for position, index in enumerate(order):
        if y_binary[index]:
            true_pos += 1
        else:
            false_pos += 1
        last_of_tie = position == len(order) - 1 or scores[order[position + 1]] != scores[index]
        if last_of_tie:
            fpr.append(false_pos / negatives)
            tpr.append(true_pos / positives)
            thresholds.append(float(scores[index]))
    return fpr, tpr, thresholds


def auc(x: Sequence[float], y: Sequence[float]) -> float:
    """Trapezoidal area; x must be non-decreasing (true for an ROC curve)."""
    return sum((x[i] - x[i - 1]) * (y[i] + y[i - 1]) / 2 for i in range(1, len(x)))


def chart_indices(length: int, limit: int) -> list[int]:
    """Evenly spaced indices that always keep the first and the last point."""
    if length <= limit:
        return list(range(length))
    step = (length - 1) / (limit - 1)
    return sorted({round(i * step) for i in range(limit)})
