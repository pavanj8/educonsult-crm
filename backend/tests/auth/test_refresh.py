"""Token refresh endpoint tests (E5, Journey J44, issue #88)."""

import pytest

from app.auth import (
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user, make_db_user


def _login(client, email: str, password: str) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def test_refresh_success_returns_new_bearer_tokens(client, db_session):
    password = "refresh-password"
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@refresh.test",
        password=password,
    )
    login_body = _login(client, "counselor@refresh.test", password)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login_body["refresh_token"]},
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
def test_refresh_success_for_all_roles(client, db_session, role: Role):
    password = "role-refresh-password"
    email = f"{role.value}@refresh.test"
    user = make_db_user(db_session, role, email=email, password=password)
    login_body = _login(client, email, password)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login_body["refresh_token"]},
    )

    assert response.status_code == 200
    body = response.json()
    verified = verify_access_token(body["access_token"])
    assert verified.id == user.id
    assert verified.role == role


def test_refresh_rejects_expired_token(client, monkeypatch):
    monkeypatch.setenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "0")
    user = make_authenticated_user(Role.COUNSELOR)
    expired_refresh = create_refresh_token(user)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": expired_refresh},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Refresh token has expired"}


def test_refresh_rejects_invalid_token(client):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "not-a-valid-jwt"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


def test_refresh_rejects_access_token(client, db_session):
    password = "access-token-password"
    make_db_user(
        db_session,
        Role.RECEPTIONIST,
        email="receptionist@refresh.test",
        password=password,
    )
    login_body = _login(client, "receptionist@refresh.test", password)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login_body["access_token"]},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


def test_refresh_rejects_missing_refresh_token(client):
    response = client.post("/auth/refresh", json={})

    assert response.status_code == 422


def test_refresh_rejects_token_for_deleted_user(client):
    user = make_authenticated_user(Role.COUNSELOR, user_id=999_999)
    refresh_token = create_refresh_token(user)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


def test_refresh_returns_503_when_database_unavailable(client):
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    user = make_authenticated_user(Role.COUNSELOR)
    refresh_token = create_refresh_token(user)

    mock_session = MagicMock()
    mock_session.get.side_effect = OperationalError("stmt", {}, Exception("no such table"))

    def override_get_db():
        yield mock_session

    from app.db.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Authentication service is temporarily unavailable",
    }


def test_refresh_uses_current_user_record(client, db_session):
    password = "current-user-password"
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@current.test",
        password=password,
    )
    stale_user = make_authenticated_user(
        Role.COUNSELOR,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )
    stale_refresh = create_refresh_token(stale_user)

    user.role = Role.BRANCH_MANAGER
    db_session.commit()

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": stale_refresh},
    )

    assert response.status_code == 200
    verified = verify_access_token(response.json()["access_token"])
    assert verified.role == Role.BRANCH_MANAGER
