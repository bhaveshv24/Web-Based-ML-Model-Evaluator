"""M2 integration tests: MLE-5 model upload, MLE-6 CSV ingestion, MLE-7 compatibility."""

import hashlib
import secrets
import uuid
from pathlib import Path

import pytest
from accounts.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from ingestion import compatibility
from ingestion.inspection import ModelInspection
from ingestion.models import Dataset, ModelArtifact
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

pytestmark = pytest.mark.django_db

PASSWORD = secrets.token_urlsafe(16) + "Aa1!"
GOOD_CSV = b"a,b,species\n1,2,setosa\n3,4,virginica\n"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def make_client(email="m2@pes.edu"):
    user = User.objects.create_user(email=email, password=PASSWORD)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client, user


def upload_model(client, name="model.pkl", content=b"\x80\x04payload"):
    return client.post(
        "/api/v1/models",
        {"file": SimpleUploadedFile(name, content)},
        format="multipart",
    )


def upload_csv(client, content=GOOD_CSV, name="data.csv", **extra):
    return client.post(
        "/api/v1/datasets",
        {"file": SimpleUploadedFile(name, content), **extra},
        format="multipart",
    )


# ---------------------------------------------------------------- MLE-5 (FR-008, SEC-004)
def test_valid_model_is_stored_under_uuid_name_with_sha256():
    client, user = make_client()
    content = b"\x80\x04" + b"x" * 100
    response = upload_model(client, "../../evil name.PKL", content)
    assert response.status_code == 201
    body = response.json()
    assert body["sha256"] == hashlib.sha256(content).hexdigest()
    stored = ModelArtifact.objects.get(id=body["id"])
    assert stored.owner == user
    assert Path(stored.file.name).name == f"{stored.id}.pkl"
    assert "evil" not in stored.file.name
    assert stored.file.read() == content


@pytest.mark.parametrize("name", ["model.pkl", "model.joblib", "model.onnx"])
def test_all_three_supported_extensions_are_accepted(name):
    client, _ = make_client()
    content = b"\x08\x07rest" if name.endswith("onnx") else b"\x80\x04rest"
    assert upload_model(client, name, content).status_code == 201


def test_unsupported_extension_is_rejected_with_400():
    client, _ = make_client()
    response = upload_model(client, "model.exe", b"MZ")
    assert response.status_code == 400
    assert not ModelArtifact.objects.exists()


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("model.onnx", b"PK\x03\x04zip"),
        ("model.onnx", b"\x80\x04pickle"),
        ("model.pkl", b"PK\x03\x04zip"),
        ("model.pkl", b"MZ\x90\x00"),
        ("model.joblib", b"\x7fELFbinary"),
    ],
)
def test_disguised_content_is_rejected(name, content):
    client, _ = make_client()
    assert upload_model(client, name, content).status_code == 400
    assert not ModelArtifact.objects.exists()


def test_empty_model_is_rejected():
    client, _ = make_client()
    assert upload_model(client, "model.pkl", b"").status_code == 400


def test_oversize_model_returns_413(monkeypatch):
    monkeypatch.setattr("ingestion.views.MODEL_LIMIT_BYTES", 10)
    monkeypatch.setattr("ingestion.validators.MODEL_LIMIT_BYTES", 10)
    client, _ = make_client()
    assert upload_model(client, "model.pkl", b"\x80\x04" + b"x" * 50).status_code == 413
    assert not ModelArtifact.objects.exists()


def test_model_upload_requires_authentication_and_file():
    assert upload_model(APIClient()).status_code == 401
    client, _ = make_client()
    assert client.post("/api/v1/models", {}, format="multipart").status_code == 400


def test_model_is_private_to_owner():
    owner, _ = make_client("o@pes.edu")
    other, _ = make_client("x@pes.edu")
    model_id = upload_model(owner).json()["id"]
    assert owner.get(f"/api/v1/models/{model_id}").status_code == 200
    assert other.get(f"/api/v1/models/{model_id}").status_code == 404


# ---------------------------------------------------------------- MLE-6 (FR-009..011)
def test_csv_is_parsed_and_target_is_suggested():
    client, _ = make_client()
    response = upload_csv(client)
    assert response.status_code == 201
    body = response.json()
    assert body["columns"] == ["a", "b", "species"]
    assert body["row_count"] == 2
    assert body["suggested_target"] == "species" == body["target_column"]
    assert body["sha256"] == hashlib.sha256(GOOD_CSV).hexdigest()
    assert Path(Dataset.objects.get(id=body["id"]).file.name).name.endswith(".csv")


def test_target_can_be_overridden_at_upload():
    client, _ = make_client()
    body = upload_csv(client, b"a,b,t\n1,x,3\n2,y,4\n", target_column="b").json()
    assert body["suggested_target"] == "t"
    assert body["target_column"] == "b"


