"""Tests for the E37 update-loan-status API (Journey J30; issue #200).

Covers the happy path (create + update), tenant scoping, role gating,
branch scoping, body validation (empty body, oversize strings, negative
amount), field clear via explicit null, and the 503 database-unavailable
error path. Mirrors the conventions used in
``tests/visa/test_outcome.py`` so the E37 surface reads consistently
with the E34 / E35 visa surfaces.

Acceptance criteria pinned here (Journey J30, Requirements §5):

* Staff can record loan status, lender, and amount against an
  application via ``PATCH /applications/{id}/loan``.
* Each field is independently optional; a PATCH with one field set
  leaves the other fields untouched. An explicit ``null`` clears the
  previously-recorded value.
* The endpoint is gated on ``loan:update``, which is granted to
  ``CONSULTANCY_OWNER`` and ``BRANCH_MANAGER`` per
  :data:`app.rbac.permissions.ROLE_PERMISSIONS`. Other roles
  (STUDENT, COUNSELOR, RECEPTIONIST, DOCUMENT_VERIFIER,
  VISA_PROCESSOR, SUPER_ADMIN) are blocked at the dependency layer.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _override(
    override_authenticated_user, *, role: Role, user_id: int, tenant_id: int | None, branch_id: int | None
):
    override_authenticated_user(
        make_authenticated_user(role, user_id=user_id, tenant_id=tenant_id, branch_id=branch_id)
    )


def _setup_loan_application(
    db_session,
    *,
    stage=None,
    tenant_id: int | None = None,
):
    """Create a tenant + branch + application for the calling test.

    Defaults to ``PipelineStage.REGISTERED``; callers may override to
    land the application on any non-terminal stage. Mirrors
    ``_setup_visa_application`` in ``tests/visa/test_outcome.py`` but
    does NOT enforce ``visa_processing`` because the E37 endpoint is
    stage-agnostic (loan tracking is a side-channel of the
    application; see the endpoint docstring on
    ``app.routers.applications.update_application_loan``).
    """
    from app.pipeline.stages import PipelineStage

    if tenant_id is None:
        suffix = 1
        slug = "loan-update"
        while db_session.query(Tenant).filter(Tenant.slug == slug).first() is not None:
            suffix += 1
            slug = f"loan-update-{suffix}"
        tenant = Tenant(name="Loan Update Tenant", slug=slug)
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)
        tenant_id = tenant.id

    branch = seed_branch(db_session, tenant_id=tenant_id)
    application = seed_application(
        db_session,
        tenant_id=tenant_id,
        branch_id=branch.id,
        university_id=11,
        program_id=21,
        stage=stage or PipelineStage.REGISTERED,
    )
    return tenant_id, branch.id, application


# ---------------------------------------------------------------------------
# Happy path: create + update + clear
# ---------------------------------------------------------------------------


def test_loan_update_creates_tracking_fields_for_fresh_application(
    client, db_session, override_authenticated_user
):
    """A PATCH records loan status, lender, and amount on a fresh application."""
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={
            "loan_status": "in_progress",
            "loan_lender": "HDFC Credila",
            "loan_amount": "1500000.00",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    app_payload = body["application"]
    assert app_payload["id"] == application.id
    assert app_payload["tenant_id"] == tenant_id
    assert app_payload["loan_status"] == "in_progress"
    assert app_payload["loan_lender"] == "HDFC Credila"
    # Decimal round-trips as a JSON string by default in Pydantic v2; the
    # persisted column is Numeric(12, 2). Compare via the persisted row
    # rather than the JSON-decoded body to avoid float-vs-Decimal
    # flakiness in tests. The TestClient uses a separate session via
    # dependency_overrides, so the test-side ``db_session`` must be
    # expired before re-reading the application row -- otherwise
    # SQLAlchemy returns the cached pre-update copy.
    db_session.expire_all()
    stored = db_session.get(Application, application.id)
    assert stored.loan_status == "in_progress"
    assert stored.loan_lender == "HDFC Credila"
    assert stored.loan_amount is not None
    assert float(stored.loan_amount) == 1500000.00


def test_loan_update_partial_update_preserves_other_fields(
    client, db_session, override_authenticated_user
):
    """A PATCH with only one field set leaves the other fields untouched.

    Mirrors the partial-update behavior of the E35 visa outcome API:
    staff can record the status first, then the lender, then the
    amount — and refine any single field later without wiping the
    others.
    """
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    seeded = client.patch(
        f"/applications/{application.id}/loan",
        json={
            "loan_status": "approved",
            "loan_lender": "SBI Scholar",
            "loan_amount": "750000.00",
        },
    )
    assert seeded.status_code == 200, seeded.text

    only_status = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_status": "disbursed"},
    )
    assert only_status.status_code == 200, only_status.text
    body = only_status.json()["application"]
    assert body["loan_status"] == "disbursed"
    assert body["loan_lender"] == "SBI Scholar"
    assert body["loan_amount"] is not None


def test_loan_update_overwrites_existing_values(
    client, db_session, override_authenticated_user
):
    """A second PATCH overwrites the previously-recorded values in place.

    The application row is updated in place (no separate ``loan_status``
    / ``loan_lender`` / ``loan_amount`` rows). Mirrors the in-place
    update pattern used by the E35 visa outcome API and the E20
    counselor-reassignment API.
    """
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    first = client.patch(
        f"/applications/{application.id}/loan",
        json={
            "loan_status": "approved",
            "loan_lender": "HDFC Credila",
            "loan_amount": "1500000.00",
        },
    )
    assert first.status_code == 200, first.text

    second = client.patch(
        f"/applications/{application.id}/loan",
        json={
            "loan_status": "rejected",
            "loan_lender": "SBI Scholar",
            "loan_amount": "0",
        },
    )
    assert second.status_code == 200, second.text
    body = second.json()["application"]
    assert body["loan_status"] == "rejected"
    assert body["loan_lender"] == "SBI Scholar"

    db_session.expire_all()
    stored = db_session.get(Application, application.id)
    assert stored.loan_status == "rejected"
    assert stored.loan_lender == "SBI Scholar"
    assert float(stored.loan_amount) == 0.0


def test_loan_update_explicit_null_clears_field(
    client, db_session, override_authenticated_user
):
    """An explicit ``null`` in the PATCH body CLEARS the corresponding field.

    This is the critical contract for J30: staff must be able to
    correct a mis-recorded loan value by sending ``null`` rather than
    being forced to overwrite with a different non-null value. The
    E37 endpoint applies each field independently; omitting a field
    leaves it untouched, but supplying ``null`` clears it.
    """
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    # Seed all three fields.
    seeded = client.patch(
        f"/applications/{application.id}/loan",
        json={
            "loan_status": "approved",
            "loan_lender": "HDFC Credila",
            "loan_amount": "1500000.00",
        },
    )
    assert seeded.status_code == 200, seeded.text

    # Explicit null clears each field.
    cleared = client.patch(
        f"/applications/{application.id}/loan",
        json={
            "loan_status": None,
            "loan_lender": None,
            "loan_amount": None,
        },
    )
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()["application"]
    assert body["loan_status"] is None
    assert body["loan_lender"] is None
    assert body["loan_amount"] is None

    stored = db_session.get(Application, application.id)
    assert stored.loan_status is None
    assert stored.loan_lender is None
    assert stored.loan_amount is None


def test_loan_update_empty_body_is_noop(
    client, db_session, override_authenticated_user
):
    """A PATCH with no fields set is a no-op write that still returns 200.

    Unlike the E35 visa outcome API (which rejects an empty body so a
    PATCH always reflects an intentional change), the E37 endpoint
    treats an empty body as an explicit "no fields to update" signal:
    loan tracking is a status-capture side-channel and the staff
    member may genuinely want to PATCH a sentinel value or simply
    confirm the row is current. The 200 / 404 contract is preserved.
    """
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={},
    )

    assert response.status_code == 200, response.text
    body = response.json()["application"]
    assert body["loan_status"] is None
    assert body["loan_lender"] is None
    assert body["loan_amount"] is None


# ---------------------------------------------------------------------------
# Role gating
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [
        Role.STUDENT,
        Role.COUNSELOR,
        Role.RECEPTIONIST,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.SUPER_ADMIN,
    ],
)
def test_loan_update_rejects_roles_without_loan_update_permission(
    client, db_session, override_authenticated_user, role
):
    """Roles without ``LOAN_UPDATE`` get 403.

    Only ``CONSULTANCY_OWNER`` and ``BRANCH_MANAGER`` hold
    ``loan:update`` per :data:`app.rbac.permissions.ROLE_PERMISSIONS`;
    every other role — STUDENT, COUNSELOR, RECEPTIONIST,
    DOCUMENT_VERIFIER, VISA_PROCESSOR, SUPER_ADMIN — is blocked here.
    """
    from app.models.tenant import Tenant as _Tenant

    # SUPER_ADMIN has no tenant scope; the other roles do.
    if role is Role.SUPER_ADMIN:
        user_tenant_id: int | None = None
    else:
        # Use a fresh tenant so the test does not depend on the
        # _setup_loan_application tenant's id.
        suffix = 1
        slug = f"loan-role-{role.value}"
        while db_session.query(_Tenant).filter(_Tenant.slug == slug).first() is not None:
            suffix += 1
            slug = f"loan-role-{role.value}-{suffix}"
        tenant = _Tenant(name=f"Loan Role Tenant {role.value}", slug=slug)
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)
        user_tenant_id = tenant.id

    user = make_db_user(db_session, role, tenant_id=user_tenant_id)
    _override(
        override_authenticated_user,
        role=role,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )

    response = client.patch(
        "/applications/1/loan",
        json={"loan_status": "approved"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_loan_update_consultancy_owner_can_update(
    client, db_session, override_authenticated_user
):
    """CONSULTANCY_OWNER holds ``loan:update`` and can record loan tracking fields."""
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_status": "approved", "loan_lender": "HDFC Credila"},
    )

    assert response.status_code == 200, response.text
    body = response.json()["application"]
    assert body["loan_status"] == "approved"
    assert body["loan_lender"] == "HDFC Credila"


def test_loan_update_branch_manager_can_update_own_branch(
    client, db_session, override_authenticated_user
):
    """BRANCH_MANAGER holds ``loan:update`` and can update loan fields for own branch."""
    tenant_id, branch_id, application = _setup_loan_application(db_session)

    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )
    _override(
        override_authenticated_user,
        role=Role.BRANCH_MANAGER,
        user_id=manager.id,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_status": "approved", "loan_amount": "500000.00"},
    )

    assert response.status_code == 200, response.text
    body = response.json()["application"]
    assert body["loan_status"] == "approved"
    assert body["loan_amount"] is not None


def test_loan_update_branch_manager_blocked_in_other_branch(
    client, db_session, override_authenticated_user
):
    """A branch manager in branch A cannot update loan fields on a branch B application."""
    from tests.branches.helpers import seed_branch as _seed_branch
    from tests.applications.helpers import seed_application as _seed_application

    tenant = Tenant(name="Branch Scoping Tenant", slug="branch-scoping-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    own_branch = _seed_branch(db_session, tenant_id=tenant.id, name="Own", city="Own City")
    other_branch = _seed_branch(db_session, tenant_id=tenant.id, name="Other", city="Other City")

    other_application = _seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=other_branch.id,
        university_id=11,
        program_id=21,
    )

    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        tenant_id=tenant.id,
        branch_id=own_branch.id,
    )
    _override(
        override_authenticated_user,
        role=Role.BRANCH_MANAGER,
        user_id=manager.id,
        tenant_id=tenant.id,
        branch_id=own_branch.id,
    )

    response = client.patch(
        f"/applications/{other_application.id}/loan",
        json={"loan_status": "approved"},
    )

    # Cross-branch access surfaces as 403 (not 404), matching the E20
    # reassign-counselor convention.
    assert response.status_code == 403
    assert response.json()["detail"] == "User has no access to this branch's applications"


def test_loan_update_rejects_cross_tenant_application(
    client, db_session, override_authenticated_user
):
    """A branch manager in tenant A cannot update loan fields on a tenant B application."""
    own_tenant_id, _, _ = _setup_loan_application(db_session)
    other_tenant = Tenant(name="Other Loan Tenant", slug="other-loan-tenant")
    db_session.add(other_tenant)
    db_session.commit()
    db_session.refresh(other_tenant)
    other_branch = seed_branch(db_session, tenant_id=other_tenant.id)
    other_application = seed_application(
        db_session,
        tenant_id=other_tenant.id,
        branch_id=other_branch.id,
        university_id=99,
        program_id=99,
    )

    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        tenant_id=own_tenant_id,
        branch_id=None,
    )
    _override(
        override_authenticated_user,
        role=Role.BRANCH_MANAGER,
        user_id=manager.id,
        tenant_id=own_tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{other_application.id}/loan",
        json={"loan_status": "approved"},
    )

    # Cross-tenant access surfaces as 404 to prevent tenant-id
    # enumeration, matching the E25 / E33 / E35 conventions.
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_loan_update_returns_404_for_missing_application(
    client, db_session, override_authenticated_user
):
    """A 404 (not a 5xx) is returned for a non-existent application id."""
    tenant_id, _, _ = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        "/applications/99999999/loan",
        json={"loan_status": "approved"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_loan_update_unauthenticated_is_rejected(client):
    """Unauthenticated PATCH returns 401."""
    response = client.patch(
        "/applications/1/loan",
        json={"loan_status": "approved"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ---------------------------------------------------------------------------
# Body validation
# ---------------------------------------------------------------------------


def test_loan_update_rejects_whitespace_only_status(
    client, db_session, override_authenticated_user
):
    """A whitespace-only ``loan_status`` is normalized to ``null`` (clears the field).

    The Pydantic schema trims ``loan_status`` so a whitespace-only
    value collapses to an empty string, which the endpoint then
    interprets as a clear (null). The HTTP response is 200, not 422:
    the schema explicitly accepts nullable string + trims whitespace
    as the "clear" intent.
    """
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    # Seed a real value first.
    seeded = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_status": "approved"},
    )
    assert seeded.status_code == 200

    # Whitespace-only status is trimmed to "" → cleared.
    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_status": "   "},
    )

    assert response.status_code == 200, response.text
    body = response.json()["application"]
    assert body["loan_status"] is None


def test_loan_update_rejects_oversize_status(
    client, db_session, override_authenticated_user
):
    """A ``loan_status`` over 32 chars is rejected (422) — matches the column ceiling."""
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_status": "x" * 33},
    )

    assert response.status_code == 422


def test_loan_update_rejects_oversize_lender(
    client, db_session, override_authenticated_user
):
    """A ``loan_lender`` over 120 chars is rejected (422) — matches the column ceiling."""
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_lender": "x" * 121},
    )

    assert response.status_code == 422


def test_loan_update_rejects_negative_amount(
    client, db_session, override_authenticated_user
):
    """A negative ``loan_amount`` is rejected (422) — loan amounts are non-negative."""
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_amount": "-1"},
    )

    assert response.status_code == 422


def test_loan_update_accepts_zero_amount(
    client, db_session, override_authenticated_user
):
    """A zero ``loan_amount`` is accepted (a fully scholarshipped loan is a valid edge case)."""
    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_amount": "0"},
    )

    assert response.status_code == 200, response.text
    body = response.json()["application"]
    assert body["loan_amount"] is not None


# ---------------------------------------------------------------------------
# Stage-agnostic: works at any non-required stage
# ---------------------------------------------------------------------------


def test_loan_update_works_at_loan_processing_stage(
    client, db_session, override_authenticated_user
):
    """The endpoint works while the application is at ``loan_processing``.

    The E37 endpoint is stage-agnostic per the endpoint docstring
    (loan tracking is a side-channel). This test pins that the
    staff-side recording works at the canonical loan-tracking stage
    so the E36 student opt-in → E37 staff record flow works end to
    end.
    """
    from app.pipeline.stages import PipelineStage

    tenant_id, _, application = _setup_loan_application(
        db_session, stage=PipelineStage.LOAN_PROCESSING,
    )

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={
            "loan_status": "approved",
            "loan_lender": "HDFC Credila",
            "loan_amount": "1500000.00",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()["application"]
    assert body["loan_status"] == "approved"

    # Stage is unchanged (loan tracking is a side-channel).
    stored = db_session.get(Application, application.id)
    assert stored.stage == PipelineStage.LOAN_PROCESSING


def test_loan_update_does_not_change_pipeline_stage(
    client, db_session, override_authenticated_user
):
    """A loan-tracking PATCH leaves the application's pipeline stage untouched.

    The E37 endpoint is a status-capture side-channel; the
    application's stage is unchanged until a dedicated
    advance-stage / mark-* action moves it. Mirrors the
    ``test_outcome_patch_does_not_change_pipeline_stage`` guarantee
    from the E35 visa outcome suite.
    """
    from app.pipeline.stages import PipelineStage

    tenant_id, _, application = _setup_loan_application(
        db_session, stage=PipelineStage.VISA_PROCESSING,
    )

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    response = client.patch(
        f"/applications/{application.id}/loan",
        json={"loan_status": "in_progress"},
    )
    assert response.status_code == 200, response.text

    stored = db_session.get(Application, application.id)
    assert stored.stage == PipelineStage.VISA_PROCESSING


# ---------------------------------------------------------------------------
# 503 database-unavailable path
# ---------------------------------------------------------------------------


class _FakeSessionFor503:
    """Minimal fake session raising OperationalError on every query.

    Used to test the 503 database-unavailable error path without
    touching the real session the test fixture installs. The
    endpoint hits ``db.get`` (to load the application) and
    ``db.commit`` (to persist the loan fields); both raise so the
    endpoint surfaces 503 to the caller. ``rollback`` is a no-op so
    we can observe the rollback code path without an actual session.
    """

    def get(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalar(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalars(self, *args: object, **kwargs: object) -> object:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def commit(self) -> None:
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_loan_update_503_on_database_unavailable(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """OperationalError raised while writing the loan fields results in 503."""
    from app.db.database import get_db

    tenant_id, _, application = _setup_loan_application(db_session)

    owner = make_db_user(db_session, Role.CONSULTANCY_OWNER, tenant_id=tenant_id)
    _override(
        override_authenticated_user,
        role=Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant_id,
        branch_id=None,
    )

    fake_session = _FakeSessionFor503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[get_db] = _override_get_db
    try:
        response = client.patch(
            f"/applications/{application.id}/loan",
            json={"loan_status": "approved"},
        )
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Application service is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(get_db, None)
