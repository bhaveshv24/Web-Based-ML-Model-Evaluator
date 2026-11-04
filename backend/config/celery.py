"""Celery application for asynchronous evaluation jobs (SAD D-01)."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ml_evaluator")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
