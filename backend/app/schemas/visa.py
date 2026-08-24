"""Schemas for the visa-stage applications queue API (E33; Journey J26),
the visa detail update API (E34; Journey J27; issue #194), and the
visa outcome update API (E35; Journey J28; issue #195).

The visa-stage queue is the read-side of the Visa Processor dashboard
(frontend ticket #192). It returns a paginated list of applications
whose pipeline stage is currently ``visa_processing`` (Requirements
§5: one of the per-application pipeline stages) so a visa processor
can pick the next application to work on, and the same payload
serves the upcoming E34 (Visa Type & Interview Recording) and E35
(Visa Outcome Update) flows without a second round-trip.

The E34 visa detail update API (Journey J27; issue #194) is the
write-side counterpart that lets a Visa Processor record or update
the visa type and embassy interview date for an application at the
visa processing stage. The request shape
(:class:`UpdateVisaDetailRequest`) requires ``visa_type`` (the
*visa type* being recorded) and treats ``interview_date`` as an
optional follow-up field — J27 describes them as two fields the
processor fills in over time, not as a single atomic entry.
The response shape (:class:`VisaDetailResponse`) mirrors the
persisted :class:`app.models.visa_detail.VisaDetail` row.

The visa outcome update API (E35; issue #195) is a tiny write-side
endpoint that lets a Visa Processor record or update the outcome
status of an application at the visa stage (Journey J28). The
shape is deliberately narrow (status + outcome_date + notes) so
the catalogue of outcome labels can evolve without an Alembic
data migration; see :class:`UpdateVisaOutcomeRequest`.

Response shape follows the established queue convention used by the
E28 document-verifier queue (see :class:`PendingDocumentQueueResponse`):
``items`` + ``total`` + ``limit`` + ``offset`` so the frontend can
render a stable page indicator.
"""

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


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


class UpdateVisaOutcomeRequest(BaseModel):
    """Body for ``PATCH /visa/applications/{id}/outcome`` (E35; Journey J28; issue #195).

    The visa outcome is a free-text string label (e.g. ``"approved"``,
    ``"rejected"``, ``"pending"``) rather than a hard-coded enum: the
    spec does not promise an admin-managed master list of outcomes for
    v1 (master data in J7 covers countries / universities / programs)
    and the catalogue of outcome labels may grow over time. The 32-char
    ceiling matches the persisted column length on
    :class:`app.models.visa_outcome.VisaOutcome`.

    ``outcome_date`` is the optional timestamp at which the outcome was
    decided (J28). Nullable so the visa processor can save a draft
    outcome without committing to a date.

    ``notes`` is optional free-text context the visa processor records
    alongside the outcome (e.g. embassy interview comments).

    The body fields are all optional individually but at least one of
    ``status`` / ``outcome_date`` / ``notes`` MUST be supplied: a no-op
    outcome update is rejected at 422 so a PATCH always reflects an
    intentional change. ``status`` is also trimmed of surrounding
    whitespace so callers cannot smuggle " " as a non-empty label.
    """

    status: str | None = Field(default=None, max_length=32)
    outcome_date: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _require_at_least_one_field_and_non_empty_status(self) -> "UpdateVisaOutcomeRequest":
        if self.status is None and self.outcome_date is None and self.notes is None:
            raise ValueError(
                "At least one of status, outcome_date, or notes must be provided."
            )
        if self.status is not None:
            trimmed = self.status.strip()
            if not trimmed:
                raise ValueError("status must be non-empty when provided")
            self.status = trimmed
        return self


class VisaOutcomeResponse(BaseModel):
    """Persisted visa outcome row returned by the E35 update endpoint.

    Mirrors the standard ``from_attributes=True`` response shape used
    everywhere else (e.g. :class:`ApplicationResponse`). The
    ``id`` / ``tenant_id`` / ``created_at`` / ``updated_at`` columns
    are inherited from :class:`TenantScopedBase`; the application-scoped
    fields live on this row.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    application_id: int
    status: str
    outcome_date: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class VisaDetailResponse(BaseModel):
    """Persisted visa detail row returned by the E34 endpoints (Journey J27; issue #194).

    Mirrors the standard ``from_attributes=True`` response shape used
    elsewhere (e.g. :class:`ApplicationResponse`) so the persisted
    :class:`app.models.visa_detail.VisaDetail` row can be returned
    directly. The ``id`` / ``tenant_id`` / ``created_at`` /
    ``updated_at`` columns are inherited from
    :class:`TenantScopedBase`; the application-scoped fields live on
    this row.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    application_id: int
    visa_type: str
    interview_date: datetime | None
    created_at: datetime
    updated_at: datetime


class UpdateVisaDetailRequest(BaseModel):
    """Body for ``GET`` / ``PUT /visa/applications/{id}/details`` (E34; Journey J27; issue #194).

    The visa type is the *required* input — J27 records a "visa type &
    embassy interview date", with the type being the field the visa
    processor MUST fill in. The interview date is an optional
    follow-up field the processor may add later, so it is nullable.

    ``visa_type`` is trimmed of surrounding whitespace so callers
    cannot smuggle " " as a non-empty label. The 100-char ceiling
    matches the persisted column length on
    :class:`app.models.visa_detail.VisaDetail`. ``interview_date``,
    when supplied, must be timezone-aware (the column is
    ``DateTime(timezone=True)``); naive datetimes are rejected by
    Pydantic so callers must be intentional about which wall clock
    they mean.
    """

    visa_type: str = Field(min_length=1, max_length=100)
    # ``interview_date`` must be timezone-aware so the persisted
    # ``DateTime(timezone=True)`` column round-trips without ambiguity
    # (embassies span many time zones, and a naive value would silently
    # lose its offset on write). ``AwareDatetime`` rejects naive
    # datetimes at the Pydantic layer with a clean 422 -- the
    # alternative of using ``datetime`` here + a model-level check
    # would let naive values reach the SQL layer and only fail later,
    # which is harder to debug for the calling frontend.
    interview_date: AwareDatetime | None = None

    @model_validator(mode="after")
    def _trim_visa_type(self) -> "UpdateVisaDetailRequest":
        trimmed = self.visa_type.strip()
        if not trimmed:
            raise ValueError("visa_type must be non-empty when provided")
        self.visa_type = trimmed
        return self
