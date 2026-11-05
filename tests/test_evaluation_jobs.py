"""MLE-09 / MLE-12 integration tests: asynchronous lifecycle, failure handling and cleanup.

Covers IT-EXE-01, IT-EXE-05..07, UT-EXE-05, REL-01 and the M3 rows of the authorization
matrix. The sandbox is replaced by test doubles here (NFR-009); the real containment suite
is tests/test_sandbox_docker.py.
"""

import secrets
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from accounts.models import AuditLog, User
from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from evaluations import executor, reaper, services, tasks
from evaluations.errors import ErrorCode, EvaluationError
from evaluations.models import Evaluation
from evaluations.sandbox import SandboxCancelled
from evaluations.services import ALLOWED_TRANSITIONS, IllegalTransition, check_transition
from ingestion import compatibility
from ingestion.inspection import ModelInspection
from ingestion.inspection import inspect_model as real_inspect_model
from ingestion.models import ModelArtifact
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from sandbox_doubles import FakeRunner
from workspaces.models import Workspace, WorkspaceMembership

pytestmark = pytest.mark.django_db

PASSWORD = secrets.token_urlsafe(16) + "Aa1!"
# Fake credential injected into error text to prove it is redacted; generated per run.
LEAK_CANARY = secrets.token_hex(6)
CSV = b"a,b,species\n1,2,x\n3,4,x\n5,6,y\n7,8,x\n"
Status = Evaluation.Status


