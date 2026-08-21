"""Checklist / document test helpers (E26; Journey J19).

Provides small factories used by the
``GET /applications/{application_id}/checklist`` endpoint tests to seed
``ChecklistItemTemplate`` and ``StudentDocument`` rows without going
through the future CRUD endpoints (E15 / E27 — those tickets own the
public APIs).
"""

from datetime import datetime, timezone

from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.pipeline.stages import PipelineStage


def seed_checklist_template(
    db_session,
    *,
    tenant_id: int,
    stage: PipelineStage,
    program_id: int | None = None,
    name: str = "Passport copy",
    description: str | None = None,
    required: bool = True,
    order_index: int | None = None,
) -> ChecklistItemTemplate:
    """Create and persist a checklist item template row."""
    now = datetime.now(timezone.utc)
    template = ChecklistItemTemplate(
        tenant_id=tenant_id,
        stage=stage,
        program_id=program_id,
        name=name,
        description=description,
        required=required,
        order_index=order_index,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


def seed_student_document(
    db_session,
    *,
    tenant_id: int,
    application_id: int,
    checklist_item_template_id: int | None,
    status: StudentDocumentStatus = StudentDocumentStatus.PENDING,
    original_filename: str = "passport.pdf",
    content_type: str = "application/pdf",
    size_bytes: int = 1024,
    storage_path: str | None = None,
    uploaded_by_user_id: int,
    uploaded_at: datetime | None = None,
    verified_by_user_id: int | None = None,
    verified_at: datetime | None = None,
    rejection_reason: str | None = None,
) -> StudentDocument:
    """Create and persist a StudentDocument row."""
    uploaded_at = uploaded_at or datetime.now(timezone.utc)
    storage_path = (
        storage_path
        or f"tenants/{tenant_id}/applications/{application_id}/{original_filename}"
    )
    now = datetime.now(timezone.utc)
    document = StudentDocument(
        tenant_id=tenant_id,
        application_id=application_id,
        checklist_item_template_id=checklist_item_template_id,
        status=status,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_path=storage_path,
        uploaded_by_user_id=uploaded_by_user_id,
        uploaded_at=uploaded_at,
        verified_by_user_id=verified_by_user_id,
        verified_at=verified_at,
        rejection_reason=rejection_reason,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document