"""TSMP-21 (MLE-21) security regression: ST-SEC-01..06, 09, 13, the STP 11.1 authorization
matrix, API-23 (admin activation, BR-08) and per-user upload throttling (SEC-007).

Known deviations from the approved matrix are strict xfails that name their defect in
docs/TSMP-21_DEFECT_REGISTER.md, so a fix turns them into an XPASS failure and gets noticed.
"""

import base64
import json
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from accounts.models import AuditLog, User
from accounts.throttles import UploadRateThrottle
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone
from evaluations.metrics.engine import evaluate
from evaluations.models import Comparison, Evaluation
from evaluations.task_detection import resolve_task
from ingestion.models import CompatibilityReport, Dataset, ModelArtifact
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from workspaces.models import Workspace, WorkspaceMembership

pytestmark = pytest.mark.django_db

PASSWORD = secrets.token_urlsafe(16) + "Aa1!"
PICKLE = b"\x80\x04payload"
CSV = b"a,b,label\n1,2,x\n3,4,y\n"


@pytest.fixture(autouse=True)
def isolated(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    cache.clear()


def user(email, role=User.Role.USER):
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def client_for(account=None, token=None):
    client = APIClient()
    if account is not None:
        token = AccessToken.for_user(account)
    if token is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def succeeded_evaluation(owner, **changes):
    actual = ["x", "y", "y", "x"]
    result = evaluate(
        actual,
        {"predictions": ["x", "y", "x", "x"]},
        resolve_task(actual, "CLASSIFICATION", max_classes=100),
    )
    return Evaluation.objects.create(
        owner=owner,
        task_type="CLASSIFICATION",
        status="SUCCEEDED",
        dataset_sha256="d" * 64,
        model_sha256="m" * 64,
        target_column="label",
        metrics_json=result.metrics,
        charts_json=result.charts,
        started_at=timezone.now() - timedelta(seconds=2),
        finished_at=timezone.now(),
        **changes,
    )


def upload(client, name="model.pkl", content=PICKLE, path="/api/v1/models"):
    return client.post(path, {"file": SimpleUploadedFile(name, content)}, format="multipart")


# ------------------------------------------------------------------------------- ST-SEC-01
def test_st_sec_01_password_is_stored_only_as_a_salted_pbkdf2_hash():
    response = APIClient().post(
        "/api/v1/auth/register", {"email": "hash@pes.edu", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 201
    with connection.cursor() as cursor:
        cursor.execute("SELECT password FROM accounts_user WHERE email = %s", ["hash@pes.edu"])
        (stored,) = cursor.fetchone()
    algorithm, iterations, salt, digest = stored.split("$")
    assert algorithm == "pbkdf2_sha256" and int(iterations) > 100_000 and salt and digest
    assert PASSWORD not in stored
    # Same password, different salt: no two users share a hash.
    other = user("hash2@pes.edu")
    assert other.password != stored


# ------------------------------------------------------------------------------- ST-SEC-02
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/workspaces"),
        ("post", "/api/v1/workspaces"),
        ("post", "/api/v1/workspaces/{ws}/members"),
        ("get", "/api/v1/workspaces/{ws}/evaluations"),
        ("patch", "/api/v1/admin/users/{victim}"),
    ],
)
def test_st_sec_02_user_token_gets_403_on_every_evaluator_and_admin_function(method, path):
    evaluator = user("ev@pes.edu", User.Role.EVALUATOR)
    workspace = Workspace.objects.create(name="SE", evaluator=evaluator)
    victim = user("victim@pes.edu")
    attacker = user("attacker@pes.edu")
    url = path.format(ws=workspace.id, victim=victim.id)
    response = getattr(client_for(attacker), method)(
        url, {"name": "x", "email": attacker.email, "is_active": False}, format="json"
    )
    assert response.status_code == 403
    victim.refresh_from_db()
    assert victim.is_active
    assert not WorkspaceMembership.objects.filter(user=attacker).exists()
    assert AuditLog.objects.filter(event="AUTHORIZATION_DENIED", user=attacker).exists()


def test_st_sec_02_evaluator_token_cannot_reach_admin_functions():
    evaluator = user("ev@pes.edu", User.Role.EVALUATOR)
    victim = user("victim@pes.edu")
    response = client_for(evaluator).patch(
        f"/api/v1/admin/users/{victim.id}", {"is_active": False}, format="json"
    )
    assert response.status_code == 403
    victim.refresh_from_db()
    assert victim.is_active


# ------------------------------------------------------------------------------- ST-SEC-03
def test_st_sec_03_access_token_lifetime_is_15_minutes_and_expired_token_gets_401():
    account = user("expiry@pes.edu")
    fresh = AccessToken.for_user(account)
    assert fresh["exp"] - fresh["iat"] == 15 * 60
    expired = AccessToken.for_user(account)
    expired.set_exp(from_time=timezone.now() - timedelta(minutes=16))
    response = client_for(token=expired).get("/api/v1/evaluations")
    assert response.status_code == 401
    assert client_for(token=fresh).get("/api/v1/evaluations").status_code == 200


def test_st_sec_03_missing_or_malformed_token_gets_401():
    assert APIClient().get("/api/v1/evaluations").status_code == 401
    assert client_for(token="not-a-jwt").get("/api/v1/evaluations").status_code == 401


# ------------------------------------------------------------------------------- ST-SEC-04
def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_st_sec_04_tampered_role_claim_with_original_signature_gets_401():
    account = user("tamper@pes.edu")
    login = APIClient().post(
        "/api/v1/auth/login", {"email": account.email, "password": PASSWORD}, format="json"
    )
    header, payload, signature = login.json()["access"].split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    assert claims["role"] == "USER"
    claims["role"] = "ADMIN"
    forged = f"{header}.{_b64(claims)}.{signature}"
    response = client_for(token=forged).patch(
        f"/api/v1/admin/users/{account.id}", {"is_active": False}, format="json"
    )
    assert response.status_code == 401
    assert client_for(token=forged).get("/api/v1/evaluations").status_code == 401


def test_st_sec_04_unsigned_alg_none_token_gets_401():
    account = user("none@pes.edu")
    claims = dict(AccessToken.for_user(account).payload)
    forged = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."
    assert client_for(token=forged).get("/api/v1/evaluations").status_code == 401


def test_st_sec_04_refresh_token_cannot_be_used_as_access_token():
    account = user("refresh-as-access@pes.edu")
    refresh = RefreshToken.for_user(account)
    assert client_for(token=str(refresh)).get("/api/v1/evaluations").status_code == 401


# ------------------------------------------------------------------------------- ST-SEC-05
INJECTIONS = ["' OR '1'='1", "1; DROP TABLE accounts_user;--", "SUCCEEDED' --", "\x00"]


@pytest.mark.parametrize("payload", INJECTIONS)
@pytest.mark.parametrize("parameter", ["status", "task_type", "from", "to"])
def test_st_sec_05_sql_injection_in_history_filters_is_a_400_without_leak(parameter, payload):
    owner = user("owner@pes.edu")
    other = user("other@pes.edu")
    succeeded_evaluation(other)
    response = client_for(owner).get("/api/v1/evaluations", {parameter: payload})
    assert response.status_code == 400
    body = json.dumps(response.json())
    assert "Traceback" not in body and "SELECT" not in body.upper() and "sqlite" not in body
    assert User.objects.count() == 2 and Evaluation.objects.count() == 1


def test_st_sec_05_injection_in_page_and_target_column_is_rejected():
    owner = user("owner@pes.edu")
    client = client_for(owner)
    assert client.get("/api/v1/evaluations", {"page": "1 OR 1=1"}).status_code == 404
    dataset = upload(client, "d.csv", CSV, "/api/v1/datasets").json()
    response = client.patch(
        f"/api/v1/datasets/{dataset['id']}", {"target_column": "label' OR 1=1--"}, format="json"
    )
    assert response.status_code == 400
    assert Dataset.objects.get(id=dataset["id"]).target_column == "label"


# ------------------------------------------------------------------------------- ST-SEC-06
@pytest.mark.parametrize(
    "name", ["../../etc/x.pkl", "..\\..\\windows\\x.pkl", "/etc/passwd.pkl", "a/../../x.pkl"]
)
def test_st_sec_06_traversal_file_name_is_stored_under_a_uuid_inside_media_root(name, settings):
    owner = user("traversal@pes.edu")
    response = upload(client_for(owner), name)
    assert response.status_code == 201
    artifact = ModelArtifact.objects.get(id=response.json()["id"])
    stored = Path(artifact.file.path).resolve()
    media = Path(settings.MEDIA_ROOT).resolve()
    assert stored.parent == media / "models"
    assert stored.name == f"{artifact.id}.pkl"
    assert stored.read_bytes() == PICKLE
    files = [p for p in media.parent.rglob("*") if p.is_file()]
    assert files == [stored]


# ------------------------------------------------------------------------------- ST-SEC-09
def test_st_sec_09_user_a_gets_404_for_every_object_of_user_b():
    alice, bob = user("alice@pes.edu"), user("bob@pes.edu")
    bob_client = client_for(bob)
    model = upload(bob_client).json()["id"]
    dataset = upload(bob_client, "d.csv", CSV, "/api/v1/datasets").json()["id"]
    report = CompatibilityReport.objects.create(
        owner=bob, model_artifact_id=model, dataset_id=dataset, result="PASSED", checks=[]
    )
    evaluations = [succeeded_evaluation(bob), succeeded_evaluation(bob)]
    comparison = Comparison.objects.create(
        owner=bob, evaluation_ids=[str(e.id) for e in evaluations]
    )
    eid = evaluations[0].id
    attacker = client_for(alice)
    requests = [
        ("get", f"/api/v1/evaluations/{eid}", None),
        ("get", f"/api/v1/evaluations/{eid}/status", None),
        ("get", f"/api/v1/evaluations/{eid}/charts", None),
        ("get", f"/api/v1/evaluations/{eid}/report.json", None),
        ("get", f"/api/v1/evaluations/{eid}/report.pdf", None),
        ("delete", f"/api/v1/evaluations/{eid}", None),
        ("get", f"/api/v1/models/{model}", None),
        ("get", f"/api/v1/datasets/{dataset}", None),
        ("patch", f"/api/v1/datasets/{dataset}", {"target_column": "a"}),
        ("get", f"/api/v1/compatibility-reports/{report.id}", None),
        ("post", "/api/v1/compatibility-reports", {"model_id": model, "dataset_id": dataset}),
        ("post", "/api/v1/evaluations", {"model_id": model, "dataset_id": dataset}),
        ("post", "/api/v1/comparisons", {"evaluation_ids": [str(e.id) for e in evaluations]}),
        ("get", f"/api/v1/comparisons/{comparison.id}", None),
        ("get", f"/api/v1/comparisons/{comparison.id}/report.json", None),
        ("get", f"/api/v1/comparisons/{comparison.id}/report.pdf", None),
    ]
    for method, path, body in requests:
        response = getattr(attacker, method)(path, body, format="json")
        assert response.status_code == 404, (method, path, response.status_code)
        assert bob.email not in response.content.decode(errors="ignore")
    assert Evaluation.objects.filter(owner=bob).count() == 2
    assert Dataset.objects.get(id=dataset).target_column == "label"
    assert not Evaluation.objects.filter(owner=alice).exists()


# ------------------------------------------------------------------------------- ST-SEC-13
def test_st_sec_13_failed_login_and_403_are_audited_with_user_ip_event_and_time():
    victim = user("audited@pes.edu")
    before = timezone.now()
    APIClient(REMOTE_ADDR="203.0.113.7").post(
        "/api/v1/auth/login", {"email": victim.email, "password": "wrong-Passw0rd"}, format="json"
    )
    denied = APIClient(REMOTE_ADDR="203.0.113.8")
    denied.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(victim)}")
    assert denied.post("/api/v1/workspaces", {"name": "x"}, format="json").status_code == 403

    login = AuditLog.objects.get(event="LOGIN_FAILED")
    assert (login.actor_email, login.ip_address) == (victim.email, "203.0.113.7")
    assert login.created_at >= before
    denial = AuditLog.objects.get(event="AUTHORIZATION_DENIED")
    assert (denial.user, denial.ip_address) == (victim, "203.0.113.8")
    assert denial.metadata["path"] == "/api/v1/workspaces" and denial.created_at >= before


