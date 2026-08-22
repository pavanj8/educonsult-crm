"""Checklist template CRUD API (E15; Journey J8).

Defines the admin endpoints consultancy owners and branch managers use
to define the document checklist for a stage/program. The companion
read-only merged view (``GET /applications/{application_id}/checklist``
— Journey J19, E26) lives in :mod:`app.routers.checklist`; this module
owns the *write* surface only.

Endpoints
---------

* ``GET    /checklist-templates``         — list templates in the
  caller's tenant, with optional ``stage`` / ``program_id`` filters.
* ``POST   /checklist-templates``         — create a template.
* ``GET    /checklist-templates/{id}``    — read one template (404 on
  cross-tenant id; never 403).
* ``PATCH  /checklist-templates/{id}``   — partial update.
* ``DELETE /checklist-templates/{id}``    — delete (204 on success).

Traceability
------------
* Requirements §5 (per-stage/program checklist templates).
* Journey J8 (Owner/Branch Manager defines a document checklist
  template for a stage/program).
* Epic E15 (Document Checklist Template Management); this router is
  the backend CRUD half of the epic.

Authorization
-------------
All endpoints require the ``checklist_template:manage`` permission
(granted to ``CONSULTANCY_OWNER`` and ``BRANCH_MANAGER`` in
:mod:`app.rbac.permissions`). Super Admin is intentionally excluded —
the permission is a tenant-scoped operational concern, not a
platform-wide one. All writes inherit ``tenant_id`` from the caller;
cross-tenant reads surface as 404 to prevent tenant-id enumeration
(ADR-0004).

Errors
------
* 401 -- caller is not authenticated.
* 403 -- caller lacks ``checklist_template:manage``, has no
  ``tenant_id``, or supplied a ``program_id`` that resolves outside
  the caller's tenant (422 -- the value is unprocessable for this
  tenant, not "not found").
* 404 -- template id does not exist OR belongs to a different tenant.
* 422 -- validation failure (empty body on PATCH, missing/blank
  required field).
* 503 -- database unavailable.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.program import Program
from app.pipeline.stages import PipelineStage
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.checklist import (
    ChecklistTemplateCreateRequest,
    ChecklistTemplateResponse,
    ChecklistTemplateUpdateRequest,
)

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Checklist template service is temporarily unavailable"


def _require_tenant_scope(current_user: AuthenticatedUser) -> int:
    """Reject callers without a tenant id; return the tenant id otherwise.

    Mirrors the master-data admin convention: Super Admin is not
    granted ``checklist_template:manage`` precisely so this guard
    never has to special-case SUPER_ADMIN. Future ticket work that
    wants to reuse this permission for a wider mutation surface
    must add its own tenant scoping.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user.tenant_id


