"""Owner-only access matrix for branch endpoints (E11, Journey J4, issue #118)."""

import pytest

from app.rbac import Permission, Role, get_permissions_for_role
from tests.branches.helpers import make_branch_payload, seed_branch
from tests.factories.users import make_authenticated_user

_BRANCH_PERMISSIONS = frozenset(
    {Permission.BRANCH_CREATE, Permission.BRANCH_READ, Permission.BRANCH_UPDATE}
)

_NON_OWNER_ROLES = frozenset(role for role in Role if role is not Role.CONSULTANCY_OWNER)


@pytest.mark.parametrize("role", sorted(_NON_OWNER_ROLES, key=lambda r: r.value))
def test_non_owner_roles_lack_branch_permissions(role: Role) -> None:
    perms = get_permissions_for_role(role)
    assert _BRANCH_PERMISSIONS.isdisjoint(perms)


@pytest.mark.parametrize("role", sorted(_NON_OWNER_ROLES, key=lambda r: r.value))
def test_create_branch_rejects_non_owner_roles(client, override_authenticated_user, role):
    override_authenticated_user(make_authenticated_user(role))

    response = client.post(
        "/branches",
        json=make_branch_payload(name=f"Denied {role.value}"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.parametrize("role", sorted(_NON_OWNER_ROLES, key=lambda r: r.value))
def test_list_branches_rejects_non_owner_roles(client, override_authenticated_user, role):
    override_authenticated_user(make_authenticated_user(role))

    response = client.get("/branches")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.parametrize("role", sorted(_NON_OWNER_ROLES, key=lambda r: r.value))
def test_update_branch_rejects_non_owner_roles(
    client, db_session, override_authenticated_user, role
):
    branch = seed_branch(db_session, tenant_id=1, name=f"Protected {role.value}")
    override_authenticated_user(make_authenticated_user(role))

    response = client.patch(
        f"/branches/{branch.id}",
        json={"name": "Denied update"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
