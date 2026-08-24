"""Pydantic schemas for analytics endpoints (E41; Journey J34)."""

from pydantic import BaseModel, ConfigDict, Field


class RegistrationsOverTimeBucket(BaseModel):
    """A single data point in the registrations-over-time series (E41; Journey J34).

    Represents the count of new student registrations (users created with
    role=STUDENT) for a specific time period, filtered by date range and
    scoped to the caller's branch.
    """

    model_config = ConfigDict(from_attributes=True)

    date: str = Field(
        description=(
            "The date bucket in ISO 8601 format (YYYY-MM-DD). "
            "For daily granularity, this is the exact date. "
            "For weekly, it's the start of the week. "
            "For monthly, it's the start of the month."
        )
    )
    count: int = Field(
        ge=0,
        description="Number of new student registrations on this date/period",
    )


class RegistrationsOverTimeResponse(BaseModel):
    """Response for GET /analytics/registrations (E41; Journey J34).

    Returns a time-series of student registrations grouped by date,
    ordered chronologically from oldest to newest. The counts reflect
    new students created within the optional date range, scoped to
    the caller's branch.
    """

    data: list[RegistrationsOverTimeBucket] = Field(
        description="Time-series data points of registrations over time"
    )
    total_registrations: int = Field(
        ge=0,
        description="Total number of registrations in the filtered date range",
    )


class ConversionFunnelBucket(BaseModel):
    """A single stage in the conversion funnel (E41; Journey J34).

    Represents the count of applications currently at a specific pipeline
    stage, filtered by date range and scoped to the caller's branch.
    """

    model_config = ConfigDict(from_attributes=True)

    stage: str = Field(
        description=(
            "The pipeline stage (one of: registered, counseling, "
            "university_shortlisting, application_submitted, "
            "document_verification, offer_letter, visa_processing, "
            "loan_processing, enrolled, rejected, withdrawn)"
        )
    )
    count: int = Field(
        ge=0,
        description="Number of applications currently at this stage",
    )


class ConversionFunnelResponse(BaseModel):
    """Response for GET /analytics/funnel (E41; Journey J34).

    Returns a list of buckets representing the conversion funnel by stage,
    ordered from earliest to latest stage. Terminal stages (enrolled,
    rejected, withdrawn) are included at the end.

    The counts reflect applications at their CURRENT stage as of the
    query time, filtered by the optional date range (created_at between
    start and end dates).
    """

    funnel: list[ConversionFunnelBucket] = Field(
        description="Conversion funnel breakdown by pipeline stage"
    )
    total_applications: int = Field(
        ge=0,
        description="Total number of applications in the filtered date range",
    )
