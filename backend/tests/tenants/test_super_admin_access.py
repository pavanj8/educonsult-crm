"""Super-admin-only access matrix for tenant endpoints (E8, Journey J1, issue #104)."""

import pytest

from app.models.tenant import Tenant
from app.rbac import Permission, Role, get_permissions_for_role
from tests.factories.users import make_authenticated_user
from tests.tenants.test_create import _create_tenant_payload

# Every tenant-scoped role must be denied platform tenant management (Requirements §1).
_NON_SUPER_ADMIN_ROLES = frozenset(role for role in Role if role is not Role.SUPER_ADMIN)

_TENANT_PERMISSIONS = frozenset({Permission.TENANT_CREATE, Permission.TENANT_READ})


@pytest.mark.parametrize("role", sorted(_NON_SUPER_ADMIN_ROLES, key=lambda r: r.value))
def test_non_super_admin_roles_lack_tenant_permissions(role: Role) -> None:
    perms = get_permissions_for_role(role)
    assert _TENANT_PERMISSIONS.isdisjoint(perms)


@pytest.mark.parametrize("role", sorted(_NON_SUPER_ADMIN_ROLES, key=lambda r: r.value))
def test_create_tenant_rejects_non_super_admin_roles(
    client, override_authenticated_user, role
):
    override_authenticated_user(make_authenticated_user(role))

    response = client.post(
        "/tenants",
        json=_create_tenant_payload(slug=f"denied-{role.value}"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.parametrize("role", sorted(_NON_SUPER_ADMIN_ROLES, key=lambda r: r.value))
def test_list_tenants_rejects_non_super_admin_roles(
    client, override_authenticated_user, role
):
    override_authenticated_user(make_authenticated_user(role))

    response = client.get("/tenants")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.parametrize("role", sorted(_NON_SUPER_ADMIN_ROLES, key=lambda r: r.value))
def test_get_tenant_rejects_non_super_admin_roles(
    client, db_session, override_authenticated_user, role
):
    tenant = Tenant(name="Protected Tenant", slug=f"protected-{role.value}")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    override_authenticated_user(make_authenticated_user(role))

    response = client.get(f"/tenants/{tenant.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
