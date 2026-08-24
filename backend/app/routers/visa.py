"""Visa-stage applications queue API (E33; Journey J26; issue #191)
and visa outcome update API (E35; Journey J28; issue #195).

Read-side endpoint backing the Visa Processor dashboard (frontend
ticket #192). Returns a paginated list of applications whose pipeline
stage is currently ``visa_processing`` (Requirements §5: per-application
pipeline stages; see :class:`app.pipeline.stages.PipelineStage`). The
queue is restricted to the calling visa processor's tenant (a visa
processor has tenant scope but no branch scope, mirroring the document
verifier's scoping model in :mod:`app.routers.verifier`).

The endpoint intentionally returns a slim per-item shape
(:class:`app.schemas.visa.VisaStageQueueItem`) rather than reusing
:class:`ApplicationResponse`, because the frontend only needs the
identifiers + pipeline stage to render the queue table.

Future ticket work (E34 / E35) may want to JOIN ``visa_details`` to
surface the visa type / interview date alongside each queue row; the
schema is kept narrow here to avoid pre-empting those decisions.

E35 (Visa Outcome Update, issue #195) provides
``PATCH /visa/applications/{application_id}/outcome`` -- a per-application
write endpoint that records the outcome/status the visa processor
decides for an application at the visa stage (Journey J28). See the
endpoint docstring for the full behavior contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application
from app.models.visa_outcome import VisaOutcome
from app.pipeline.stages import PipelineStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.routers._application_lookup import get_tenant_application
from app.schemas.visa import (
    UpdateVisaOutcomeRequest,
    VisaOutcomeResponse,
    VisaStageQueueItem,
    VisaStageQueueResponse,
)

router = APIRouter()


@router.get("/applications/queue", response_model=VisaStageQueueResponse)
def list_visa_stage_applications(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.VISA_MANAGE)),
    ],
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VisaStageQueueResponse:
    """Return the visa-stage applications queue for the calling tenant (E33; J26).

    Gated on ``visa:manage`` (granted to ``VISA_PROCESSOR``,
    ``CONSULTANCY_OWNER``, and ``SUPER_ADMIN`` per
    :data:`app.rbac.permissions.ROLE_PERMISSIONS`). Roles that do not
    hold this permission — STUDENT, COUNSELOR, RECEPTIONIST,
    BRANCH_MANAGER, DOCUMENT_VERIFIER — are blocked at the dependency
    layer (403 ``Insufficient permissions``) before the query runs.

    A visa processor has tenant scope but no branch scope (mirrors the
    document verifier model in :mod:`app.routers.verifier`); the queue
    is therefore restricted to the visa processor's tenant and the
    endpoint rejects callers without a tenant scope before querying to
    avoid returning unscoped platform data. (SUPER_ADMIN has no tenant
    scope today; such callers are rejected here rather than silently
    returning platform-wide data, consistent with the E28 verifier
    queue behaviour.)

    Only applications whose ``stage`` is ``visa_processing`` are
    returned. Results are ordered by ``application.id`` ascending so
    pagination is stable; the response mirrors the E28 document-verifier
    queue shape (``items`` + ``total`` + ``limit`` + ``offset``) for
    frontend consistency.

    Errors:

    * 401 -- caller is not authenticated.
    * 403 -- caller lacks the ``visa:manage`` permission, or has no
      tenant scope.
    * 503 -- database unavailable while loading the queue.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant scope",
        )

    base_query = (
        select(Application)
        .where(
            Application.tenant_id == current_user.tenant_id,
            Application.stage == PipelineStage.VISA_PROCESSING.value,
        )
        .order_by(Application.id)
    )

    try:
        total = db.scalar(
            select(func.count()).select_from(base_query.order_by(None).subquery())
        )
        rows = db.scalars(base_query.limit(limit).offset(offset)).all()
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Visa queue is temporarily unavailable",
        ) from None

    items = [
        VisaStageQueueItem.model_validate(row)
        for row in rows
    ]
    return VisaStageQueueResponse(
        items=items,
        total=total or 0,
        limit=limit,
        offset=offset,
    )


_OUTCOME_DB_UNAVAILABLE_DETAIL = "Visa outcome update is temporarily unavailable"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)



