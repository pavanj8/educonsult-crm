"""Application routes (E18; E21; Journey J11; J14)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application, ApplicationStage
from app.models.program import Program
from app.models.university import University
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.application import ApplicationResponse, CreateApplicationRequest

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Application service is temporarily unavailable"


def _get_active_student(
    current_user: AuthenticatedUser,
    db: Session,
) -> User:
    """Load the authenticated student account or raise 401/403."""
    try:
        student = db.get(User, current_user.id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    if student.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student account is missing tenant scope",
        )

    return student


def _validate_university_and_program(
    db: Session,
    *,
    tenant_id: int,
    university_id: int,
    program_id: int,
) -> None:
    """Reject university/program references outside the current tenant or university."""
    try:
        university = db.get(University, university_id)
        program = db.get(Program, program_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if university is None or university.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid university",
        )

    if program is None or program.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid program",
        )

    if program.university_id != university.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Program does not belong to the selected university",
        )


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    payload: CreateApplicationRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_CREATE)),
    ],
    db: Session = Depends(get_db),
) -> Application:
    """Create a new university/program application for the authenticated student."""
    student = _get_active_student(current_user, db)

    _validate_university_and_program(
        db,
        tenant_id=student.tenant_id,
        university_id=payload.university_id,
        program_id=payload.program_id,
    )

    application = Application(
        tenant_id=student.tenant_id,
        student_id=student.id,
        university_id=payload.university_id,
        program_id=payload.program_id,
        stage=PipelineStage.REGISTERED,
    )
    db.add(application)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(application)
    return application


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_READ_OWN)),
    ],
    db: Session = Depends(get_db),
) -> list[Application]:
    """List applications belonging to the authenticated student."""
    student = _get_active_student(current_user, db)

    try:
        statement = apply_tenant_scope(
            select(Application)
            .where(Application.student_id == student.id)
            .order_by(Application.id),
            Application,
            current_user,
        )
        return list(db.scalars(statement).all())
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


def _assigned_query_for_role(
    current_user: AuthenticatedUser,
    branch_id: int | None,
) -> Select[tuple[Application]]:
    """Build the role-scoped assigned queue query with stable ordering."""
    statement: Select[tuple[Application]] = apply_tenant_scope(
        select(Application).order_by(Application.id),
        Application,
        current_user,
    )

    if current_user.role == Role.COUNSELOR:
        if current_user.branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no branch scope",
            )
        return statement.where(
            Application.assigned_counselor_id == current_user.id,
            Application.branch_id == current_user.branch_id,
        )

    if current_user.role == Role.BRANCH_MANAGER:
        if current_user.branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no branch scope",
            )
        statement = statement.where(Application.branch_id == current_user.branch_id)
    elif current_user.role == Role.CONSULTANCY_OWNER:
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected role for this endpoint",
        )

    if branch_id is not None:
        statement = statement.where(Application.branch_id == branch_id)
    return statement


@router.get("/assigned-to-me", response_model=list[ApplicationResponse])
def list_assigned_applications(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_READ_ASSIGNED)),
    ],
    db: Session = Depends(get_db),
    stage: ApplicationStage | None = Query(default=None),
    branch_id: int | None = Query(default=None, ge=1),
    student_id: int | None = Query(default=None, ge=1),
) -> list[Application]:
    """Return the role-scoped application queue with optional filters."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant scope",
        )

    try:
        statement = _assigned_query_for_role(current_user, branch_id)
        if stage is not None:
            statement = statement.where(Application.stage == stage.value)
        if student_id is not None:
            statement = statement.where(Application.student_id == student_id)
        return list(db.scalars(statement).all())
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
