"""Staff deactivation/reactivation permission tests (E13, Journey J6, issue #125).

Proves POST /staff/{id}/deactivate and /reactivate enforce RBAC from Requirements §3:
- Consultancy Owner may deactivate/reactivate staff in any branch within their tenant.
- Branch Manager may deactivate/reactivate staff only in their own branch.
- Branch Manager cannot act on peer branch managers (role hierarchy).
- Other roles are denied via STAFF_DEACTIVATE permission.
- Cross-tenant targets are not found (404).
"""

import pytest

from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user, make_db_user

_UNAUTHORIZED_ROLES = [
    Role.SUPER_ADMIN,
    Role.COUNSELOR,
    Role.DOCUMENT_VERIFIER,
    Role.VISA_PROCESSOR,
    Role.RECEPTIONIST,
    Role.STUDENT,
]


def _seed_staff_user(
    db_session,
    *,
    email: str = "counselor@example.test",
    role: Role = Role.COUNSELOR,
    tenant_id: int = 1,
    branch_id: int,
    is_active: bool = True,
) -> int:
    user = make_db_user(
        db_session,
        role,
        email=email,
        tenant_id=tenant_id,
        branch_id=branch_id,
        is_active=is_active,
    )
    return user.id


def test_owner_can_deactivate_staff_in_any_branch(
    client, db_session, override_authenticated_user
):
    branch_one = seed_branch(db_session, tenant_id=1, name="Branch One", city="Mumbai")
    branch_two = seed_branch(db_session, tenant_id=1, name="Branch Two", city="Delhi")
    staff_one = _seed_staff_user(
        db_session,
        email="deactivate.b1@example.test",
        branch_id=branch_one.id,
    )
    staff_two = _seed_staff_user(
        db_session,
        email="deactivate.b2@example.test",
        role=Role.RECEPTIONIST,
        branch_id=branch_two.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response_one = client.post(f"/staff/{staff_one}/deactivate")
    response_two = client.post(f"/staff/{staff_two}/deactivate")

    assert response_one.status_code == 200
    assert response_one.json()["is_active"] is False
    assert response_two.status_code == 200
    assert response_two.json()["is_active"] is False


def test_owner_can_reactivate_staff_in_any_branch(
    client, db_session, override_authenticated_user
):
    branch_one = seed_branch(db_session, tenant_id=1, name="Branch One", city="Mumbai")
    branch_two = seed_branch(db_session, tenant_id=1, name="Branch Two", city="Delhi")
    staff_one = _seed_staff_user(
        db_session,
        email="reactivate.b1@example.test",
        branch_id=branch_one.id,
        is_active=False,
    )
    staff_two = _seed_staff_user(
        db_session,
        email="reactivate.b2@example.test",
        role=Role.VISA_PROCESSOR,
        branch_id=branch_two.id,
        is_active=False,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response_one = client.post(f"/staff/{staff_one}/reactivate")
    response_two = client.post(f"/staff/{staff_two}/reactivate")

    assert response_one.status_code == 200
    assert response_one.json()["is_active"] is True
    assert response_two.status_code == 200
    assert response_two.json()["is_active"] is True


def test_branch_manager_can_reactivate_staff_in_own_branch(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    staff_id = _seed_staff_user(
        db_session,
        email="reactivate.own.branch@example.test",
        branch_id=branch.id,
        is_active=False,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(f"/staff/{staff_id}/reactivate")

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_branch_manager_cannot_reactivate_staff_in_other_branch(
    client, db_session, override_authenticated_user
):
    own_branch = seed_branch(db_session, tenant_id=1, name="Own Branch", city="Mumbai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Other Branch", city="Delhi")
    other_staff = _seed_staff_user(
        db_session,
        email="reactivate.other.branch@example.test",
        branch_id=other_branch.id,
        is_active=False,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=own_branch.id,
        )
    )

    response = client.post(f"/staff/{other_staff}/reactivate")

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_branch_manager_cannot_deactivate_branch_manager(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Shared Branch", city="Mumbai")
    peer_manager = _seed_staff_user(
        db_session,
        email="peer.manager@example.test",
        role=Role.BRANCH_MANAGER,
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(f"/staff/{peer_manager}/deactivate")

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


def test_branch_manager_cannot_reactivate_branch_manager(
    client, db_session, override_authenticated_user
):
    branch = seed_branch(db_session, tenant_id=1, name="Shared Branch", city="Mumbai")
    peer_manager = _seed_staff_user(
        db_session,
        email="inactive.peer.manager@example.test",
        role=Role.BRANCH_MANAGER,
        branch_id=branch.id,
        is_active=False,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.post(f"/staff/{peer_manager}/reactivate")

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]


@pytest.mark.parametrize("role", _UNAUTHORIZED_ROLES)
def test_unauthorized_roles_cannot_deactivate_staff(
    client, db_session, override_authenticated_user, role: Role
):
    branch = seed_branch(db_session, tenant_id=1, name=f"Branch for {role.value}", city="Mumbai")
    staff_id = _seed_staff_user(
        db_session,
        email=f"target.deactivate.{role.value}@example.test",
        branch_id=branch.id,
    )
    override_authenticated_user(make_authenticated_user(role, tenant_id=1, branch_id=branch.id))

    response = client.post(f"/staff/{staff_id}/deactivate")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.parametrize("role", _UNAUTHORIZED_ROLES)
def test_unauthorized_roles_cannot_reactivate_staff(
    client, db_session, override_authenticated_user, role: Role
):
    branch = seed_branch(db_session, tenant_id=1, name=f"Branch for {role.value}", city="Mumbai")
    staff_id = _seed_staff_user(
        db_session,
        email=f"target.reactivate.{role.value}@example.test",
        branch_id=branch.id,
        is_active=False,
    )
    override_authenticated_user(make_authenticated_user(role, tenant_id=1, branch_id=branch.id))

    response = client.post(f"/staff/{staff_id}/reactivate")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_deactivate_cross_tenant_staff_returns_404(
    client, db_session, override_authenticated_user
):
    other_tenant_branch = seed_branch(db_session, tenant_id=2, name="Other Tenant", city="Delhi")
    other_staff = _seed_staff_user(
        db_session,
        email="cross.tenant.deactivate@example.test",
        tenant_id=2,
        branch_id=other_tenant_branch.id,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(f"/staff/{other_staff}/deactivate")

    assert response.status_code == 404
    assert response.json()["detail"] == "Staff member not found"


def test_reactivate_cross_tenant_staff_returns_404(
    client, db_session, override_authenticated_user
):
    other_tenant_branch = seed_branch(db_session, tenant_id=2, name="Other Tenant", city="Delhi")
    other_staff = _seed_staff_user(
        db_session,
        email="cross.tenant.reactivate@example.test",
        tenant_id=2,
        branch_id=other_tenant_branch.id,
        is_active=False,
    )
    override_authenticated_user(make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=1))

    response = client.post(f"/staff/{other_staff}/reactivate")

    assert response.status_code == 404
    assert response.json()["detail"] == "Staff member not found"


def test_branch_manager_jwt_can_reactivate_own_branch_staff(client, db_session):
    branch = seed_branch(db_session, tenant_id=1, name="Manager Branch", city="Chennai")
    staff_id = _seed_staff_user(
        db_session,
        email="jwt.reactivate.own@example.test",
        branch_id=branch.id,
        is_active=False,
    )
    password = "manager-password"
    make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="manager.reactivate@staff.test",
        password=password,
        tenant_id=1,
        branch_id=branch.id,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "manager.reactivate@staff.test", "password": password},
    )
    headers = make_auth_headers(login_response.json()["access_token"])

    response = client.post(f"/staff/{staff_id}/reactivate", headers=headers)

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_branch_manager_jwt_cannot_reactivate_other_branch_staff(client, db_session):
    own_branch = seed_branch(db_session, tenant_id=1, name="Manager Branch", city="Chennai")
    other_branch = seed_branch(db_session, tenant_id=1, name="Remote Branch", city="Kolkata")
    other_staff = _seed_staff_user(
        db_session,
        email="jwt.reactivate.other@example.test",
        branch_id=other_branch.id,
        is_active=False,
    )
    password = "manager-password"
    make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="manager.reactivate.denied@staff.test",
        password=password,
        tenant_id=1,
        branch_id=own_branch.id,
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "manager.reactivate.denied@staff.test", "password": password},
    )
    headers = make_auth_headers(login_response.json()["access_token"])

    response = client.post(f"/staff/{other_staff}/reactivate", headers=headers)

    assert response.status_code == 403
    assert "cannot act on user" in response.json()["detail"]
