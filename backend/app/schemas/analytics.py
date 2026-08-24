"""Pydantic schemas for analytics endpoints (E41; Journey J34)."""

from pydantic import BaseModel, ConfigDict, Field


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
