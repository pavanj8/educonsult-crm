"""Pydantic schemas for student document endpoints (E27; Journey J20).

The E27 student-document upload API exposes a single endpoint
(``POST /applications/{application_id}/documents``) whose request is a
multipart form (``file`` + optional ``checklist_item_template_id``) and
whose response is a :class:`StudentDocumentUploadResponse` carrying
the persisted :class:`StudentDocument` row's metadata.

Validation of *file type* and *file size* lands in E27 sibling ticket
#176 — the router here does not duplicate those checks. The schemas in
this module own only the request/response shape.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.student_document import StudentDocumentStatus


class StudentDocumentUploadResponse(BaseModel):
    """Response body for ``POST /applications/{application_id}/documents``.

    Returned immediately after a successful upload so the frontend can
    re-render the checklist view (Journey J19) without a second
    round-trip. ``storage_path`` is the object key on the S3-compatible
    store; it is server-internal and is not meant for client display —
    a future download/serve endpoint will turn it into a presigned URL.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    application_id: int
    checklist_item_template_id: Optional[int]
    status: StudentDocumentStatus
    original_filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    uploaded_by_user_id: int
    uploaded_at: datetime
    verified_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Field-constraint primitives
# ---------------------------------------------------------------------------

# Form fields used by the upload endpoint. Centralised so the router can
# reference the same constants in its OpenAPI examples and tests.
FILE_FORM_FIELD = "file"
CHECKLIST_ITEM_TEMPLATE_ID_FORM_FIELD = "checklist_item_template_id"

# ``checklist_item_template_id`` is optional (ad-hoc uploads with no
# checklist template are still persisted with the FK set to NULL). When
# provided it must reference a positive integer.
CHECKLIST_ITEM_TEMPLATE_ID_FIELD = Field(
    default=None,
    ge=1,
    description=(
        "Optional id of the ChecklistItemTemplate this upload fulfils; "
        "omit for ad-hoc uploads."
    ),
)


__all__ = [
    "CHECKLIST_ITEM_TEMPLATE_ID_FIELD",
    "CHECKLIST_ITEM_TEMPLATE_ID_FORM_FIELD",
    "FILE_FORM_FIELD",
    "StudentDocumentUploadResponse",
]