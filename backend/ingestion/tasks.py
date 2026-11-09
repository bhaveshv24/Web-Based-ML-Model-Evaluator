"""Celery task purge_expired (SAD 2.1, NFR-010)."""

from celery import shared_task

from . import retention


@shared_task(name="ingestion.purge_expired", ignore_result=True)
def purge_expired() -> dict[str, int]:
    return retention.purge_expired()