def _get_tenant_template(
    template_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> ChecklistItemTemplate:
    """Load a template belonging to the caller's tenant, or raise 404.

    Cross-tenant access surfaces as 404, not 403, so a hostile client
    cannot enumerate tenant IDs by probing the endpoint
    (ADR-0004).
    """
    tenant_id = _require_tenant_scope(current_user)
    try:
        template = db.get(ChecklistItemTemplate, template_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if template is None or template.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checklist template not found",
        )
    return template


def _resolve_program_for_tenant(
    program_id: Optional[int],
    tenant_id: int,
    db: Session,
) -> None:
    """Resolve an optional ``program_id`` FK that must belong to the caller's tenant.

    ``None`` is a legitimate value (means "applies to every program
    in the tenant" per Requirements §5). A non-None value that does
    not resolve to a program row in the caller's tenant yields 422 —
    the value is unprocessable for this tenant, not "not found".
    """
    if program_id is None:
        return
    try:
        program = db.get(Program, program_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if program is None or program.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid program for the caller's tenant",
        )


@router.get("", response_model=list[ChecklistTemplateResponse])
def list_checklist_templates(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.CHECKLIST_TEMPLATE_MANAGE)),
    ],
    db: Session = Depends(get_db),
    stage: Optional[PipelineStage] = Query(
        default=None,
        description="Filter to templates targeting this pipeline stage.",
    ),
    program_id: Optional[int] = Query(
        default=None,
        ge=1,
        description=(
            "Filter to templates scoped to this program. Use 0/omit to "
            "return only global (program_id IS NULL) templates; combined "
            "with the stage filter."
        ),
    ),
) -> list[ChecklistItemTemplate]:
    """List checklist templates in the caller's tenant (E15; Journey J8).

    Results are scoped to the caller's ``tenant_id`` and sorted by
    ``(stage, order_index NULLS LAST, id)`` for deterministic UI
    ordering (ADR-0012). Optional ``stage`` and ``program_id`` query
    parameters narrow the list; passing neither returns every
    template the tenant owns.
    """
    tenant_id = _require_tenant_scope(current_user)
    try:
        statement = (
            select(ChecklistItemTemplate)
            .where(ChecklistItemTemplate.tenant_id == tenant_id)
            .order_by(
                ChecklistItemTemplate.stage,
                ChecklistItemTemplate.order_index.is_(None),
                ChecklistItemTemplate.order_index,
                ChecklistItemTemplate.id,
            )
        )
        if stage is not None:
            statement = statement.where(ChecklistItemTemplate.stage == stage)
        if program_id is not None:
            statement = statement.where(
                ChecklistItemTemplate.program_id == program_id
            )
        return list(db.scalars(statement).all())
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "",
    response_model=ChecklistTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_checklist_template(
    payload: ChecklistTemplateCreateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.CHECKLIST_TEMPLATE_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> ChecklistItemTemplate:
    """Create a checklist template in the caller's tenant (E15; Journey J8).

    The tenant id is taken from the authenticated caller. A
    ``program_id``, when provided, must resolve to a program in the
    same tenant; otherwise the endpoint returns 422 (the value is
    unprocessable for this tenant, not "not found").
    """
    tenant_id = _require_tenant_scope(current_user)
    _resolve_program_for_tenant(payload.program_id, tenant_id, db)

    template = ChecklistItemTemplate(
        tenant_id=tenant_id,
        stage=payload.stage,
        program_id=payload.program_id,
        name=payload.name,
        description=payload.description,
        required=payload.required,
        order_index=payload.order_index,
    )
    db.add(template)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=ChecklistTemplateResponse)
def get_checklist_template(
    template_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.CHECKLIST_TEMPLATE_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> ChecklistItemTemplate:
    """Return a single checklist template by id (E15; Journey J8)."""
    return _get_tenant_template(template_id, current_user, db)


@router.patch("/{template_id}", response_model=ChecklistTemplateResponse)
def update_checklist_template(
    template_id: int,
    payload: ChecklistTemplateUpdateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.CHECKLIST_TEMPLATE_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> ChecklistItemTemplate:
    """Update a checklist template within the caller's tenant (E15; Journey J8).

    All fields are optional; at least one must be provided. Setting
    ``program_id`` to a value outside the caller's tenant yields 422.
    A successful update returns the refreshed row.
    """
    tenant_id = _require_tenant_scope(current_user)
    template = _get_tenant_template(template_id, current_user, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    if "program_id" in update_data:
        _resolve_program_for_tenant(update_data["program_id"], tenant_id, db)

    for field, value in update_data.items():
        setattr(template, field, value)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checklist_template(
    template_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.CHECKLIST_TEMPLATE_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> None:
    """Delete a checklist template within the caller's tenant (E15; Journey J8).

    The endpoint does not pre-check for in-flight
    :class:`StudentDocument` rows referencing the template. Because the
    template's ``program_id`` FK is ``ON DELETE CASCADE`` on the
    programs side but the ``StudentDocument.checklist_item_template_id``
    FK is intentionally NOT cascaded (E31 re-upload semantics:
    historical uploads against a removed template must survive for the
    audit trail), the caller's tenant will retain orphan upload rows
    after the delete. Callers that care about cleanup are responsible
    for inspecting or archiving those rows separately; deleting a
    template does not delete student uploads against it.
    """
    template = _get_tenant_template(template_id, current_user, db)
    db.delete(template)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None