"""Owner invite email tests for POST /tenants (E8, Journey J1, issue #102)."""

from sqlalchemy import func

from app.auth.password import verify_password
from app.email.service import EmailDeliveryError
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user, make_db_user
from tests.tenants.test_create import _create_tenant_payload


def test_create_tenant_sends_owner_invite_email(
    client, override_authenticated_user, mock_owner_invite_email
):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post("/tenants", json=_create_tenant_payload())

    assert response.status_code == 201
    mock_owner_invite_email.assert_called_once()
    call_kwargs = mock_owner_invite_email.call_args.kwargs
    assert call_kwargs["to_email"] == "owner@apex.test"
    assert call_kwargs["tenant_name"] == "Apex EduConsult"
    assert call_kwargs["temporary_password"]


def test_create_tenant_creates_consultancy_owner_user(
    client, override_authenticated_user, db_session, mock_owner_invite_email
):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(owner_email="owner@new-tenant.test"),
    )

    assert response.status_code == 201
    tenant_id = response.json()["id"]
    owner = (
        db_session.query(User)
        .filter(func.lower(User.email) == "owner@new-tenant.test")
        .one()
    )
    assert owner.role == Role.CONSULTANCY_OWNER
    assert owner.tenant_id == tenant_id
    assert owner.branch_id is None

    temp_password = mock_owner_invite_email.call_args.kwargs["temporary_password"]
    assert verify_password(temp_password, owner.password_hash)


def test_create_tenant_normalizes_owner_email(
    client, override_authenticated_user, db_session, mock_owner_invite_email
):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(
            slug="normalized-owner",
            owner_email="  Owner@Example.COM  ",
        ),
    )

    assert response.status_code == 201
    mock_owner_invite_email.assert_called_once()
    assert mock_owner_invite_email.call_args.kwargs["to_email"] == "owner@example.com"
    owner = db_session.query(User).filter(User.email == "owner@example.com").one()
    assert owner.role == Role.CONSULTANCY_OWNER


def test_create_tenant_rejects_duplicate_owner_email(
    client, override_authenticated_user, db_session, mock_owner_invite_email
):
    make_db_user(db_session, Role.COUNSELOR, email="existing@example.test")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(
            slug="duplicate-owner",
            owner_email="existing@example.test",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A user with this email already exists"
    mock_owner_invite_email.assert_not_called()
    assert db_session.query(Tenant).count() == 0


def test_create_tenant_rejects_invalid_owner_email(client, override_authenticated_user):
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(owner_email="not-an-email"),
    )

    assert response.status_code == 422


def test_create_tenant_rolls_back_when_invite_email_fails(
    client, override_authenticated_user, db_session, mock_owner_invite_email
):
    mock_owner_invite_email.side_effect = EmailDeliveryError("SMTP unavailable")
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(slug="email-failure"),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to send owner invite email"
    assert db_session.query(Tenant).count() == 0
    assert db_session.query(User).count() == 0
