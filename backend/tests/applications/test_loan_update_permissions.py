"""Permission checks for PATCH /applications/{id}/loan (E37, issue #202).

Complements the endpoint-level tests in ``test_loan_update.py``
(issue #200) by exercising the *permission matrix* for the staff
loan-status update endpoint:

* CONSULTANCY_OWNER and BRANCH_MANAGER all hold the ``loan:update``
  permission and succeed.
* COUNSELOR, STUDENT, RECEPTIONIST, DOCUMENT_VERIFIER,
  VISA_PROCESSOR, and SUPER_ADMIN do NOT hold that permission and
  are rejected with 403 ("Insufficient permissions") -- regardless
  of which application they target.
* BRANCH_MANAGER is branch-scoped (ADR-0004) and is rejected with
  403 when targeting an application belonging to a different branch.
* Cross-tenant access surfaces as 404 to prevent tenant-id
  enumeration, matching the E20 / E25 / E33 / E35 conventions.

The endpoint implementation itself -- the route, the schema, the
``_enforce_branch_scope`` helper -- lives on ``main`` (issue #200).
This file ONLY adds the permission-matrix tests that are the
explicit acceptance criterion for issue #202 ("Tests: loan field
updates and permission checks"); it does not re-implement or
duplicate any endpoint logic.
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


@pytest.mark.parametrize("role", [Role.CONSULTANCY_OWNER, Role.BRANCH_MANAGER])
def test_loan_update_allowed_for_owner_and_branch_manager(
    client, db_session, override_authenticated_user, role
):
    """Roles granted ``loan:update`` succeed (200) and persist the loan tracking fields.

    Consultancy owners and branch managers both hold
    ``loan:update`` per :data:`app.rbac.permissions.ROLE_PERMISSIONS`
    and are the two staff roles the E37 endpoint is designed for
    (Journey J30). The endpoint persists the supplied status /
    lender / amount onto the application's ``loan_status`` /
    ``loan_lender`` / ``loan_amount`` columns.
    """
    tenant = _tenant(db_session, f"loan-allow-{role.value}")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(db_session, role, tenant_id=tenant.id, branch_id=branch.id)
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=branch.id)
    override_authenticated_user(
        make_authenticated_user(
            role, user_id=actor.id, tenant_id=tenant.id, branch_id=branch.id
        )
    )

    response = client.patch(
        f"/applications/{app.id}/loan",
        json={
            "loan_status": "approved",
            "loan_lender": "HDFC Credila",
            "loan_amount": "1500000.00",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()["application"]
    assert body["loan_status"] == "approved"
    assert body["loan_lender"] == "HDFC Credila"

    # ``db_session`` and the session used by the request handler share a
    # StaticPool connection but each has its own SQLAlchemy identity map,
    # so the test session still holds the pre-commit ``Application``
    # instance after the request's commit. Expire the cached instance
    # before re-reading so the assertion observes the committed row.
    db_session.expire(app)
    refreshed = db_session.get(Application, app.id)
    assert refreshed is not None
    assert refreshed.loan_status == "approved"
    assert refreshed.loan_lender == "HDFC Credila"
    assert refreshed.loan_amount is not None


@pytest.mark.parametrize(
    "role",
    [
        Role.COUNSELOR,
        Role.STUDENT,
        Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
    ],
)
def test_loan_update_rejects_staff_roles_without_loan_update_permission(
    client, db_session, override_authenticated_user, role
):
    """Roles without ``loan:update`` get 403 ("Insufficient permissions").

    Only CONSULTANCY_OWNER and BRANCH_MANAGER hold ``loan:update``
    per :data:`app.rbac.permissions.ROLE_PERMISSIONS`; every other
    tenant-scoped staff role is blocked here. The endpoint surfaces
    this as 403 *before* any DB query runs (the
    ``require_permission(...)`` dependency raises on the missing
    permission), so the application row is untouched.
    """
    tenant = _tenant(db_session, f"loan-deny-{role.value}")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    actor = make_db_user(db_session, role, tenant_id=tenant.id, branch_id=branch.id)
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=branch.id)
    override_authenticated_user(
        make_authenticated_user(
            role, user_id=actor.id, tenant_id=tenant.id, branch_id=branch.id
        )
    )

    response = client.patch(
        f"/applications/{app.id}/loan",
        json={"loan_status": "approved"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"

    # The application row was never touched.
    db_session.expire(app)
    refreshed = db_session.get(Application, app.id)
    assert refreshed.loan_status is None
    assert refreshed.loan_lender is None
    assert refreshed.loan_amount is None


def test_loan_update_rejects_super_admin_without_loan_update_permission(
    client, db_session, override_authenticated_user
):
    """SUPER_ADMIN does NOT hold ``loan:update`` and is rejected with 403.

    Per :data:`app.rbac.permissions.ROLE_PERMISSIONS`,
    ``SUPER_ADMIN`` is intentionally NOT granted ``loan:update``: the
    Super Admin oversees platform-wide tenants / billing
    (Requirements §3 + §4) and is not a tenant-scoped staff role. A
    cross-tenant write attempt would also fail the tenant-scope
    check, but the dependency layer blocks earlier at 403 so the
    response is uniform with the other staff roles that lack the
    permission.
    """
    app = seed_application(db_session, tenant_id=1, branch_id=1)
    override_authenticated_user(
        make_authenticated_user(
            Role.SUPER_ADMIN,
            user_id=999,
            tenant_id=None,
            branch_id=None,
        )
    )

    response = client.patch(
        f"/applications/{app.id}/loan",
        json={"loan_status": "approved"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_loan_update_branch_manager_blocked_in_other_branch(
    client, db_session, override_authenticated_user
):
    """BRANCH_MANAGER is branch-scoped (ADR-0004) and is rejected with 403 for cross-branch applications.

    The endpoint's ``_enforce_branch_scope`` helper raises 403 before
    any loan field is updated, so the application's loan fields
    remain ``None``. Consultancy owners keep cross-branch visibility
    by design (ADR-0004).
    """
    tenant = _tenant(db_session, "loan-branch")
    manager_branch = seed_branch(db_session, tenant_id=tenant.id)
    other_branch = seed_branch(db_session, tenant_id=tenant.id, name="Other", city="Pune")
    app = seed_application(db_session, tenant_id=tenant.id, branch_id=other_branch.id)
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=manager_branch.id
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
        f"/applications/{app.id}/loan",
        json={"loan_status": "approved", "loan_amount": "500000.00"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no access to this branch's applications"

    db_session.expire(app)
    refreshed = db_session.get(Application, app.id)
    assert refreshed.loan_status is None
    assert refreshed.loan_amount is None


def test_loan_update_consultancy_owner_can_act_cross_branch(
    client, db_session, override_authenticated_user
):
    """CONSULTANCY_OWNER keeps cross-branch visibility by design (ADR-0004).

    Pin the consult of ADR-0004: a consultancy owner can record loan
    tracking fields on applications belonging to any branch inside
    their tenant. The endpoint's ``_enforce_branch_scope`` helper
    intentionally does NOT raise for ``CONSULTANCY_OWNER``.
    """
    tenant = _tenant(db_session, "loan-cross-branch")
    branch_a = seed_branch(db_session, tenant_id=tenant.id, name="A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=tenant.id, name="B", city="Delhi")
    app_in_branch_b = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch_b.id
    )
    # Owner has no branch_id (consultancy-owner scope, per factory).
    owner = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant.id
    )
    # Sanity: factory default places owner on branch_a if a branch_id
    # were inferred; here we explicitly constructed without branch_id.
    assert owner.branch_id is None

    override_authenticated_user(
        make_authenticated_user(
            Role.CONSULTANCY_OWNER,
            user_id=owner.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    response = client.patch(
        f"/applications/{app_in_branch_b.id}/loan",
        json={"loan_status": "approved"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["application"]["loan_status"] == "approved"

    db_session.expire(app_in_branch_b)
    refreshed = db_session.get(Application, app_in_branch_b.id)
    assert refreshed.loan_status == "approved"

    # ``branch_a`` is unused here but must exist for the schema check
    # to mirror production reality.
    assert branch_a.id != branch_b.id


def test_loan_update_rejects_cross_tenant_application(
    client, db_session, override_authenticated_user
):
    """Cross-tenant access surfaces as 404 to prevent tenant-id enumeration.

    Matches the E20 / E25 / E33 / E35 conventions: the
    ``get_tenant_application`` helper raises 404 (not 403) so the
    response cannot be used to enumerate which application ids
    belong to which tenant. The application's loan fields are
    untouched.
    """
    own_tenant = _tenant(db_session, "loan-own")
    other_tenant = _tenant(db_session, "loan-other")
    other_branch = seed_branch(db_session, tenant_id=other_tenant.id)
    other_app = seed_application(
        db_session, tenant_id=other_tenant.id, branch_id=other_branch.id
    )
    actor = make_db_user(
        db_session, Role.CONSULTANCY_OWNER, tenant_id=own_tenant.id
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.CONSULTANCY_OWNER,
            user_id=actor.id,
            tenant_id=own_tenant.id,
            branch_id=None,
        )
    )

    response = client.patch(
        f"/applications/{other_app.id}/loan",
        json={"loan_status": "approved"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"

    db_session.expire(other_app)
    refreshed = db_session.get(Application, other_app.id)
    assert refreshed.loan_status is None
