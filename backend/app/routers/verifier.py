"""Document verifier pending-document queue API (E28; Journey J21)."""

from __future__ import annotations

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
from app.schemas.verifier import PendingDocumentItem, PendingDocumentQueueResponse

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
