"""Counselor dashboard and queue routes (E21; Journey J14)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application, PipelineStage
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.application import ApplicationWithStudentResponse, CounselorQueueFilter

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Counselor service is temporarily unavailable"


def _get_counselor_applications_base_query(
    db: Session,
    current_user: AuthenticatedUser,
) -> select:
    """Build base query for counselor's assigned applications."""
    return (
        select(Application)
        .where(Application.assigned_counselor_id == current_user.id)
        .where(Application.tenant_id == current_user.tenant_id)
    )


def _build_student_join(query, db: Session, current_user: AuthenticatedUser):
    """Add LEFT JOIN with students table."""
    return query.join(
        User,
        User.id == Application.student_id,
        isouter=True,
    ).where(User.tenant_id == current_user.tenant_id)


@router.get("/queue", response_model=list[ApplicationWithStudentResponse])
def get_counselor_queue(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.APPLICATION_READ_ASSIGNED))
    ],
    db: Session = Depends(get_db),
    stage: PipelineStage | None = Query(default=None, description="Filter by pipeline stage"),
    search: str | None = Query(default=None, max_length=100, description="Search by student name or email"),
) -> list[ApplicationWithStudentResponse]:
    """Get the counselor's assigned application queue (E21; Journey J14).

    Returns applications assigned to the authenticated counselor with optional
    filtering by stage and/or search term.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        # Build base query for counselor's assigned applications
        query = _get_counselor_applications_base_query(db, current_user)

        # Apply stage filter if provided
        if stage is not None:
            query = query.where(Application.stage == stage)

        # Apply search filter if provided (search student name or email)
        if search:
            search_term = f"%{search.strip()}%"
            query = query.join(
                User,
                User.id == Application.student_id,
                isouter=True,
            ).where(
                (User.name.ilike(search_term)) | (User.email.ilike(search_term))
            )

        # Order by created_at descending (newest first)
        query = query.order_by(Application.created_at.desc())

        applications = list(db.scalars(query).all())

        # Build response with student details
        result: list[ApplicationWithStudentResponse] = []
        for app in applications:
            student = db.get(User, app.student_id)
            if student:
                result.append(
                    ApplicationWithStudentResponse(
                        id=app.id,
                        tenant_id=app.tenant_id,
                        student_id=app.student_id,
                        assigned_counselor_id=app.assigned_counselor_id,
                        target_university_id=app.target_university_id,
                        target_program_id=app.target_program_id,
                        stage=app.stage,
                        stage_reason=app.stage_reason,
                        enrollment_date=app.enrollment_date,
                        loan_opted_in=app.loan_opted_in,
                        loan_status=app.loan_status,
                        loan_lender=app.loan_lender,
                        loan_amount=app.loan_amount,
                        created_at=app.created_at,
                        updated_at=app.updated_at,
                        student_name=student.name,
                        student_email=student.email,
                        student_phone=student.phone,
                        student_role=student.role,
                    )
                )
            else:
                # Edge case: student not found
                result.append(
                    ApplicationWithStudentResponse(
                        id=app.id,
                        tenant_id=app.tenant_id,
                        student_id=app.student_id,
                        assigned_counselor_id=app.assigned_counselor_id,
                        target_university_id=app.target_university_id,
                        target_program_id=app.target_program_id,
                        stage=app.stage,
                        stage_reason=app.stage_reason,
                        enrollment_date=app.enrollment_date,
                        loan_opted_in=app.loan_opted_in,
                        loan_status=app.loan_status,
                        loan_lender=app.loan_lender,
                        loan_amount=app.loan_amount,
                        created_at=app.created_at,
                        updated_at=app.updated_at,
                        student_name=None,
                        student_email="unknown@example.com",
                        student_phone=None,
                        student_role=Role.STUDENT,
                    )
                )

        return result

    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


def _stage_to_str(stage: PipelineStage | str) -> str:
    """Convert stage to string, handling both enum and plain string from SQLite."""
    if isinstance(stage, str):
        return stage
    return stage.value


@router.get("/queue/counts", response_model=dict[str, int])
def get_counselor_queue_counts(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.APPLICATION_READ_ASSIGNED))
    ],
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Get counts of applications in each stage for the counselor's queue (E21; Journey J14).

    Useful for displaying stage badges in the dashboard.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        # Count applications by stage for this counselor
        counts = (
            db.execute(
                select(Application.stage, func.count(Application.id))
                .where(Application.assigned_counselor_id == current_user.id)
                .where(Application.tenant_id == current_user.tenant_id)
                .group_by(Application.stage)
            )
        ).all()

        # Convert to dict with stage as key
        # Handle both enum values and plain strings (SQLite returns strings)
        return {_stage_to_str(stage): count for stage, count in counts}

    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None
