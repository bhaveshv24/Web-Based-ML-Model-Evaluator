"""Final integration regressions for shared access, administration and safe deletion."""

import secrets
from pathlib import Path

import pytest
from accounts.models import AuditLog, User
from django.core.files.base import ContentFile
from django.db import transaction
from evaluations.models import Evaluation
from ingestion.models import Dataset, ModelArtifact
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from workspaces.models import Workspace, WorkspaceMembership

pytestmark = pytest.mark.django_db(transaction=True)


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def test_available_workspaces_include_memberships_without_granting_management():
    owner = User.objects.create_user(email="member@example.org")
    evaluator = User.objects.create_user(email="evaluator@example.org", role="EVALUATOR")
    workspace = Workspace.objects.create(name="Shared", evaluator=evaluator)
    Workspace.objects.create(name="Private", evaluator=evaluator)
    WorkspaceMembership.objects.create(workspace=workspace, user=owner)
    client = client_for(owner)
    assert [row["id"] for row in client.get("/api/v1/workspaces/available").json()] == [
        str(workspace.pk)
    ]
    assert client.post("/api/v1/workspaces", {"name": "No"}).status_code == 403


def test_admin_lists_accounts_and_audit_without_exposing_password_hashes():
    admin = User.objects.create_user(email="admin@example.org", role="ADMIN")
    owner = User.objects.create_user(email="student@example.org")
    AuditLog.objects.create(event="TEST_EVENT", user=owner)
    client = client_for(admin)
    data = client.get("/api/v1/admin/users?q=student").json()
    assert [row["email"] for row in data["results"]] == [owner.email]
    assert "password" not in data["results"][0]
    assert client.get("/api/v1/admin/audit").json()["results"][0]["event"] == "TEST_EVENT"
    for path in ("/api/v1/admin/users", "/api/v1/admin/audit"):
        assert client_for(owner).get(path).status_code == 403
        assert APIClient().get(path).status_code == 401


def test_logout_cannot_blacklist_another_accounts_refresh_token():
    owner = User.objects.create_user(email="owner@example.org")
    other = User.objects.create_user(email="other@example.org")
    token = str(RefreshToken.for_user(other))
    assert client_for(owner).post("/api/v1/auth/logout", {"refresh": token}).status_code == 401
    assert str(RefreshToken(token)) == token


def test_delete_keeps_shared_inputs_until_last_evaluation_is_deleted(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(email="owner@example.org")
    model = ModelArtifact.objects.create(
        owner=owner, original_filename="model.pkl", extension=".pkl", size_bytes=2, sha256="a" * 64
    )
    model.file.save("model.pkl", ContentFile(b"xx"))
    dataset = Dataset.objects.create(
        owner=owner, original_filename="data.csv", size_bytes=8, sha256="b" * 64,
        columns=["x", "y"], row_count=1, target_column="y",
    )
    dataset.file.save("data.csv", ContentFile(b"x,y\n1,2\n"))
    paths = [Path(model.file.path), Path(dataset.file.path)]
    first = Evaluation.objects.create(owner=owner, model_artifact=model, dataset=dataset)
    last = Evaluation.objects.create(owner=owner, model_artifact=model, dataset=dataset)
    client = client_for(owner)
    assert client.delete(f"/api/v1/evaluations/{first.id}").status_code == 204
    assert all(path.exists() for path in paths)
    assert client.delete(f"/api/v1/evaluations/{last.id}").status_code == 204
    assert not any(path.exists() for path in paths)
    assert not ModelArtifact.objects.exists() and not Dataset.objects.exists()


def test_rolled_back_upload_deletion_keeps_the_stored_file(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(email="rollback@example.org")
    model = ModelArtifact.objects.create(
        owner=owner, original_filename="model.pkl", extension=".pkl", size_bytes=2, sha256="a" * 64
    )
    model.file.save("model.pkl", ContentFile(b"xx"))
    pk, path = model.pk, Path(model.file.path)
    with pytest.raises(RuntimeError), transaction.atomic():
        model.delete()
        raise RuntimeError("force rollback")
    assert ModelArtifact.objects.filter(pk=pk).exists()
    assert path.read_bytes() == b"xx"


def test_registration_race_returns_validation_error(monkeypatch):
    from accounts.serializers import RegisterSerializer
    from django.db import IntegrityError
    from rest_framework.exceptions import ValidationError

    def duplicate(**kwargs):
        raise IntegrityError("duplicate email")

    monkeypatch.setattr(User.objects, "create_user", duplicate)
    with pytest.raises(ValidationError) as error:
        RegisterSerializer().create({
            "email": "race@example.org", "password": secrets.token_urlsafe(16)
        })
    assert "email" in error.value.detail
