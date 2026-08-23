"""Meeting scheduling endpoints (E22; Journey J15).

Schedule / list / update meeting API for the counseling domain (J15).
Tenant and branch scoping are enforced through the shared
``apply_tenant_scope`` / ``apply_branch_scope`` helpers from
``app/db`` to match the rest of the codebase (ADR-0004).
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.branch_scope import BranchScopeError, apply_branch_scope
from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application
from app.models.meeting import Meeting
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.meeting import MeetingCreate, MeetingResponse, MeetingUpdate

router = APIRouter(prefix="/meetings", tags=["meetings"])

_DB_UNAVAILABLE_DETAIL = "Meeting service is temporarily unavailable"
_APPLICATION_NOT_FOUND_DETAIL = "Application not found"
_BRANCH_ACCESS_DENIED_DETAIL = "User has no access to this application"
_MEETING_NOT_FOUND_DETAIL = "Meeting not found"
_STUDENT_MISMATCH_DETAIL = "Student is not the application's student"
_COUNSELOR_NOT_FOUND_DETAIL = "Counselor not found"
_APPLICATION_NOT_ASSIGNED_DETAIL = (
    "Application has no assigned counselor; cannot schedule meeting"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _handle_db_error(exc: OperationalError, *, rollback: bool, db: Session | None = None) -> None:
    """Convert an :class:`OperationalError` into a 503 HTTPException.

    ``rollback=True`` performs ``db.rollback()`` before raising so the
    session is left in a usable state for the next request; the read-only
    path passes ``rollback=False`` (no pending mutations to roll back).
    Centralizing the message here keeps the 4x ``try/except
    OperationalError -> 503`` boilerplate out of each handler.
    """
    if rollback and db is not None:
        db.rollback()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_DB_UNAVAILABLE_DETAIL,
    ) from exc


def _load_application(
    db: Session, application_id: int, user: AuthenticatedUser
) -> Application:
    """Load the application's parent application, enforcing tenant + branch scope.

    Branch-scoped actors (counselor, branch manager) are restricted to
    applications in their own branch. Consultancy owners keep
    cross-branch visibility by design (ADR-0004). Counselors must also
    be the assigned counselor on the application; a missing counselor
    assignment is surfaced as 409 (not 403) so consumers can distinguish
    "wrong counselor" from "no counselor assigned yet".
    """
    try:
        application = db.get(Application, application_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if application is None or application.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_APPLICATION_NOT_FOUND_DETAIL,
        )

    try:
        scoped_statement: Select[tuple[Application]] = apply_tenant_scope(
            select(Application).where(Application.id == application.id),
            Application,
            user,
        )
        if user.role not in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER):
            scoped_statement = apply_branch_scope(scoped_statement, Application, user)
    except (TenantScopeError, BranchScopeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_BRANCH_ACCESS_DENIED_DETAIL,
        ) from None

    if db.execute(scoped_statement.limit(1)).scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_BRANCH_ACCESS_DENIED_DETAIL,
        )

    if user.role == Role.COUNSELOR:
        if application.assigned_counselor_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_APPLICATION_NOT_ASSIGNED_DETAIL,
            )
        if application.assigned_counselor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Meeting is not assigned to this counselor",
            )

    return application


def _validate_people(
    db: Session,
    user: AuthenticatedUser,
    app: Application,
    student_id: int,
    counselor_id: int,
) -> None:
    """Validate that the named student + counselor exist, are tenant-scoped, and match the application."""
    try:
        student = db.get(User, student_id)
        counselor = db.get(User, counselor_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if (
        student is None
        or student.tenant_id != user.tenant_id
        or student.id != app.student_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_STUDENT_MISMATCH_DETAIL,
        )

    if (
        counselor is None
        or counselor.tenant_id != user.tenant_id
        or counselor.role != Role.COUNSELOR
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_COUNSELOR_NOT_FOUND_DETAIL,
        )


def _scoped_meetings_query(
    db: Session, user: AuthenticatedUser
) -> Select[tuple[Meeting]]:
    """Return a tenant + branch-scoped SELECT on ``Meeting``.

    Branch-scoped actors (counselor, branch manager) are restricted to
    meetings whose parent application lives in their own branch.
    Counselors also see only meetings where they are the assigned
    counselor. Students see only their own meetings (filtered by
    ``student_id``).
    """
    statement: Select[tuple[Meeting]] = apply_tenant_scope(
        select(Meeting), Meeting, user
    )

    if user.role == Role.STUDENT:
        return statement.where(Meeting.student_id == user.id)

    return statement


def _enforce_meeting_branch_scope(
    db: Session, user: AuthenticatedUser, meeting: Meeting
) -> None:
    """Branch-scope a single meeting for branch-scoped actors."""
    if user.role in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER):
        return

    if user.role == Role.STUDENT:
        if meeting.student_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Meeting is not visible to this student",
            )
        return

    if user.role == Role.COUNSELOR:
        if meeting.counselor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Meeting is not assigned to this counselor",
            )
        return

    if user.role == Role.BRANCH_MANAGER:
        # Need to look up the parent application to compare branch_id.
        try:
            application = db.get(Application, meeting.application_id)
        except OperationalError as exc:
            _handle_db_error(exc, rollback=False)
        if (
            application is None
            or application.tenant_id != user.tenant_id
            or user.branch_id is None
            or application.branch_id != user.branch_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_BRANCH_ACCESS_DENIED_DETAIL,
            )


def _load_meeting(
    db: Session, meeting_id: int, user: AuthenticatedUser
) -> Meeting:
    """Load a meeting with full tenant + branch + role scoping."""
    try:
        meeting = db.get(Meeting, meeting_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if meeting is None or meeting.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_MEETING_NOT_FOUND_DETAIL,
        )

    _enforce_meeting_branch_scope(db, user, meeting)
    return meeting


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def schedule_meeting(
    payload: MeetingCreate,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MEETING_SCHEDULE)),
    ],
    db: Session = Depends(get_db),
) -> Meeting:
    """Schedule a new meeting (J15).

    Counselors may only schedule meetings for applications they are
    assigned to, and only for themselves as the counselor. Branch
    managers may schedule any meeting in their branch. Consultancy
    owners may schedule any meeting in their tenant.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    application = _load_application(db, payload.application_id, current_user)

    if (
        current_user.role == Role.COUNSELOR
        and payload.counselor_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Counselors may only schedule their own meetings",
        )

    if (
        current_user.role == Role.BRANCH_MANAGER
        and current_user.branch_id is not None
        and payload.counselor_id != current_user.id
    ):
        # The owning counselor's User row must be looked up to verify
        # the counselor is in the same branch as the caller.
        try:
            counselor = db.get(User, payload.counselor_id)
        except OperationalError as exc:
            _handle_db_error(exc, rollback=False)
        if (
            counselor is None
            or counselor.tenant_id != current_user.tenant_id
            or counselor.role != Role.COUNSELOR
            or counselor.branch_id != current_user.branch_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=_COUNSELOR_NOT_FOUND_DETAIL,
            )

    _validate_people(db, current_user, application, payload.student_id, payload.counselor_id)

    now = _utc_now()
    meeting = Meeting(
        tenant_id=current_user.tenant_id,
        application_id=payload.application_id,
        student_id=payload.student_id,
        counselor_id=payload.counselor_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        location=payload.location,
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(meeting)
    try:
        db.commit()
    except OperationalError as exc:
        _handle_db_error(exc, rollback=True, db=db)

    db.refresh(meeting)
    return meeting


@router.get("", response_model=list[MeetingResponse])
def list_meetings(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MEETING_READ)),
    ],
    db: Session = Depends(get_db),
    application_id: int | None = Query(default=None, gt=0),
    student_id: int | None = Query(default=None, gt=0),
) -> list[Meeting]:
    """List meetings visible to the caller (J15).

    Tenant + branch scoping is applied through
    :func:`_scoped_meetings_query`. Counselors see only their own
    meetings; branch managers see meetings for applications in their
    branch; consultancy owners see all meetings in their tenant;
    students see only meetings where they are the named student.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        statement = _scoped_meetings_query(db, current_user)

        # Branch manager: restrict to meetings whose parent application
        # is in the caller's branch. Use a join so the helper's
        # branch-scoping semantics apply consistently.
        if current_user.role == Role.BRANCH_MANAGER:
            if current_user.branch_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_BRANCH_ACCESS_DENIED_DETAIL,
                )
            statement = (
                statement.join(Application, Meeting.application_id == Application.id)
                .where(Application.branch_id == current_user.branch_id)
            )
        elif current_user.role == Role.COUNSELOR:
            # Counselors: only their own meetings AND in their branch.
            statement = statement.where(Meeting.counselor_id == current_user.id)
            statement = (
                statement.join(Application, Meeting.application_id == Application.id)
                .where(Application.branch_id == current_user.branch_id)
            )

        if application_id is not None:
            statement = statement.where(Meeting.application_id == application_id)
        if student_id is not None:
            statement = statement.where(Meeting.student_id == student_id)

        statement = statement.order_by(Meeting.scheduled_at)
        return list(db.scalars(statement).all())
    except (TenantScopeError, BranchScopeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)


@router.patch("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MEETING_SCHEDULE)),
    ],
    db: Session = Depends(get_db),
) -> Meeting:
    """Update an existing meeting (J15).

    Tenant + branch + role scoping is enforced in :func:`_load_meeting`.
    Fields are applied via ``exclude_unset`` so an omitted field is left
    untouched rather than reset to its schema default.
    """
    meeting = _load_meeting(db, meeting_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(meeting, key, value)
    meeting.updated_at = _utc_now()
    try:
        db.commit()
    except OperationalError as exc:
        _handle_db_error(exc, rollback=True, db=db)

    db.refresh(meeting)
    return meeting
