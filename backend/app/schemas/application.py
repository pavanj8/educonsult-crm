"""Pydantic schemas for application endpoints (E18; E21; E25; Journey J11; J14; J18)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.application import ApplicationStage as ApplicationStageEnum
from app.pipeline.stages import PipelineStage


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

    ``reason`` is an optional free-text note. Per Requirements §5
    ("Enrolled / Rejected / Withdrawn, three distinct terminal states,
    each capturing a reason"), a non-empty ``reason`` is REQUIRED for
    any transition whose ``to_stage`` is ``rejected`` or ``withdrawn``.
    Forward pipeline transitions and ``enrolled`` may omit it; a
    validation error (422) is raised when the rule is violated.
    """

    to_stage: ApplicationStageEnum
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _require_reason_for_terminal_rejections(self) -> "AdvanceStageRequest":
        terminal_rejections = {
            PipelineStage.REJECTED,
            PipelineStage.WITHDRAWN,
        }
        if (
            self.to_stage in terminal_rejections
            and (self.reason is None or not self.reason.strip())
        ):
            raise ValueError(
                f"reason is required when to_stage is '{self.to_stage.value}'"
            )
        return self


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
    reason: str | None


class AdvanceStageResponse(BaseModel):
    """Response for ``POST /applications/{id}/stage`` (E25; issue #169)."""

    application: ApplicationResponse
    history_entry: StageHistoryEntry

class MarkEnrolledRequest(BaseModel):
    """Body for ``POST /applications/{id}/mark-enrolled`` (E38; Journey J31).

    Marking an application ENROLLED captures optional free-text enrollment
    ``details`` (e.g. intake term, offer confirmation notes). Unlike the
    REJECTED / WITHDRAWN terminal transitions a reason is not mandatory for a
    positive enrollment outcome (Requirements §5); the value is recorded on the
    resulting :class:`~app.models.stage_history.StageHistory` ``reason`` column.
    """

    details: str | None = Field(default=None, max_length=2000)


class MarkRejectedRequest(BaseModel):
    """Body for ``POST /applications/{id}/mark-rejected`` (E39; Journey J32).

    Marking an application REJECTED REQUIRES a reason (Requirements §5: the
    terminal REJECTED / WITHDRAWN states each capture a reason). The reason is
    trimmed; empty / whitespace-only / missing is a 422. Recorded on the
    resulting StageHistory ``reason`` column.
    """

    reason: str = Field(max_length=2000)

    @model_validator(mode="after")
    def _require_non_empty_reason(self) -> "MarkRejectedRequest":
        trimmed = self.reason.strip()
        if not trimmed:
            raise ValueError("reason is required")
        self.reason = trimmed
        return self


class MarkWithdrawnRequest(BaseModel):
    """Body for ``POST /applications/{id}/mark-withdrawn`` (E40; Journey J33).

    Marking an application WITHDRAWN REQUIRES a reason (Requirements §5: the
    terminal REJECTED / WITHDRAWN states each capture a reason). The reason is
    trimmed; empty / whitespace-only / missing is a 422. Recorded on the
    resulting StageHistory ``reason`` column.
    """

    reason: str = Field(max_length=2000)

    @model_validator(mode="after")
    def _require_non_empty_reason(self) -> "MarkWithdrawnRequest":
        trimmed = self.reason.strip()
        if not trimmed:
            raise ValueError("reason is required")
        self.reason = trimmed
        return self


class ReassignCounselorRequest(BaseModel):
    """Body for ``PATCH /applications/{id}/counselor`` (E20; Journey J13; issue #153).

    The new counselor's user id. ``None`` unassigns the application's current
    counselor (explicit unassign by a manager is recorded; the route does not
    silently no-op). The endpoint's permission + tenant/branch scoping
    guarantees are documented on the route function.
    """

    counselor_id: int | None = Field(default=None, ge=1)