@pytest.fixture(autouse=True)
def isolated_dirs(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.SANDBOX_WORK_DIR = tmp_path / "jobs"
    settings.SANDBOX_HOST_WORK_DIR = tmp_path / "jobs"
    return tmp_path


@pytest.fixture
def enqueued(monkeypatch):
    calls = []
    monkeypatch.setattr(services, "enqueue_evaluation", lambda pk: calls.append(str(pk)))
    return calls


@pytest.fixture(autouse=True)
def fake_inspector(monkeypatch):
    monkeypatch.setattr(
        compatibility.inspection, "inspect_model", lambda *_: ModelInspection(2, ("a", "b"))
    )


def make_client(email=None):
    email = email or f"m3-{uuid.uuid4().hex[:8]}@pes.edu"
    user = User.objects.create_user(email=email, password=PASSWORD)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client, user


def validated_pair(client, csv=CSV, validate=True):
    model = client.post(
        "/api/v1/models",
        {"file": SimpleUploadedFile("model.pkl", b"\x80\x04" + b"m" * 32)},
        format="multipart",
    ).json()
    dataset = client.post(
        "/api/v1/datasets", {"file": SimpleUploadedFile("d.csv", csv)}, format="multipart"
    ).json()
    if validate:
        report = client.post(
            "/api/v1/compatibility-reports",
            {"model_id": model["id"], "dataset_id": dataset["id"]},
            format="json",
        )
        assert report.json()["result"] == "PASSED"
    return model["id"], dataset["id"]


def submit(client, model_id, dataset_id, **extra):
    return client.post(
        "/api/v1/evaluations",
        {"model_id": model_id, "dataset_id": dataset_id, **extra},
        format="json",
    )


def rule_based(header, rows):
    """A 'model' that predicts x when a < 4: right on 3 of the 4 rows of CSV."""
    return {
        "predictions": ["x" if float(row[0]) < 4 else "y" for row in rows],
        "classes": ["x", "y"],
        "probabilities": [[0.8, 0.2] if float(row[0]) < 4 else [0.3, 0.7] for row in rows],
    }


def queued_job(client=None, **extra):
    client = client or make_client()[0]
    model_id, dataset_id = validated_pair(client)
    response = submit(client, model_id, dataset_id, **extra)
    assert response.status_code == 202
    return client, response.json()["id"]


def assert_sanitized(text: str):
    for leak in ("Traceback", "/srv", "/tmp", "/Users", 'File "', LEAK_CANARY, "SECRET"):
        assert leak not in text


# --------------------------------------------------------------- IT-EXE-01, FR-014, BR-01
def test_post_returns_202_queued_immediately_and_enqueues_once(enqueued):
    client, user = make_client()
    model_id, dataset_id = validated_pair(client)
    started = time.monotonic()
    response = submit(client, model_id, dataset_id)
    assert time.monotonic() - started < 1.0
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert response["Location"] == f"/api/v1/evaluations/{body['id']}"
    assert body["status_url"] == f"/api/v1/evaluations/{body['id']}/status"
    assert enqueued == [body["id"]]
    stored = Evaluation.objects.get(id=body["id"])
    assert stored.owner == user and stored.status == Status.QUEUED
    assert stored.dataset_sha256 and stored.model_sha256 and stored.target_column == "species"
    assert stored.task_type == "" and stored.task_type_overridden is False


def test_each_submission_gets_its_own_job_id(enqueued):
    client, _ = make_client()
    model_id, dataset_id = validated_pair(client)
    ids = {submit(client, model_id, dataset_id).json()["id"] for _ in range(3)}
    assert len(ids) == 3 and sorted(enqueued) == sorted(ids)


def test_task_type_override_is_stored(enqueued):
    _, job_id = queued_job(task_type="CLASSIFICATION")
    stored = Evaluation.objects.get(id=job_id)
    assert stored.task_type == "CLASSIFICATION" and stored.task_type_overridden


def test_unvalidated_failed_or_stale_pairs_cannot_be_evaluated(enqueued, monkeypatch):
    client, _ = make_client()
    model_id, dataset_id = validated_pair(client, validate=False)
    response = submit(client, model_id, dataset_id)
    assert response.status_code == 400
    assert "compatibility" in str(response.json())

    monkeypatch.setattr(
        compatibility.inspection, "inspect_model", lambda *_: ModelInspection(5, None)
    )
    client.post(
        "/api/v1/compatibility-reports",
        {"model_id": model_id, "dataset_id": dataset_id},
        format="json",
    )
    assert submit(client, model_id, dataset_id).status_code == 400

    monkeypatch.setattr(
        compatibility.inspection, "inspect_model", lambda *_: ModelInspection(2, ("a", "b"))
    )
    model_id, dataset_id = validated_pair(make_client("other@pes.edu")[0])
    owner_client = APIClient()
    owner = User.objects.get(email="other@pes.edu")
    owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(owner)}")
    patched = owner_client.patch(
        f"/api/v1/datasets/{dataset_id}", {"target_column": "b"}, format="json"
    )
    assert patched.status_code == 200
    assert submit(owner_client, model_id, dataset_id).status_code == 400  # re-validate first
    assert not Evaluation.objects.exists() and enqueued == []


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"model_id": "not-a-uuid", "dataset_id": str(uuid.uuid4())}, 400),
        ({"dataset_id": str(uuid.uuid4())}, 400),
        ({"model_id": str(uuid.uuid4()), "dataset_id": str(uuid.uuid4())}, 404),
    ],
)
def test_submission_input_validation(payload, code, enqueued):
    client, _ = make_client()
    assert client.post("/api/v1/evaluations", payload, format="json").status_code == code
    assert client.post("/api/v1/evaluations", [1, 2], format="json").status_code == 400


def test_invalid_task_type_and_foreign_artifacts_are_rejected(enqueued):
    client, _ = make_client()
    model_id, dataset_id = validated_pair(client)
    assert submit(client, model_id, dataset_id, task_type="CLUSTERING").status_code == 400
    intruder, _ = make_client("intruder@pes.edu")
    assert submit(intruder, model_id, dataset_id).status_code == 404
    assert APIClient().post("/api/v1/evaluations", {}, format="json").status_code == 401


def test_workspace_submission_requires_membership(enqueued):
    client, user = make_client()
    model_id, dataset_id = validated_pair(client)
    evaluator = User.objects.create_user(
        email="ta@pes.edu", password=PASSWORD, role=User.Role.EVALUATOR
    )
    workspace = Workspace.objects.create(name="SE", evaluator=evaluator)
    response = submit(client, model_id, dataset_id, workspace_id=str(workspace.id))
    assert response.status_code == 404
    WorkspaceMembership.objects.create(workspace=workspace, user=user)
    response = submit(client, model_id, dataset_id, workspace_id=str(workspace.id))
    assert response.status_code == 202
    assert Evaluation.objects.get(id=response.json()["id"]).workspace == workspace