def test_target_can_be_overridden_after_upload_and_is_revalidated():
    client, _ = make_client()
    dataset_id = upload_csv(client, b"a,b,t\n1,x,3\n2,y,4\n").json()["id"]
    ok = client.patch(f"/api/v1/datasets/{dataset_id}", {"target_column": "a"}, format="json")
    assert ok.status_code == 200 and ok.json()["target_column"] == "a"
    bad = client.patch(f"/api/v1/datasets/{dataset_id}", {"target_column": "nope"}, format="json")
    assert bad.status_code == 400
    assert Dataset.objects.get(id=dataset_id).target_column == "a"
    missing = client.patch(f"/api/v1/datasets/{dataset_id}", {}, format="json")
    assert missing.status_code == 400


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"a,a,t\n1,2,3\n", "DATASET_DUPLICATE_COLUMNS"),
        (b"a,,t\n1,2,3\n", "DATASET_HEADER"),
        (b"age,t\n,yes\n", "DATASET_MISSING_FEATURE"),
        (b"a,t\n", "DATASET_EMPTY"),
        (b"a,t\n1,2,3\n", "DATASET_WIDTH"),
        (b"\xff\xfe\x00", "DATASET_ENCODING"),
    ],
)
def test_invalid_csv_is_rejected_with_issue_code(content, code):
    client, _ = make_client()
    response = upload_csv(client, content)
    assert response.status_code == 400
    assert code in str(response.json())
    assert not Dataset.objects.exists()


def test_unknown_target_override_is_rejected():
    client, _ = make_client()
    assert upload_csv(client, target_column="ghost").status_code == 400


def test_oversize_dataset_returns_413(monkeypatch):
    monkeypatch.setattr("ingestion.views.DATASET_LIMIT_BYTES", 5)
    client, _ = make_client()
    assert upload_csv(client).status_code == 413


def test_dataset_is_private_to_owner():
    owner, _ = make_client("o@pes.edu")
    other, _ = make_client("x@pes.edu")
    dataset_id = upload_csv(owner).json()["id"]
    assert other.get(f"/api/v1/datasets/{dataset_id}").status_code == 404
    patch = other.patch(f"/api/v1/datasets/{dataset_id}", {"target_column": "a"}, format="json")
    assert patch.status_code == 404


# ---------------------------------------------------------------- MLE-7 (FR-012/013, BR-01/06/07)
def _ids(client):
    return upload_model(client).json()["id"], upload_csv(client).json()["id"]


def test_compatible_model_and_dataset_pass(monkeypatch):
    monkeypatch.setattr(
        compatibility.inspection, "inspect_model", lambda *_: ModelInspection(2, ("a", "b"))
    )
    client, _ = make_client()
    model_id, dataset_id = _ids(client)
    response = client.post(
        "/api/v1/compatibility-reports",
        {"model_id": model_id, "dataset_id": dataset_id},
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["result"] == "PASSED"
    by_code = {c["code"]: c for c in body["checks"]}
    assert by_code["FEATURE_COUNT"]["expected"] == 2 and by_code["FEATURE_COUNT"]["actual"] == 2
    assert "species" not in by_code["TARGET_EXCLUDED"]["actual"]
    fetched = client.get(f"/api/v1/compatibility-reports/{body['id']}")
    assert fetched.status_code == 200 and fetched.json()["result"] == "PASSED"


def test_feature_count_mismatch_fails_with_expected_and_actual(monkeypatch):
    monkeypatch.setattr(
        compatibility.inspection, "inspect_model", lambda *_: ModelInspection(4, None)
    )
    client, _ = make_client()
    model_id, dataset_id = _ids(client)
    body = client.post(
        "/api/v1/compatibility-reports",
        {"model_id": model_id, "dataset_id": dataset_id},
        format="json",
    ).json()
    assert body["result"] == "FAILED"
    check = next(c for c in body["checks"] if c["code"] == "FEATURE_COUNT")
    assert (check["status"], check["expected"], check["actual"]) == ("FAILED", 4, 2)


def test_feature_name_mismatch_lists_missing_and_unexpected(monkeypatch):
    monkeypatch.setattr(
        compatibility.inspection, "inspect_model", lambda *_: ModelInspection(None, ("a", "z"))
    )
    client, _ = make_client()
    model_id, dataset_id = _ids(client)
    body = client.post(
        "/api/v1/compatibility-reports",
        {"model_id": model_id, "dataset_id": dataset_id},
        format="json",
    ).json()
    check = next(c for c in body["checks"] if c["code"] == "FEATURE_NAMES")
    assert body["result"] == "FAILED"
    assert "z" in check["message"] and "b" in check["message"]


def test_report_fails_closed_when_no_safe_inspector_exists():
    client, _ = make_client()
    model_id, dataset_id = _ids(client)
    body = client.post(
        "/api/v1/compatibility-reports",
        {"model_id": model_id, "dataset_id": dataset_id},
        format="json",
    ).json()
    assert body["result"] == "FAILED"
    assert any(c["code"] == "MODEL_INSPECTION" for c in body["checks"])


def test_report_inputs_are_validated_and_owner_scoped():
    owner, _ = make_client("o@pes.edu")
    other, _ = make_client("x@pes.edu")
    model_id, dataset_id = _ids(owner)
    payload = {"model_id": model_id, "dataset_id": dataset_id}
    assert other.post("/api/v1/compatibility-reports", payload, format="json").status_code == 404
    assert owner.post("/api/v1/compatibility-reports", {}, format="json").status_code == 400
    bogus = {"model_id": "not-a-uuid", "dataset_id": dataset_id}
    assert owner.post("/api/v1/compatibility-reports", bogus, format="json").status_code == 404
    unknown = {"model_id": str(uuid.uuid4()), "dataset_id": dataset_id}
    assert owner.post("/api/v1/compatibility-reports", unknown, format="json").status_code == 404
    report_id = owner.post("/api/v1/compatibility-reports", payload, format="json").json()["id"]
    assert other.get(f"/api/v1/compatibility-reports/{report_id}").status_code == 404
