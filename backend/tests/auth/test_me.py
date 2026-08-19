from app.auth import create_access_token
from app.rbac.roles import Role
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


def test_me_returns_authenticated_user_profile(client, db_session):
    password = "me-password"
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@me.test",
        password=password,
    )

    login_response = client.post(
        "/auth/login",
        json={"email": "counselor@me.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.get("/auth/me", headers=make_auth_headers(access_token))

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": "counselor@me.test",
        "role": "counselor",
        "tenant_id": user.tenant_id,
        "branch_id": user.branch_id,
    }


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
