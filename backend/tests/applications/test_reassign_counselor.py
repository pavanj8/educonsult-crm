"""Tests for ``PATCH /applications/{id}/counselor`` (E20; Journey J13; issue #153).

Manual counselor reassignment endpoint. Covers:

* Happy path: branch manager, consultancy owner, and receptionist each
  reassign an application's counselor (with a non-null and a null
  ``counselor_id``); the response reflects the change and the DB row
  is updated.
* Permission rejection: STUDENT, COUNSELOR, DOCUMENT_VERIFIER, and
  VISA_PROCESSOR all lack the ``application:reassign_counselor``
  permission and are rejected with 403.
* Authentication: missing Bearer token is rejected with 401.
* Tenant scoping: a manager in tenant A cannot reassign an
  application belonging to tenant B (404, not 403).
* Branch scoping: a branch manager in branch A cannot reassign an
  application belonging to branch B (403); consultancy owners keep
  cross-branch visibility.
* Target validation: invalid / inactive / wrong-role / wrong-branch /
  wrong-tenant counselor ids surface as 422 (not 403 -- the caller is
  authenticated and authorized to make the call, the input is bad).
* Operational errors surface as 503.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from app.models.application import Application
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _create_tenant(db_session: Session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _auth_for(user) -> object:
    return make_authenticated_user(
        user.role,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


def _auth_consultancy_owner(user) -> object:
    return make_authenticated_user(
        Role.CONSULTANCY_OWNER,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=None,
    )


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_branch_manager_reassigns_to_other_counselor_in_same_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    original_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=original_counselor.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == application.id
    assert body["assigned_counselor_id"] == new_counselor.id

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.assigned_counselor_id == new_counselor.id


def test_receptionist_reassigns_to_other_counselor_in_same_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    receptionist = make_db_user(
        db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(receptionist))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] == new_counselor.id


def test_consultancy_owner_reassigns_within_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] == new_counselor.id


def test_consultancy_owner_can_reassign_across_branches(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Owners have cross-branch visibility and may assign any counselor in the tenant."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    counselor_in_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_a.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": counselor_in_b.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] == counselor_in_b.id


def test_reassign_with_null_counselor_id_unassigns(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Passing ``counselor_id: null`` clears the assigned counselor."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": None},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] is None

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.assigned_counselor_id is None


def test_reassign_with_omitted_counselor_id_unassigns(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Omitting the field is accepted as unassign (default = null)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] is None


def test_reassign_to_same_counselor_is_idempotent(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Reassigning the application to the counselor it already has returns 200 and a stable payload."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] == counselor.id


def test_reassign_does_not_change_application_stage(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The reassignment endpoint must not mutate the application's pipeline stage."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        stage="counseling",
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "counseling"


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "actor_role",
    [Role.STUDENT, Role.COUNSELOR, Role.DOCUMENT_VERIFIER, Role.VISA_PROCESSOR],
)
def test_reassign_rejects_roles_without_permission(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    actor_role: Role,
) -> None:
    """Roles without ``application:reassign_counselor`` get 403."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(
        db_session, actor_role, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(actor))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_reassign_rejects_super_admin_without_permission(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Super Admin does NOT have APPLICATION_REASSIGN_COUNSELOR (only owners / managers / receptionists do)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.SUPER_ADMIN,
            user_id=1,
            tenant_id=None,
            branch_id=None,
        )
    )

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_reassign_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": 1},
    )

    assert response.status_code == 401


def test_reassign_rejects_invalid_jwt(
    client: TestClient,
    db_session: Session,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": 1},
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )

    assert response.status_code == 401


def test_reassign_rejects_branch_manager_without_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager without ``branch_id`` has no scope to act on any application (403)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            user_id=999,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tenant / branch scoping tests
# ---------------------------------------------------------------------------


