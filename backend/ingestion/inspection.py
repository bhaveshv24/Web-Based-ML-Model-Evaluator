"""Model inspection boundary.

Pickle/joblib files are executable content and must NEVER be loaded by the web process
(see README "Security boundary"). Real inspection belongs in the hardened sandbox owned by
M3 (MLE-11). Until that exists this function reports "unavailable" and the compatibility
report fails closed instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInspection:
    expected_feature_count: int | None = None
    feature_names: tuple[str, ...] | None = None


def inspect_model(path: str, extension: str) -> ModelInspection | None:
    """Return what the model expects, or None when no safe inspector is available."""
    return None
