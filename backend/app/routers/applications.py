"""Application routes (E18; E21; E25; Journey J11; J14; J18)."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application, ApplicationStage
from app.models.program import Program
from app.models.stage_history import StageHistory
from app.models.university import University
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.application import (
    AdvanceStageRequest,
    AdvanceStageResponse,
    ApplicationResponse,
    CreateApplicationRequest,
    MarkEnrolledRequest,
    StageHistoryEntry,
)
from app.services.stage_progression import (
    InvalidStageTransitionError,
    validate_transition,
)

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Application service is temporarily unavailable"
_BRANCH_ACCESS_DENIED_DETAIL = "User has no access to this branch's applications"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _get_tenant_application(
    application_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Application:
    """Load an application belonging to the caller's tenant, or raise 404.

    Used by the E25 advance-stage endpoint (issue #169). Mirrors the
    tenant-scoping convention used by the E11/E12 routers so cross-tenant
    requests surface as 404 (never 403) -- prevents tenant-id enumeration.
    """
    try:
        application = db.get(Application, application_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if application is None or (
        current_user.tenant_id is not None
        and application.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    return application


def _enforce_branch_scope(
    application: Application,
    current_user: AuthenticatedUser,
) -> None:
    """Block counselors / branch managers from acting on applications in other branches.

    Consultancy owners and super admins keep cross-branch visibility by
    design (ADR-0004 + Security Analyst finding on iteration #1 of issue
    #169). A missing ``current_user.branch_id`` is treated as a 403 for
    the same reason: a counselor without a branch assignment must not
    be able to advance anything.
    """
    if current_user.role in (Role.COUNSELOR, Role.BRANCH_MANAGER):
        if (
            current_user.branch_id is None
            or application.branch_id != current_user.branch_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_BRANCH_ACCESS_DENIED_DETAIL,
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


@router.post("/{application_id}/stage", response_model=AdvanceStageResponse)
def advance_application_stage(
    application_id: int,
    payload: AdvanceStageRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_ADVANCE_STAGE)),
    ],
    db: Session = Depends(get_db),
) -> AdvanceStageResponse:
    """Advance an application's pipeline stage and log the transition (E25; J18; #169).

    Requires the ``application:advance_stage`` permission (consultancy
    owner, branch manager, or counselor). Validates the (current stage →
    ``payload.to_stage``) transition against the platform-default or
    tenant-specific rule table (see
    :func:`app.services.stage_progression.validate_transition`), updates
    ``Application.stage``, and appends one :class:`StageHistory` row
    recording ``from_stage`` / ``to_stage`` / ``changed_by_user_id`` /
    ``changed_at`` / ``reason`` (the optional reason required by
    Requirements §5 for terminal REJECTED / WITHDRAWN transitions).

    Errors:

    * 401 — caller is not authenticated.
    * 403 — caller lacks the permission, has no tenant scope, has no
      branch scope (counselor / branch manager), or is in a different
      branch than the application.
    * 404 — application does not exist or belongs to a different tenant.
    * 422 — ``to_stage`` is not a permitted transition from the current
      stage, or the request body fails Pydantic validation (e.g.
      ``reason`` missing for a terminal-stage transition). The
      application is left untouched; no history row is written.
    * 503 — database unavailable while loading / writing the application
      or history row.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    application = _get_tenant_application(application_id, current_user, db)
    _enforce_branch_scope(application, current_user)

    from_stage = PipelineStage(application.stage)
    to_stage = payload.to_stage

    try:
        validate_transition(db, from_stage, to_stage, current_user.tenant_id)
    except InvalidStageTransitionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Transition from '{from_stage.value}' to '{to_stage.value}' "
                "is not allowed."
            ),
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    application.stage = to_stage

    history_entry = StageHistory(
        tenant_id=application.tenant_id,
        application_id=application.id,
        from_stage=from_stage,
        to_stage=to_stage,
        changed_by_user_id=current_user.id,
        changed_at=_utc_now(),
        reason=payload.reason,
    )
    db.add(history_entry)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(application)
    db.refresh(history_entry)

    return AdvanceStageResponse(
        application=ApplicationResponse.model_validate(application),
        history_entry=StageHistoryEntry.model_validate(history_entry),
    )

@router.post("/{application_id}/mark-enrolled", response_model=AdvanceStageResponse)
def mark_application_enrolled(
    application_id: int,
    payload: MarkEnrolledRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_ADVANCE_STAGE)),
    ],
    db: Session = Depends(get_db),
) -> AdvanceStageResponse:
    """Mark an application ENROLLED, capturing optional details (E38; J31).

    A dedicated, intent-revealing wrapper over the stage machine for the
    "Mark Enrolled" staff action (frontend #204). Requires the
    ``application:advance_stage`` permission (consultancy owner, branch manager,
    or counselor) and, for counselor / branch manager, that the application is in
    the caller's branch. Validates the (current stage -> ``enrolled``) transition
    via :func:`app.services.stage_progression.validate_transition`, flips
    ``Application.stage`` to ``enrolled``, and appends one :class:`StageHistory`
    row recording the transition and the optional ``details`` (as ``reason``).

    Errors: 403 (lacks permission / no tenant scope / wrong branch), 404
    (missing / cross-tenant), 422 (application is not in a stage from which it
    may be enrolled), 503 (database unavailable).
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    application = _get_tenant_application(application_id, current_user, db)
    _enforce_branch_scope(application, current_user)

    from_stage = PipelineStage(application.stage)
    to_stage = PipelineStage.ENROLLED

    try:
        validate_transition(db, from_stage, to_stage, current_user.tenant_id)
    except InvalidStageTransitionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Application in stage '{from_stage.value}' cannot be marked enrolled."
            ),
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    application.stage = to_stage

    history_entry = StageHistory(
        tenant_id=application.tenant_id,
        application_id=application.id,
        from_stage=from_stage,
        to_stage=to_stage,
        changed_by_user_id=current_user.id,
        changed_at=_utc_now(),
        reason=payload.details,
    )
    db.add(history_entry)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(application)
    db.refresh(history_entry)

    return AdvanceStageResponse(
        application=ApplicationResponse.model_validate(application),
        history_entry=StageHistoryEntry.model_validate(history_entry),
    )
