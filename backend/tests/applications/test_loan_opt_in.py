"""Tests for ``PATCH /applications/{id}/loan-opt-in`` (E36; Journey J29; issue #199).

The student-side loan opt-in toggle endpoint. Covers:

* Happy path: the application's owning student opts in (``loan_opt_in=True``)
  and opts back out (``loan_opt_in=False``); the response reflects the
  change and the DB row is updated.
* Permission rejection: every staff role (consultancy owner, branch manager,
  counselor, receptionist, document verifier, visa processor, super admin)
  lacks ``application:read_own`` and is rejected with 403.
* Authentication: missing Bearer token is rejected with 401.
* Tenant scoping: a student in tenant A cannot toggle an application
  belonging to tenant B (404, not 403).
* Student-scope: a student in tenant A cannot toggle ANOTHER student's
  application in the same tenant (403).
* Idempotency: re-PATCHing the same value leaves the row unchanged and
  returns 200.
* Payload shape: the response is the full ``ApplicationResponse`` shape.
* Operational errors surface as 503.
"""

from __future__ import annotations


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


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_student_can_opt_in_to_loan_tracking(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The owning student can opt into loan tracking on their application."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    assert application.loan_opt_in is False  # default per E36 / #198

    override_authenticated_user(_auth_for(student))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == application.id
    assert body["loan_opt_in"] is True

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.loan_opt_in is True


def test_student_can_opt_out_of_loan_tracking(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The owning student can opt back out of loan tracking (toggle is symmetric)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    # Simulate a prior opt-in by writing True directly to the column.
    application.loan_opt_in = True
    db_session.commit()
    db_session.refresh(application)

    override_authenticated_user(_auth_for(student))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": False},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["loan_opt_in"] is False

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.loan_opt_in is False


def test_loan_opt_in_toggle_is_idempotent(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Re-PATCHing the same value is accepted (200) and the row stays consistent."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    override_authenticated_user(_auth_for(student))

    # First opt-in.
    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["loan_opt_in"] is True

    # Second opt-in is idempotent.
    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["loan_opt_in"] is True

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.loan_opt_in is True


def test_loan_opt_in_does_not_change_application_stage(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The toggle must not mutate the application's pipeline stage."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        stage="counseling",
    )
    override_authenticated_user(_auth_for(student))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "counseling"


def test_loan_opt_in_response_includes_full_application_payload(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """The response is the full ``ApplicationResponse`` shape (E36 contract)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
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
    assert body["loan_opt_in"] is True


# ---------------------------------------------------------------------------
# Permission tests — staff roles cannot toggle a student's loan_opt_in
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "actor_role",
    [
        Role.CONSULTANCY_OWNER,
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
    ],
)
def test_loan_opt_in_rejects_staff_roles(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    actor_role: Role,
) -> None:
    """No staff role currently has ``application:read_own``; all are 403.

    The loan opt-in toggle is a STUDENT-only endpoint. The staff-side
    ``status / lender / amount`` fields are owned by E37 (Journey J30)
    and are tracked via a separate, staff-only endpoint that has not
    shipped yet. Until then, ``loan_opt_in`` is exclusively a
    student-managed flag.
    """
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )

    branch_arg = branch.id if actor_role in (
        Role.COUNSELOR, Role.BRANCH_MANAGER, Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
    ) else None
    actor = make_db_user(
        db_session, actor_role, tenant_id=tenant.id, branch_id=branch_arg
    )
    override_authenticated_user(_auth_for(actor))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_loan_opt_in_rejects_super_admin(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Super Admin does NOT have ``application:read_own`` (403)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
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
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_loan_opt_in_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
    )

    assert response.status_code == 401


def test_loan_opt_in_rejects_invalid_jwt(
    client: TestClient,
    db_session: Session,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tenant / student-scope tests
# ---------------------------------------------------------------------------


def test_loan_opt_in_returns_404_for_cross_tenant_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student in tenant A cannot toggle an application in tenant B (404, not 403)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    student_b = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant_b.id, branch_id=branch_b.id
    )
    application_a = seed_application(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        student_id=student_b.id,  # student is in tenant B
    )
    override_authenticated_user(_auth_for(student_b))

    response = client.patch(
        f"/applications/{application_a.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_loan_opt_in_returns_404_for_missing_application(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    override_authenticated_user(_auth_for(student))

    response = client.patch(
        "/applications/999999/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_loan_opt_in_rejects_other_student_in_same_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student cannot toggle ANOTHER student's application (403, not 404).

    The tenant scoping helper returns the application successfully
    (because the student and the application share a tenant), so the
    student-scope check inside the endpoint is what surfaces the 403
    with the "Students may only update their own applications" detail.
    """
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    owning_student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    other_student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=owning_student.id,
    )
    override_authenticated_user(_auth_for(other_student))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": True},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Students may only update their own applications"

    # The DB row must NOT have changed.
    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.loan_opt_in is False


# ---------------------------------------------------------------------------
# Payload-shape tests
# ---------------------------------------------------------------------------


def test_loan_opt_in_rejects_missing_loan_opt_in_field(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Body without ``loan_opt_in`` is rejected at the Pydantic layer (422)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_loan_opt_in_rejects_non_boolean_loan_opt_in(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A non-boolean ``loan_opt_in`` is rejected at the Pydantic layer (422)."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    override_authenticated_user(_auth_for(student))

    response = client.patch(
        f"/applications/{application.id}/loan-opt-in",
        json={"loan_opt_in": "yes"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Operational-error coverage
# ---------------------------------------------------------------------------


def test_loan_opt_in_returns_503_when_commit_fails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError on the final ``db.commit()`` is caught and surfaces as 503."""
    tenant = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    override_authenticated_user(_auth_for(student))

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
            f"/applications/{application.id}/loan-opt-in",
            json={"loan_opt_in": True},
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Application service is temporarily unavailable"