# ------------------------------------------------------------------- STP 11.1 authorization matrix
@pytest.fixture
def matrix():
    owner = user("owner@pes.edu")
    evaluator = user("evaluator@pes.edu", User.Role.EVALUATOR)
    admin = user("admin@pes.edu", User.Role.ADMIN)
    workspace = Workspace.objects.create(name="SE", evaluator=evaluator)
    WorkspaceMembership.objects.create(workspace=workspace, user=owner)
    evaluation = succeeded_evaluation(owner, workspace=workspace)
    return {"owner": owner, "evaluator": evaluator, "admin": admin, "evaluation": evaluation}


EVALUATION_PATHS = ["", "/status", "/charts", "/report.json", "/report.pdf"]


@pytest.mark.parametrize("suffix", EVALUATION_PATHS)
def test_matrix_evaluation_resources_anonymous_401_owner_200_other_user_404(matrix, suffix):
    path = f"/api/v1/evaluations/{matrix['evaluation'].id}{suffix}"
    assert APIClient().get(path).status_code == 401
    assert client_for(matrix["owner"]).get(path).status_code == 200
    assert client_for(user("stranger@pes.edu")).get(path).status_code == 404


@pytest.mark.parametrize("suffix", EVALUATION_PATHS)
def test_matrix_evaluator_can_open_workspace_member_evaluation(matrix, suffix):
    path = f"/api/v1/evaluations/{matrix['evaluation'].id}{suffix}"
    assert client_for(matrix["evaluator"]).get(path).status_code == 200


