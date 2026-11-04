"""PERF-01 seed: 50 accounts, each with one SUCCEEDED classification evaluation.

Run inside the api container (Django settings and the production database):
    LOAD_PASSWORD=... docker compose exec -T -e LOAD_PASSWORD api \
        python manage.py shell < scripts/validation/perf/seed_load_users.py
Prints one line per account: "<email> <evaluation id>".
"""
import os
from datetime import timedelta

from accounts.models import User
from django.utils import timezone
from evaluations.metrics.engine import evaluate
from evaluations.models import Evaluation
from evaluations.task_detection import resolve_task

password = os.environ["LOAD_PASSWORD"]
actual = ["setosa", "versicolor", "virginica"] * 50
result = evaluate(
    actual,
    {"predictions": actual[:-1] + ["setosa"],
     "classes": ["setosa", "versicolor", "virginica"],
     "probabilities": [[0.8, 0.1, 0.1]] * len(actual)},
    resolve_task(actual, "CLASSIFICATION", max_classes=100),
)
for index in range(int(os.environ.get("LOAD_USERS", "50"))):
    email = f"loadtest-{index}@pes.edu"
    user, _ = User.objects.get_or_create(email=email)
    user.set_password(password)
    user.save()
    evaluation = Evaluation.objects.filter(owner=user).first() or Evaluation.objects.create(
        owner=user, task_type="CLASSIFICATION", status="SUCCEEDED",
        dataset_sha256="d" * 64, model_sha256="m" * 64, target_column="species",
        sandbox_image="ml-evaluator-sandbox:1.0", metrics_json=result.metrics,
        charts_json=result.charts, started_at=timezone.now() - timedelta(seconds=2),
        finished_at=timezone.now(),
    )
    print(email, evaluation.id)
