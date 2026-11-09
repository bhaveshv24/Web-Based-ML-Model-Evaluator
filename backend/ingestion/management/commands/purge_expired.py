"""Run the NFR-010 retention purge once: python manage.py purge_expired."""

from django.core.management.base import BaseCommand

from ingestion.retention import purge_expired


class Command(BaseCommand):
    help = "Delete uploads and stored reports older than RETENTION_DAYS (NFR-010)."

    def handle(self, *args, **options):
        counts = purge_expired()
        self.stdout.write(", ".join(f"{key}={value}" for key, value in counts.items()))
