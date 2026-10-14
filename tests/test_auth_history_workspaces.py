"""M1 integration and security tests mapped to the approved STP."""

import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from accounts.models import AuditLog, User
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import override_settings
from evaluations.models import Evaluation, EvaluationArtifact, Report
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from workspaces.models import Workspace, WorkspaceMembership

pytestmark = pytest.mark.django_db

TEST_PASSWORD = secrets.token_urlsafe(16) + "Aa1!"
WRONG_PASSWORD = secrets.token_urlsafe(16) + "Bb2!"


def create_user(email="user@pes.edu", role=User.Role.USER):
    return User.objects.create_user(email=email, password=TEST_PASSWORD, role=role)


def authorize(client, user):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")


def test_registration_rejects_weak_password_and_hashes_strong_password():
    client = APIClient()
    weak = client.post("/api/v1/auth/register", {"email": "a@pes.edu", "password": "abc123"})
    assert weak.status_code == 400

    response = client.post(
        "/api/v1/auth/register",
        {"email": "Atharva@PES.EDU", "password": TEST_PASSWORD},
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(email="atharva@pes.edu")
    assert user.role == User.Role.USER
    assert user.password != TEST_PASSWORD
    assert user.check_password(TEST_PASSWORD)


def test_duplicate_email_is_rejected_without_account_details():
    create_user("duplicate@pes.edu")
    response = APIClient().post(
        "/api/v1/auth/register",
        {"email": "DUPLICATE@pes.edu", "password": TEST_PASSWORD},
        format="json",
    )
    assert response.status_code in {400, 409}
    assert User.objects.filter(email="duplicate@pes.edu").count() == 1


def test_login_issues_role_token_with_required_lifetimes():
    create_user(role=User.Role.EVALUATOR)
    response = APIClient().post(
        "/api/v1/auth/login",
        {"email": "user@pes.edu", "password": TEST_PASSWORD},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["role"] == User.Role.EVALUATOR

    access = AccessToken(response.data["access"])
    refresh = RefreshToken(response.data["refresh"])
    assert access["role"] == User.Role.EVALUATOR
    assert access["exp"] - access["iat"] == 15 * 60
    assert refresh["exp"] - refresh["iat"] == 7 * 24 * 60 * 60


def test_wrong_password_is_generic_and_audited():
    create_user()
    response = APIClient().post(
        "/api/v1/auth/login",
        {"email": "user@pes.edu", "password": WRONG_PASSWORD},
        format="json",
    )
    assert response.status_code == 401
    assert "password" not in str(response.data).lower()
    assert AuditLog.objects.filter(event="LOGIN_FAILED", actor_email="user@pes.edu").exists()


def test_refresh_rotates_and_blacklists_old_token():
    user = create_user()
    original = str(RefreshToken.for_user(user))
    client = APIClient()
    first = client.post("/api/v1/auth/token/refresh", {"refresh": original}, format="json")
    assert first.status_code == 200
    assert first.data["refresh"] != original
    reused = client.post("/api/v1/auth/token/refresh", {"refresh": original}, format="json")
    assert reused.status_code == 401


def test_logout_revokes_refresh_token():
    user = create_user()
    refresh = str(RefreshToken.for_user(user))
    client = APIClient()
    authorize(client, user)
    logout = client.post("/api/v1/auth/logout", {"refresh": refresh}, format="json")
    assert logout.status_code == 204
    assert (
        APIClient()
        .post("/api/v1/auth/token/refresh", {"refresh": refresh}, format="json")
        .status_code
        == 401
    )


def test_login_is_limited_to_five_attempts_per_ip_and_email():
    cache.clear()
    client = APIClient()
    payload = {"email": "rate-limit@pes.edu", "password": WRONG_PASSWORD}
    responses = [client.post("/api/v1/auth/login", payload, format="json") for _ in range(6)]
    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429


def test_history_is_owned_newest_first_and_filterable():
    owner = create_user()
    other = create_user("other@pes.edu")
    older = Evaluation.objects.create(
        owner=owner,
        status=Evaluation.Status.FAILED,
        task_type=Evaluation.TaskType.CLASSIFICATION,
    )
    newer = Evaluation.objects.create(
        owner=owner,
        status=Evaluation.Status.SUCCEEDED,
        task_type=Evaluation.TaskType.REGRESSION,
    )
    Evaluation.objects.create(
        owner=other,
        status=Evaluation.Status.FAILED,
        task_type=Evaluation.TaskType.CLASSIFICATION,
    )

    client = APIClient()
    authorize(client, owner)
    history = client.get("/api/v1/evaluations")
    assert history.status_code == 200
    assert [item["id"] for item in history.data["results"]] == [str(newer.id), str(older.id)]

    filtered = client.get("/api/v1/evaluations?status=FAILED&task_type=CLASSIFICATION")
    assert [item["id"] for item in filtered.data["results"]] == [str(older.id)]


def test_history_date_filter_and_invalid_filter():
    owner = create_user()
    evaluation = Evaluation.objects.create(
        owner=owner,
        status=Evaluation.Status.SUCCEEDED,
        task_type=Evaluation.TaskType.CLASSIFICATION,
    )
    client = APIClient()
    authorize(client, owner)
    start = datetime.now(UTC) - timedelta(minutes=1)
    response = client.get("/api/v1/evaluations", {"from": start.isoformat()})
    assert [item["id"] for item in response.data["results"]] == [str(evaluation.id)]
    assert client.get("/api/v1/evaluations?status=NOT_REAL").status_code == 400


def test_history_page_size_is_at_most_twenty():
    owner = create_user()
    Evaluation.objects.bulk_create(
        [
            Evaluation(
                owner=owner,
                status=Evaluation.Status.QUEUED,
                task_type=Evaluation.TaskType.CLASSIFICATION,
            )
            for _ in range(21)
        ]
    )
    client = APIClient()
    authorize(client, owner)
    response = client.get("/api/v1/evaluations")
    assert response.data["count"] == 21
    assert len(response.data["results"]) == 20


def test_non_owner_receives_404_for_detail_and_delete():
    owner = create_user()
    other = create_user("other@pes.edu")
    evaluation = Evaluation.objects.create(
        owner=owner,
        status=Evaluation.Status.QUEUED,
        task_type=Evaluation.TaskType.CLASSIFICATION,
    )
    client = APIClient()
    authorize(client, other)
    assert client.get(f"/api/v1/evaluations/{evaluation.id}").status_code == 404
    assert client.delete(f"/api/v1/evaluations/{evaluation.id}").status_code == 404
    assert Evaluation.objects.filter(id=evaluation.id).exists()


def test_deleting_own_evaluation_removes_rows_and_files(tmp_path):
    owner = create_user()
    evaluation = Evaluation.objects.create(
        owner=owner,
        status=Evaluation.Status.SUCCEEDED,
        task_type=Evaluation.TaskType.REGRESSION,
    )
    with override_settings(MEDIA_ROOT=tmp_path):
        artifact = EvaluationArtifact.objects.create(evaluation=evaluation)
        artifact.file.save("model.bin", ContentFile(b"model"), save=True)
        report = Report.objects.create(evaluation=evaluation, format=Report.Format.JSON)
        report.file.save("report.json", ContentFile(b"{}"), save=True)
        paths = [Path(artifact.file.path), Path(report.file.path)]

        client = APIClient()
        authorize(client, owner)
        assert client.delete(f"/api/v1/evaluations/{evaluation.id}").status_code == 204
        assert not Evaluation.objects.filter(id=evaluation.id).exists()
        assert not EvaluationArtifact.objects.exists()
        assert not Report.objects.exists()
        assert not any(path.exists() for path in paths)


def test_user_cannot_manage_workspaces_and_denial_is_audited():
    user = create_user()
    client = APIClient()
    authorize(client, user)
    response = client.post("/api/v1/workspaces", {"name": "ML Lab"}, format="json")
    assert response.status_code == 403
    assert AuditLog.objects.filter(event="AUTHORIZATION_DENIED", user=user).exists()


def test_evaluator_can_create_workspace_add_member_and_view_only_its_evaluations():
    evaluator = create_user("evaluator@pes.edu", User.Role.EVALUATOR)
    student = create_user("student@pes.edu")
    outsider = create_user("outsider@pes.edu")
    client = APIClient()
    authorize(client, evaluator)

    created = client.post("/api/v1/workspaces", {"name": "SE ML Lab"}, format="json")
    assert created.status_code == 201
    workspace = Workspace.objects.get(id=created.data["id"])

    member = client.post(
        f"/api/v1/workspaces/{workspace.id}/members",
        {"email": "student@pes.edu"},
        format="json",
    )
    assert member.status_code == 201
    assert WorkspaceMembership.objects.filter(workspace=workspace, user=student).exists()

    included = Evaluation.objects.create(
        owner=student,
        workspace=workspace,
        status=Evaluation.Status.SUCCEEDED,
        task_type=Evaluation.TaskType.CLASSIFICATION,
    )
    Evaluation.objects.create(
        owner=outsider,
        workspace=workspace,
        status=Evaluation.Status.SUCCEEDED,
        task_type=Evaluation.TaskType.CLASSIFICATION,
    )
    visible = client.get(f"/api/v1/workspaces/{workspace.id}/evaluations")
    assert visible.status_code == 200
    assert [item["id"] for item in visible.data["results"]] == [str(included.id)]


def test_evaluator_cannot_manage_another_evaluators_workspace():
    owner = create_user("owner@pes.edu", User.Role.EVALUATOR)
    other = create_user("other@pes.edu", User.Role.EVALUATOR)
    student = create_user("student@pes.edu")
    workspace = Workspace.objects.create(name="Private course", evaluator=owner)
    client = APIClient()
    authorize(client, other)
    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/members",
        {"email": student.email},
        format="json",
    )
    assert response.status_code == 404
