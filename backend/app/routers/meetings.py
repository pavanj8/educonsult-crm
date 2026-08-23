"""Meeting scheduling endpoints (E22; Journey J15)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application
from app.models.meeting import Meeting
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.meeting import MeetingCreate, MeetingResponse, MeetingUpdate

router = APIRouter(prefix="/meetings", tags=["meetings"])
_DB_ERROR = "Meeting service is temporarily unavailable"


def _load_application(db: Session, application_id: int, user: AuthenticatedUser) -> Application:
    try:
        application = db.get(Application, application_id)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail=_DB_ERROR) from exc
    if application is None or application.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Application not found")
    if user.role in (Role.COUNSELOR, Role.BRANCH_MANAGER) and (
        user.branch_id is None or application.branch_id != user.branch_id
    ):
        raise HTTPException(status_code=403, detail="User has no access to this application")
    if user.role == Role.COUNSELOR and application.assigned_counselor_id != user.id:
        raise HTTPException(status_code=403, detail="Meeting is not assigned to this counselor")
    return application


def _validate_people(db: Session, user: AuthenticatedUser, app: Application, student_id: int, counselor_id: int) -> None:
    try:
        student = db.get(User, student_id)
        counselor = db.get(User, counselor_id)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail=_DB_ERROR) from exc
    if student is None or student.tenant_id != user.tenant_id or student.id != app.student_id:
        raise HTTPException(status_code=422, detail="Student is not the application's student")
    if counselor is None or counselor.tenant_id != user.tenant_id or counselor.role != Role.COUNSELOR:
        raise HTTPException(status_code=422, detail="Counselor not found")


def _load_meeting(db: Session, meeting_id: int, user: AuthenticatedUser) -> Meeting:
    try:
        meeting = db.get(Meeting, meeting_id)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail=_DB_ERROR) from exc
    if meeting is None or meeting.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if user.role == Role.COUNSELOR and meeting.counselor_id != user.id:
        raise HTTPException(status_code=403, detail="Meeting is not assigned to this counselor")
    return meeting


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def schedule_meeting(payload: MeetingCreate, current_user: Annotated[AuthenticatedUser, Depends(require_permission(Permission.MEETING_SCHEDULE))], db: Session = Depends(get_db)) -> Meeting:
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    application = _load_application(db, payload.application_id, current_user)
    if current_user.role == Role.COUNSELOR and payload.counselor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Counselors may only schedule their own meetings")
    _validate_people(db, current_user, application, payload.student_id, payload.counselor_id)
    meeting = Meeting(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(meeting)
    try:
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=_DB_ERROR) from exc
    db.refresh(meeting)
    return meeting


@router.get("", response_model=list[MeetingResponse])
def list_meetings(current_user: Annotated[AuthenticatedUser, Depends(require_permission(Permission.MEETING_READ))], db: Session = Depends(get_db), application_id: int | None = Query(default=None, gt=0), student_id: int | None = Query(default=None, gt=0)) -> list[Meeting]:
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        statement = select(Meeting).where(Meeting.tenant_id == current_user.tenant_id).order_by(Meeting.scheduled_at)
        if current_user.role == Role.COUNSELOR:
            statement = statement.where(Meeting.counselor_id == current_user.id)
        if application_id is not None:
            statement = statement.where(Meeting.application_id == application_id)
        if student_id is not None:
            statement = statement.where(Meeting.student_id == student_id)
        return list(db.scalars(statement).all())
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail=_DB_ERROR) from exc


@router.patch("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(meeting_id: int, payload: MeetingUpdate, current_user: Annotated[AuthenticatedUser, Depends(require_permission(Permission.MEETING_SCHEDULE))], db: Session = Depends(get_db)) -> Meeting:
    meeting = _load_meeting(db, meeting_id, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(meeting, key, value)
    try:
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=_DB_ERROR) from exc
    db.refresh(meeting)
    return meeting
