"""End-to-end tenant management flow tests (E8, Journey J1, issue #104)."""

from app.auth import verify_access_token
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user
from tests.tenants.test_create import _create_tenant_payload


def test_super_admin_tenant_creation_list_and_detail_flow(
    client, override_authenticated_user, mock_owner_invite_email
):
    """Super admin creates a tenant, lists it, and retrieves its detail record."""
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    create_response = client.post(
        "/tenants",
        json=_create_tenant_payload(
            name="Flow Test Consultancy",
            slug="flow-test",
            owner_email="flow-owner@example.test",
        ),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    tenant_id = created["id"]

    list_response = client.get("/tenants")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == tenant_id
    assert listed[0]["slug"] == "flow-test"

    detail_response = client.get(f"/tenants/{tenant_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["name"] == "Flow Test Consultancy"
    assert detail["slug"] == "flow-test"

    mock_owner_invite_email.assert_called_once()
    assert mock_owner_invite_email.call_args.kwargs["to_email"] == "flow-owner@example.test"


def test_invited_owner_can_login_with_temporary_password(
    client, override_authenticated_user, mock_owner_invite_email
):
    """Owner invite provisions credentials the invited owner can use to sign in."""
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    create_response = client.post(
        "/tenants",
        json=_create_tenant_payload(
            slug="owner-login",
            owner_email="invited-owner@example.test",
        ),
    )
    assert create_response.status_code == 201

    temporary_password = mock_owner_invite_email.call_args.kwargs["temporary_password"]
    login_response = client.post(
        "/auth/login",
        json={
            "email": "invited-owner@example.test",
            "password": temporary_password,
        },
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["access_token"]
    assert body["refresh_token"]

    verified = verify_access_token(body["access_token"])
    assert verified.role == Role.CONSULTANCY_OWNER
    assert verified.tenant_id == create_response.json()["id"]
