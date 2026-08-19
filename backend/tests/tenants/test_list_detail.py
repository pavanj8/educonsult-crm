"""GET /tenants list and detail endpoint tests (E8, Journey J1, issue #101)."""

from app.auth import create_access_token
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_list_tenants_success_as_super_admin(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    first = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    second = _create_tenant(db_session, name="Global Reach", slug="globalreach")

    response = client.get("/tenants")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == first.id
    assert body[0]["name"] == "Apex EduConsult"
    assert body[0]["slug"] == "apex"
    assert body[1]["id"] == second.id
    assert body[1]["name"] == "Global Reach"
    assert body[1]["slug"] == "globalreach"


def test_list_tenants_returns_empty_list(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.get("/tenants")

    assert response.status_code == 200
    assert response.json() == []


def test_list_tenants_success_with_real_jwt(client, db_session):
    password = "super-admin-password"
    make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        email="superadmin@list.test",
        password=password,
    )
    _create_tenant(db_session, name="Listed Tenant", slug="listed")
    login_response = client.post(
        "/auth/login",
        json={"email": "superadmin@list.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.get("/tenants", headers=make_auth_headers(access_token))

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["slug"] == "listed"


def test_list_tenants_rejects_unauthenticated_request(client):
    response = client.get("/tenants")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_list_tenants_rejects_non_super_admin(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER))

    response = client.get("/tenants")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_list_tenants_rejects_non_super_admin_jwt(client, db_session):
    user = make_db_user(db_session, Role.COUNSELOR)
    token = create_access_token(make_authenticated_user(Role.COUNSELOR, user_id=user.id))

    response = client.get("/tenants", headers=make_auth_headers(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_get_tenant_success_as_super_admin(client, db_session, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    tenant = _create_tenant(db_session, name="Detail Tenant", slug="detail")

    response = client.get(f"/tenants/{tenant.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == tenant.id
    assert body["name"] == "Detail Tenant"
    assert body["slug"] == "detail"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_get_tenant_success_with_real_jwt(client, db_session):
    password = "super-admin-password"
    make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        email="superadmin@detail.test",
        password=password,
    )
    tenant = _create_tenant(db_session, name="JWT Tenant", slug="jwt-tenant")
    login_response = client.post(
        "/auth/login",
        json={"email": "superadmin@detail.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.get(f"/tenants/{tenant.id}", headers=make_auth_headers(access_token))

    assert response.status_code == 200
    assert response.json()["slug"] == "jwt-tenant"


def test_get_tenant_returns_404_for_unknown_id(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.get("/tenants/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_get_tenant_rejects_unauthenticated_request(client, db_session):
    tenant = _create_tenant(db_session, name="Protected", slug="protected")

    response = client.get(f"/tenants/{tenant.id}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_get_tenant_rejects_non_super_admin(client, db_session, override_authenticated_user):
    tenant = _create_tenant(db_session, name="Protected", slug="protected-owner")
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER))

    response = client.get(f"/tenants/{tenant.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_get_tenant_rejects_non_super_admin_jwt(client, db_session):
    tenant = _create_tenant(db_session, name="Protected", slug="protected-counselor")
    user = make_db_user(db_session, Role.COUNSELOR)
    token = create_access_token(make_authenticated_user(Role.COUNSELOR, user_id=user.id))

    response = client.get(f"/tenants/{tenant.id}", headers=make_auth_headers(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
