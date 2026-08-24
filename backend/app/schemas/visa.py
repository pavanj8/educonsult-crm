"""Schemas for the visa-stage applications queue API (E33; Journey J26).

The visa-stage queue is the read-side of the Visa Processor dashboard
(frontend ticket #192). It returns a paginated list of applications
whose pipeline stage is currently ``visa_processing`` (Requirements
§5: one of the per-application pipeline stages) so a visa processor
can pick the next application to work on, and the same payload
serves the upcoming E34 (Visa Type & Interview Recording) and E35
(Visa Outcome Update) flows without a second round-trip.

Response shape follows the established queue convention used by the
E28 document-verifier queue (see :class:`PendingDocumentQueueResponse`):
``items`` + ``total`` + ``limit`` + ``offset`` so the frontend can
render a stable page indicator.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VisaStageQueueItem(BaseModel):
    """One row of the visa-stage applications queue.

    Mirrors the standard :class:`ApplicationResponse` payload so the
    frontend can hydrate its visa-processor table without going through
    the generic ``GET /applications/{id}`` endpoint. ``stage`` is
    always ``"visa_processing"`` for items returned by this queue.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    branch_id: int | None
    student_id: int
    assigned_counselor_id: int | None
    university_id: int
    program_id: int
    stage: str
    created_at: datetime
    updated_at: datetime


class VisaStageQueueResponse(BaseModel):
    """Paginated response for the visa-stage applications queue (E33; J26)."""

    items: list[VisaStageQueueItem]
    total: int
    limit: int
    offset: int
