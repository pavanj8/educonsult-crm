"""Student-document upload router (E27; Journey J20; issue #175;
E31 / Journey J24 re-upload support added in issue #187).

Endpoint
--------
``POST /applications/{application_id}/documents``
    multipart/form-data upload carrying:

    * ``file`` — the document bytes (required)
    * ``checklist_item_template_id`` — optional FK to
      :class:`ChecklistItemTemplate`. Omit for ad-hoc uploads (the
      ``student_documents.checklist_item_template_id`` column is
      nullable for that case; see the model docstring).
    * ``supersedes_document_id`` — optional id of a previously
      **rejected** :class:`StudentDocument` this upload replaces
      (E31 / Journey J24 / issue #187). When supplied, the new row
      is persisted with ``supersedes_id`` pointing at the rejected
      row; the rejected row itself is left untouched so the
      verifier's earlier ``rejection_reason`` and audit trail are
      preserved (Requirements §8).

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
* Requirements §8 (Audit log on key actions such as document
  approvals — the re-upload flow preserves the rejected row's
  audit trail by linking the new row to it via ``supersedes_id``).
* Requirements §2 (Storage: S3-compatible object storage; AWS S3 for
  SaaS, MinIO for on-prem).
* Journey J20 (Student uploads a document against a checklist item).
* Journey J24 (Student re-uploads a rejected document).
* Epic E27 (Student Document Upload); this router is the file-upload
  half. Sibling tickets own the StudentDocument read side (#174),
  the size/type validation layer (#176 — see
  :mod:`app.storage.validation`), the upload UI (#177), and the
  validation+completeness test suite (#178).
* Epic E31 (Document Re-upload Flow); this router handles the
  ``supersedes_document_id`` form field on the existing upload
  endpoint (issue #187). Sibling issue #188 owns the frontend
  re-upload flow UI.
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
    SUPERSEDES_DOCUMENT_ID_FORM_FIELD,
    StudentDocumentUploadResponse,
)
from app.storage import (
    FILE_TOO_LARGE_DETAIL,
    DocumentStorageError,
    DocumentStorageService,
    get_document_storage,
    validate_file_size,
    validate_file_type,
)

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Document service is unavailable"
_STORAGE_UNAVAILABLE_DETAIL = "Document storage is temporarily unavailable"

#: A defensive upper bound for the streaming read loop. The user-facing
#: 10 MB cap (Requirements §5: "default limits 10MB") is enforced by
#: :func:`app.storage.validation.validate_file_size` *after* the stream
#: completes; this ceiling sits well above that value (50 MB) so its
#: only job is to keep the process RSS bounded under a hostile payload,
#: even in the unlikely event the post-read validator is ever relaxed.
#: See :func:`_read_upload_bytes` for the full rationale.
_STREAMING_CEILING_BYTES = 50 * 1024 * 1024


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


def _resolve_superseded_document(
    db: Session,
    *,
    tenant_id: int,
    application_id: int,
    superseded_id: int | None,
) -> int | None:
    """Validate the optional ``supersedes_document_id`` form field (E31 / J24).

    When omitted the upload is an *initial* upload (NULL FK; the
    ``student_documents.supersedes_id`` column is nullable for that
    reason — see ``student_document.py``'s docstring). When provided,
    the referenced :class:`StudentDocument` row must:

    * exist,
    * belong to the caller's tenant (cross-tenant ids are 422, not
      404 — the same rationale as :func:`_resolve_checklist_template`),
    * belong to the *same* application this upload is being filed
      against (a re-upload replaces its own predecessor; one cannot
      re-upload into a different application's audit chain),
    * and be in ``rejected`` status — J24 only fires after the
      verifier rejected the previous attempt (J23). An approved or
      still-pending document is not eligible: re-uploading against an
      approved document would silently shadow a verified file, and
      re-uploading against a still-pending document would create two
      competing ``pending`` rows for the same checklist slot. Both
      are rejected as 422 with a stable ``detail`` so the frontend
      can surface the right error.

    The rejected row itself is *never* mutated here — the audit trail
    (verifier, rejection_reason, verified_at) stays intact for
    Requirements §8. Only the *new* row's ``supersedes_id`` is set.
    """
    if superseded_id is None:
        return None

    try:
        document = db.get(StudentDocument, superseded_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if document is None or document.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid supersedes_document_id",
        )

    if document.application_id != application_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="supersedes_document_id must reference a document on this application",
        )

    if document.status != StudentDocumentStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "supersedes_document_id must reference a rejected document "
                f"(current status: '{document.status.value}')"
            ),
        )

    return document.id


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    """Read the multipart upload into memory with a defensive upper bound.

    The user-facing 10 MB cap is enforced by :func:`app.storage.validation.
    validate_file_size` after the stream completes — that is the rule from
    Requirements §5 ("default limits 10MB"). The streaming cap here is a
    **defensive safety net** set well above :data:`MAX_FILE_BYTES` (50 MB)
    so the process RSS cannot be ballooned by an arbitrarily large payload
    even if the validator were ever removed in a future refactor. It is
    intentionally redundant today; do not lower it to ``MAX_FILE_BYTES``
    (the only line that should enforce the public 10 MB rule is
    :func:`validate_file_size`).
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _STREAMING_CEILING_BYTES:
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
    supersedes_document_id: Annotated[
        int | None,
        Form(
            alias=SUPERSEDES_DOCUMENT_ID_FORM_FIELD,
            description=(
                "Optional id of a previously rejected StudentDocument this "
                "upload replaces (E31 / Journey J24 / issue #187). Omit for "
                "initial uploads."
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

    Re-upload (E31 / J24)
    ---------------------
    When the optional ``supersedes_document_id`` form field is set,
    the new row's ``supersedes_id`` is populated with that document's
    id, *if* the referenced row is ``rejected`` and belongs to this
    application in this tenant (see :func:`_resolve_superseded_document`).
    The rejected row is never mutated — its
    ``status='rejected'`` / ``rejection_reason`` / ``verified_by`` /
    ``verified_at`` stay intact for the audit trail (Requirements §8),
    and the new row starts in ``pending`` state for the verifier to
    re-review.

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
      another tenant; OR ``supersedes_document_id`` does not exist,
      belongs to another tenant, references a different application,
      or references a document whose ``status`` is not ``rejected``.
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
    supersedes_id = _resolve_superseded_document(
        db,
        tenant_id=student.tenant_id,
        application_id=application.id,
        superseded_id=supersedes_document_id,
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
        supersedes_id=supersedes_id,
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
    "SUPERSEDES_DOCUMENT_ID_FORM_FIELD",
]