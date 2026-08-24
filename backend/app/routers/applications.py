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
from app.routers._application_lookup import get_tenant_application
from app.schemas.application import (
    AdvanceStageRequest,
    AdvanceStageResponse,
    ApplicationResponse,
    CreateApplicationRequest,
    MarkEnrolledRequest,
    MarkRejectedRequest,
    MarkWithdrawnRequest,
    ReassignCounselorRequest,
    StageHistoryEntry,
    UpdateLoanRequest,
    UpdateLoanResponse,
)
from app.services.counselor_assignment import assign_counselor_round_robin
from app.services.notifications import notify_application_stage_changed
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




def _enforce_branch_scope(
    application: Application,
    current_user: AuthenticatedUser,
) -> None:
    """Block counselors / branch managers / receptionists from acting on applications in other branches.

    Consultancy owners and super admins keep cross-branch visibility by
    design (ADR-0004 + Security Analyst finding on iteration #1 of issue
    #169). A missing ``current_user.branch_id`` is treated as a 403 for
    the same reason: a counselor / branch manager / receptionist without
    a branch assignment must not be able to act on anything.

    Receptionists are included because the E20 manual-reassignment flow
    (Journey J13, issue #153) is granted to them too -- a receptionist
    is bound to a single branch (ADR-0004) and must not be able to
    reassign counselors in a sibling branch.
    """
    if current_user.role in (
        Role.COUNSELOR,
        Role.BRANCH_MANAGER,
        Role.RECEPTIONIST,
    ):
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

    # Auto-assign a counselor round-robin within the student's branch (E19; J12;
    # #151). branch_id is inherited from the student; when the branch has no
    # active counselor (or the student has no branch) the application is created
    # unassigned and can be assigned later (E20).
    assigned_counselor_id = assign_counselor_round_robin(
        db, tenant_id=student.tenant_id, branch_id=student.branch_id
    )

    application = Application(
        tenant_id=student.tenant_id,
        student_id=student.id,
        university_id=payload.university_id,
        program_id=payload.program_id,
        stage=PipelineStage.REGISTERED,
        branch_id=student.branch_id,
        assigned_counselor_id=assigned_counselor_id,
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

    application = get_tenant_application(application_id, current_user, db)
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

    notify_application_stage_changed(
        db, application=application, from_stage=from_stage, to_stage=to_stage,
        actor_user_id=current_user.id,
    )

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

    application = get_tenant_application(application_id, current_user, db)
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

    notify_application_stage_changed(
        db, application=application, from_stage=from_stage, to_stage=to_stage,
        actor_user_id=current_user.id,
    )

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


@router.post("/{application_id}/mark-rejected", response_model=AdvanceStageResponse)
def mark_application_rejected(
    application_id: int,
    payload: MarkRejectedRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_ADVANCE_STAGE)),
    ],
    db: Session = Depends(get_db),
) -> AdvanceStageResponse:
    """Mark an application REJECTED, capturing the REQUIRED reason (E39; J32).

    A dedicated action endpoint for the "Mark Rejected" staff action (frontend
    #206). Requires ``application:advance_stage`` (consultancy owner, branch
    manager, or counselor) and, for counselor / branch manager, that the
    application is in the caller's branch. Validates the (current stage ->
    ``rejected``) transition, flips ``Application.stage`` to ``rejected``, and
    appends a :class:`StageHistory` row recording the transition and the reason.

    Errors: 403 (lacks permission / no tenant scope / wrong branch), 404
    (missing / cross-tenant), 422 (application already in a terminal stage that
    cannot be rejected, or reason empty/>2000 chars), 503 (database unavailable).
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    application = get_tenant_application(application_id, current_user, db)
    _enforce_branch_scope(application, current_user)

    from_stage = PipelineStage(application.stage)
    to_stage = PipelineStage.REJECTED

    try:
        validate_transition(db, from_stage, to_stage, current_user.tenant_id)
    except InvalidStageTransitionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Application in stage '{from_stage.value}' cannot be marked rejected."
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

    notify_application_stage_changed(
        db, application=application, from_stage=from_stage, to_stage=to_stage,
        actor_user_id=current_user.id,
    )

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


@router.post("/{application_id}/mark-withdrawn", response_model=AdvanceStageResponse)
def mark_application_withdrawn(
    application_id: int,
    payload: MarkWithdrawnRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_ADVANCE_STAGE)),
    ],
    db: Session = Depends(get_db),
) -> AdvanceStageResponse:
    """Mark an application WITHDRAWN, capturing the REQUIRED reason (E40; J33).

    Dedicated action endpoint for the "Mark Withdrawn" staff action (frontend
    #208). Requires ``application:advance_stage`` (owner/manager/counselor) and,
    for counselor / branch manager, that the application is in the caller's
    branch. Validates the (current stage -> ``withdrawn``) transition, flips
    ``Application.stage``, and appends a StageHistory row with the reason.

    Errors: 403 (lacks permission / no tenant scope / wrong branch), 404
    (missing / cross-tenant), 422 (application already terminal, or reason
    empty/>2000 chars), 503 (database unavailable).
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    application = get_tenant_application(application_id, current_user, db)
    _enforce_branch_scope(application, current_user)

    from_stage = PipelineStage(application.stage)
    to_stage = PipelineStage.WITHDRAWN

    try:
        validate_transition(db, from_stage, to_stage, current_user.tenant_id)
    except InvalidStageTransitionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Application in stage '{from_stage.value}' cannot be marked withdrawn."
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

    notify_application_stage_changed(
        db, application=application, from_stage=from_stage, to_stage=to_stage,
        actor_user_id=current_user.id,
    )

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


_COUNSELOR_NOT_FOUND_DETAIL = "Target counselor not found"
_COUNSELOR_INACTIVE_DETAIL = "Target counselor is not active"


def _validate_target_counselor(
    db: Session,
    *,
    tenant_id: int,
    branch_id: int | None,
    counselor_id: int,
) -> None:
    """Validate the target counselor for a manual reassignment, or raise 422.

    Enforces the same shape used elsewhere on the platform (E19
    round-robin): the target must be an active ``COUNSELOR`` whose
    ``tenant_id`` matches the application's tenant. For branch-scoped
    actors (branch manager / receptionist) the counselor must also be
    in the same branch as the application. ``branch_id=None`` means
    cross-branch visibility is granted (consultancy owner scope).

    This helper is a validator, not a loader: it has no return value,
    just side-effects (raising 422 / 503 when the target is invalid).
    The caller does not need the loaded ``User`` object -- it only
    needs assurance that the requested ``counselor_id`` is acceptable.
    """
    try:
        counselor = db.get(User, counselor_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if (
        counselor is None
        or counselor.tenant_id != tenant_id
        or counselor.role != Role.COUNSELOR
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_COUNSELOR_NOT_FOUND_DETAIL,
        )

    if not counselor.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_COUNSELOR_INACTIVE_DETAIL,
        )

    if branch_id is not None and counselor.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_COUNSELOR_NOT_FOUND_DETAIL,
        )


