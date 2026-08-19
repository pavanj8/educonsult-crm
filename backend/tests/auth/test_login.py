import pytest

from app.auth import verify_access_token, verify_refresh_token
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
