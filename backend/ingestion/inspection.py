"""Model inspection boundary.

Pickle/joblib files are executable content and must NEVER be loaded by the web process
(see README "Security boundary"). Inspection is delegated to the evaluation worker, which
loads the model only inside the hardened per-job sandbox (MLE-11, SAD 5.1 step 6) and
returns n_features_in_ / feature_names_in_. Whenever that path is disabled or fails, this
function returns None and the compatibility report fails closed instead of guessing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("ingestion.inspection")


@dataclass(frozen=True)
class ModelInspection:
    expected_feature_count: int | None = None
    feature_names: tuple[str, ...] | None = None


def inspect_model(path: str, extension: str) -> ModelInspection | None:
    """Return what the model expects, or None when no safe inspector is available."""
    if not settings.SANDBOX_INSPECTION_ENABLED:
        return None
    try:
        relative = Path(path).resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())
    except (OSError, ValueError):
        return None
    try:
        from evaluations.tasks import inspect_model as inspect_task

        pending = inspect_task.apply_async(args=[str(relative), extension], retry=False)
        result = pending.get(timeout=settings.SANDBOX_INSPECT_TIMEOUT_SECONDS + 30)
    except Exception as exc:  # broker/worker unavailable or timed out
        logger.warning("model inspection unavailable: %s", type(exc).__name__)
        return None
    if not isinstance(result, dict) or not isinstance(result.get("expected_feature_count"), int):
        return None
    names = result.get("feature_names")
    return ModelInspection(
        expected_feature_count=result["expected_feature_count"],
        feature_names=tuple(names) if isinstance(names, list) else None,
    )
