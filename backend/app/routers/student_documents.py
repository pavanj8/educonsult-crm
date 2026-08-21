"""Student-document upload router (E27; Journey J20; issue #175).

Endpoint
--------
``POST /applications/{application_id}/documents``
    multipart/form-data upload carrying:

    * ``file`` — the document bytes (required)
    * ``checklist_item_template_id`` — optional FK to
      :class:`ChecklistItemTemplate`. Omit for ad-hoc uploads (the
      ``student_documents.checklist_item_template_id`` column is
      nullable for that case; see the model docstring).

The endpoint streams the file to the S3-compatible document store
configured by :mod:`app.storage`, then inserts a
:class:`StudentDocument` row in ``pending`` state. The response shape
mirrors the row so the frontend can update its checklist view
in-place (Journey J19: "Student views the document checklist for
their application").

Traceability
------------
* Requirements §5 (Documents: per-stage/program checklist templates;
  students upload against each checklist item; default limits 10MB,
  PDF/JPG/PNG/DOCX).
* Requirements §2 (Storage: S3-compatible object storage; AWS S3 for
  SaaS, MinIO for on-prem).
* Journey J20 (Student uploads a document against a checklist item).
* Epic E27 (Student Document Upload); this router is the file-upload
  half. Sibling tickets own the StudentDocument read side (#174),
  the size/type validation layer (#176 — see
  :mod:`app.storage.validation`), the upload UI (#177), and the
  validation+completeness test suite (#178).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application
from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.student_document import (
    CHECKLIST_ITEM_TEMPLATE_ID_FORM_FIELD,
    FILE_FORM_FIELD,
    StudentDocumentUploadResponse,
)
from app.storage import (
    FILE_TOO_LARGE_DETAIL,
    MAX_FILE_BYTES,
    DocumentStorageError,
    DocumentStorageService,
    get_document_storage,
    validate_file_size,
    validate_file_type,
)

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Document service is unavailable"
_STORAGE_UNAVAILABLE_DETAIL = "Document storage is temporarily unavailable"

#: Maximum allowed upload size, in bytes. Re-exported for the in-router
#: streaming cap below so the value is sourced from a single place (the
#: validation module — Requirements §5: "default limits 10MB").
_MAX_FILE_BYTES_HARD_LIMIT = MAX_FILE_BYTES


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_active_student(
    current_user: AuthenticatedUser,
    db: Session,
) -> User:
    """Load the authenticated student account or raise 401/403.

    Mirrors :func:`app.routers.applications._get_active_student` and
    :func:`app.routers.checklist._get_tenant_application`'s student
    half. The student must be active (Requirements §3: deactivated
    accounts must not be able to mutate their own data) and must carry
    a tenant scope (ADR-0004: every table has ``tenant_id``; an upload
    is persisted with the student's ``tenant_id``).
    """
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


def _get_tenant_application(
    application_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Application:
    """Load the application belonging to the caller's tenant (404 otherwise).

    Cross-tenant access is a 404 — never 403 — so a hostile client
    cannot enumerate tenant ids by probing the endpoint. The student
    must additionally own the application (see :func:`_authorize_owner`).
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


def _authorize_owner(
    application: Application,
    current_user: AuthenticatedUser,
) -> None:
    """A student can only upload to their *own* application (Journey J20)."""
    if application.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot upload documents to another student's application",
        )


