"""Tests for the per-tier usage limit enforcement service (E9 task #107).

Covers the helper module directly:

* ``get_tenant_plan`` returns the assigned plan row (or ``None`` when
  no plan is set / the FK is dangling).
* The three ``enforce_*_limit`` functions no-op when the tenant has
  no plan assigned (every existing tenant pre-#106), so they do not
  block ordinary E11 / E12 / E16 / E17 create flows.
* They no-op when the plan's cap is ``NULL`` (Enterprise tier --
  Requirements §4 "unlimited/custom").
* They raise :exc:`PlanLimitExceeded` once the tenant's current count
  reaches the cap, and the exception carries the resource name, the
  limit, and the plan tier code so the HTTP layer can render a
  stable 422 detail.
* The current-count helpers (``_count_branches`` / ``_count_staff``
  / ``_count_students``) count only the rows owned by the tenant
  under inspection -- a neighbour tenant's rows do not leak into the
  headcount.

These tests are *white-box* (they hit the helper directly). The
end-to-end wiring of the helper into the routers is covered by the
sibling black-box integration tests under ``tests/services/
test_plan_limits_integration.py`` (which exercise the actual HTTP
endpoints so the 422 contract on ``POST /branches``, ``POST /staff``,
``POST /students`` and ``POST /auth/register-student`` is locked in
without depending on this module's internals).
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac.roles import Role
from app.services.plan_limits import (
    PlanLimitExceeded,
    enforce_branch_limit,
    enforce_staff_limit,
    enforce_student_limit,
    get_tenant_plan,
)
from tests.branches.helpers import seed_branch
from tests.factories.ids import next_test_id


def _make_plan(
    db_session,
    *,
    code: PlanTier,
    name: str,
    max_branches: int | None,
    max_staff: int | None,
    max_students: int | None,
) -> Plan:
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=code,
        name=name,
        max_branches=max_branches,
        max_staff=max_staff,
        max_students=max_students,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def _make_tenant(db_session, *, plan_id: int | None = None) -> Tenant:
    now = datetime.now(timezone.utc)
    seq = next_test_id()
    tenant = Tenant(
        name=f"Tenant {seq}",
        slug=f"tenant-{seq}",
        plan_id=plan_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _make_staff(db_session, *, tenant_id: int, role: Role = Role.COUNSELOR) -> User:
    now = datetime.now(timezone.utc)
    seq = next_test_id()
    user = User(
        email=f"{role.value}-{seq}@example.test",
        password_hash="x",
        role=role,
        tenant_id=tenant_id,
        branch_id=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_student(db_session, *, tenant_id: int) -> User:
    now = datetime.now(timezone.utc)
    seq = next_test_id()
    user = User(
        email=f"student-{seq}@example.test",
        password_hash="x",
        role=Role.STUDENT,
        tenant_id=tenant_id,
        branch_id=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_get_tenant_plan_returns_none_when_plan_id_is_null(db_session):
    """Tenants without an assigned plan return None (no enforcement)."""
    tenant = _make_tenant(db_session, plan_id=None)

    assert get_tenant_plan(db_session, tenant.id) is None


def test_get_tenant_plan_returns_assigned_plan(db_session):
    """A tenant with ``plan_id`` set returns the matching Plan row."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)

    resolved = get_tenant_plan(db_session, tenant.id)

    assert resolved is not None
    assert resolved.id == plan.id
    assert resolved.code == PlanTier.STARTER


def test_get_tenant_plan_returns_none_for_unknown_tenant(db_session):
    """``get_tenant_plan`` is defensive: an unknown tenant_id returns None."""
    assert get_tenant_plan(db_session, 999_999) is None


def test_get_tenant_plan_returns_none_for_dangling_fk(db_session):
    """A dangling ``plan_id`` (FK target row missing) returns None.

    ``ON DELETE RESTRICT`` on ``tenants.plan_id`` normally prevents
    this state, but the enforcement layer must not 500 on a stale
    pointer: the contract is "no plan => no enforcement".
    """
    tenant = _make_tenant(db_session, plan_id=42_424_242)

    assert get_tenant_plan(db_session, tenant.id) is None