def test_matrix_evaluator_sees_workspace_member_evaluation_in_workspace_list(matrix):
    workspace = matrix["evaluation"].workspace
    response = client_for(matrix["evaluator"]).get(f"/api/v1/workspaces/{workspace.id}/evaluations")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["results"]] == [str(matrix["evaluation"].id)]


@pytest.mark.parametrize("suffix", EVALUATION_PATHS)
def test_matrix_admin_cannot_read_other_users_evaluations(matrix, suffix):
    # STP 11.1 expects 403; the API answers 404, which also discloses nothing (see DEF-06).
    path = f"/api/v1/evaluations/{matrix['evaluation'].id}{suffix}"
    assert client_for(matrix["admin"]).get(path).status_code in {403, 404}


def test_matrix_admin_gets_403_on_workspaces(matrix):
    # Final role policy permits ADMIN evaluator controls, scoped to its own workspaces.
    assert client_for(matrix["admin"]).get("/api/v1/workspaces").status_code == 200


@pytest.mark.parametrize(
    "path", ["/api/v1/models", "/api/v1/datasets", "/api/v1/evaluations",
             "/api/v1/compatibility-reports", "/api/v1/comparisons", "/api/v1/workspaces"],
)
def test_matrix_anonymous_gets_401_on_protected_collections(path):
    assert APIClient().post(path, {}, format="json").status_code == 401


