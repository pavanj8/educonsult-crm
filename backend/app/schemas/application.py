"""Pydantic schemas for application endpoints (E18; E21; E25; Journey J11; J14; J18; E37; J30)."""

from datetime import datetime
from decimal import Decimal

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
    loan_opt_in: bool
    # E37 task #200 (Journey J30): the three loan-tracking fields
    # staff record via ``PATCH /applications/{id}/loan``. Nullable so a
    # brand-new application (and pre-E37 rows that pre-date the
    # migration) return nulls until staff record something.
    loan_status: str | None
    loan_lender: str | None
    loan_amount: Decimal | None
    created_at: datetime
    updated_at: datetime


class UpdateLoanRequest(BaseModel):
    """Body for ``PATCH /applications/{id}/loan`` (E37; Journey J30; issue #200).

    Lets staff record or update the loan tracking fields on an
    application (Requirements §5: "Loans: Tracking-only fields
    (opted-in, status, amount, lender) — no separate loan officer
    workflow for v1"). All three fields are individually optional so
    staff can record them progressively: status first, lender next,
    amount last, then refine any individual field later.

    Each field is independently nullable so an explicit ``null`` in
    the PATCH body CLEARS that previously-recorded field rather than
    silently preserving it. The E37 update API applies only the
    fields the caller supplied, so a PATCH of just ``{"loan_status":
    "approved"}`` updates the status while leaving the lender and
    amount untouched.

    ``loan_status`` is trimmed of surrounding whitespace so callers
    cannot smuggle " " as a non-empty label. The 32-char ceiling
    matches the persisted column length on
    :class:`app.models.application.Application`.

    ``loan_lender`` is trimmed the same way; the 120-char ceiling
    matches the persisted column length and is comfortably larger than
    any realistic lender label.

    ``loan_amount`` must be a non-negative decimal; zero is allowed
    (a fully scholarshipped loan is a real edge case). The Pydantic
    ``Decimal`` type round-trips through the ``Numeric(12, 2)``
    column without precision loss for the realistic loan-amount
    range.
    """

    loan_status: str | None = Field(default=None, max_length=32)
    loan_lender: str | None = Field(default=None, max_length=120)
    loan_amount: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _trim_loan_strings(self) -> "UpdateLoanRequest":
        if self.loan_status is not None:
            self.loan_status = self.loan_status.strip()
        if self.loan_lender is not None:
            self.loan_lender = self.loan_lender.strip()
        return self


class UpdateLoanResponse(BaseModel):
    """Response for ``PATCH /applications/{id}/loan`` (E37; Journey J30; issue #200).

    Returns the full updated :class:`ApplicationResponse` so the
    frontend can re-hydrate its application detail view from one
    round-trip without a separate GET.
    """

    application: ApplicationResponse


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

    Manual counselor reassignment for an application. The ``counselor_id``
    field accepts either a positive integer (the id of the new counselor
    to assign) or ``null`` (unassign the current counselor). When a non-null
    id is supplied, the endpoint validates that the target user is an
    active ``COUNSELOR`` in the same branch as the application (or, for
    consultancy owners acting cross-branch, in the same tenant).

    Permission gating is handled by ``require_permission(...)`` on the
    endpoint itself; this schema enforces only the shape of the request
    payload and the integer-vs-null choice.
    """

    counselor_id: int | None = Field(
        default=None,
        description=(
            "Id of the new counselor to assign, or null to unassign the "
            "current counselor."
        ),
    )


class SetLoanOptInRequest(BaseModel):
    """Body for ``PATCH /applications/{id}/loan-opt-in`` (E36; Journey J29; issue #199).

    Student-side opt-in toggle for loan tracking on an application.
    Requirements §5: "Loans: Tracking-only fields (opted-in, status,
    amount, lender) — no separate loan officer workflow for v1".
    This endpoint owns the ``opted-in`` flag; the staff-side
    ``status / lender / amount`` fields are tracked separately under
    E37 (Journey J30) and are out of scope here.

    The toggle is intentionally symmetric: a student may opt in AND
    opt back out before loan-tracking fields are recorded (E37). Once
    staff-side loan fields (lender / amount / status) have been
    recorded the staff workflow continues to be authoritative for
    those fields; a subsequent opt-out still flips ``loan_opt_in``
    back to ``false`` and does not delete any staff-recorded loan
    data. This is consistent with the v1 spec ("Tracking-only
    fields").

    The ``loan_opt_in`` field is ``strict=True`` so that Pydantic does
    NOT silently coerce strings / ints to ``True`` (e.g. the truthy
    string ``"yes"`` must surface as a 422, not silently become
    ``True`` -- a future caller could be passing a UI form value
    that needs to be an explicit ``true`` / ``false``).
    """

    loan_opt_in: bool = Field(
        strict=True,
        description=(
            "Whether the student opts into loan tracking on this "
            "application (true) or out of it (false)."
        ),
    )
