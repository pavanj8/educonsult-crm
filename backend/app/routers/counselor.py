"""Counselor dashboard and queue routes (E21; Journey J14)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.dependencies import require_role
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.application import ApplicationWithStudentResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Counselor service is temporarily unavailable"


def _counselor_base_query(
    db: Session,
    current_user: AuthenticatedUser,
) -> select:
    """Build a tenant- and branch-scoped base query for the counselor's queue.

    Tenant scoping goes through :func:`apply_tenant_scope` (ADR-0004) so the
    multi-tenant invariant is enforced in one place. The per-counselor
    ``assigned_counselor_id`` filter narrows to "this counselor's queue",
    and the inner join on the student :class:`User` enforces the
    branch scope: the application is only returned when the student's
    ``branch_id`` matches the counselor's ``branch_id``.

    Branch scope is required (not implicit) because a counselor's
    ``assigned_counselor_id`` only identifies the owner, not the branch
    the application was created in. Without the join, a counselor who
    happens to be assigned an out-of-branch application (manual
    reassignment bug, data import, etc.) would see rows outside their
    branch. The join guarantees the counselor never sees another
    branch's students even if the assigned_counselor_id filter passes.
    """
    if current_user.branch_id is None:
        # A counselor without a branch_id has no scope to enforce; refuse
        # rather than returning an over-broad result set.
        raise TenantScopeError(
            f"User with role {current_user.role.value} requires branch_id for branch-scoped queries"
        )

    statement: select = apply_tenant_scope(
        select(Application).order_by(Application.id),
        Application,
        current_user,
    )
    return (
        statement.join(User, User.id == Application.student_id, isouter=False)
        .where(Application.assigned_counselor_id == current_user.id)
        .where(User.branch_id == current_user.branch_id)
    )


@router.get("/queue", response_model=list[ApplicationWithStudentResponse])
def get_counselor_queue(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_role(Role.COUNSELOR))
    ],
    db: Session = Depends(get_db),
    stage: PipelineStage | None = Query(default=None, description="Filter by pipeline stage"),
    search: str | None = Query(default=None, max_length=100, description="Search by student name or email"),
) -> list[ApplicationWithStudentResponse]:
    """Get the counselor's assigned application queue (E21; Journey J14).

    Restricted to the ``COUNSELOR`` role only. Branch Managers and Consultancy
    Owners use ``GET /applications/assigned-to-me`` for their broader queue
    views (E21 backend, #156); mixing the three role views into one endpoint
    produced a wrong-data contract for the latter two roles, which is why
    this endpoint is narrowed.
    """
    try:
        query = _counselor_base_query(db, current_user)

        if stage is not None:
            query = query.where(Application.stage == stage.value)

        if search:
            search_term = f"%{search.strip()}%"
            query = query.where(
                (User.name.ilike(search_term)) | (User.email.ilike(search_term))
            )

        applications = list(db.scalars(query).all())

        # Build response with student details. Skip applications where the
        # student row is missing (FK CASCADE deleted or orphan insertion) so
        # the frontend receives clean rows instead of synthesised placeholders.
        # The branch-scope inner join in _counselor_base_query already
        # guarantees a populated User for every returned application.
        result: list[ApplicationWithStudentResponse] = []
        for app in applications:
            student = db.get(User, app.student_id)
            if student is None:
                continue
            result.append(
                ApplicationWithStudentResponse(
                    id=app.id,
                    tenant_id=app.tenant_id,
                    student_id=app.student_id,
                    assigned_counselor_id=app.assigned_counselor_id,
                    target_university_id=app.target_university_id,
                    target_program_id=app.target_program_id,
                    university_id=app.university_id,
                    program_id=app.program_id,
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

        return result

    except TenantScopeError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/queue/counts", response_model=dict[str, int])
def get_counselor_queue_counts(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_role(Role.COUNSELOR))
    ],
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Get counts of applications in each stage for the counselor's queue (E21; Journey J14).

    Useful for displaying stage badges in the dashboard. The response is keyed
    by :class:`PipelineStage` enum string values (``registered``, ``counseling``,
    ...) so the JSON wire format matches what the frontend expects.
    """
    try:
        query = _counselor_base_query(db, current_user)
        rows = db.execute(
            select(Application.stage, func.count(Application.id))
            .select_from(query.subquery())
            .group_by(Application.stage)
        ).all()

        return {stage.value: count for stage, count in rows}

    except TenantScopeError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None