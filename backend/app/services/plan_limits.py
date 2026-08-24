"""Per-tier subscription usage limit enforcement (E9 task #107; Journey J2).

Requirements §4 Billing & Subscription spells out three plan tiers
(Starter / Growth / Enterprise) with per-tier caps on branches,
staff, and students. This module is the *enforcement* layer that
translates those caps into a hard error on the create-branch /
create-staff / create-student endpoints, so a tenant that has hit its
tier cap cannot grow past it through any UI flow.

Where the limits live
---------------------
The per-tier numbers themselves live on :class:`app.models.plan.Plan`
rows (Starter / Growth / Enterprise, with NULL meaning "unlimited"
for Enterprise per Requirements §4). The tenant -> plan pointer is
``tenants.plan_id``, set by the E9 task #106 super-admin assign-plan
API. **Both columns are pre-requisites of this module**: without
``tenants.plan_id`` (or with it NULL), enforcement is a no-op (the
tenant has not been assigned a tier yet, so we do not block
creation).

Why "no plan -> no enforcement" (and not "no plan -> reject")
-------------------------------------------------------------
The plan assignment ticket (#106) and this enforcement ticket (#107)
ship in different PRs. Until #106 lands on ``main``, every tenant
has no plan, and the entire platform must keep working -- including
the branch/staff/student create endpoints that downstream journeys
(J4 / J5 / J9 / J10) depend on. We therefore make enforcement a
strict superset of "no enforcement":

* If the tenant has no ``plan_id`` set, every check returns silently
  (no cap). When #106 starts assigning plans, those tenants begin
  to be enforced without any further change to this module.
* If the tenant's ``plan_id`` points at a row that no longer exists
  (defensive: e.g. the plan row was deleted despite the FK), we
  also fall through to no-cap rather than 500ing -- the FK is
  RESTRICT, so this is a paranoid case, not a normal one.
* If the plan's ``max_branches`` / ``max_staff`` / ``max_students``
  is NULL, we treat that as "unlimited" (the Enterprise tier
  advertises "unlimited/custom" per Requirements §4 and uses NULL
  as the no-cap sentinel -- see ``app.models.plan.Plan``).

Error contract
--------------
:exc:`PlanLimitExceeded` is raised when the tenant is at or above
its cap for the resource being created. The exception carries a
``resource`` string ("branches" / "staff" / "students") and a
``limit`` integer (the plan's cap) so the HTTP layer can render a
stable, helpful 422 response without re-reading the plan.

The HTTP layer converts :exc:`PlanLimitExceeded` to ``422
Unprocessable Entity`` (the limit is a *business-rule* violation, not
an authorization failure -- ``403`` would be misleading because the
caller *is* authorized to create, just not at this tier).

Why a separate ``PlanLimitExceeded`` exception
----------------------------------------------
We could re-use :class:`fastapi.HTTPException` directly, but:

* It keeps the service layer free of HTTP concerns, so the helper
  is unit-testable without a ``TestClient`` and stays usable from
  background jobs / CLI commands that do not go through HTTP.
* The exception carries typed fields (``resource``, ``limit``) so
  tests can assert on the diagnostic without parsing a string.

Traceability
------------
* Requirements §4 (3 subscription tiers with limits).
* Journey J2 (Super Admin sets/updates a tenant's subscription plan)
  -- the limits enforced here are the limits a Super Admin
  implicitly picks when they assign a tier.
* Epic E9 (Subscription Plan Assignment); this module is the
  enforcement half. The plan catalog (Starter/Growth/Enterprise +
  limits fields) is owned by E9 task #105; the assign/change plan
  API is owned by E9 task #106; the black-box tests for the
  whole epic are owned by E9 task #108.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.user import User

if TYPE_CHECKING:
    pass


class PlanLimitExceeded(Exception):
    """Raised when a tenant has reached its plan's cap for a resource.

    Attributes
    ----------
    resource:
        One of ``"branches"``, ``"staff"``, ``"students"`` -- the
        type of row that was being created. Stable lowercase plural.
    limit:
        The plan's cap for this resource (a positive integer; the
        NULL / "unlimited" path never raises this exception).
    plan_code:
        The :class:`~app.models.plan.PlanTier` value of the plan that
        was hit (``"starter"`` / ``"growth"`` / ``"enterprise"``).
        Included for diagnostic clarity in API responses and logs;
        the HTTP layer surfaces it in the 422 detail.
    """

    def __init__(self, *, resource: str, limit: int, plan_code: str) -> None:
        self.resource = resource
        self.limit = limit
        self.plan_code = plan_code
        super().__init__(
            f"Plan {plan_code!r} limit reached: max {limit} {resource}"
        )


def get_tenant_plan(db: Session, tenant_id: int) -> Plan | None:
    """Return the plan assigned to ``tenant_id`` or ``None``.

    Returns ``None`` if the tenant has no ``plan_id`` set (the common
    case on tenants created before a Super Admin has assigned a
    tier) or if the FK is somehow dangling (paranoid -- the schema's
    ``ON DELETE RESTRICT`` prevents a real plan row from going away
    while tenants still point at it).
    """
    plan_id = db.execute(
        select(Tenant.plan_id).where(Tenant.id == tenant_id)
    ).scalar_one_or_none()
    if plan_id is None:
        return None
    return db.get(Plan, plan_id)


def _count_branches(db: Session, tenant_id: int) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(Branch)
            .where(Branch.tenant_id == tenant_id)
        ).scalar_one()
    )


def _count_staff(db: Session, tenant_id: int) -> int:
    """Count *staff* rows (every non-student user) for ``tenant_id``.

    The cap on ``Plan.max_staff`` is about staff accounts (counselors,
    verifiers, branch managers, visa processors, receptionists).
    Students have their own ``max_students`` cap, so a tenant's
    student population does not eat into its staff headcount.
    """
    staff_roles = (
        User.role.in_(
            (
                "branch_manager",
                "counselor",
                "document_verifier",
                "visa_processor",
                "receptionist",
            )
        ),
    )
    return int(
        db.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == tenant_id, *staff_roles)
        ).scalar_one()
    )


def _count_students(db: Session, tenant_id: int) -> int:
    """Count *student* users for ``tenant_id``.

    Matches by ``role == "student"`` -- we do not constrain on
    ``is_active`` here because deactivated students still occupy a
    seat in the tenant's headcount (a reactivated row should not
    silently push the tenant past its cap). The plan limits are a
    structural ceiling on the tenant's student roster, not on its
    currently-active student logins.
    """
    return int(
        db.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == tenant_id, User.role == "student")
        ).scalar_one()
    )


def _check_limit(
    *,
    db: Session,
    tenant_id: int,
    limit_attr: str,
    current_count: int,
    resource: str,
) -> None:
    """Raise :exc:`PlanLimitExceeded` if ``current_count >= cap``.

    No-op when the tenant has no plan or when the plan's cap is NULL
    ("unlimited"). Kept private because the public entry points
    (:func:`enforce_branch_limit` / :func:`enforce_staff_limit` /
    :func:`enforce_student_limit`) are the only callers.
    """
    plan = get_tenant_plan(db, tenant_id)
    if plan is None:
        return
    cap = getattr(plan, limit_attr)
    if cap is None:
        return
    if current_count >= cap:
        raise PlanLimitExceeded(
            resource=resource,
            limit=cap,
            plan_code=plan.code.value,
        )


def enforce_branch_limit(db: Session, tenant_id: int) -> None:
    """Raise :exc:`PlanLimitExceeded` if ``tenant_id`` has hit its branch cap.

    Called by ``POST /branches`` (E11 / Journey J4) **before** a new
    ``Branch`` row is inserted, so the check counts the *existing*
    branches; the new branch being created pushes the count to
    ``existing + 1`` and would exceed the cap.
    """
    _check_limit(
        db=db,
        tenant_id=tenant_id,
        limit_attr="max_branches",
        current_count=_count_branches(db, tenant_id),
        resource="branches",
    )


def enforce_staff_limit(db: Session, tenant_id: int) -> None:
    """Raise :exc:`PlanLimitExceeded` if ``tenant_id`` has hit its staff cap.

    Called by ``POST /staff`` (E12 / Journey J5) **before** a new
    ``User`` row with a staff role is inserted. Counts the
    pre-insert staff roster so the to-be-created row tips the count
    past the cap.
    """
    _check_limit(
        db=db,
        tenant_id=tenant_id,
        limit_attr="max_staff",
        current_count=_count_staff(db, tenant_id),
        resource="staff",
    )


def enforce_student_limit(db: Session, tenant_id: int) -> None:
    """Raise :exc:`PlanLimitExceeded` if ``tenant_id`` has hit its student cap.

    Called by both ``POST /students`` (E17 / Journey J10 -- staff
    walk-in record creation) and ``POST /auth/register-student``
    (E16 / Journey J9 -- student self-registration) **before** the
    new ``User`` row with ``role=student`` is inserted.
    """
    _check_limit(
        db=db,
        tenant_id=tenant_id,
        limit_attr="max_students",
        current_count=_count_students(db, tenant_id),
        resource="students",
    )


__all__ = [
    "PlanLimitExceeded",
    "enforce_branch_limit",
    "enforce_staff_limit",
    "enforce_student_limit",
    "get_tenant_plan",
]