def test_reassign_returns_404_for_cross_tenant_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A manager in tenant A cannot reassign an application belonging to tenant B (404, not 403)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    manager_b = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    new_counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    application_a = seed_application(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager_b))

    response = client.patch(
        f"/applications/{application_a.id}/counselor",
        json={"counselor_id": new_counselor_b.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_reassign_returns_404_for_missing_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        "/applications/999999/counselor",
        json={"counselor_id": 1},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_branch_manager_cannot_reassign_application_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A branch manager in branch A cannot reassign an application belonging to branch B (403)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_in_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.patch(
        f"/applications/{application_in_b.id}/counselor",
        json={"counselor_id": counselor_b.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_receptionist_cannot_reassign_application_in_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A receptionist in branch A cannot reassign an application belonging to branch B (403)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    receptionist_a = make_db_user(
        db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_in_b = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_b.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(receptionist_a))

    response = client.patch(
        f"/applications/{application_in_b.id}/counselor",
        json={"counselor_id": counselor_b.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Target-validation tests
# ---------------------------------------------------------------------------


def test_reassign_rejects_unknown_counselor_id(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": 999999},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor not found"


def test_reassign_rejects_inactive_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    inactive = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
        is_active=False,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": inactive.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor is not active"


def test_reassign_rejects_counselor_from_another_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant_a.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": counselor_b.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor not found"


def test_reassign_rejects_user_with_wrong_role(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A user with a non-COUNSELOR role in the right branch is rejected."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    not_a_counselor = make_db_user(
        db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": not_a_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor not found"


def test_branch_manager_cannot_assign_counselor_from_other_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Branch manager in branch A cannot pick a counselor from branch B (422)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Pune")
    manager_a = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch_a.id
    )
    counselor_b = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch_b.id
    )
    application_in_a = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch_a.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager_a))

    response = client.patch(
        f"/applications/{application_in_a.id}/counselor",
        json={"counselor_id": counselor_b.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor not found"


def test_reassign_rejects_negative_counselor_id_at_schema(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A non-positive ``counselor_id`` is rejected at the Pydantic layer (422)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": -1},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_branch_manager_cannot_assign_branch_less_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Branch-scoped actors cannot assign a counselor whose own ``branch_id`` is NULL.

    A branch-less counselor (``branch_id IS NULL``) is an unusual state in
    production but is allowed by the ``User`` model. A branch manager /
    receptionist is bound to a single branch and the branch-id equality
    check (``counselor.branch_id != application.branch_id``) treats
    ``None`` as not-equal to a non-null branch, so the assignment is
    rejected with 422 ``Target counselor not found``. The endpoint does
    NOT treat branch-less counselors as auto-eligible.
    """
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    branch_less_counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=None,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": branch_less_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor not found"


def test_receptionist_cannot_assign_branch_less_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A receptionist (also branch-scoped) cannot assign a branch-less counselor (422)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    receptionist = make_db_user(
        db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch.id
    )
    branch_less_counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=None,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(receptionist))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": branch_less_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor not found"


def test_consultancy_owner_can_assign_branch_less_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Consultancy owners (cross-branch by design) CAN assign a branch-less counselor.

    The branch-equality check is skipped for owners (because
    ``_target_branch_scope`` returns ``None`` for them), so a branch-less
    counselor in the same tenant is accepted. This is consistent with
    owners being able to assign across any branch in the tenant.
    """
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id, branch_id=None
    )
    branch_less_counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=None,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_consultancy_owner(owner))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": branch_less_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] == branch_less_counselor.id


# ---------------------------------------------------------------------------
# Operational-error coverage
# ---------------------------------------------------------------------------


def test_reassign_returns_503_when_application_lookup_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    mock_session = MagicMock()
    mock_session.get.side_effect = OperationalError(
        "stmt", {}, Exception("no such table")
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.patch(
            f"/applications/{application.id}/counselor",
            json={"counselor_id": new_counselor.id},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Application service is temporarily unavailable"


def test_reassign_returns_503_when_target_counselor_lookup_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError on the target-counselor db.get() surfaces as 503."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    mock_session = MagicMock()
    # First db.get() returns the application; the second (target counselor) raises.
    mock_session.get.side_effect = [
        application,
        OperationalError("stmt", {}, Exception("disk full")),
    ]

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.patch(
            f"/applications/{application.id}/counselor",
            json={"counselor_id": new_counselor.id},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Application service is temporarily unavailable"


def test_reassign_returns_503_when_commit_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError on the final db.commit() is caught and surfaces as 503."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    real_session = db_session

    class _FlakyCommitSession:
        def __init__(self, real):
            self._real = real

        def get(self, *args, **kwargs):
            return self._real.get(*args, **kwargs)

        def commit(self, *args, **kwargs):
            raise OperationalError("stmt", {}, Exception("disk full"))

        def add(self, *args, **kwargs):
            return self._real.add(*args, **kwargs)

        def refresh(self, *args, **kwargs):
            return self._real.refresh(*args, **kwargs)

        def rollback(self, *args, **kwargs):
            return self._real.rollback(*args, **kwargs)

        def scalars(self, *args, **kwargs):
            return self._real.scalars(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def override_get_db():
        yield _FlakyCommitSession(real_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.patch(
            f"/applications/{application.id}/counselor",
            json={"counselor_id": new_counselor.id},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Payload shape tests
# ---------------------------------------------------------------------------


def test_reassign_response_includes_full_application_payload(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The response is the full ApplicationResponse shape, not just the counselor id."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id
    )
    new_counselor = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=None,
    )
    override_authenticated_user(_auth_for(manager))

    response = client.patch(
        f"/applications/{application.id}/counselor",
        json={"counselor_id": new_counselor.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # All ApplicationResponse fields must be present.
    for field in (
        "id",
        "tenant_id",
        "branch_id",
        "student_id",
        "assigned_counselor_id",
        "university_id",
        "program_id",
        "stage",
        "loan_opt_in",
        "created_at",
        "updated_at",
    ):
        assert field in body, f"Missing {field} in response"
    assert body["id"] == application.id
    assert body["assigned_counselor_id"] == new_counselor.id