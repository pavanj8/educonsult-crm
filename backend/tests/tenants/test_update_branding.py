"""PATCH /tenants/{id}/branding endpoint tests (E10, Journey J3, issue #110).

Covers the super-admin and consultancy-owner happy paths, partial updates,
field validation (logo URL, hex brand color, ISO currency), empty-payload
rejection, cross-tenant denial, and the standard 401/403/404 matrix.
"""

from datetime import datetime, timezone

import pytest

from app.auth import create_access_token
from app.models.tenant import Tenant
from app.rbac import Permission, Role, get_permissions_for_role
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user


def _create_tenant(db_session, *, name: str, slug: str, tenant_id: int | None = None) -> Tenant:
    now = datetime.now(timezone.utc)
    tenant = Tenant(
        name=name,
        slug=slug,
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _branding_payload(**overrides) -> dict[str, str | None]:
    payload: dict[str, str | None] = {
        "logo_url": "https://cdn.example.test/apex/logo.png",
        "brand_color": "#1A2B3C",
        "currency": "USD",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Permission model
# ---------------------------------------------------------------------------


def test_super_admin_has_tenant_update_permission() -> None:
    assert Permission.TENANT_UPDATE in get_permissions_for_role(Role.SUPER_ADMIN)


def test_consultancy_owner_has_tenant_update_permission() -> None:
    """Journey J3: Consultancy Owner updates their own tenant's branding."""
    assert Permission.TENANT_UPDATE in get_permissions_for_role(Role.CONSULTANCY_OWNER)


@pytest.mark.parametrize(
    "role",
    sorted(
        (role for role in Role if role not in {Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER}),
        key=lambda r: r.value,
    ),
)
def test_non_owner_roles_lack_tenant_update_permission(role: Role) -> None:
    assert Permission.TENANT_UPDATE not in get_permissions_for_role(role)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_update_branding_success_as_super_admin(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json=_branding_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == tenant.id
    assert body["logo_url"] == "https://cdn.example.test/apex/logo.png"
    assert body["brand_color"] == "#1A2B3C"
    assert body["currency"] == "USD"

    db_session.refresh(tenant)
    assert tenant.logo_url == "https://cdn.example.test/apex/logo.png"
    assert tenant.brand_color == "#1A2B3C"
    assert tenant.currency == "USD"


def test_update_branding_success_as_owner(client, db_session):
    """J3: The consultancy owner of the target tenant can patch their own branding."""
    password = "owner-password"
    tenant = _create_tenant(
        db_session, name="Apex EduConsult", slug="apex"
    )
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@apex.test",
        password=password,
        tenant_id=tenant.id,
        branch_id=None,
    )

    login_response = client.post(
        "/auth/login",
        json={"email": "owner@apex.test", "password": password},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        headers=make_auth_headers(access_token),
        json=_branding_payload(brand_color="#FF00FF"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["brand_color"] == "#FF00FF"
    assert body["logo_url"] == "https://cdn.example.test/apex/logo.png"
    assert body["currency"] == "USD"

    db_session.refresh(tenant)
    assert tenant.brand_color == "#FF00FF"


def test_update_branding_partial_fields(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"currency": "INR"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "INR"
    assert body["logo_url"] is None
    assert body["brand_color"] is None


def test_update_branding_normalizes_currency_case_and_whitespace(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"currency": "  inr "},
    )

    assert response.status_code == 200
    assert response.json()["currency"] == "INR"


def test_update_branding_normalizes_logo_url_whitespace(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"logo_url": "  https://cdn.example.test/apex/logo.png  "},
    )

    assert response.status_code == 200
    assert response.json()["logo_url"] == "https://cdn.example.test/apex/logo.png"


def test_update_branding_accepts_lowercase_hex(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"brand_color": "#abcdef"},
    )

    assert response.status_code == 200
    assert response.json()["brand_color"] == "#abcdef"


# ---------------------------------------------------------------------------
# Empty payload / validation
# ---------------------------------------------------------------------------


def test_update_branding_rejects_empty_payload(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(f"/tenants/{tenant.id}/branding", json={})

    assert response.status_code == 422
    assert response.json()["detail"] == "At least one branding field must be provided"


def test_update_branding_rejects_invalid_logo_url_scheme(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"logo_url": "ftp://example.test/logo.png"},
    )

    assert response.status_code == 422


def test_update_branding_rejects_malformed_brand_color(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"brand_color": "not-a-color"},
    )

    assert response.status_code == 422


def test_update_branding_rejects_short_hex_brand_color(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"brand_color": "#FFF"},
    )

    assert response.status_code == 422


def test_update_branding_rejects_invalid_currency_code(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"currency": "DOLLARS"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Auth / access matrix
# ---------------------------------------------------------------------------


def test_update_branding_returns_404_for_unknown_id(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.patch("/tenants/99999/branding", json={"currency": "USD"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_update_branding_rejects_unauthenticated_request(client, db_session):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"currency": "USD"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_update_branding_rejects_role_without_permission(
    client, db_session, override_authenticated_user
):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    override_authenticated_user(make_authenticated_user(Role.BRANCH_MANAGER, tenant_id=tenant.id))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        json={"currency": "USD"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_update_branding_rejects_cross_tenant_owner(client, db_session):
    """An owner of tenant A must not edit tenant B's branding (404, not 403)."""
    password = "owner-password"
    make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@other.test",
        password=password,
        tenant_id=7,
        branch_id=None,
    )
    target_tenant = _create_tenant(
        db_session, name="Foreign Tenant", slug="foreign"
    )
    assert target_tenant.id != 7

    login_response = client.post(
        "/auth/login",
        json={"email": "owner@other.test", "password": password},
    )
    access_token = login_response.json()["access_token"]

    response = client.patch(
        f"/tenants/{target_tenant.id}/branding",
        headers=make_auth_headers(access_token),
        json={"currency": "USD"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_update_branding_rejects_non_owner_jwt(client, db_session):
    user = make_db_user(db_session, Role.COUNSELOR, tenant_id=1)
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    token = create_access_token(make_authenticated_user(Role.COUNSELOR, user_id=user.id))

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        headers=make_auth_headers(token),
        json={"currency": "USD"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_update_branding_rejects_invalid_access_token(client, db_session):
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")

    response = client.patch(
        f"/tenants/{tenant.id}/branding",
        headers=make_auth_headers("not-a-valid-jwt"),
        json={"currency": "USD"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"