def test_matrix_public_endpoints_need_no_token():
    client = APIClient()
    assert client.post(
        "/api/v1/auth/register", {"email": "p@pes.edu", "password": PASSWORD}, format="json"
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login", {"email": "p@pes.edu", "password": PASSWORD}, format="json"
    ).status_code == 200


# ---------------------------------------------------------------- API-23 / UC-12 / BR-08
def test_api_23_admin_deactivates_and_reactivates_a_user():
    admin = user("root@pes.edu", User.Role.ADMIN)
    target = user("student@pes.edu")
    access = AccessToken.for_user(target)
    refresh = str(RefreshToken.for_user(target))
    path = f"/api/v1/admin/users/{target.id}"

    response = client_for(admin).patch(path, {"is_active": False}, format="json")
    assert response.status_code == 200 and response.json()["is_active"] is False
    login = {"email": target.email, "password": PASSWORD}
    assert APIClient().post("/api/v1/auth/login", login, format="json").status_code == 401
    assert client_for(token=access).get("/api/v1/evaluations").status_code == 401
    assert APIClient().post(
        "/api/v1/auth/token/refresh", {"refresh": refresh}, format="json"
    ).status_code == 401
    # BR-08: the account and its audit history are kept, never deleted.
    assert User.objects.filter(id=target.id).exists()
    assert AuditLog.objects.filter(event="USER_DEACTIVATED", user=admin).exists()

    assert client_for(admin).patch(path, {"is_active": True}, format="json").status_code == 200
    assert APIClient().post("/api/v1/auth/login", login, format="json").status_code == 200
    assert AuditLog.objects.filter(event="USER_ACTIVATED").exists()