def _resolve_checklist_template(
    db: Session,
    *,
    tenant_id: int,
    template_id: int | None,
) -> int | None:
    """Validate the optional ``checklist_item_template_id`` form field.

    When omitted the upload is ad-hoc (NULL FK — the column is nullable
    for that reason; see ``student_document.py``'s docstring). When
    provided, the template must exist and belong to the caller's
    tenant (cross-tenant template ids are rejected as 422 — they're
    a bad request, not a tenant-existence leak).
    """
    if template_id is None:
        return None

    try:
        template = db.get(ChecklistItemTemplate, template_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if template is None or template.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid checklist_item_template_id",
        )

    return template.id


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    """Read the multipart upload into memory with a hard cap.

    The cap is the **10 MB** platform default (Requirements §5; see
    :data:`app.storage.validation.MAX_FILE_BYTES`). It is enforced
    while streaming so a malicious client cannot balloon the process
    RSS by uploading an arbitrarily large payload; the user-facing
    413 is emitted by :func:`validate_file_size` after the stream
    completes.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_FILE_BYTES_HARD_LIMIT:
            # Drop anything we've buffered so the request is bounded.
            chunks.clear()
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=FILE_TOO_LARGE_DETAIL,
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/{application_id}/documents",
    response_model=StudentDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_student_document(
    application_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
    ],
    file: Annotated[UploadFile, File(description="The document to upload")],
    db: Session = Depends(get_db),
    checklist_item_template_id: Annotated[
        int | None,
        Form(
            alias=CHECKLIST_ITEM_TEMPLATE_ID_FORM_FIELD,
            description=(
                "Optional id of the ChecklistItemTemplate this upload fulfils; "
                "omit for ad-hoc uploads."
            ),
        ),
    ] = None,
) -> StudentDocumentUploadResponse:
    """Upload a student document to S3-compatible storage and persist the row.

    Authorization
    -------------
    Requires the ``document:upload`` permission (granted to STUDENT).
    Beyond RBAC, the caller must own the application and be active in
    the tenant — enforced by :func:`_get_active_student`,
    :func:`_get_tenant_application`, and :func:`_authorize_owner`.
    Cross-tenant application ids surface as 404 to prevent tenant-id
    enumeration (ADR-0004).

    Errors
    ------
    * 400 — ``file`` form field is missing, empty, or has no filename.
    * 401 — caller is not authenticated.
    * 403 — caller has ``document:upload`` but is not the application
      owner, is deactivated, or has no tenant scope.
    * 404 — application does not exist or belongs to a different tenant.
    * 413 — uploaded file exceeds the 10 MB cap (Requirements §5).
    * 415 — uploaded file's extension is not in
      :data:`app.storage.validation.ALLOWED_EXTENSIONS` (PDF/JPG/PNG/
      DOCX), or its ``Content-Type`` does not match the extension.
    * 422 — ``checklist_item_template_id`` does not exist or belongs to
      another tenant.
    * 503 — storage backend is unreachable / rejected the upload, or
      the database is unavailable while reading / writing the row.
    """
    if file is None or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'file' form field",
        )

    student = _get_active_student(current_user, db)
    application = _get_tenant_application(application_id, current_user, db)
    _authorize_owner(application, current_user)

    template_id = _resolve_checklist_template(
        db,
        tenant_id=student.tenant_id,
        template_id=checklist_item_template_id,
    )

    content = await _read_upload_bytes(file)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    content_type = file.content_type or "application/octet-stream"
    original_filename = file.filename

    # Requirements §5: default limits 10MB, PDF/JPG/PNG/DOCX.
    # ``validate_file_size`` raises HTTP 413; ``validate_file_type`` raises
    # HTTP 415. We run both before talking to storage so an oversized /
    # wrong-type upload never costs a storage round-trip.
    validate_file_size(len(content))
    validate_file_type(filename=original_filename, content_type=content_type)

    storage: DocumentStorageService = get_document_storage()
    try:
        storage_path = storage.store(
            tenant_id=student.tenant_id,
            application_id=application.id,
            original_filename=original_filename,
            content=content,
            content_type=content_type,
        )
    except DocumentStorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_STORAGE_UNAVAILABLE_DETAIL,
        ) from None

    uploaded_at = _utc_now()
    document = StudentDocument(
        tenant_id=student.tenant_id,
        application_id=application.id,
        checklist_item_template_id=template_id,
        status=StudentDocumentStatus.PENDING,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=len(content),
        storage_path=storage_path,
        uploaded_by_user_id=student.id,
        uploaded_at=uploaded_at,
    )
    db.add(document)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(document)
    return StudentDocumentUploadResponse.model_validate(document)


__all__ = [
    "router",
    "FILE_FORM_FIELD",
]