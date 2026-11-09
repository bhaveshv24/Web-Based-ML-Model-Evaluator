"""Compatibility entry point for the original retention task and callers."""

from ingestion.retention import purge_expired as purge_uploads


def purge_expired(*, now=None) -> dict[str, int]:
    counts = purge_uploads(now=now)
    return {
        "reports": counts["reports"],
        "evaluation_artifacts": counts["artifacts"],
        "models": counts["models"],
        "datasets": counts["datasets"],
    }
