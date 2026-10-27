from __future__ import annotations

from collections import Counter


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def classification_metrics(y_true: list[object], y_pred: list[object]) -> dict[str, object]:
    if len(y_true) != len(y_pred) or not y_true:
        raise ValueError("y_true and y_pred must have the same non-zero length")
    labels = sorted(set(y_true) | set(y_pred), key=str)
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for actual, predicted in zip(y_true, y_pred, strict=True):
        matrix[index[actual]][index[predicted]] += 1

    support = Counter(y_true)
    per_class: dict[str, dict[str, float | int]] = {}
    macro = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    weighted = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    total = len(y_true)
    for label in labels:
        i = index[label]
        tp = matrix[i][i]
        fp = sum(row[i] for row in matrix) - tp
        fn = sum(matrix[i]) - tp
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        per_class[str(label)] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support[label],
        }
        for metric, value in (("precision", precision), ("recall", recall), ("f1", f1)):
            macro[metric] += value / len(labels)
            weighted[metric] += value * support[label] / total

    return {
        "accuracy": sum(a == p for a, p in zip(y_true, y_pred, strict=True)) / total,
        "precision_macro": macro["precision"],
        "recall_macro": macro["recall"],
        "f1_macro": macro["f1"],
        "precision_weighted": weighted["precision"],
        "recall_weighted": weighted["recall"],
        "f1_weighted": weighted["f1"],
        "labels": [str(label) for label in labels],
        "confusion_matrix": matrix,
        "per_class": per_class,
    }