def test_enforce_branch_limit_is_noop_when_no_plan_assigned(db_session):
    """A tenant with no plan can create unlimited branches."""
    tenant = _make_tenant(db_session, plan_id=None)
    seed_branch(db_session, tenant_id=tenant.id)
    seed_branch(db_session, tenant_id=tenant.id, name="Branch 2", city="Delhi")

    enforce_branch_limit(db_session, tenant.id)  # must not raise


def test_enforce_branch_limit_is_noop_when_plan_cap_is_null(db_session):
    """Enterprise-style plans with NULL caps do not enforce (Requirements §4)."""
    plan = _make_plan(
        db_session,
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    for i in range(5):
        seed_branch(db_session, tenant_id=tenant.id, name=f"B{i}", city="City")

    enforce_branch_limit(db_session, tenant.id)  # must not raise


def test_enforce_branch_limit_raises_when_at_cap(db_session):
    """Hitting the branch cap raises PlanLimitExceeded with full diagnostics."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    seed_branch(db_session, tenant_id=tenant.id)  # tenant is already at cap

    with pytest.raises(PlanLimitExceeded) as exc_info:
        enforce_branch_limit(db_session, tenant.id)

    assert exc_info.value.resource == "branches"
    assert exc_info.value.limit == 1
    assert exc_info.value.plan_code == "starter"


def test_enforce_branch_limit_allows_one_below_cap(db_session):
    """A tenant one below the cap is not yet at the limit."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=2,
        max_staff=5,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    seed_branch(db_session, tenant_id=tenant.id)  # 1 of 2 -- one slot left

    enforce_branch_limit(db_session, tenant.id)  # must not raise


def test_enforce_branch_limit_only_counts_caller_tenants_branches(db_session):
    """Branches from a neighbour tenant do not consume the cap.

    Tenant 1 sits on the Starter plan (cap=1) and is already at the
    cap, so its check must raise. The neighbour tenant is on the
    Growth plan (cap=5) and has zero branches, so its check must
    not raise -- proving the headcount filter is per-tenant and
    does not leak neighbour branches into the caller's count.
    """
    starter = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    growth = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=200,
    )
    tenant = _make_tenant(db_session, plan_id=starter.id)
    seed_branch(db_session, tenant_id=tenant.id)  # tenant 1 at cap
    # Neighbour tenant is independent: its branches must not push
    # tenant 1 past its cap, and tenant 1's branches must not push
    # the neighbour past its own (looser) cap.
    other_tenant = _make_tenant(db_session, plan_id=growth.id)
    seed_branch(db_session, tenant_id=other_tenant.id, name="Other", city="Other")

    with pytest.raises(PlanLimitExceeded):
        enforce_branch_limit(db_session, tenant.id)
    # The other tenant has 1 branch under a cap=5 Growth plan.
    enforce_branch_limit(db_session, other_tenant.id)  # must not raise


def test_enforce_staff_limit_raises_when_at_cap(db_session):
    """Hitting the staff cap raises with resource='staff'."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=2,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    _make_staff(db_session, tenant_id=tenant.id, role=Role.COUNSELOR)
    _make_staff(db_session, tenant_id=tenant.id, role=Role.DOCUMENT_VERIFIER)

    with pytest.raises(PlanLimitExceeded) as exc_info:
        enforce_staff_limit(db_session, tenant.id)

    assert exc_info.value.resource == "staff"
    assert exc_info.value.limit == 2
    assert exc_info.value.plan_code == "starter"


def test_enforce_staff_limit_does_not_count_students(db_session):
    """Student rows are counted by ``max_students``, not ``max_st staff``."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=1,
        max_students=10,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    _make_staff(db_session, tenant_id=tenant.id, role=Role.COUNSELOR)  # at cap
    _make_student(db_session, tenant_id=tenant.id)  # student does NOT count

    with pytest.raises(PlanLimitExceeded):
        enforce_staff_limit(db_session, tenant.id)
    # ... but the student cap is not yet hit:
    enforce_student_limit(db_session, tenant.id)


