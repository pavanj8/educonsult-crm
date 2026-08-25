"""``/me/*`` self-service endpoints for the authenticated caller.

These endpoints resolve to the authenticated user's own data only,
independent of any tenant-admin role. They live under ``/me`` (rather
than being tacked onto a domain router) so the contract is obvious:
``GET /me/<thing>`` means "the caller's own <thing>".

Today this router exposes:

* ``GET /me/meetings`` -- the authenticated student's own meetings
  (E23; Journey J16; frontend ticket #162). Strictly student-scoped:
  any other role is rejected with 403 so a counselor or staff token
  cannot use the self-prefix to bypass the staff-side ``GET /meetings``
  route's role-aware scoping (the staff-side route exists for
  E22 / Journey J15 and enforces its own tenant + branch + role
  semantics; duplicating that surface here would be a scope-creep
  risk).
* ``GET /me/plan-usage`` -- the authenticated consultancy owner's own
  plan and usage summary (E45; Journey J38). Owner-only: returns the
  tenant's assigned subscription plan (tier + limits) and current
  usage counts (branches/staff/students).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.branch import Branch
from app.models.meeting import Meeting
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.meeting import MeetingResponse
from app.schemas.plan import PlanAndUsageResponse

router = APIRouter(prefix="/me", tags=["me"])

_STUDENT_ONLY_DETAIL = "Only students can access this endpoint"
_OWNER_ONLY_DETAIL = "Only consultancy owners can access this endpoint"


def _ensure_student(current_user: AuthenticatedUser) -> None:
    """Reject any caller that is not authenticated as a student.

    The frontend widget this backs (ticket #162, ``UpcomingMeetings``
    on the student dashboard) is only rendered for students. A
    counselor or staff token that hits ``/me/meetings`` must be turned
    away rather than silently handed an empty list: silent empties
    would mask a privilege-escalation regression where a staff-side
    token accidentally ends up routed through the self-prefix.
    """
    if current_user.role != Role.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_STUDENT_ONLY_DETAIL,
        )


@router.get("/meetings", response_model=list[MeetingResponse])
def list_my_meetings(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> list[Meeting]:
    """Return the authenticated student's meetings (E23; J16).

    The result is tenant-scoped through ``tenant_id`` and additionally
    constrained to ``Meeting.student_id == current_user.id`` -- two
    students in the same tenant receive disjoint result sets, and a
    cross-tenant caller's token sees no meetings from any other
    tenant. Meetings are returned in ``scheduled_at`` ascending order
    so the frontend widget's client-side filter for "upcoming" (E23
    acceptance criterion: "Student sees upcoming meetings") can render
    them with no further sorting. The endpoint deliberately returns
    *all* of the student's meetings (past and future); the widget
    filters to ``scheduled_at >= now`` defensively so this endpoint
    stays a thin, predictable list and so a future "past meetings"
    view (out of scope for ticket #162) can reuse it without an
    extra round-trip.

    The dependency is ``get_current_user`` rather than
    ``require_permission(MEETING_READ)`` because the role check is
    intentionally narrower than the permission check: a SUPER_ADMIN
    has ``NOTIFICATION_READ`` but no ``MEETING_READ``, and we want
    every non-student caller (regardless of which permission they do
    or don't have) to be rejected with the same specific
    "Only students can access this endpoint" message so the
    contract is uniform.
    """
    _ensure_student(current_user)

    if current_user.tenant_id is None:
        # The student role requires a tenant_id (RBAC) so this branch
        # is defensive only -- if it ever fires it means a corrupted
        # token slipped through and we must not leak the full table.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        statement = (
            select(Meeting)
            .where(
                Meeting.tenant_id == current_user.tenant_id,
                Meeting.student_id == current_user.id,
            )
            .order_by(Meeting.scheduled_at)
        )
        return list(db.scalars(statement).all())
    except OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meeting service is temporarily unavailable",
        ) from exc


def _ensure_owner(current_user: AuthenticatedUser) -> None:
    """Reject any caller that is not authenticated as a consultancy owner.

    The plan-usage endpoint (E45; Journey J38) is only rendered for
    consultancy owners. A student or staff token that hits
    ``/me/plan-usage`` must be turned away with 403.
    """
    if current_user.role != Role.CONSULTANCY_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_OWNER_ONLY_DETAIL,
        )


@router.get("/plan-usage", response_model=PlanAndUsageResponse)
def get_my_plan_and_usage(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> PlanAndUsageResponse:
    """Return the authenticated owner's tenant plan and usage (E45; J38).

    The endpoint returns:

    * The tenant's assigned plan (tier name, code, and limits). If the
      tenant has no plan assigned yet, ``plan`` is ``null``.
    * Current usage counts for the tenant (branches, staff, students).

    The endpoint is scoped to the authenticated user's tenant via
    ``current_user.tenant_id`` and role-gated to ``CONSULTANCY_OWNER`` so
    only owners can read their own consultancy's billing/usage data.

    Usage counts match the E9 task #107 enforcement semantics:
    * ``branches`` -- count of ``Branch`` rows for the tenant.
    * ``staff`` -- count of non-student ``User`` rows (counselors,
      verifiers, branch managers, visa processors, receptionists).
    * ``students`` -- count of ``User`` rows with ``role == 'student'``.

    The plan detail is loaded via the ``Tenant.plan`` relationship; if
    ``tenant.plan_id`` is NULL (no plan assigned), the response
    ``plan`` field is ``null`` and the frontend displays a "no plan
    assigned, contact platform admin" message.
    """
    _ensure_owner(current_user)

    if current_user.tenant_id is None:
        # The consultancy owner role requires a tenant_id (RBAC) so
        # this branch is defensive only.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        # Load the tenant with the plan relationship eager-loaded
        tenant = (
            db.query(Tenant)
            .filter(Tenant.id == current_user.tenant_id)
            .one_or_none()
        )

        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        # Count branches for this tenant
        branches_count = db.execute(
            select(func.count()).select_from(Branch).where(Branch.tenant_id == tenant.id)
        ).scalar_one()

        # Count staff (non-student users) for this tenant
        staff_count = db.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == tenant.id,
                User.role.in_(
                    [
                        Role.BRANCH_MANAGER,
                        Role.COUNSELOR,
                        Role.DOCUMENT_VERIFIER,
                        Role.VISA_PROCESSOR,
                        Role.RECEPTIONIST,
                    ]
                ),
            )
        ).scalar_one()

        # Count students for this tenant
        students_count = db.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == tenant.id, User.role == Role.STUDENT)
        ).scalar_one()

        return PlanAndUsageResponse(
            plan=tenant.plan,
            usage={
                "branches": branches_count,
                "staff": staff_count,
                "students": students_count,
            },
        )
    except OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plan and usage service is temporarily unavailable",
        ) from exc
