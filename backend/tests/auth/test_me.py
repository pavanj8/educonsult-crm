<<<<<<< HEAD
import pytest

from app.auth import create_access_token
=======
"""Authenticated session (/auth/me) token handling tests (E5, Journey J44, issue #88)."""

from app.auth import create_access_token, create_refresh_token
>>>>>>> origin/main
from app.rbac.roles import Role
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


<<<<<<< HEAD
def _login(client, email: str, password: str) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def test_me_success_returns_user_profile(client, db_session):
=======
def test_me_returns_authenticated_user_profile(client, db_session):
>>>>>>> origin/main
    password = "me-password"
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@me.test",
        password=password,
    )
<<<<<<< HEAD
    login_body = _login(client, "counselor@me.test", password)

    response = client.get("/auth/me", headers=make_auth_headers(login_body["access_token"]))
=======

    login_response = client.post(
        "/auth/login",
        json={"email": "counselor@me.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.get("/auth/me", headers=make_auth_headers(access_token))
>>>>>>> origin/main

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": "counselor@me.test",
        "role": "counselor",
        "tenant_id": user.tenant_id,
        "branch_id": user.branch_id,
    }


<<<<<<< HEAD
@pytest.mark.parametrize("role", list(Role))
def test_me_success_for_all_roles(client, db_session, role: Role):
    password = "role-me-password"
    email = f"{role.value}@me.test"
    user = make_db_user(db_session, role, email=email, password=password)
    login_body = _login(client, email, password)

    response = client.get("/auth/me", headers=make_auth_headers(login_body["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == email
    assert body["role"] == role.value
    assert body["tenant_id"] == user.tenant_id
    assert body["branch_id"] == user.branch_id


def test_me_rejects_missing_authorization(client):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_me_rejects_invalid_token(client):
    response = client.get("/auth/me", headers=make_auth_headers("not-a-valid-jwt"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}


def test_me_rejects_expired_token(client, monkeypatch):
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "0")
    user = make_authenticated_user(Role.COUNSELOR)
    expired_access = create_access_token(user)

    response = client.get("/auth/me", headers=make_auth_headers(expired_access))

    assert response.status_code == 401
    assert response.json() == {"detail": "Access token has expired"}


def test_me_rejects_refresh_token(client, db_session):
    password = "refresh-token-password"
    make_db_user(
        db_session,
        Role.RECEPTIONIST,
        email="receptionist@me.test",
        password=password,
    )
    login_body = _login(client, "receptionist@me.test", password)

    response = client.get(
        "/auth/me",
        headers=make_auth_headers(login_body["refresh_token"]),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}


def test_me_rejects_token_for_deleted_user(client):
    user = make_authenticated_user(Role.COUNSELOR, user_id=999_999)
    access_token = create_access_token(user)

    response = client.get("/auth/me", headers=make_auth_headers(access_token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token"}


def test_me_uses_current_user_record(client, db_session):
    password = "current-user-password"
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@current-me.test",
        password=password,
    )
    stale_user = make_authenticated_user(
        Role.COUNSELOR,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )
    stale_access = create_access_token(stale_user)

    user.role = Role.BRANCH_MANAGER
    user.email = "updated@current-me.test"
    db_session.commit()

    response = client.get("/auth/me", headers=make_auth_headers(stale_access))

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": "updated@current-me.test",
        "role": "branch_manager",
        "tenant_id": user.tenant_id,
        "branch_id": user.branch_id,
    }
=======
def test_me_rejects_unauthenticated_request(client):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_rejects_invalid_access_token(client):
    response = client.get("/auth/me", headers=make_auth_headers("not-a-valid-jwt"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_me_rejects_expired_access_token(client, monkeypatch):
    from datetime import timedelta

    import app.auth.jwt as jwt_module

    user = make_authenticated_user(Role.STUDENT, user_id=42)
    monkeypatch.setattr(jwt_module, "access_token_lifetime", lambda: timedelta(seconds=-1))
    expired_token = create_access_token(user)

    response = client.get("/auth/me", headers=make_auth_headers(expired_token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token has expired"


def test_me_rejects_when_user_record_missing(client, db_session):
    user = make_authenticated_user(Role.RECEPTIONIST, user_id=999_999)
    token = create_access_token(user)

    response = client.get("/auth/me", headers=make_auth_headers(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_rejects_refresh_token_as_bearer(client):
    user = make_authenticated_user(Role.COUNSELOR)
    refresh_token = create_refresh_token(user)

    response = client.get("/auth/me", headers=make_auth_headers(refresh_token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"
>>>>>>> origin/main
