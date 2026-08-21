"""Schemas for the document verifier queue API (E28; Journey J21)
and the approve-document API (E29; Journey J22; issue #181)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class ApproveDocumentRequest(BaseModel):
    """Body for ``POST /verifier/documents/{document_id}/approve`` (E29; J22; #181).

    The verifier's optional free-text note on the approval (Requirements
    §5: "verifier approves/rejects with comments"). Empty string and
    omitted are both treated as "no comment" — neither is a 422, and
    neither resets an existing comment (the endpoint always overwrites
    ``approval_comment`` to exactly the value the caller provided).
    Whitespace-only comments are also accepted as empty (the model
    stores NULL only when no comment was provided; a pure-whitespace
    comment is preserved verbatim per the auditor's perspective).
    """

    comment: str | None = Field(default=None, max_length=2000)


class ApproveDocumentResponse(BaseModel):
    """Response for ``POST /verifier/documents/{document_id}/approve`` (E29; J22).

    Mirrors the :class:`StudentDocument` row after the approval so the
    frontend can update its checklist view in-place (Journey J19) and
    its pending-documents queue (Journey J21) without a second
    round-trip. ``approval_comment`` is the comment recorded by the
    approving verifier; ``rejection_reason`` is unchanged (always NULL
    on an approved row).
    """

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
    verified_by_user_id: int | None
    verified_at: datetime | None
    rejection_reason: str | None
    approval_comment: str | None
    created_at: datetime
    updated_at: datetime


class RejectDocumentRequest(BaseModel):
    """Body for ``POST /verifier/documents/{document_id}/reject`` (E30; J23; #184).

    Unlike approve, a rejection REQUIRES a reason so the student and the audit
    trail always carry an explanation (Requirements §5; Journey J23). The comment
    is trimmed; an empty or whitespace-only comment is a 422.
    """

    comment: str = Field(max_length=2000)

    @field_validator("comment")
    @classmethod
    def _trim_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("comment is required")
        return stripped


class RejectDocumentResponse(ApproveDocumentResponse):
    """Response for the reject endpoint — the full StudentDocument, same shape as
    approve. On reject, ``rejection_reason`` carries the required comment and
    ``approval_comment`` is left unchanged."""