def test_unreachable_queue_returns_503_and_records_a_failed_job(monkeypatch):
    def broker_down(_pk):
        raise ConnectionError(f"Error 61 connecting to redis:6379 pass{'word'}={LEAK_CANARY}")

    monkeypatch.setattr(services, "enqueue_evaluation", broker_down)
    client, _ = make_client()
    model_id, dataset_id = validated_pair(client)
    response = submit(client, model_id, dataset_id)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "QUEUE_UNAVAILABLE"
    assert_sanitized(str(response.json()))
    job = Evaluation.objects.get()
    assert job.status == Status.FAILED and job.error_code == "QUEUE_UNAVAILABLE"
    assert_sanitized(job.error_message)


# ---------------------------------------------------------------- UT-EXE-05 state machine
def test_ut_exe_05_illegal_transition_raises_and_leaves_status_unchanged(enqueued):
    _, job_id = queued_job()
    token = services.claim(job_id)
    assert services.complete(job_id, token, task_type="CLASSIFICATION", metrics={}, charts={})
    with pytest.raises(IllegalTransition):
        services.transition(job_id, Status.SUCCEEDED, Status.RUNNING)
    assert Evaluation.objects.get(id=job_id).status == Status.SUCCEEDED


def test_transition_table_is_one_way_and_terminal_states_are_immutable():
    for terminal in (Status.SUCCEEDED, Status.FAILED, Status.TIMED_OUT):
        assert ALLOWED_TRANSITIONS[terminal] == frozenset()
        for target in Status.values:
            with pytest.raises(IllegalTransition):
                check_transition(terminal, target)
    with pytest.raises(IllegalTransition):
        check_transition(Status.RUNNING, Status.QUEUED)
    with pytest.raises(IllegalTransition):
        check_transition(Status.QUEUED, Status.SUCCEEDED)


def test_compare_and_set_rejects_stale_state_and_foreign_tokens(enqueued):
    _, job_id = queued_job()
    token = services.claim(job_id)
    assert services.claim(job_id) is None  # second worker cannot claim
    assert not services.complete(job_id, uuid.uuid4(), task_type="X", metrics={}, charts={})
    assert not services.transition(job_id, Status.QUEUED, Status.RUNNING)
    assert services.fail(job_id, code=ErrorCode.MODEL_LOAD_FAILED, run_token=token)
    assert not services.complete(job_id, token, task_type="X", metrics={"a": 1}, charts={})
    job = Evaluation.objects.get(id=job_id)
    assert job.status == Status.FAILED and job.metrics_json is None


# ------------------------------------------------------- full worker path (IT-EXE-07)
def test_successful_evaluation_end_to_end_with_status_detail_and_charts(enqueued):
    client, job_id = queued_job()
    assert client.get(f"/api/v1/evaluations/{job_id}/charts").status_code == 409
    runner = FakeRunner(rule_based)

    assert executor.execute_evaluation(job_id, runner=runner) == Status.SUCCEEDED

    # BR-06: only X and the model reached the sandbox; the target never did.
    assert runner.seen_files == [["X.csv", "model.pkl"]]
    assert runner.seen_headers == [["a", "b"]]
    assert not any(Path(r.workspace.path).exists() for r in runner.requests)

    status = client.get(f"/api/v1/evaluations/{job_id}/status").json()
    assert status["status"] == "SUCCEEDED" and status["task_type"] == "CLASSIFICATION"
    assert status["error_code"] == "" and status["duration_seconds"] is not None
    detail = client.get(f"/api/v1/evaluations/{job_id}").json()
    stored = Evaluation.objects.get(id=job_id)
    assert detail["metrics_json"] == stored.metrics_json
    assert detail["charts_json"] == stored.charts_json
    assert detail["metrics_json"]["accuracy"] == 0.75
    assert detail["metrics_json"]["roc_auc"] is not None
    assert detail["metrics_json"]["task_detection"]["source"] == "detected"
    charts = client.get(f"/api/v1/evaluations/{job_id}/charts").json()
    assert charts["charts"]["confusion_matrix"] == [[2, 1], [0, 1]]
    listing = client.get("/api/v1/evaluations?task_type=CLASSIFICATION").json()
    assert [item["id"] for item in listing["results"]] == [job_id]


