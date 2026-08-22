"""Pydantic schemas for checklist endpoints (E15 CRUD; E26 read view).

This module owns:

* the *write* schemas for the E15 checklist-template CRUD endpoints
  (POST / PATCH / GET / DELETE on :class:`ChecklistItemTemplate`
  rows), and
* the *read* schemas used by the E26 merged checklist-for-application
  endpoint (``GET /applications/{application_id}/checklist``).

The two halves are kept in the same module because they describe the
same domain object (a checklist template) from different angles.

Traceability
------------
* Requirements §5 (per-stage/program checklist templates; student
  uploads against each checklist item).
* Journey J8 (Owner/Branch Manager defines a document checklist
  template for a stage/program) — E15 CRUD.
* Journey J19 (Student views the document checklist for their
  application) — E26 read.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.application import ApplicationStage as ApplicationStageEnum
from app.models.student_document import StudentDocumentStatus
from app.pipeline.stages import PipelineStage

# ---------------------------------------------------------------------------
# E15 — checklist template CRUD (Journey J8)
# ---------------------------------------------------------------------------


class ChecklistTemplateResponse(BaseModel):
    """Response shape for a single :class:`ChecklistItemTemplate` row.

    Returned by every E15 CRUD endpoint. ``id`` is the template's
    primary key (used by the client-side builder as the row identifier);
    ``tenant_id`` is echoed so the frontend can validate which tenant
    the row belongs to without a second round-trip.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    stage: PipelineStage
    program_id: Optional[int]
    name: str
    description: Optional[str]
    required: bool
    order_index: Optional[int]
    created_at: datetime
    updated_at: datetime


class ChecklistTemplateCreateRequest(BaseModel):
    """Payload for ``POST /checklist-templates`` (E15; Journey J8).

    Tenant id is taken from the authenticated caller; the body never
    carries it. ``stage`` is required (a template must target a
    specific pipeline stage). ``program_id`` is optional: ``None`` (or
    omitted) means the template applies to *every* program in the
    tenant. When ``program_id`` is provided it must resolve to a
    :class:`Program` row in the caller's tenant — the endpoint
    enforces this and returns 422 on a cross-tenant FK.
    """

    stage: PipelineStage
    program_id: Optional[int] = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    required: bool = True
    order_index: Optional[int] = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name must not be empty")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ChecklistTemplateUpdateRequest(BaseModel):
    """Payload for ``PATCH /checklist-templates/{template_id}`` (E15; Journey J8).

    All fields are optional; at least one must be provided (the
    endpoint rejects an empty body with 422). When ``program_id`` is
    set it must resolve to a program in the caller's tenant.
    """

    stage: Optional[PipelineStage] = None
    program_id: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    required: Optional[bool] = None
    order_index: Optional[int] = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name must not be empty")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


# ---------------------------------------------------------------------------
# E26 — checklist-for-application merged read view (Journey J19)
# ---------------------------------------------------------------------------


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