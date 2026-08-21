"""Document verifier pending-document queue API (E28; Journey J21) and
approve-document API (E29; Journey J22; issue #181)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.verifier import (
    ApproveDocumentRequest,
    ApproveDocumentResponse,
    PendingDocumentItem,
    PendingDocumentQueueResponse,
    RejectDocumentRequest,
    RejectDocumentResponse,
)

router = APIRouter()


@router.get("/documents/pending", response_model=PendingDocumentQueueResponse)
def list_pending_documents(
    current_user: Annotated[AuthenticatedUser, Depends(require_permission(Permission.DOCUMENT_VERIFY))],
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PendingDocumentQueueResponse:
    """Return the authenticated verifier's pending-document queue.

    Gated to ``document:verify`` (granted only to ``DOCUMENT_VERIFIER`` per
    :data:`app.rbac.permissions.ROLE_PERMISSIONS`), so students and other
    roles that have ``document:read`` cannot enumerate other tenants'
    pending queues. A document verifier has tenant scope but no branch
    scope. Queue entries are therefore restricted to the verifier's tenant,
    while application metadata provides the branch assignment. A missing
    tenant scope is rejected before querying to avoid returning unscoped
    platform data.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant scope",
        )

    base_query = (
        select(StudentDocument, Application)
        .join(Application, Application.id == StudentDocument.application_id)
        .where(
            StudentDocument.tenant_id == current_user.tenant_id,
            Application.tenant_id == current_user.tenant_id,
            StudentDocument.status == StudentDocumentStatus.PENDING,
        )
    )

    try:
        total = db.scalar(
            select(func.count()).select_from(base_query.order_by(None).subquery())
        )
        rows = db.execute(
            base_query.order_by(StudentDocument.uploaded_at, StudentDocument.id)
            .limit(limit)
            .offset(offset)
        ).all()
    except OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document queue is temporarily unavailable",
        ) from exc

    items = [
        PendingDocumentItem(
            id=document.id,
            tenant_id=document.tenant_id,
            application_id=document.application_id,
            checklist_item_template_id=document.checklist_item_template_id,
            status=document.status,
            original_filename=document.original_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            uploaded_by_user_id=document.uploaded_by_user_id,
            uploaded_at=document.uploaded_at,
            application_stage=application.stage.value,
            student_id=application.student_id,
            university_id=application.university_id,
            program_id=application.program_id,
        )
        for document, application in rows
    ]
    return PendingDocumentQueueResponse(
        items=items,
        total=total or 0,
        limit=limit,
        offset=offset,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_tenant_document(
    document_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> StudentDocument:
    """Load a document belonging to the caller's tenant (404 otherwise).

    Used by :func:`approve_document` (E29; Journey J22; issue #181).
    Cross-tenant access surfaces as 404 — never 403 — to prevent a
    hostile client from enumerating other tenants' document ids by
    probing the endpoint (mirrors the tenant-scoping convention used
    by :func:`app.routers.applications._get_tenant_application`).
    """
    try:
        document = db.get(StudentDocument, document_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is temporarily unavailable",
        ) from None

    if document is None or (
        current_user.tenant_id is not None
        and document.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.post(
    "/documents/{document_id}/approve",
    response_model=ApproveDocumentResponse,
)
def approve_document(
    document_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.DOCUMENT_VERIFY)),
    ],
    db: Session = Depends(get_db),
    payload: ApproveDocumentRequest | None = None,
) -> StudentDocument:
    """Approve a pending student document with an optional comment (E29; J22; #181).

    Authorization
    -------------
    Requires the ``document:verify`` permission (granted only to
    ``DOCUMENT_VERIFIER`` per :data:`app.rbac.permissions.ROLE_PERMISSIONS`).
    A document verifier has tenant scope but no branch scope; the
    endpoint enforces tenant scoping via
    :func:`_get_tenant_document` so cross-tenant requests surface as
    404, never 403 (no tenant enumeration).

    Body
    ----
    Optional :class:`ApproveDocumentRequest` body carrying an optional
    ``comment`` (max 2000 chars; ``None`` or empty string both mean
    "no comment"). Both are persisted as-is — the endpoint always
    overwrites the prior ``approval_comment`` to whatever the caller
    sent, so a verifier can also clear an earlier comment by sending
    an empty body / ``null`` ``comment``.

    Effect
    ------
    On success the document's ``status`` flips from ``pending`` to
    ``approved``, ``verified_by_user_id`` is set to the calling
    verifier's id, ``verified_at`` is set to the current UTC
    timestamp, and ``approval_comment`` is set to the provided
    comment (``None`` if omitted). ``rejection_reason`` is never
    touched on the approve path.

    Errors
    ------
    * 401 — caller is not authenticated.
    * 403 — caller lacks the ``document:verify`` permission, or has
      no tenant scope.
    * 404 — document does not exist or belongs to a different tenant.
    * 422 — document is not in ``pending`` state. Already-approved and
      already-rejected documents are rejected: an approve cannot
      silently flip a previously-rejected document (the student must
      re-upload per Journey J24 / E31), and re-approving an already-
      approved document is also rejected to keep the audit trail
      stable (the first verifier who approved wins). Also 422 when the
      body fails Pydantic validation (e.g. ``comment`` exceeds 2000
      chars).
    * 503 — database unavailable while loading / writing the
      document.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant scope",
        )

    # FastAPI delivers ``None`` for an absent JSON body on an
    # optional body parameter; normalise so the rest of the handler
    # can treat payload as a typed object with ``comment=None``.
    comment = payload.comment if payload is not None else None

    document = _get_tenant_document(document_id, current_user, db)

    if document.status != StudentDocumentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Only pending documents can be approved "
                f"(current status: '{document.status.value}')"
            ),
        )

    document.status = StudentDocumentStatus.APPROVED
    document.verified_by_user_id = current_user.id
    document.verified_at = _utc_now()
    document.approval_comment = comment

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is temporarily unavailable",
        ) from None

    db.refresh(document)
    return document


@router.post(
    "/documents/{document_id}/reject",
    response_model=RejectDocumentResponse,
)
def reject_document(
    document_id: int,
    payload: RejectDocumentRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.DOCUMENT_VERIFY)),
    ],
    db: Session = Depends(get_db),
) -> StudentDocument:
    """Reject a pending student document with a REQUIRED comment (E30; J23; #184).

    Mirrors :func:`approve_document` but a rejection reason is mandatory (the
    student and the audit trail must always have an explanation). Tenant scope is
    enforced via :func:`_get_tenant_document`, so cross-tenant requests surface as
    404 (no tenant enumeration), and only ``pending`` documents can be rejected.

    Errors: 403 (no tenant scope), 404 (missing / cross-tenant), 422 (document not
    pending, or comment empty/>2000 chars), 503 (database unavailable).
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant scope",
        )

    document = _get_tenant_document(document_id, current_user, db)

    if document.status != StudentDocumentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Only pending documents can be rejected "
                f"(current status: '{document.status.value}')"
            ),
        )

    document.status = StudentDocumentStatus.REJECTED
    document.verified_by_user_id = current_user.id
    document.verified_at = _utc_now()
    document.rejection_reason = payload.comment

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is temporarily unavailable",
        ) from None

    db.refresh(document)
    return document