def test_duplicate_delivery_runs_the_job_only_once(enqueued):
    _, job_id = queued_job()
    runner = FakeRunner(rule_based)
    assert executor.execute_evaluation(job_id, runner=runner) == Status.SUCCEEDED
    assert executor.execute_evaluation(job_id, runner=runner) is None
    assert len(runner.requests) == 1


def test_multiple_jobs_use_separate_workspaces_and_keep_their_own_results(enqueued):
    client, _ = make_client()
    ids = []
    for csv in (CSV, b"a,b,species\n1,2,x\n9,9,x\n"):
        model_id, dataset_id = validated_pair(client, csv=csv)
        ids.append(submit(client, model_id, dataset_id).json()["id"])
    runner = FakeRunner(rule_based)
    for job_id in reversed(ids):
        assert executor.execute_evaluation(job_id, runner=runner) == Status.SUCCEEDED
    paths = [r.workspace.path for r in runner.requests]
    assert len(set(paths)) == 2 and not any(p.exists() for p in paths)
    assert {r.job_id for r in runner.requests} == set(ids)
    first, second = (Evaluation.objects.get(id=pk) for pk in ids)
    assert first.metrics_json["accuracy"] == 0.75 and first.metrics_json["n_samples"] == 4
    assert second.metrics_json["accuracy"] == 0.5 and second.metrics_json["n_samples"] == 2


# ----------------------------------------------- MLE-12 failures, timeouts and cleanup
@pytest.mark.parametrize(
    ("error", "status", "code", "event"),
    [
        (
            EvaluationError(ErrorCode.TIMEOUT, "Limit: 120 seconds."),
            "TIMED_OUT",
            "TIMEOUT",
            "EVALUATION_TIMED_OUT",
        ),
        (
            EvaluationError(ErrorCode.RESOURCE_EXHAUSTED),
            "FAILED",
            "RESOURCE_EXHAUSTED",
            "SANDBOX_POLICY_VIOLATION",
        ),
        (
            EvaluationError(ErrorCode.SANDBOX_POLICY_VIOLATION),
            "FAILED",
            "SANDBOX_POLICY_VIOLATION",
            "SANDBOX_POLICY_VIOLATION",
        ),
        (
            EvaluationError(ErrorCode.MODEL_LOAD_FAILED),
            "FAILED",
            "MODEL_LOAD_FAILED",
            "EVALUATION_FAILED",
        ),
        (SoftTimeLimitExceeded(), "TIMED_OUT", "TIMEOUT", "EVALUATION_TIMED_OUT"),
        (
            RuntimeError(f"boom at /srv/app/backend/x.py tok{'en'}={LEAK_CANARY}"),
            "FAILED",
            "INTERNAL_ERROR",
            "EVALUATION_FAILED",
        ),
    ],
)
def test_failures_are_categorized_sanitized_audited_and_cleaned_up(
    enqueued, error, status, code, event
):
    client, job_id = queued_job()
    runner = FakeRunner(error=error)
    assert executor.execute_evaluation(job_id, runner=runner) == status
    job = Evaluation.objects.get(id=job_id)
    assert job.status == status and job.error_code == code
    assert job.metrics_json is None and job.charts_json is None and job.finished_at
    assert_sanitized(job.error_message)
    assert not runner.requests[0].workspace.path.exists()
    audit = AuditLog.objects.get(event=event)
    assert audit.user_id == job.owner_id
    assert audit.metadata["evaluation_id"] == job_id and audit.metadata["error_code"] == code
    for path in ("status", ""):
        body = client.get(f"/api/v1/evaluations/{job_id}/{path}".rstrip("/")).json()
        assert body["status"] == status and body["error_code"] == code
        assert_sanitized(str(body))
    assert client.get(f"/api/v1/evaluations/{job_id}/charts").status_code == 409