def _target_branch_scope(
    current_user: AuthenticatedUser,
    application: Application,
) -> int | None:
    """Return the branch scope the target counselor must match.

    Consultancy owners (cross-branch by design, ADR-0004) get ``None``
    so the target-counselor validator allows any branch in the tenant.
    Branch-scoped actors (branch manager / receptionist) must match the
    application's branch.
    """
    if current_user.role == Role.CONSULTANCY_OWNER:
        return None
    return application.branch_id


@router.patch("/{application_id}/loan", response_model=UpdateLoanResponse)
def update_application_loan(
    application_id: int,
    payload: UpdateLoanRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.LOAN_UPDATE)),
    ],
    db: Session = Depends(get_db),
) -> UpdateLoanResponse:
    """Record or update the loan tracking fields on an application (E37; J30; #200).

    Lets staff record the loan status, lender, and amount against an
    application (Requirements §5: "Loans: Tracking-only fields
    (opted-in, status, amount, lender) — no separate loan officer
    workflow for v1"). The endpoint is the write-side counterpart
    to the E36 ``loan_opt_in`` flag (Journey J29): a student opts
    in, then staff capture the lender / amount / status as the loan
    progresses through the optional ``loan_processing`` pipeline
    stage.

    Behavior:

    * Gated on ``loan:update`` (granted to ``CONSULTANCY_OWNER`` and
      ``BRANCH_MANAGER`` per
      :data:`app.rbac.permissions.ROLE_PERMISSIONS`). Roles that do
      not hold this permission — STUDENT, COUNSELOR, RECEPTIONIST,
      DOCUMENT_VERIFIER, VISA_PROCESSOR, SUPER_ADMIN — are blocked
      at the dependency layer (403 ``Insufficient permissions``)
      before any DB query runs.

      ``SUPER_ADMIN`` is intentionally NOT granted ``loan:update``:
      the Super Admin oversees platform-wide tenants / billing
      (Requirements §3 + §4) and is not a tenant-scoped staff
      role. Cross-tenant write attempts by Super Admins would also
      fail the tenant-scope check on the caller's
      ``current_user.tenant_id``, but we block earlier at the
      dependency layer for a clean 403.

    * Tenant scoping is enforced via
      :func:`get_tenant_application`: cross-tenant requests surface
      as 404, never 403, to prevent tenant enumeration — same
      convention as the E20 / E25 / E35 endpoints.

    * Branch scoping for branch managers is enforced via
      :func:`_enforce_branch_scope`: branch managers can only
      update loan tracking fields on applications in their own
      branch. Consultancy owners keep cross-branch visibility by
      design (ADR-0004).

    * Each PATCH field is independently optional so staff can record
      them progressively (status first, lender next, amount last)
      and refine any single field later. An explicit ``null`` in the
      body CLEARS the corresponding previously-recorded value
      rather than silently preserving it. An empty PATCH body
      (no fields supplied) is a no-op write that still 200s (the
      application row is unchanged).

    * The endpoint does NOT require the application's pipeline
      stage to be ``loan_processing`` (or any particular stage).
      Loan tracking is a side-channel of the application: staff
      may capture the lender / amount before the application
      enters ``loan_processing`` (e.g. immediately after the
      student opts in via E36) and may refine the recorded values
      after the application returns from ``loan_processing`` to
      ``visa_processing``. The E25 stage-progression flow owns
      the pipeline stage; this endpoint owns the loan tracking
      fields.

    * The endpoint does NOT write a :class:`StageHistory` row and
      does NOT trigger an in-app notification. Recording loan
      tracking fields is a status-capture side-channel, not a
      pipeline-stage transition. Future notification wiring for
      loan-tracking events is out of scope and tracked as a
      separate ticket.

    Errors:

    * 401 -- caller is not authenticated.
    * 403 -- caller lacks ``loan:update``, has no tenant scope, or
      (branch manager) is in a different branch than the
      application.
    * 404 -- application does not exist or belongs to a different
      tenant.
    * 422 -- the request body fails Pydantic validation
      (``loan_status`` over 32 chars / ``loan_lender`` over 120
      chars / negative ``loan_amount``).
    * 503 -- database unavailable while loading / writing the
      application.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    application = get_tenant_application(application_id, current_user, db)
    _enforce_branch_scope(application, current_user)

    if "loan_status" in payload.model_fields_set:
        # ``payload.loan_status`` may be a string OR None depending on
        # whether the caller wanted to record a value or clear a
        # previously-recorded one; both intents must be honored. The
        # Pydantic field setter trims whitespace, so a value of "" or
        # "   " collapses to "" -- treat an empty trimmed string as
        # an explicit clear so staff can ``PATCH {"loan_status":
        # " "}`` to undo a bad value (mirrors the visa detail
        # whitespace-only-status behavior).
        application.loan_status = payload.loan_status or None
    if "loan_lender" in payload.model_fields_set:
        application.loan_lender = payload.loan_lender or None
    if "loan_amount" in payload.model_fields_set:
        # ``loan_amount`` is a ``Decimal | None`` -- either record a
        # non-negative amount or explicitly clear the field.
        application.loan_amount = payload.loan_amount

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(application)
    return UpdateLoanResponse(
        application=ApplicationResponse.model_validate(application),
    )


@router.patch("/{application_id}/counselor", response_model=ApplicationResponse)
def reassign_application_counselor(
    application_id: int,
    payload: ReassignCounselorRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.APPLICATION_REASSIGN_COUNSELOR)),
    ],
    db: Session = Depends(get_db),
) -> Application:
    """Manually reassign a counselor to an application (E20; Journey J13; issue #153).

    Staff action for "Branch Manager/Receptionist manually reassigns a
    counselor" (Journey J13). Gated on the
    ``application:reassign_counselor`` permission, which is granted to
    consultancy owners, branch managers, and receptionists (see
    :data:`app.rbac.permissions.ROLE_PERMISSIONS`).

    Behavior:

    * Tenant scoping is enforced via :func:`_get_tenant_application`
      (cross-tenant access surfaces as 404, not 403 -- prevents tenant
      enumeration).
    * Branch scoping for branch managers / receptionists is enforced
      via :func:`_enforce_branch_scope` (cross-branch access surfaces
      as 403). Consultancy owners keep cross-branch visibility by
      design (ADR-0004).
    * The target counselor must exist, belong to the application's
      tenant, have ``role=COUNSELOR``, be ``is_active=True``, and (for
      branch-scoped actors) be in the same branch as the application.
      Cross-branch assignment by a branch manager / receptionist
      surfaces as 422; consultancy owners may assign across branches
      because :func:`_target_branch_scope` returns ``None`` for them.
    * Passing ``counselor_id=None`` unassigns the application's current
      counselor (the route deliberately does not silently no-op so a
      explicit unassign by a manager is always recorded).
    * No stage-history row is written and no in-app notification is
      generated by this endpoint -- those surfaces are not part of the
      Journey J13 acceptance criteria and are deliberately out of scope
      for this ticket.

    Request body shape (both forms accepted -- explicit null and
    omitted field are equivalent and both unassign):

    .. code-block:: json

       { "counselor_id": 42 }

    .. code-block:: json

       { "counselor_id": null }

    .. code-block:: json

       {}

    Errors:

    * 401 -- caller is not authenticated.
    * 403 -- caller lacks the permission, has no tenant scope, or
      (branch-scoped actor) has no branch scope / is in a different
      branch than the application.
    * 404 -- application does not exist or belongs to a different tenant.
    * 422 -- ``counselor_id`` does not name an active counselor in the
      same tenant + branch, or the body fails Pydantic validation.
    * 503 -- database unavailable while loading the application, the
      target counselor, or the commit.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    application = get_tenant_application(application_id, current_user, db)
    _enforce_branch_scope(application, current_user)

    if payload.counselor_id is not None:
        _validate_target_counselor(
            db,
            tenant_id=application.tenant_id,
            branch_id=_target_branch_scope(current_user, application),
            counselor_id=payload.counselor_id,
        )

    application.assigned_counselor_id = payload.counselor_id

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
