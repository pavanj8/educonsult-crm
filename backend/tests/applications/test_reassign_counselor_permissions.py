"""Permission checks for PATCH /applications/{id}/counselor (E20, issue #155).

Complements the endpoint-level tests in ``test_reassign_counselor.py``
(issue #153) by exercising the *permission matrix* for the manual
counselor-reassignment endpoint:

* CONSULTANCY_OWNER, BRANCH_MANAGER, and RECEPTIONIST all hold the
  ``application:reassign_counselor`` permission and succeed.
* COUNSELOR and STUDENT do NOT hold that permission and are rejected
  with 403 ("Insufficient permissions") -- regardless of which
  application they target.
* BRANCH_MANAGER is branch-scoped (ADR-0004) and is rejected with 403
  when targeting an application belonging to a different branch.
* A target counselor in a different tenant is rejected with 422 by the
  endpoint's ``_validate_target_counselor`` guard ("Target counselor not
  found") to avoid leaking user-id existence across tenants (a 422
  rather than 403/404 is the deliberate design choice in #153).

The endpoint implementation itself -- the route, the schema, the
``_validate_target_counselor`` / ``_target_branch_scope`` helpers, the
target-counselor / cross-branch / cross-tenant behavior -- lives on
``main`` (issue #153). This file ONLY adds the permission-matrix tests
that are the explicit acceptance criterion for issue #155; it does not
re-implement or duplicate any endpoint logic.
"""

import pytest

from app.models.application import Application
from app.models.tenant import Tenant
from app.rbac.roles import Role
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
    """Roles granted ``application:reassign_counselor`` succeed (200) and persist the new counselor id."""
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

    # ``db_session`` and the session used by the request handler share a
    # StaticPool connection but each has its own SQLAlchemy identity map,
    # so the test session still holds the pre-commit ``Application``
    # instance after the request's commit. Expire the cached instance
    # before re-reading so the assertion observes the committed row.
    db_session.expire(app)
    refreshed = db_session.get(Application, app.id)
    assert refreshed is not None
    assert refreshed.assigned_counselor_id == target.id


def test_reassignment_rejects_counselor_target_from_wrong_tenant(
    client, db_session, override_authenticated_user
):
    """A target counselor belonging to a different tenant is rejected (422, ``Target counselor not found``).

    The endpoint surfaces this as 422 rather than 403/404 on purpose
    (see ``_validate_target_counselor`` in ``app/routers/applications.py``):
    a 422 keeps the response shape identical for "unknown id" and
    "wrong tenant" so the caller cannot enumerate which user ids exist
    in other tenants.
    """
    tenant = _tenant(db_session, "reassign-target-tenant")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=branch.id)
    actor = make_db_user(db_session, Role.RECEPTIONIST, tenant_id=tenant.id, branch_id=branch.id)
    target = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    # Move the target out of the actor's tenant so the validator sees a
    # tenant mismatch (simulates a real cross-tenant User row).
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

    assert response.status_code == 422
    assert response.json()["detail"] == "Target counselor not found"
    db_session.expire(app)
    assert db_session.get(Application, app.id).assigned_counselor_id is None


def test_counselor_and_student_cannot_reassign(client, db_session, override_authenticated_user):
    """COUNSELOR and STUDENT lack the permission; both get 403 ("Insufficient permissions")."""
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
        assert response.json()["detail"] == "Insufficient permissions"


def test_manager_cannot_reassign_application_in_another_branch(
    client, db_session, override_authenticated_user
):
    """BRANCH_MANAGER is branch-scoped (ADR-0004) and is rejected with 403 for cross-branch applications.

    The endpoint's ``_enforce_branch_scope`` helper raises 403 before the
    target counselor is even looked up, so the application remains
    untouched. Consultancy owners keep cross-branch visibility by design.
    """
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
    db_session.expire(app)
    assert db_session.get(Application, app.id).assigned_counselor_id is None
