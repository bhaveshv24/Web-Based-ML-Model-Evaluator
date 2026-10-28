"""End-to-end asynchronous workflow through a real Redis broker and Celery worker (ST-EXE-01).

API -> Redis -> Celery worker -> runner -> trusted metrics -> DB -> polling client, including
sandboxed-path model inspection dispatched through the queue. The isolation backend is
swapped for the test-only TrustedSubprocessRunner because this test is about the queue
and lifecycle; real containment is covered by tests/test_sandbox_docker.py.
"""

import io
import time
import uuid

import pytest
from accounts.models import User
from config.celery import app as celery_app
from django.core.files.uploadedfile import SimpleUploadedFile
from evaluations.models import Evaluation
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

pytestmark = [pytest.mark.redis, pytest.mark.django_db(transaction=True)]

redis = pytest.importorskip("redis")
sklearn_linear = pytest.importorskip("sklearn.linear_model")
joblib = pytest.importorskip("joblib")
pd = pytest.importorskip("pandas")


@pytest.fixture
def worker(settings, tmp_path):
    url = settings.REDIS_URL.rsplit("/", 1)[0] + "/15"  # dedicated test database
    try:
        redis.Redis.from_url(url, socket_connect_timeout=1).ping()
    except Exception:  # noqa: BLE001
        pytest.skip("Redis is not reachable")
    redis.Redis.from_url(url).flushdb()
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.SANDBOX_WORK_DIR = tmp_path / "jobs"
    settings.SANDBOX_HOST_WORK_DIR = tmp_path / "jobs"
    settings.SANDBOX_RUNNER_CLASS = "sandbox_doubles.TrustedSubprocessRunner"
    settings.SANDBOX_INSPECTION_ENABLED = True
    celery_app.conf.update(broker_url=url, result_backend=url, task_always_eager=False)
    from celery.contrib.testing.worker import start_worker

    with start_worker(celery_app, pool="threads", concurrency=3, perform_ping_check=False):
        yield
    redis.Redis.from_url(url).flushdb()


def client_for_new_user():
    user = User.objects.create_user(email=f"e2e-{uuid.uuid4().hex[:6]}@pes.edu", password="x1")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def upload_trained_pair(client, flip: bool):
    frame = pd.DataFrame({"a": [float(i) for i in range(20)], "b": [i % 3 for i in range(20)]})
    target = ["low" if (i < 10) != flip else "high" for i in range(20)]
    model = sklearn_linear.LogisticRegression().fit(frame, ["low"] * 10 + ["high"] * 10)
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    csv = frame.assign(label=target).to_csv(index=False).encode()
    model_id = client.post(
        "/api/v1/models",
        {"file": SimpleUploadedFile("m.joblib", buffer.getvalue())},
        format="multipart",
    ).json()["id"]
    dataset_id = client.post(
        "/api/v1/datasets", {"file": SimpleUploadedFile("d.csv", csv)}, format="multipart"
    ).json()["id"]
    report = client.post(
        "/api/v1/compatibility-reports",
        {"model_id": model_id, "dataset_id": dataset_id},
        format="json",
    ).json()
    assert report["result"] == "PASSED", report["checks"]
    expected = sum(p == t for p, t in zip(model.predict(frame), target, strict=True)) / 20
    return model_id, dataset_id, expected


def wait_for_terminal(client, job_id, timeout=60):
    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/evaluations/{job_id}/status").json()
        if not seen or seen[-1] != body["status"]:
            seen.append(body["status"])
        if body["status"] in ("SUCCEEDED", "FAILED", "TIMED_OUT"):
            return body, seen
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} did not finish; saw {seen}")


def test_concurrent_jobs_flow_through_the_real_queue(worker):
    client = client_for_new_user()
    jobs = []
    for flip in (False, True, False):
        model_id, dataset_id, expected = upload_trained_pair(client, flip)
        started = time.monotonic()
        response = client.post(
            "/api/v1/evaluations",
            {"model_id": model_id, "dataset_id": dataset_id},
            format="json",
        )
        assert time.monotonic() - started < 1.0
        assert response.status_code == 202 and response.json()["status"] == "QUEUED"
        jobs.append((response.json()["id"], expected))

    for job_id, expected in jobs:
        body, seen = wait_for_terminal(client, job_id)
        assert body["status"] == "SUCCEEDED", body
        assert seen[-1] == "SUCCEEDED" and set(seen) <= {"QUEUED", "RUNNING", "SUCCEEDED"}
        detail = client.get(f"/api/v1/evaluations/{job_id}").json()
        assert detail["metrics_json"]["accuracy"] == pytest.approx(expected)
        assert detail["task_type"] == "CLASSIFICATION"
        assert client.get(f"/api/v1/evaluations/{job_id}/charts").status_code == 200
    assert {j for j, _ in jobs} == set(
        str(pk) for pk in Evaluation.objects.values_list("id", flat=True)
    )
    accuracies = [e for _, e in jobs]
    assert accuracies[0] != accuracies[1]  # each result stayed with its own job
