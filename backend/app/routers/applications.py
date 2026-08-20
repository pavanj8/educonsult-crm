"""Application routes (E21; Journey J14)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application, ApplicationStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.application import ApplicationResponse

router = APIRouter(prefix="/applications")

_DB_UNAVAILABLE_DETAIL = "Application service is temporarily unavailable"


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
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None
