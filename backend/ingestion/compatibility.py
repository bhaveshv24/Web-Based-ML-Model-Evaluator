"""Model-dataset compatibility checks (MLE-7, FR-012/013, BR-01, BR-06/07)."""

from __future__ import annotations

from typing import Any

from . import inspection
from .models import CompatibilityReport, Dataset, ModelArtifact
from .validators import validate_feature_compatibility

PASSED = "PASSED"
FAILED = "FAILED"


def _check(code: str, status: str, message: str, expected: Any = None, actual: Any = None) -> dict:
    return {
        "code": code,
        "status": status,
        "message": message,
        "expected": expected,
        "actual": actual,
    }


def build_checks(model: ModelArtifact, dataset: Dataset) -> list[dict]:
    columns = list(dataset.columns)
    target = dataset.target_column
    # BR-06/07: the target label is never a model feature.
    features = [name for name in columns if name != target]
    checks = [
        _check(
            "TARGET_EXCLUDED",
            PASSED if target not in features else FAILED,
            "Target column is excluded from the feature set",
            expected=f"'{target}' not in features",
            actual=features,
        )
    ]

    result = inspection.inspect_model(model.file.path, model.extension)
    if result is None:
        checks.append(
            _check(
                "MODEL_INSPECTION",
                FAILED,
                "Sandboxed model inspection is unavailable; compatibility cannot be confirmed",
                expected="inspection result",
                actual="unavailable",
            )
        )
        return checks

    if result.expected_feature_count is not None:
        issues = validate_feature_compatibility(result.expected_feature_count, columns, target)
        checks.append(
            _check(
                "FEATURE_COUNT",
                FAILED if issues else PASSED,
                "Feature count matches the model" if not issues else issues[0].message,
                expected=result.expected_feature_count,
                actual=len(features),
            )
        )
    if result.feature_names is not None:
        expected_names = list(result.feature_names)
        missing = [n for n in expected_names if n not in features]
        extra = [n for n in features if n not in expected_names]
        checks.append(
            _check(
                "FEATURE_NAMES",
                FAILED if missing or extra else PASSED,
                "Feature names match the model"
                if not (missing or extra)
                else f"Missing: {missing}; unexpected: {extra}",
                expected=expected_names,
                actual=features,
            )
        )
    return checks


def run_compatibility(owner, model: ModelArtifact, dataset: Dataset) -> CompatibilityReport:
    checks = build_checks(model, dataset)
    overall = FAILED if any(c["status"] == FAILED for c in checks) else PASSED
    return CompatibilityReport.objects.create(
        owner=owner, model_artifact=model, dataset=dataset, result=overall, checks=checks
    )
