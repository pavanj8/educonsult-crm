"""Checklist-for-application retrieval API (E26; Journey J19).

Merges the per-stage/per-program :class:`ChecklistItemTemplate` rows
with the latest :class:`StudentDocument` upload against each template
and returns one row per template so the frontend can render the
student's document checklist (Journey J19: "Student views the document
checklist for their application").

Traceability
------------
* Requirements §5 (per-stage/program checklist templates; student
  uploads against each checklist item).
* Journey J19 (Student views the document checklist for their
  application).
* Epic E26 (Student Document Checklist View); this router is the
  backend half; the frontend component is sibling issue #173.
* Related model tickets: E15 (ChecklistItemTemplate CRUD; this router
  only needs the persisted shape), E27 (StudentDocument upload API;
  this router only needs the persisted shape and ``status``).

The endpoint is read-only. Authorization is gated to the application
owner (the student) plus the staff roles that legitimately need to
inspect a student's checklist (counselor, branch manager, document
verifier, consultancy owner). Counselors, branch managers, and document
verifiers are branch-scoped; consultancy owners see any branch in their
tenant by design (ADR-0004). Cross-tenant access returns 404 (never 403)
to prevent tenant-id enumeration (ADR-0004).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError
from app.models.application import Application
from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.program import Program
from app.models.student_document import StudentDocument
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.checklist import (
    ChecklistItemView,
    ChecklistResponse,
    ChecklistUploadSummary,
)

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Checklist service is temporarily unavailable"


def _get_tenant_application(
    application_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Application:
    """Load an application belonging to the caller's tenant, or raise 404.

    Mirrors the convention used by the E25 advance-stage router: cross-tenant
    access surfaces as 404, not 403, so a hostile client cannot enumerate
    tenant IDs by probing the endpoint.

    Student callers must additionally be ``is_active=True`` — a deactivated
    student must not be able to read their own checklist, mirroring the
    E18 list-applications router's contract (ADR-0004 + ADR-0020).
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

    if current_user.role == Role.STUDENT:
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

    return application


def _authorize_checklist_read(
    application: Application,
    current_user: AuthenticatedUser,
) -> None:
    """Gate the checklist read to legitimate viewers.

    Rules (Requirements §3; ADR-0004):

    * The student who owns the application can always view their own
      checklist (matches the J19 actor).
    * Counselors, Branch Managers, and Document Verifiers are
      branch-scoped (Requirements §3: "Branch Manager manages their own
      branch only (staff, students, visibility)"; ADR-0004). They may
      only inspect applications whose ``branch_id`` matches their own.
    * Consultancy Owner (and Super Admin, who does not pass RBAC here)
      may inspect any application within their tenant.
    * Receptionist, Visa Processor, and any other role are blocked at
      the RBAC layer and never reach this helper.
    """
    if current_user.role == Role.STUDENT:
        if application.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view another student's checklist",
            )
        return

    if current_user.role in (Role.COUNSELOR, Role.BRANCH_MANAGER, Role.DOCUMENT_VERIFIER):
        if (
            current_user.branch_id is None
            or application.branch_id != current_user.branch_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view checklist for an application outside your branch",
            )
        # Counselors additionally require an explicit assignment.
        if current_user.role == Role.COUNSELOR:
            if application.assigned_counselor_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Counselor can only view checklists for their assigned applications",
                )
        return

    # CONSULTANCY_OWNER is allowed cross-branch by design (ADR-0004);
    # SUPER_ADMIN is excluded at the RBAC layer (no DOCUMENT_READ grant).


