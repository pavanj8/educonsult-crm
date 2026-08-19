"""Login endpoint tests (E5, Journey J44, issue #88)."""

import pytest

from app.auth import verify_access_token, verify_refresh_token
from app.db.database import get_db
from app.main import app
from app.rbac.roles import Role
from tests.factories.users import make_db_user


def test_login_success_returns_bearer_tokens(client, db_session):
    password = "correct-password"
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=password,
    )

    response = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert isinstance(body["refresh_token"], str)

    verified_access = verify_access_token(body["access_token"])
    assert verified_access.id == user.id
    assert verified_access.role == Role.COUNSELOR
    assert verified_access.tenant_id == user.tenant_id
    assert verified_access.branch_id == user.branch_id

    verified_refresh = verify_refresh_token(body["refresh_token"])
    assert verified_refresh.id == user.id
    assert verified_refresh.role == Role.COUNSELOR


@pytest.mark.parametrize("role", list(Role))
def test_login_success_for_all_roles(client, db_session, role: Role):
    password = "role-password"
    email = f"{role.value}@login.test"
    user = make_db_user(db_session, role, email=email, password=password)

    response = client.post("/auth/login", json={"email": email, "password": password})

    assert response.status_code == 200
    body = response.json()
    verified = verify_access_token(body["access_token"])
    assert verified.id == user.id
    assert verified.role == role


def test_login_matches_email_case_insensitively(client, db_session):
    password = "case-password"
    make_db_user(
        db_session,
        Role.RECEPTIONIST,
        email="staff@example.test",
        password=password,
    )

    response = client.post(
        "/auth/login",
        json={"email": "Staff@Example.TEST", "password": password},
    )

    assert response.status_code == 200


def test_login_rejects_wrong_password(client, db_session):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password="correct-password",
    )

    response = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_login_rejects_unknown_email(client, db_session):
    response = client.post(
        "/auth/login",
        json={"email": "missing@example.test", "password": "any-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_login_rejects_missing_credentials(client):
    response = client.post("/auth/login", json={"email": "user@example.test"})

    assert response.status_code == 422


def test_login_rejects_missing_email(client):
    response = client.post("/auth/login", json={"password": "any-password"})

    assert response.status_code == 422


def test_login_rejects_empty_email(client):
    response = client.post(
        "/auth/login",
        json={"email": "", "password": "any-password"},
    )

    assert response.status_code == 422


def test_login_rejects_empty_password(client):
    response = client.post(
        "/auth/login",
        json={"email": "user@example.test", "password": ""},
    )

    assert response.status_code == 422


def test_login_trims_email_whitespace(client, db_session):
    password = "trim-password"
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=password,
    )

    response = client.post(
        "/auth/login",
        json={"email": "  counselor@example.test  ", "password": password},
    )

    assert response.status_code == 200


def test_login_returns_503_when_database_unavailable(client):
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    mock_session = MagicMock()
    mock_session.query.side_effect = OperationalError("stmt", {}, Exception("no such table"))

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "WrongPass1!"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Authentication service is temporarily unavailable",
    }


def test_health_remains_available_after_failed_login(client):
    client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPass1!"},
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
