"""Schemas for the document verifier queue API (E28; Journey J21)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.student_document import StudentDocumentStatus


class PendingDocumentItem(BaseModel):
    """Pending document queue entry, including application context."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    application_id: int
    checklist_item_template_id: int | None
    status: StudentDocumentStatus
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by_user_id: int
    uploaded_at: datetime
    application_stage: str
    student_id: int
    university_id: int
    program_id: int


class PendingDocumentQueueResponse(BaseModel):
    """Paginated response for the document verifier queue."""

    items: list[PendingDocumentItem]
    total: int
    limit: int
    offset: int
