"""M2 integration tests: MLE-5 model upload, MLE-6 CSV ingestion, MLE-7 compatibility."""

import hashlib
import secrets
import time
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
# ir_version=8, producer_name="pytorch", producer_version="2.1", then a graph field.
ONNX_HEADER = b"\x08\x08\x12\x07pytorch\x1a\x032.1\x3a\x80\x01" + b"\x00" * 8


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
    content = ONNX_HEADER if name.endswith("onnx") else b"\x80\x04rest"
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


# ------------------------------------------------- review follow-up (PR #27) regression tests
@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("fake.pkl", b"just some arbitrary text, not a pickle"),
        ("fake.joblib", b"arbitrary bytes that are not joblib"),
        ("fake.onnx", b"\x08garbage that only starts with 0x08"),
        ("fake.onnx", b"\x08\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"),
        ("fake.pkl", b"\x80\x09unknown protocol"),
    ],
)
def test_arbitrary_bytes_do_not_pass_signature_check(name, content):
    client, _ = make_client()
    response = upload_model(client, name, content)
    assert response.status_code == 400
    assert "MODEL_SIGNATURE" in str(response.json())
    assert not ModelArtifact.objects.exists()


@pytest.mark.parametrize(
    "header",
    [b"x\x9c", b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00", b"\x5d\x00\x00", b"\x04\x22\x4d\x18"],
)
def test_compressed_joblib_is_accepted(header):
    client, _ = make_client()
    assert upload_model(client, "model.joblib", header + b"0" * 40).status_code == 201


def test_oversized_csv_field_is_a_400_not_a_500():
    client, _ = make_client()
    response = upload_csv(client, b"a,t\n" + b"x" * 200_000 + b",1\n")
    assert response.status_code == 400
    assert "DATASET_PARSE" in str(response.json())


def test_very_wide_csv_is_rejected_quickly():
    client, _ = make_client()
    header = ",".join(f"c{i}" for i in range(50_000)).encode()
    started = time.monotonic()
    response = upload_csv(client, header + b"\n1\n")
    assert response.status_code == 400
    assert "DATASET_COLUMNS" in str(response.json())
    assert time.monotonic() - started < 5


def test_overlong_column_name_is_rejected_before_it_reaches_the_database():
    client, _ = make_client()
    response = upload_csv(client, b"a," + b"n" * 300 + b"\n1,2\n")
    assert response.status_code == 400
    assert "DATASET_COLUMN_NAME" in str(response.json())


def test_row_level_errors_are_capped():
    client, _ = make_client()
    content = b"a,t\n" + b"1,2,3\n" * 5000
    response = upload_csv(client, content)
    assert response.status_code == 400
    reported = response.json()["error"]["details"][0]["messages"]
    assert 1 <= len(reported) <= 20


@pytest.mark.parametrize("bad", [123, ["a"], {"x": 1}, True])
def test_non_string_target_column_is_a_400(bad):
    client, _ = make_client()
    dataset_id = upload_csv(client).json()["id"]
    response = client.patch(f"/api/v1/datasets/{dataset_id}", {"target_column": bad}, format="json")
    assert response.status_code == 400
    assert Dataset.objects.get(id=dataset_id).target_column == "species"


@pytest.mark.parametrize("bad", [[1, 2], "text", 7])
def test_non_object_json_body_is_a_400(bad):
    client, _ = make_client()
    dataset_id = upload_csv(client).json()["id"]
    assert client.patch(f"/api/v1/datasets/{dataset_id}", bad, format="json").status_code == 400
    assert client.post("/api/v1/compatibility-reports", bad, format="json").status_code == 400


@pytest.mark.parametrize("bad", [123, ["x"], {"a": 1}])
def test_non_string_report_ids_are_a_400(bad):
    client, _ = make_client()
    payload = {"model_id": bad, "dataset_id": bad}
    assert client.post("/api/v1/compatibility-reports", payload, format="json").status_code == 400


def test_non_string_target_column_in_upload_form_is_not_a_500():
    client, _ = make_client()
    response = upload_csv(client, target_column="  ")
    assert response.status_code == 201  # blank means "use the suggested target"
    assert response.json()["target_column"] == "species"
