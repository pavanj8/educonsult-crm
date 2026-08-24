"""Visa-stage applications queue API (E33; Journey J26; issue #191).

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
identifiers + pipeline stage to render the queue table. Visa detail
recording (E34) and outcome updates (E35) are out of scope for this
ticket.

Future ticket work (E34 / E35) may want to JOIN ``visa_details`` to
surface the visa type / interview date alongside each queue row; the
schema is kept narrow here to avoid pre-empting those decisions.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application
from app.pipeline.stages import PipelineStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.visa import VisaStageQueueItem, VisaStageQueueResponse

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