def test_invalid_predictions_never_publish_partial_metrics(enqueued):
    _, job_id = queued_job()
    runner = FakeRunner(lambda header, rows: {"predictions": ["x"] * (len(rows) - 1)})
    assert executor.execute_evaluation(job_id, runner=runner) == Status.FAILED
    job = Evaluation.objects.get(id=job_id)
    assert job.error_code == "INVALID_PREDICTIONS" and "Expected 4 predictions" in job.error_message
    assert job.metrics_json is None


def test_result_persistence_failure_marks_the_job_failed(enqueued, monkeypatch):
    _, job_id = queued_job()

    def db_down(*args, **kwargs):
        raise RuntimeError("could not serialize access at /var/lib/postgresql")

    monkeypatch.setattr(services, "complete", db_down)
    assert executor.execute_evaluation(job_id, runner=FakeRunner(rule_based)) == Status.FAILED
    job = Evaluation.objects.get(id=job_id)
    assert job.error_code == "INTERNAL_ERROR" and job.metrics_json is None
    assert_sanitized(job.error_message)


def test_deleting_a_running_job_cancels_its_sandbox_and_cleans_up(enqueued):
    client, job_id = queued_job()

    def delete_then_poll(request):
        assert client.delete(f"/api/v1/evaluations/{job_id}").status_code == 204
        assert request.cancel_check() is True
        raise SandboxCancelled()

    runner = FakeRunner(before=delete_then_poll)
    assert executor.execute_evaluation(job_id, runner=runner) is None
    assert not Evaluation.objects.filter(id=job_id).exists()
    assert not runner.requests[0].workspace.path.exists()


def test_unsupported_task_override_fails_before_any_model_code_runs(enqueued):
    _, job_id = queued_job(task_type="REGRESSION")
    runner = FakeRunner(rule_based)
    assert executor.execute_evaluation(job_id, runner=runner) == Status.FAILED
    job = Evaluation.objects.get(id=job_id)
    assert job.error_code == "UNSUPPORTED_TASK" and "numeric target" in job.error_message
    assert runner.requests == []


def test_tampered_symlinked_or_deleted_inputs_are_rejected(enqueued, isolated_dirs):
    runner = FakeRunner(rule_based)
    _, tampered = queued_job()
    artifact = Evaluation.objects.get(id=tampered).model_artifact
    Path(artifact.file.path).write_bytes(b"\x80\x04swapped-after-upload")
    assert executor.execute_evaluation(tampered, runner=runner) == Status.FAILED

    client, _ = make_client("second@pes.edu")
    _, linked = queued_job(client)
    model_path = Path(Evaluation.objects.get(id=linked).model_artifact.file.path)
    outside = isolated_dirs / "outside.pkl"
    outside.write_bytes(model_path.read_bytes())
    model_path.unlink()
    model_path.symlink_to(outside)
    assert executor.execute_evaluation(linked, runner=runner) == Status.FAILED

    client, _ = make_client("third@pes.edu")
    _, orphaned = queued_job(client)
    Evaluation.objects.get(id=orphaned).dataset.delete()
    assert executor.execute_evaluation(orphaned, runner=runner) == Status.FAILED

    for job_id in (tampered, linked, orphaned):
        job = Evaluation.objects.get(id=job_id)
        assert job.error_code == "INVALID_INPUT"
        assert_sanitized(job.error_message)
    assert runner.requests == []


def test_missing_isolation_backend_fails_closed_without_fallback(enqueued, monkeypatch):
    def no_docker():
        raise ConnectionError("unix:///var/run/docker.sock refused")

    monkeypatch.setattr("evaluations.sandbox.docker_runner._client_from_settings", no_docker)
    _, job_id = queued_job()
    assert executor.execute_evaluation(job_id) == Status.FAILED
    job = Evaluation.objects.get(id=job_id)
    assert job.error_code == "SANDBOX_UNAVAILABLE"
    assert "docker.sock" not in job.error_message


