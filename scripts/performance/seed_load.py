"""Seed 50 independent accounts and status records for PERF-01 on a disposable stack."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import User  # noqa: E402
from evaluations.models import Evaluation  # noqa: E402

password = os.environ["PERF_PASSWORD"]
for index in range(50):
    email = f"perf-{index}@example.test"
    user, created = User.objects.get_or_create(email=email)
    if created:
        user.set_password(password)
        user.save(update_fields=["password"])
    if not Evaluation.objects.filter(owner=user).exists():
        Evaluation.objects.create(
            owner=user, status=Evaluation.Status.SUCCEEDED,
            task_type=Evaluation.TaskType.CLASSIFICATION,
        )
print("Seeded 50 PERF-01 users and status records")
