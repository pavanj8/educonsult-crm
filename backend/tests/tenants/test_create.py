"""POST /tenants endpoint tests (E8, Journey J1, issue #100)."""

from app.auth import create_access_token
from app.rbac.roles import Role
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


def _create_tenant_payload(*, name: str = "Apex EduConsult", slug: str = "apex"):
    return {"name": name, "slug": slug}


def test_create_tenant_success_as_super_admin(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post("/tenants", json=_create_tenant_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["name"] == "Apex EduConsult"
    assert body["slug"] == "apex"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_create_tenant_success_with_real_jwt(client, db_session):
    password = "super-admin-password"
    make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        email="superadmin@tenants.test",
        password=password,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "superadmin@tenants.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.post(
        "/tenants",
        headers=make_auth_headers(access_token),
        json=_create_tenant_payload(name="Global Reach", slug="globalreach"),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Global Reach"
    assert response.json()["slug"] == "globalreach"


def test_create_tenant_normalizes_slug(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(name="North Star", slug="North-Star"),
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "north-star"


def test_create_tenant_rejects_unauthenticated_request(client):
    response = client.post("/tenants", json=_create_tenant_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_create_tenant_rejects_non_super_admin(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER))

    response = client.post("/tenants", json=_create_tenant_payload())

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_create_tenant_rejects_duplicate_slug(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    first = client.post("/tenants", json=_create_tenant_payload())
    assert first.status_code == 201

    duplicate = client.post(
        "/tenants",
        json=_create_tenant_payload(name="Another Consultancy", slug="apex"),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "A tenant with this slug already exists"


def test_create_tenant_rejects_invalid_slug(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(slug="invalid slug!"),
    )

    assert response.status_code == 422


def test_create_tenant_rejects_empty_name(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(name="   ", slug="valid-slug"),
    )

    assert response.status_code == 422


def test_create_tenant_rejects_invalid_access_token(client):
    response = client.post(
        "/tenants",
        headers=make_auth_headers("not-a-valid-jwt"),
        json=_create_tenant_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_create_tenant_rejects_non_super_admin_jwt(client, db_session):
    user = make_db_user(db_session, Role.COUNSELOR)
    token = create_access_token(make_authenticated_user(Role.COUNSELOR, user_id=user.id))

    response = client.post(
        "/tenants",
        headers=make_auth_headers(token),
        json=_create_tenant_payload(slug="counselor-attempt"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
