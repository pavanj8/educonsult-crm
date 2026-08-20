<<<<<<< HEAD
"""Application routes (E21; Journey J14)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
=======
"""Application routes (E18; Journey J11)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
>>>>>>> origin/main
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
<<<<<<< HEAD
from app.models.application import Application, ApplicationStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.application import ApplicationResponse

router = APIRouter(prefix="/applications")
=======
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application
from app.models.program import Program
from app.models.university import University
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.application import ApplicationResponse, CreateApplicationRequest

router = APIRouter()
>>>>>>> origin/main

_DB_UNAVAILABLE_DETAIL = "Application service is temporarily unavailable"


<<<<<<< HEAD
@router.get("/assigned-to-me", response_model=list[ApplicationResponse])
def list_assigned_applications(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.APPLICATION_READ_ASSIGNED))
    ],
    db: Session = Depends(get_db),
    stage: ApplicationStage | None = Query(
        default=None,
        description="Filter by pipeline stage",
    ),
    branch_id: int | None = Query(
        default=None,
        ge=1,
        description=(
            "Filter by branch. For Counselors this parameter is ignored (they are "
            "pinned to their own branch). For Branch Managers and Consultancy Owners, "
            "passing a branch_id outside the caller's accessible scope returns an "
            "empty list — no error, no cross-tenant leakage."
        ),
    ),
    student_id: int | None = Query(
        default=None,
        ge=1,
        description="Filter by student ID",
    ),
) -> list[Application]:
    """Return applications in the caller's scope.

    E21 · Journey J14: Counselor views their assigned student/application queue.

    Behaviour by role:
    - **Counselor**: returns applications *assigned to them*, scoped to their branch.
    - **Branch Manager**: returns all applications in their branch (including unassigned).
    - **Consultancy Owner**: returns all applications across their tenant (including unassigned).

    Filters (all optional):
    - **stage**: pipeline stage filter (e.g. ``registered``, ``counseling``)
    - **branch_id**: branch filter — see parameter description for role-specific behaviour
    - **student_id**: filter by student ID
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant scope",
        )

    # Build base statement based on role
    if current_user.role == Role.COUNSELOR:
        # Counselors see only applications assigned to them
        if current_user.branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no branch scope",
            )
        statement: Select[tuple[Application]] = (
            select(Application)
            .where(Application.tenant_id == current_user.tenant_id)
            .where(Application.assigned_counselor_id == current_user.id)
            .where(Application.branch_id == current_user.branch_id)
            .order_by(Application.id)
        )
    elif current_user.role == Role.BRANCH_MANAGER:
        # Branch managers see all applications in their branch
        if current_user.branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no branch scope",
            )
        statement = (
            select(Application)
            .where(Application.tenant_id == current_user.tenant_id)
            .where(Application.branch_id == current_user.branch_id)
            .order_by(Application.id)
        )
        # Branch managers can optionally filter by branch_id
        if branch_id is not None:
            statement = statement.where(Application.branch_id == branch_id)
    elif current_user.role == Role.CONSULTANCY_OWNER:
        # Owners see all applications across their tenant
        statement = (
            select(Application)
            .where(Application.tenant_id == current_user.tenant_id)
            .order_by(Application.id)
        )
        # Owners can filter by any branch within their tenant
        if branch_id is not None:
            statement = statement.where(Application.branch_id == branch_id)
    else:
        # All roles that reach this point have passed require_permission, which
        # explicitly gates APPLICATION_READ_ASSIGNED for COUNSELOR, BRANCH_MANAGER,
        # and CONSULTANCY_OWNER only. Any other role is rejected before this handler
        # is invoked, making this branch unreachable. Raise 500 to make the invariant
        # explicit rather than return a misleading 403.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected role for this endpoint",
        )

    # Apply optional filters
    if stage is not None:
        statement = statement.where(Application.stage == stage.value)

    if student_id is not None:
        statement = statement.where(Application.student_id == student_id)

    try:
        return list(db.scalars(statement).all())
=======
def _get_active_student(
    current_user: AuthenticatedUser,
    db: Session,
) -> User:
    """Load the authenticated student account or raise 401/403."""
    try:
        student = db.get(User, current_user.id)
>>>>>>> origin/main
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None
<<<<<<< HEAD
=======

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
    """Reject university_id/program_id that don't exist or belong to another tenant.

    Both references must exist and belong to the caller's tenant; the program
    must additionally belong to the university. This guards the multi-tenancy
    boundary (Requirement §1) and the data-integrity expectation that an
    application references valid master data (Requirement §5; J11 "university +
    program").
    """
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
>>>>>>> origin/main