def test_enforce_staff_limit_is_noop_when_no_plan_assigned(db_session):
    """A tenant with no plan can create unlimited staff."""
    tenant = _make_tenant(db_session, plan_id=None)
    for _ in range(3):
        _make_staff(db_session, tenant_id=tenant.id)

    enforce_staff_limit(db_session, tenant.id)  # must not raise


def test_enforce_staff_limit_counts_all_staff_role_variants(db_session):
    """Every staff role (manager/counselor/verifier/visa/receptionist) counts."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    for role in (
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
    ):
        _make_staff(db_session, tenant_id=tenant.id, role=role)

    with pytest.raises(PlanLimitExceeded):
        enforce_staff_limit(db_session, tenant.id)


def test_enforce_student_limit_raises_when_at_cap(db_session):
    """Hitting the student cap raises with resource='students'."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=2,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    _make_student(db_session, tenant_id=tenant.id)
    _make_student(db_session, tenant_id=tenant.id)

    with pytest.raises(PlanLimitExceeded) as exc_info:
        enforce_student_limit(db_session, tenant.id)

    assert exc_info.value.resource == "students"
    assert exc_info.value.limit == 2
    assert exc_info.value.plan_code == "starter"


def test_enforce_student_limit_does_not_count_staff(db_session):
    """Staff rows are counted by ``max_staff``, not ``max_students``."""
    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=10,
        max_students=1,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    _make_student(db_session, tenant_id=tenant.id)  # at cap
    _make_staff(db_session, tenant_id=tenant.id, role=Role.COUNSELOR)  # not a student

    with pytest.raises(PlanLimitExceeded):
        enforce_student_limit(db_session, tenant.id)
    # ... but the staff cap is not yet hit:
    enforce_staff_limit(db_session, tenant.id)


def test_enforce_student_limit_is_noop_when_no_plan_assigned(db_session):
    """A tenant with no plan can register unlimited students."""
    tenant = _make_tenant(db_session, plan_id=None)
    for _ in range(5):
        _make_student(db_session, tenant_id=tenant.id)

    enforce_student_limit(db_session, tenant.id)  # must not raise


def test_enforce_student_limit_only_counts_caller_tenants_students(db_session):
    """Students from a neighbour tenant do not consume the cap.

    Tenant 1 sits on the Starter plan (cap=1) and is already at the
    cap, so its check must raise. The neighbour tenant is on the
    Growth plan (cap=10) with a different student, so its check must
    not raise -- proving the headcount filter is per-tenant.
    """
    starter = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=1,
    )
    growth = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=10,
    )
    tenant = _make_tenant(db_session, plan_id=starter.id)
    _make_student(db_session, tenant_id=tenant.id)  # at cap
    other_tenant = _make_tenant(db_session, plan_id=growth.id)
    _make_student(db_session, tenant_id=other_tenant.id)  # different tenant

    with pytest.raises(PlanLimitExceeded):
        enforce_student_limit(db_session, tenant.id)
    # The other tenant has 1 student under a cap=10 Growth plan.
    enforce_student_limit(db_session, other_tenant.id)  # must not raise


def test_plan_id_fk_rejects_unknown_plan_id(db_session):
    """``tenants.plan_id`` is enforced as a real FK (RESTRICT semantics).

    The FK check fires at flush time (not at ``setattr`` time), so we
    explicitly ``flush()`` to trigger it -- the production code path
    never sees a row that bypasses the flush because every
    tenant-create call wraps the row in a unit of work that commits.
    """
    tenant = _make_tenant(db_session, plan_id=None)
    tenant.plan_id = 99_999_999  # no such plan row
    db_session.add(tenant)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()