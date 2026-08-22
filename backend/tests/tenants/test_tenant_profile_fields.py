"""E10 task #109 tests: tenant profile fields on the existing tenant API surface.

These tests exercise the *existing* ``POST /tenants`` / ``GET /tenants`` /
``GET /tenants/{id}`` endpoints to confirm they now expose the three
new tenant-profile fields that task #109 added:

* ``logo_url`` -- nullable; ``None`` for a freshly created tenant
  (the S3/MinIO upload lives behind the E10 task #111 endpoint, not here).
* ``brand_color`` -- nullable; ``None`` until the owner sets one via the
  E10 task #110 PATCH endpoint (out of scope for this issue).
* ``currency`` -- ISO 4217 3-letter code; defaults to ``"INR"`` because
  Requirements §1 names India as the home market.

The dedicated PATCH endpoint and the logo upload endpoint are NOT
covered here -- those are sibling tickets #110 and #111 and must not
be re-implemented by this issue ("no ticket, no code").
"""

from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user
from tests.tenants.test_create import _create_tenant_payload


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_create_tenant_response_exposes_brand_color_and_currency_defaults(
    client, override_authenticated_user
):
    """POST /tenants response surfaces the new branding fields with sensible defaults."""
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(
            name="Branding Consultancy",
            slug="branding",
            owner_email="owner@branding.test",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["logo_url"] is None
    assert body["brand_color"] is None
    assert body["currency"] == "INR"


def test_list_tenants_response_includes_branding_fields(
    client, db_session, override_authenticated_user
):
    """GET /tenants includes the new fields on every list entry."""
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    _create_tenant(db_session, name="Apex EduConsult", slug="apex-list")

    body = client.get("/tenants").json()
    assert len(body) == 1
    assert body[0]["logo_url"] is None
    assert body[0]["brand_color"] is None
    assert body[0]["currency"] == "INR"


def test_get_tenant_response_includes_branding_fields(
    client, db_session, override_authenticated_user
):
    """GET /tenants/{id} surfaces the branding fields too."""
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    tenant = _create_tenant(db_session, name="Detail Tenant", slug="detail-e10")

    body = client.get(f"/tenants/{tenant.id}").json()
    assert body["logo_url"] is None
    assert body["brand_color"] is None
    assert body["currency"] == "INR"


def test_tenant_currency_default_is_INR(db_session):
    """A tenant persisted without an explicit currency defaults to 'INR'."""
    tenant = Tenant(name="Defaults", slug="defaults-currency")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.currency == "INR"


def test_tenant_branding_fields_default_to_none(db_session):
    """``logo_url`` and ``brand_color`` are nullable and default to NULL."""
    tenant = Tenant(name="Defaults", slug="defaults-branding")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.logo_url is None
    assert tenant.brand_color is None