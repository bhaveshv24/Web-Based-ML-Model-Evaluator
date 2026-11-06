"""TSMP-21 (MLE-21) regression tests for backend edge cases that no earlier test exercised.

Each case was chosen from the coverage report of the final regression run: the branch it hits
was never executed, and it guards a stated requirement. Tests only; no product code changes.
"""

import logging
import secrets
import types

import pytest
from accounts.models import AuditLog, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from evaluations import audit
from evaluations.errors import ErrorCode
from ingestion import views as ingestion_views
from ingestion.validators import MODEL_LIMIT_BYTES, validate_csv_bytes, validate_model_upload
from rest_framework.exceptions import APIException
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from workspaces.models import Workspace, WorkspaceMembership

PASSWORD = secrets.token_urlsafe(16) + "Aa1!"
PICKLE_PREFIX = b"\x80\x04payload"
ONNX_PREFIX = b"\x08\x08\x12\x07pytorch\x1a\x032.1\x3a\x80\x01"


@pytest.fixture(autouse=True)
def isolated(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    cache.clear()


def client_for(account):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(account)}")
    return client


def codes(issues):
    return {issue.code for issue in issues}


# ----------------------------------------------------------------------------- FR-001


@pytest.mark.django_db
@pytest.mark.parametrize("password", ["abcdefghijk", "12345678901"], ids=["letters", "digits"])
def test_fr001_password_needs_both_letters_and_digits(password):
    response = APIClient().post(
        "/api/v1/auth/register", {"email": "new@pes.edu", "password": password}, format="json"
    )
    assert response.status_code == 400
    assert "letters and digits" in str(response.json())
    assert not User.objects.filter(email="new@pes.edu").exists()


@pytest.mark.django_db
def test_fr001_manager_requires_email_and_normalizes_it():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password=PASSWORD)
    created = User.objects.create_user(email="Mixed@PES.EDU", password=PASSWORD)
    assert created.email == "mixed@pes.edu"
    assert created.check_password(PASSWORD) and created.password != PASSWORD


@pytest.mark.django_db
def test_fr004_superuser_is_an_admin():
    admin = User.objects.create_superuser(email="root@pes.edu", password=PASSWORD)
    assert admin.role == "ADMIN" and admin.is_staff and admin.is_superuser


# ----------------------------------------------------------------------------- FR-003


@pytest.mark.django_db
@pytest.mark.parametrize("token", ["not-a-jwt", "access"], ids=["garbage", "access-token"])
def test_fr003_logout_with_an_invalid_refresh_token_is_401(token):
    account = User.objects.create_user(email="out@pes.edu", password=PASSWORD)
    refresh = str(AccessToken.for_user(account)) if token == "access" else token
    response = client_for(account).post("/api/v1/auth/logout", {"refresh": refresh}, format="json")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


# ----------------------------------------------------------------------------- FR-007


@pytest.mark.django_db
def test_fr007_member_must_be_an_existing_active_user_and_not_already_added():
    evaluator = User.objects.create_user(email="ev@pes.edu", password=PASSWORD, role="EVALUATOR")
    member = User.objects.create_user(email="member@pes.edu", password=PASSWORD)
    User.objects.create_user(email="gone@pes.edu", password=PASSWORD, is_active=False)
    workspace = Workspace.objects.create(name="Lab", evaluator=evaluator)
    client = client_for(evaluator)
    url = f"/api/v1/workspaces/{workspace.id}/members"

    assert client.post(url, {"email": "MEMBER@pes.edu"}, format="json").status_code == 201
    for email in ("nobody@pes.edu", "gone@pes.edu", "member@pes.edu"):
        response = client.post(url, {"email": email}, format="json")
        assert response.status_code == 400, email
    assert WorkspaceMembership.objects.filter(workspace=workspace).count() == 1
    assert WorkspaceMembership.objects.get(workspace=workspace).user == member


# ----------------------------------------------------------------------- FR-008 / SEC-004


