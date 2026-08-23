"""Permission checks for PATCH /applications/{id}/counselor (E20, issue #155)."""

import pytest

from app.models.application import Application
from app.models.tenant import Tenant
from app.rbac.roles import Role
from app.schemas.application import ApplicationResponse
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


def _tenant(db_session, slug):
    row = Tenant(name=slug, slug=slug)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.mark.parametrize("role", [Role.CONSULTANCY_OWNER, Role.BRANCH_MANAGER, Role.RECEPTIONIST])
def test_reassignment_allowed_for_owner_manager_and_receptionist(
    client, db_session, override_authenticated_user, role
):
    tenant = _tenant(db_session, f"reassign-allow-{role.value}")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(db_session, role, tenant_id=tenant.id, branch_id=branch.id)
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=branch.id)
    target = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    override_authenticated_user(
        make_authenticated_user(
            role, user_id=actor.id, tenant_id=tenant.id, branch_id=branch.id
        )
    )

    response = client.patch(
        f"/applications/{app.id}/counselor",
        json={"counselor_id": target.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_counselor_id"] == target.id
    assert (
        ApplicationResponse.model_validate(db_session.get(Application, app.id)).assigned_counselor_id
        == target.id
    )


def test_reassignment_rejects_counselor_target_from_wrong_tenant(
    client, db_session, override_authenticated_user
):
    tenant = _tenant(db_session, "reassign-target-tenant")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=branch.id)
    actor = make_db_user(db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch.id)
    target = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    target.tenant_id = 999999
    db_session.commit()
    override_authenticated_user(
        make_authenticated_user(
            Role.RECEPTIONIST,
            user_id=actor.id,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.patch(
        f"/applications/{app.id}/counselor",
        json={"counselor_id": target.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code in (403, 404)
    assert db_session.get(Application, app.id).assigned_counselor_id is None


def test_counselor_and_student_cannot_reassign(client, db_session, override_authenticated_user):
    tenant = _tenant(db_session, "reassign-denied")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=branch.id)
    target = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    for role in (Role.COUNSELOR, Role.STUDENT):
        actor = make_db_user(db_session, role, tenant_id=tenant.id, branch_id=branch.id)
        override_authenticated_user(
            make_authenticated_user(
                role, user_id=actor.id, tenant_id=tenant.id, branch_id=branch.id
            )
        )
        response = client.patch(
            f"/applications/{app.id}/counselor",
            json={"counselor_id": target.id},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 403


def test_manager_cannot_reassign_application_in_another_branch(
    client, db_session, override_authenticated_user
):
    tenant = _tenant(db_session, "reassign-branch")
    manager_branch = seed_branch(db_session, tenant_id=tenant.id)
    other_branch = seed_branch(db_session, tenant_id=tenant.id, name="Other", city="Pune")
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=other_branch.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=manager_branch.id
    )
    target = make_db_user(
        db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=other_branch.id
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            user_id=manager.id,
            tenant_id=tenant.id,
            branch_id=manager_branch.id,
        )
    )

    response = client.patch(
        f"/applications/{app.id}/counselor",
        json={"counselor_id": target.id},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert db_session.get(Application, app.id).assigned_counselor_id is None