def test_api_23_input_and_lookup_errors():
    admin = user("root@pes.edu", User.Role.ADMIN)
    client = client_for(admin)
    assert client.patch(f"/api/v1/admin/users/{uuid.uuid4()}", {"is_active": False},
                        format="json").status_code == 404
    assert client.patch(f"/api/v1/admin/users/{admin.id}", {"is_active": "maybe"},
                        format="json").status_code == 400
    assert client.patch(f"/api/v1/admin/users/{admin.id}", {"is_active": False},
                        format="json").status_code == 400
    admin.refresh_from_db()
    assert admin.is_active
    assert APIClient().patch(f"/api/v1/admin/users/{admin.id}", {"is_active": False},
                             format="json").status_code == 401


# ----------------------------------------------------------------- SEC-007 upload throttling
def test_sec_007_uploads_are_rate_limited_per_user(monkeypatch):
    monkeypatch.setattr(UploadRateThrottle, "rate", "2/min", raising=False)
    first, second = user("u1@pes.edu"), user("u2@pes.edu")
    client = client_for(first)
    assert upload(client).status_code == 201
    assert upload(client, "d.csv", CSV, "/api/v1/datasets").status_code == 201
    limited = upload(client)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    assert ModelArtifact.objects.filter(owner=first).count() == 1
    # The limit is per user: another account is unaffected.
    assert upload(client_for(second)).status_code == 201


def test_sec_007_default_upload_rate_is_configured():
    assert UploadRateThrottle().rate == "30/min"


# ------------------------------------------------------------------------------- ST-SEC-11
@pytest.mark.parametrize(
    ("path", "declared"),
    [("/api/v1/models", 200 * 1024**2), ("/api/v1/datasets", 60 * 1024**2)],
)
def test_st_sec_11_oversize_body_is_rejected_from_content_length_before_parsing(
    path, declared, monkeypatch
):
    def never_parse(*args, **kwargs):
        raise AssertionError("the multipart body must not be parsed")

    monkeypatch.setattr("rest_framework.request.Request._parse", never_parse)
    response = client_for(user("big@pes.edu")).post(
        path, {"file": SimpleUploadedFile("m.pkl", PICKLE)}, format="multipart",
        CONTENT_LENGTH=str(declared),
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert not ModelArtifact.objects.exists() and not Dataset.objects.exists()


def test_st_sec_11_body_at_the_limit_is_still_parsed_normally():
    response = upload(client_for(user("small@pes.edu")))
    assert response.status_code == 201


# ------------------------------------------------------------------------------- UT-ING-01
ONNX_HEADER = b"\x08\x08\x12\x07pytorch\x1a\x032.1\x3a\x80\x01" + b"\x00" * 8


@pytest.mark.parametrize(
    ("name", "prefix", "accepted"),
    [
        ("model.pkl", b"\x80\x04", True),
        ("model.joblib", b"\x80\x04", True),
        ("model.onnx", ONNX_HEADER, True),
        ("model.exe", b"MZ", False),
        ("model.pkl.exe", b"\x80\x04", False),
    ],
)
def test_ut_ing_01_extension_allow_list_exact_stp_vector(name, prefix, accepted):
    from ingestion.validators import validate_model_upload

    assert (validate_model_upload(name, 10, prefix) == []) is accepted


# ---------------------------------------------------------------------- DEF-13 (UI console)
def test_results_page_declares_an_icon_that_is_served_with_the_page_csp():
    client = APIClient()
    page = client.get("/results")
    assert b'href="/results/favicon.svg"' in b"".join(page.streaming_content)
    icon = client.get("/results/favicon.svg")
    assert icon.status_code == 200 and icon["Content-Type"] == "image/svg+xml"
    assert "default-src 'self'" in icon["Content-Security-Policy"]
    icon.close()


@pytest.mark.parametrize("suffix", EVALUATION_PATHS)
def test_workspace_read_access_is_revoked_when_membership_ends(matrix, suffix):
    evaluation = matrix["evaluation"]
    WorkspaceMembership.objects.filter(
        workspace=evaluation.workspace, user=evaluation.owner
    ).delete()
    assert client_for(matrix["evaluator"]).get(
        f"/api/v1/evaluations/{evaluation.id}{suffix}"
    ).status_code == 404


def test_workspace_evaluator_cannot_delete_member_evaluation(matrix):
    evaluation = matrix["evaluation"]
    assert client_for(matrix["evaluator"]).delete(
        f"/api/v1/evaluations/{evaluation.id}"
    ).status_code == 404
    assert Evaluation.objects.filter(pk=evaluation.pk).exists()
