from __future__ import annotations

from math import sqrt


def regression_metrics(y_true: list[float], y_pred: list[float]) -> dict[str, float]:
    if len(y_true) != len(y_pred) or not y_true:
        raise ValueError("y_true and y_pred must have the same non-zero length")
    errors = [
        float(actual) - float(predicted) for actual, predicted in zip(y_true, y_pred, strict=True)
    ]
    mae = sum(abs(error) for error in errors) / len(errors)
    mse = sum(error**2 for error in errors) / len(errors)
    mean = sum(y_true) / len(y_true)
    total = sum((float(value) - mean) ** 2 for value in y_true)
    residual = sum(error**2 for error in errors)
    r2 = 1.0 - residual / total if total else (1.0 if residual == 0 else 0.0)
    return {"mae": mae, "mse": mse, "rmse": sqrt(mse), "r2": r2}