def test_unwritable_workspace_root_reports_sandbox_unavailable(enqueued, settings, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    settings.SANDBOX_WORK_DIR = blocker / "jobs"
    _, job_id = queued_job()
    assert executor.execute_evaluation(job_id, runner=FakeRunner(rule_based)) == Status.FAILED
    assert Evaluation.objects.get(id=job_id).error_code == "SANDBOX_UNAVAILABLE"


# ------------------------------------------------------------- REL-01 / NFR-006 reaper
def test_reaper_fails_stuck_jobs_and_discards_late_worker_results(enqueued):
    _, job_id = queued_job()
    token = services.claim(job_id)
    Evaluation.objects.filter(id=job_id).update(started_at=timezone.now() - timedelta(seconds=181))
    swept = []

    class Sweeper:
        def remove_orphans(self, active, min_age_seconds):
            swept.append((set(active), min_age_seconds))
            return 1

    summary = reaper.reap_stale(runner=Sweeper())
    assert summary["running"] == 1 and summary["containers"] == 1
    assert swept == [(set(), 90)]
    job = Evaluation.objects.get(id=job_id)
    assert job.status == Status.FAILED and job.error_code == "WORKER_LOST"
    assert AuditLog.objects.filter(event="EVALUATION_REAPED").count() == 1
    # The original worker finishing later cannot resurrect or overwrite the job.
    assert not services.complete(job_id, token, task_type="X", metrics={"a": 1}, charts={})
    assert Evaluation.objects.get(id=job_id).metrics_json is None


def test_worker_that_loses_ownership_mid_run_does_not_publish(enqueued):
    _, job_id = queued_job()

    def reaped_meanwhile(_request):
        Evaluation.objects.filter(id=job_id).update(
            started_at=timezone.now() - timedelta(minutes=10)
        )
        reaper.reap_stale(runner=object())

    runner = FakeRunner(rule_based, before=reaped_meanwhile)
    assert executor.execute_evaluation(job_id, runner=runner) is None
    job = Evaluation.objects.get(id=job_id)
    assert job.status == Status.FAILED and job.metrics_json is None


def test_reaper_expires_jobs_that_never_left_the_queue_and_keeps_fresh_ones(enqueued, settings):
    _, old = queued_job()
    _, fresh = queued_job()
    Evaluation.objects.filter(id=old).update(
        created_at=timezone.now() - timedelta(seconds=settings.EVALUATION_QUEUE_TIMEOUT_SECONDS + 1)
    )
    assert reaper.reap_stale(runner=object())["queued"] == 1
    assert Evaluation.objects.get(id=old).error_code == "QUEUE_EXPIRED"
    assert Evaluation.objects.get(id=fresh).status == Status.QUEUED


def test_reaper_tolerates_unavailable_docker(enqueued):
    class Down:
        def remove_orphans(self, *args, **kwargs):
            raise EvaluationError(ErrorCode.SANDBOX_UNAVAILABLE)

    assert reaper.reap_stale(runner=Down())["containers"] == 0


def test_no_job_can_stay_running_longer_than_five_minutes(settings):
    worst_case = (
        settings.EVALUATION_TIMEOUT_SECONDS
        + settings.EVALUATION_REAPER_GRACE_SECONDS
        + settings.CELERY_BEAT_SCHEDULE["reap-stale-evaluations"]["schedule"]
    )
    assert settings.EVALUATION_TIMEOUT_SECONDS == 120
    assert worst_case < 300
    assert tasks.run_evaluation.soft_time_limit < tasks.run_evaluation.time_limit < 300


# ----------------------------------------------------------- Celery task entry points
def test_celery_tasks_delegate_to_executor_and_reaper(enqueued, monkeypatch):
    _, job_id = queued_job()
    monkeypatch.setattr(executor, "get_sandbox_runner", lambda: FakeRunner(rule_based))
    assert tasks.run_evaluation(job_id) == Status.SUCCEEDED
    assert tasks.run_evaluation(job_id) is None  # redelivery is a no-op
    monkeypatch.setattr(reaper, "get_sandbox_runner", lambda: object())
    assert tasks.reap_stale_evaluations()["running"] == 0
    assert tasks.run_evaluation.acks_late is True
    # Transient DB errors are retried (claiming is idempotent) instead of stranding a job.
    from django.db import OperationalError

    assert OperationalError in tasks.run_evaluation.autoretry_for


def test_enqueue_uses_the_registered_task(monkeypatch):
    sent = []
    monkeypatch.setattr(
        tasks.run_evaluation, "apply_async", lambda args, retry: sent.append((args, retry))
    )
    services.enqueue_evaluation("abc")
    assert sent == [(["abc"], True)]


# ------------------------------------------------------------ IDOR on job endpoints
def test_other_users_cannot_see_status_charts_or_details(enqueued):
    _, job_id = queued_job()
    intruder, _ = make_client("intruder@pes.edu")
    for suffix in ("", "/status", "/charts"):
        assert intruder.get(f"/api/v1/evaluations/{job_id}{suffix}").status_code == 404
        assert APIClient().get(f"/api/v1/evaluations/{job_id}{suffix}").status_code == 401


# ------------------------------------------ SAD 5.1 step 6: sandboxed model inspection
class InspectRunner:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.requests = payload, error, []

    def run(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.payload


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"n_features_in": 2, "feature_names_in": ["a", "b"]},
            {"expected_feature_count": 2, "feature_names": ["a", "b"]},
        ),
        (
            {"n_features_in": 2, "feature_names_in": ["a"]},
            {"expected_feature_count": 2, "feature_names": None},
        ),
        ({"n_features_in": None, "feature_names_in": None}, None),
        ({"n_features_in": True}, None),
        ({"n_features_in": 10**6}, None),
    ],
)
def test_inspect_stored_model_validates_sandbox_output(settings, payload, expected):
    models = Path(settings.MEDIA_ROOT) / "models"
    models.mkdir(parents=True)
    (models / "m.pkl").write_bytes(b"\x80\x04model")
    runner = InspectRunner(payload)
    assert executor.inspect_stored_model("models/m.pkl", ".pkl", runner=runner) == expected
    request = runner.requests[0]
    assert request.mode == "inspect" and request.command() == ["inspect", "/input/model.pkl"]
    assert not request.workspace.path.exists()


