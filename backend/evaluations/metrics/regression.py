from __future__ import annotations

from math import fsum, sqrt


def regression_metrics(y_true: list[float], y_pred: list[float]) -> dict[str, float]:
    if len(y_true) != len(y_pred) or not y_true:
        raise ValueError("y_true and y_pred must have the same non-zero length")
    actual = [float(value) for value in y_true]
    errors = [a - float(p) for a, p in zip(actual, y_pred, strict=True)]
    count = len(errors)
    mae = fsum(abs(error) for error in errors) / count
    mse = fsum(error**2 for error in errors) / count
    mean = fsum(actual) / count
    total = fsum((value - mean) ** 2 for value in actual)
    residual = fsum(error**2 for error in errors)
    # Constant target: R^2 is undefined; follow scikit-learn's force_finite convention.
    r2 = 1.0 - residual / total if total else (1.0 if residual == 0 else 0.0)
    return {"mae": mae, "mse": mse, "rmse": sqrt(mse), "r2": r2}
