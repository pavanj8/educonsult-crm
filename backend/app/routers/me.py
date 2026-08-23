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
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.meeting import Meeting
from app.rbac.dependencies import require_permission
from app.rbac.permissions import Permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.meeting import MeetingResponse

router = APIRouter(prefix="/me", tags=["me"])

_STUDENT_ONLY_DETAIL = "Only students can access this endpoint"


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
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MEETING_READ)),
    ],
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