@router.patch(
    "/applications/{application_id}/outcome",
    response_model=VisaOutcomeResponse,
)
def update_visa_outcome(
    application_id: int,
    payload: UpdateVisaOutcomeRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.VISA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> VisaOutcome:
    """Record or update the visa outcome/status for an application (E35; Journey J28; issue #195).

    Lets a Visa Processor persist the outcome decision (status,
    optional outcome date, optional notes) against an application.
    The endpoint is the write-side counterpart to the E33 queue
    (#191): when the queue surfaces an application, the visa
    processor drills into the application detail and PATCHes the
    outcome from there.

    Behavior:

    * Gated on ``visa:manage`` (granted to ``VISA_PROCESSOR``,
      ``CONSULTANCY_OWNER``, and ``SUPER_ADMIN`` per
      :data:`app.rbac.permissions.ROLE_PERMISSIONS`). Roles that do
      not hold this permission -- STUDENT, COUNSELOR, RECEPTIONIST,
      BRANCH_MANAGER, DOCUMENT_VERIFIER -- are blocked at the
      dependency layer (403 ``Insufficient permissions``) before any
      DB query runs.
    * Tenant scoping is enforced via
      :func:`_get_tenant_application_for_outcome` (cross-tenant
      requests surface as 404, never 403, to prevent tenant
      enumeration -- same convention as the E25 ``_get_tenant_application``
      helper).
    * The endpoint REQUIRES the application's current pipeline stage
      to be ``visa_processing``. Applications in any other stage
      (including terminal stages) are rejected with 422 -- an
      outcome is recorded for *the* application at the visa stage,
      not as a free-floating note. This matches Journey J28's
      "Visa Processor updates visa outcome/status" phrasing: the
      outcome is captured while the application is still being
      processed at the visa stage.
    * If a :class:`VisaOutcome` row already exists for the
      application (the visa processor is *updating* the outcome),
      the existing row is updated in place. Otherwise a new row is
      inserted. The 1:1 unique constraint on ``application_id``
      guarantees there is at most one row per application, so the
      create-vs-update decision reduces to "does the lookup return
      a row?". The unique constraint is also keyed off
      ``tenant_id`` indirectly (via the FK to ``applications.id``
      which is itself tenant-scoped), so a crafted cross-tenant
      race is impossible.
    * The endpoint does NOT write a :class:`StageHistory` row and
      does NOT trigger an in-app notification. The application's
      pipeline stage is unchanged by an outcome update (the
      outcome decision is captured alongside the visa stage -- the
      application has not yet enrolled / rejected / withdrawn).
      Future notification wiring for outcome events is out of scope
      and tracked as a separate ticket.

    Errors:

    * 401 -- caller is not authenticated.
    * 403 -- caller lacks ``visa:manage``, or has no tenant scope.
    * 404 -- application does not exist or belongs to a different tenant.
    * 422 -- application is not in the ``visa_processing`` stage
      (e.g. still at ``offer_letter``, already enrolled, already
      rejected/withdrawn), or the request body is empty / contains
      only whitespace ``status``, or the request body fails Pydantic
      validation. No row is written in either 422 case.
    * 503 -- database unavailable while loading / writing the
      application or the :class:`VisaOutcome` row.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant scope",
        )

    application = get_tenant_application(
        application_id,
        current_user,
        db,
        db_unavailable_detail=_OUTCOME_DB_UNAVAILABLE_DETAIL,
    )

    if application.stage != PipelineStage.VISA_PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Application in stage '{application.stage}' cannot have "
                "its visa outcome updated. The application must be in the "
                "'visa_processing' stage."
            ),
        )

    try:
        existing = db.scalar(
            select(VisaOutcome).where(
                VisaOutcome.application_id == application.id,
            )
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_OUTCOME_DB_UNAVAILABLE_DETAIL,
        ) from None

    if existing is None and payload.status is None:
        # ``status`` is the only required input on first creation:
        # ``outcome_date`` and ``notes`` are optional context, but a
        # brand-new outcome record without a status label is
        # meaningless. Reject as 422 so callers must be intentional.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status is required when creating a new visa outcome",
        )

    now = datetime.now(timezone.utc)
    if existing is None:
        outcome = VisaOutcome(
            tenant_id=application.tenant_id,
            application_id=application.id,
            status=payload.status or "",
            outcome_date=payload.outcome_date,
            notes=payload.notes,
            created_at=now,
            updated_at=now,
        )
        db.add(outcome)
    else:
        if payload.status is not None:
            existing.status = payload.status
        if payload.outcome_date is not None:
            existing.outcome_date = payload.outcome_date
        if payload.notes is not None:
            existing.notes = payload.notes
        existing.updated_at = now
        outcome = existing

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_OUTCOME_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(outcome)
    return outcome
