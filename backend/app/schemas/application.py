"""Pydantic schemas for application endpoints (E18; E21; E25; Journey J11; J14; J18)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationStage as ApplicationStageEnum


class CreateApplicationRequest(BaseModel):
    university_id: int = Field(ge=1)
    program_id: int = Field(ge=1)


class ApplicationResponse(BaseModel):
    """Application data returned by the E18 and E21 endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    branch_id: int | None
    student_id: int
    assigned_counselor_id: int | None
    university_id: int
    program_id: int
    stage: ApplicationStageEnum
    created_at: datetime
    updated_at: datetime


class AdvanceStageRequest(BaseModel):
    """Body for ``POST /applications/{id}/stage`` (E25; Journey J18; issue #169).

    The target stage the caller wants to advance the application to. The
    endpoint validates that a (current stage -> to_stage) transition is
    permitted by the platform-default or tenant-specific rule table
    (see :mod:`app.services.stage_progression`).
    """

    to_stage: ApplicationStageEnum


class StageHistoryEntry(BaseModel):
    """A single stage transition log row (E25; Journey J18; issue #169).

    Returned by the advance-stage endpoint alongside the updated
    application so clients can render an immediate history entry without a
    separate list call. Also produced by the future stage-history listing
    endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    application_id: int
    from_stage: ApplicationStageEnum | None
    to_stage: ApplicationStageEnum
    changed_by_user_id: int | None
    changed_at: datetime


class AdvanceStageResponse(BaseModel):
    """Response for ``POST /applications/{id}/stage`` (E25; issue #169)."""

    application: ApplicationResponse
    history_entry: StageHistoryEntry
