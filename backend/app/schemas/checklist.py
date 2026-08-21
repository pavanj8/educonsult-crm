"""Pydantic schemas for the E26 checklist read endpoint (Journey J19).

The endpoint returns a merged view: for a given application, each
checklist template applicable to the application's stage/program is
returned along with the most recent upload's status (pending /
approved / rejected). The shape is intentionally flat so the frontend
can render the checklist view directly without further joins.

The companion ORM models live in :mod:`app.models.checklist_item_template`
and :mod:`app.models.student_document`; the merge logic itself lives
in :mod:`app.routers.checklist`.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationStage as ApplicationStageEnum
from app.models.student_document import StudentDocumentStatus


class ChecklistUploadSummary(BaseModel):
    """Summary of the most recent upload against a checklist item.

    Returned inline with each :class:`ChecklistItemView` so the frontend
    can render "approved / pending / rejected / not uploaded" badges
    without a second round-trip. ``status`` is the upload's current
    verification status (Journey J22/J23) or ``None`` when no upload
    has been recorded yet.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: StudentDocumentStatus
    original_filename: str
    uploaded_at: datetime
    verified_at: Optional[datetime]
    rejection_reason: Optional[str]


class ChecklistItemView(BaseModel):
    """One row in the merged E26 checklist response (Journey J19).

    Combines:

    * the template definition (``template_id``, ``stage``, ``name``,
      ``description``, ``required``, ``order_index``), and
    * the latest upload against that template (``upload``).

    When no upload has been recorded for the template, ``upload`` is
    ``None``. When the latest upload was rejected, the frontend can
    surface ``upload.rejection_reason`` and the E31 re-upload flow
    becomes available.
    """

    model_config = ConfigDict(from_attributes=True)

    template_id: int
    stage: ApplicationStageEnum
    name: str
    description: Optional[str]
    required: bool
    order_index: Optional[int]
    upload: Optional[ChecklistUploadSummary]


class ChecklistResponse(BaseModel):
    """Top-level body of ``GET /applications/{application_id}/checklist``.

    ``application_id`` echoes the path parameter so the frontend can
    re-validate without an extra round-trip. ``items`` is sorted by
    ``(order_index NULLS LAST, template_id)`` for deterministic UI
    ordering (ADR-0012: stable list ordering at the API boundary).
    """

    application_id: int = Field(ge=1)
    items: list[ChecklistItemView]