def _load_application_program_id(
    db: Session,
    application: Application,
) -> int | None:
    """Return the program's id, or None if the program's been deleted.

    The endpoint must not 500 when the application's program row has
    gone away (admin deletion edge case); the merge logic treats
    ``program_id is None`` as "no program-specific templates apply".
    """
    try:
        program = db.get(Program, application.program_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    return program.id if program is not None else None


def _applicable_template_ids(
    db: Session,
    *,
    tenant_id: int,
    stage: str,
    program_id: int | None,
) -> list[int]:
    """Return the ids of templates that apply to ``(stage, program_id)``.

    A template "applies" when:

    * its ``tenant_id`` matches,
    * its ``stage`` matches,
    * and either its ``program_id`` is NULL (applies to all programs) or
      its ``program_id`` matches the application's program.
    """
    try:
        statement = (
            select(ChecklistItemTemplate.id)
            .where(
                ChecklistItemTemplate.tenant_id == tenant_id,
                ChecklistItemTemplate.stage == stage,
            )
            .order_by(ChecklistItemTemplate.id)
        )
        if program_id is None:
            statement = statement.where(ChecklistItemTemplate.program_id.is_(None))
        else:
            statement = statement.where(
                (ChecklistItemTemplate.program_id.is_(None))
                | (ChecklistItemTemplate.program_id == program_id)
            )
        return [row for row in db.scalars(statement).all()]
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


def _latest_upload_per_template(
    db: Session,
    *,
    tenant_id: int,
    application_id: int,
    template_ids: list[int],
) -> dict[int, StudentDocument]:
    """For each template id, return the latest upload for this application.

    Returns a dict keyed by ``checklist_item_template_id``. Templates
    with no upload yet are simply absent from the mapping. Uploads
    attached to ``checklist_item_template_id IS NULL`` (ad-hoc uploads
    not tied to any template) are not part of the merged view and are
    filtered out here.
    """
    if not template_ids:
        return {}

    try:
        statement = (
            select(StudentDocument)
            .where(
                StudentDocument.tenant_id == tenant_id,
                StudentDocument.application_id == application_id,
                StudentDocument.checklist_item_template_id.in_(template_ids),
            )
            .order_by(
                StudentDocument.checklist_item_template_id,
                StudentDocument.uploaded_at.desc(),
                StudentDocument.id.desc(),
            )
        )
        rows = list(db.scalars(statement).all())
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    latest: dict[int, StudentDocument] = {}
    for row in rows:
        if row.checklist_item_template_id is None:
            continue
        if row.checklist_item_template_id not in latest:
            latest[row.checklist_item_template_id] = row
    return latest


@router.get(
    "/{application_id}/checklist",
    response_model=ChecklistResponse,
)
def get_application_checklist(
    application_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.DOCUMENT_READ)),
    ],
    db: Session = Depends(get_db),
) -> ChecklistResponse:
    """Return the merged checklist for one application (E26; Journey J19).

    Joins:

    * ``ChecklistItemTemplate`` rows for the application's stage and
      program (program-NULL templates apply universally),
    * the latest ``StudentDocument`` upload for each template against
      this application (no upload → ``upload`` is ``None`` in the
      response).

    Authorization
    -------------
    Requires the ``document:read`` permission (granted to all roles
    that legitimately need to inspect documents). Beyond RBAC, the
    endpoint enforces a student-owner check for the STUDENT role and a
    counselor-assignment check for the COUNSELOR role so a counselor
    cannot inspect a checklist for an application they do not own.
    Cross-tenant access surfaces as 404.

    Errors
    ------
    * 401 — caller is not authenticated.
    * 403 — caller has ``document:read`` but is not a legitimate
      viewer of this specific application (student-owner / counselor-
      assignment failure). 404 is used for cross-tenant access.
    * 404 — application does not exist or belongs to a different
      tenant.
    * 503 — database unavailable while loading the application,
      templates, or uploads.
    """
    application = _get_tenant_application(application_id, current_user, db)
    _authorize_checklist_read(application, current_user)

    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        template_ids = _applicable_template_ids(
            db,
            tenant_id=current_user.tenant_id,
            stage=application.stage,
            program_id=_load_application_program_id(db, application),
        )
    except TenantScopeError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None

    uploads_by_template = _latest_upload_per_template(
        db,
        tenant_id=current_user.tenant_id,
        application_id=application.id,
        template_ids=template_ids,
    )

    try:
        templates = list(
            db.scalars(
                select(ChecklistItemTemplate)
                .where(ChecklistItemTemplate.id.in_(template_ids))
                .order_by(
                    ChecklistItemTemplate.order_index.is_(None),
                    ChecklistItemTemplate.order_index,
                    ChecklistItemTemplate.id,
                )
            ).all()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    # Touch the User mapper so the FK relationships exist for future
    # extensions (the model layer is imported for side-effect; see
    # `app.models`).
    _ = User  # noqa: F841 — imported for module side effects

    items = [
        ChecklistItemView(
            template_id=template.id,
            stage=template.stage,
            name=template.name,
            description=template.description,
            required=template.required,
            order_index=template.order_index,
            upload=(
                ChecklistUploadSummary.model_validate(uploads_by_template[template.id])
                if template.id in uploads_by_template
                else None
            ),
        )
        for template in templates
    ]

    return ChecklistResponse(
        application_id=application.id,
        items=items,
    )
