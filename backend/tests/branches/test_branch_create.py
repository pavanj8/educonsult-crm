"""POST /branches endpoint tests (E11, Journey J4, issue #115)."""

from app.auth import create_access_token
from app.rbac.roles import Role
from tests.branches.helpers import make_branch_payload
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


def test_create_branch_success_as_owner(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER))

    response = client.post("/branches", json=make_branch_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["tenant_id"] == 1
    assert body["name"] == "Mumbai HQ"
    assert body["city"] == "Mumbai"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_create_branch_success_with_real_jwt(client, db_session):
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@branches.test",
        password=password,
        tenant_id=1,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "owner@branches.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.post(
        "/branches",
        headers=make_auth_headers(access_token),
        json=make_branch_payload(name="Delhi Center", city="Delhi"),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Delhi Center"
    assert response.json()["city"] == "Delhi"
    assert response.json()["tenant_id"] == 1


def test_create_branch_strips_whitespace(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER))

    response = client.post(
        "/branches",
        json={"name": "  Pune Office  ", "city": "  Pune  "},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Pune Office"
    assert response.json()["city"] == "Pune"


def test_create_branch_rejects_unauthenticated_request(client):
    response = client.post("/branches", json=make_branch_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_create_branch_rejects_non_owner(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.BRANCH_MANAGER))

    response = client.post("/branches", json=make_branch_payload())

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_create_branch_rejects_empty_name(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER))

    response = client.post(
        "/branches",
        json=make_branch_payload(name="   "),
    )

    assert response.status_code == 422


def test_create_branch_rejects_invalid_access_token(client):
    response = client.post(
        "/branches",
        headers=make_auth_headers("not-a-valid-jwt"),
        json=make_branch_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_create_branch_rejects_non_owner_jwt(client, db_session):
    user = make_db_user(db_session, Role.COUNSELOR)
    token = create_access_token(make_authenticated_user(Role.COUNSELOR, user_id=user.id))

    response = client.post(
        "/branches",
        headers=make_auth_headers(token),
        json=make_branch_payload(name="Counselor Attempt"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