def test_inspect_stored_model_fails_closed(settings):
    models = Path(settings.MEDIA_ROOT) / "models"
    models.mkdir(parents=True)
    (models / "m.pkl").write_bytes(b"\x80\x04model")
    failing = InspectRunner(error=EvaluationError(ErrorCode.MODEL_LOAD_FAILED))
    assert executor.inspect_stored_model("models/m.pkl", ".pkl", runner=failing) is None
    assert executor.inspect_stored_model("../../etc/passwd", ".pkl", runner=failing) is None
    assert executor.inspect_stored_model("models/m.pkl", ".exe", runner=failing) is None


def test_web_inspection_hook_is_off_by_default_and_fails_closed(settings, monkeypatch):
    path = str(Path(settings.MEDIA_ROOT) / "models" / "m.pkl")
    assert real_inspect_model(path, ".pkl") is None  # default: disabled

    settings.SANDBOX_INSPECTION_ENABLED = True

    class Pending:
        def __init__(self, value):
            self.value = value

        def get(self, timeout):
            if isinstance(self.value, Exception):
                raise self.value
            return self.value

    sent = []

    def fake_apply_async(args, retry, value):
        sent.append(args)
        return Pending(value)

    for value, expected in (
        (
            {"expected_feature_count": 2, "feature_names": ["a", "b"]},
            ModelInspection(2, ("a", "b")),
        ),
        ({"expected_feature_count": 3, "feature_names": None}, ModelInspection(3, None)),
        (TimeoutError("worker busy"), None),
        ({"expected_feature_count": "2"}, None),
    ):
        monkeypatch.setattr(
            tasks.inspect_model,
            "apply_async",
            lambda args, retry, v=value: fake_apply_async(args, retry, v),
        )
        assert real_inspect_model(path, ".pkl") == expected
    assert sent[0] == ["models/m.pkl", ".pkl"]
    assert real_inspect_model("/etc/passwd", ".pkl") is None


def test_model_artifact_deletion_keeps_history_snapshot(enqueued):
    _, job_id = queued_job()
    ModelArtifact.objects.all().delete()
    job = Evaluation.objects.get(id=job_id)
    assert job.model_artifact is None and len(job.model_sha256) == 64
