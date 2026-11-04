"""Project configuration package. Loads the Celery app so shared tasks bind to it."""

from .celery import app as celery_app

__all__ = ["celery_app"]