def test_fr008_validator_rejects_a_model_one_byte_over_100_mb():
    assert "MODEL_SIZE" not in codes(
        validate_model_upload("m.pkl", MODEL_LIMIT_BYTES, PICKLE_PREFIX)
    )
    issues = validate_model_upload("m.pkl", MODEL_LIMIT_BYTES + 1, PICKLE_PREFIX)
    issue = next(i for i in issues if i.code == "MODEL_SIZE")
    assert (issue.expected, issue.actual) == (MODEL_LIMIT_BYTES, MODEL_LIMIT_BYTES + 1)


@pytest.mark.parametrize(
    "prefix",
    [ONNX_PREFIX[:2] + b"\x80", ONNX_PREFIX[:7]],
    ids=["cut-inside-a-tag", "cut-inside-a-field"],
)
def test_fr008_onnx_signature_accepts_a_prefix_cut_mid_field(prefix):
    # Only the first 64 bytes are inspected, so a valid ONNX file can be cut anywhere.
    assert not validate_model_upload("m.onnx", 10_000, prefix)


def test_sec004_unreadable_content_length_falls_through_to_the_file_checks():
    request = types.SimpleNamespace(META={"CONTENT_LENGTH": "not-a-number"})
    ingestion_views._reject_oversize_body(request, limit=10)  # must not raise
    request.META["CONTENT_LENGTH"] = str(10 + ingestion_views.MULTIPART_OVERHEAD_BYTES + 1)
    with pytest.raises(APIException) as raised:
        ingestion_views._reject_oversize_body(request, limit=10)
    assert raised.value.status_code == 413


# ------------------------------------------------------------------------ FR-009 / FR-010


def test_fr009_row_limit_boundary():
    content = b"a,b\n1,2\n3,4\n5,6\n"
    summary, issues = validate_csv_bytes(content, row_limit=3)
    assert summary is not None and not issues
    summary, issues = validate_csv_bytes(content, row_limit=2)
    # The summary is still returned; the upload view rejects whenever any issue is present.
    issue = next(i for i in issues if i.code == "DATASET_ROWS")
    assert (issue.expected, issue.actual) == (2, 3)


@pytest.mark.parametrize("content", [b"", b"\xef\xbb\xbf"], ids=["empty", "bom-only"])
def test_fr010_file_without_a_header_is_rejected(content):
    summary, issues = validate_csv_bytes(content)
    assert summary is None and codes(issues) == {"DATASET_HEADER"}


@pytest.mark.django_db
def test_fr009_owner_reads_dataset_detail_and_blank_target_override_is_rejected():
    owner = User.objects.create_user(email="ds@pes.edu", password=PASSWORD)
    client = client_for(owner)
    upload = client.post(
        "/api/v1/datasets",
        {"file": SimpleUploadedFile("iris.csv", b"a,b,species\n1,2,x\n3,4,y\n")},
        format="multipart",
    )
    assert upload.status_code == 201
    url = f"/api/v1/datasets/{upload.json()['id']}"

    detail = client.get(url)
    assert detail.status_code == 200
    body = detail.json()
    assert body["row_count"] == 2 and body["columns"] == ["a", "b", "species"]
    assert body["suggested_target"] == "species"
    assert body["sha256"] == upload.json()["sha256"]

    blank = client.patch(url, {"target_column": "   "}, format="json")
    assert blank.status_code == 400
    assert client.get(url).json()["target_column"] == "species"


# ----------------------------------------------------------------------------- SEC-006


@pytest.mark.django_db
def test_sec006_audit_write_failure_never_masks_the_job_result(monkeypatch, caplog):
    def broken(**_):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(AuditLog.objects, "create", broken)
    with caplog.at_level(logging.ERROR, logger="evaluations.audit"):
        assert audit.record_failure("job-1", None, ErrorCode.TIMEOUT) is None
    assert "audit write failed" in caplog.text
