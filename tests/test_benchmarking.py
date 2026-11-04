"""M4 integration evidence for chart contracts, comparison guards and Appendix B exports."""

import uuid
from datetime import timedelta
from io import BytesIO

import pytest
from accounts.models import User
from django.utils import timezone
from evaluations.metrics.engine import evaluate
from evaluations.models import Evaluation
from evaluations.task_detection import resolve_task
from ingestion.models import Dataset, ModelArtifact
from pypdf import PdfReader
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

pytestmark = pytest.mark.django_db


def authenticated(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def owner():
    return User.objects.create_user(email="reports@example.org")


@pytest.fixture
def create_result(owner):
    def create(*, task="CLASSIFICATION", score=0, **changes):
        if task == "CLASSIFICATION":
            actual = ["a", "b", "c", "c"]
            payload = {
                "predictions": ["a", "b", "c", "b" if score else "c"],
                "classes": ["a", "b", "c"],
                "probabilities": [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, score, 1-score]],
            }
        else:
            actual = ["1.5", "2.5", "3.5"]
            payload = {"predictions": [1.5, 2.5, 3.5 + score]}
        result = evaluate(actual, payload, resolve_task(actual, task, max_classes=100))
        return Evaluation.objects.create(**{
            "owner": owner,
            "task_type": task,
            "status": "SUCCEEDED",
            "model_sha256": "a" * 64,
            "dataset_sha256": "b" * 64,
            "target_column": "label",
            "sandbox_image": "ml-evaluator-sandbox:1.0",
            "metrics_json": result.metrics,
            "charts_json": result.charts,
            "started_at": timezone.now() - timedelta(seconds=1),
            "finished_at": timezone.now(),
            **changes,
        })

    return create


def compare(client, rows):
    return client.post("/api/v1/comparisons", {"evaluation_ids": [str(row.id) for row in rows]})


@pytest.mark.parametrize("size, expected", [(1, 400), (2, 201), (3, 201), (5, 201), (6, 400)])
def test_comparison_limits_and_order(owner, create_result, size, expected):
    rows = [create_result(score=int(i != 1)) for i in range(size)]
    response = compare(authenticated(owner), rows)
    assert response.status_code == expected
    if expected == 201:
        data = response.json()
        assert [run["id"] for run in data["evaluations"]] == [str(row.id) for row in rows]
        assert data["best_per_metric"]["accuracy"] == str(rows[1].id)
        assert "confusion_matrix" not in data["best_per_metric"]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"dataset_sha256": "c" * 64}, "different datasets"),
        ({"task": "REGRESSION"}, "different task types"),
        ({"status": "RUNNING"}, "SUCCEEDED"),
        ({"dataset_sha256": ""}, "dataset checksum"),
    ],
)
def test_comparison_guards(owner, create_result, changes, message):
    response = compare(authenticated(owner), [create_result(), create_result(**changes)])
    assert response.status_code == 400
    assert message in str(response.json()["error"]["details"])


def test_duplicate_and_unknown_ids(owner, create_result):
    client = authenticated(owner)
    row = create_result()
    assert compare(client, [row, row]).status_code == 400
    response = client.post(
        "/api/v1/comparisons", {"evaluation_ids": [str(row.id), str(uuid.uuid4())]},
    )
    assert response.status_code == 404


def test_classification_chart_contract(owner, create_result):
    evaluation = create_result()
    data = authenticated(owner).get(f"/api/v1/evaluations/{evaluation.id}/charts").json()["charts"]
    assert data["labels"] == ["a", "b", "c"]
    assert data["confusion_matrix"] == [[1, 0, 0], [0, 1, 0], [0, 0, 2]]
    assert set(data["roc"]["curves"]) == {"a", "b", "c"}


def pdf_text(response):
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    reader = PdfReader(BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_evaluation_exports(owner, create_result):
    model = ModelArtifact.objects.create(
        owner=owner, original_filename="R&D <model>.onnx", extension=".onnx", size_bytes=400,
    )
    dataset = Dataset.objects.create(
        owner=owner, original_filename="observations.csv", size_bytes=900, row_count=3,
        columns=["a", "label"], target_column="label",
    )
    evaluation = create_result(task="REGRESSION", model_artifact=model, dataset=dataset)
    client = authenticated(owner)
    path = f"/api/v1/evaluations/{evaluation.id}/report"
    response = client.get(path + ".json")
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert response["Cache-Control"] == "private, no-store"
    body = response.json()
    assert body["schema_version"] == 1 and body["owner"]["email"] == owner.email
    row, = body["evaluations"]
    assert row["model"] == {
        "id": str(model.id), "filename": model.original_filename, "format": ".onnx",
        "size_bytes": 400, "sha256": "a" * 64,
    }
    assert row["dataset"]["rows"] == 3 and row["dataset"]["target_column"] == "label"
    assert row["dataset"]["sha256"] == "b" * 64 and row["duration_seconds"] >= 1
    assert row["metrics"]["rmse"] == 0
    assert row["charts"]["residual_histogram"]["counts"] == [3]
    text = pdf_text(client.get(path + ".pdf"))
    for value in ("R&D <model>.onnx", "observations.csv", "rmse", "Actual / predicted",
                  "Predicted / residual", "Residual / count", row["sandbox_image"]):
        assert value in text


def test_comparison_exports_and_deletion(owner, create_result):
    client = authenticated(owner)
    rows = [create_result(score=1), create_result()]
    data = compare(client, rows).json()
    path = f"/api/v1/comparisons/{data['id']}"
    assert client.get(path).json() == data
    assert client.get(path + "/report.json").json()["best_per_metric"] == data["best_per_metric"]
    text = pdf_text(client.get(path + "/report.pdf"))
    for value in ("(best)", "Confusion matrix", "ROC for a", *(str(row.id) for row in rows)):
        assert value in text
    rows[0].delete()
    assert client.get(path).status_code == 404
    assert client.get(path + "/report.pdf").status_code == 404


def test_reports_are_owner_only(owner, create_result):
    client = authenticated(owner)
    rows = [create_result(), create_result()]
    comparison = compare(client, rows).json()["id"]
    other = authenticated(User.objects.create_user(email="other@example.org"))
    assert compare(other, rows).status_code == 404
    for stem in (f"evaluations/{rows[0].id}", f"comparisons/{comparison}"):
        for extension in ("json", "pdf"):
            path = f"/api/v1/{stem}/report.{extension}"
            assert other.get(path).status_code == 404
            assert APIClient().get(path).status_code == 401
    queued = create_result(status="QUEUED")
    assert client.get(f"/api/v1/evaluations/{queued.id}/report.pdf").status_code == 409


def test_dashboard_shell_serves_only_known_assets():
    client = APIClient()
    for asset in ("", "/dashboard.css", "/dashboard.js"):
        response = client.get("/results" + asset)
        assert response.status_code == 200
        assert "object-src 'none'" in response["Content-Security-Policy"]
        response.close()
    assert client.get("/results/settings.py").status_code == 404
