"""Pydantic schemas for analytics endpoints (E41, E42; Journey J34, J35)."""

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


class BranchComparisonBucket(BaseModel):
    """Metrics for a single branch in cross-branch comparison (E42; Journey J35).

    Represents aggregated application metrics for one branch,
    used by consultancy owners to compare performance across branches.
    """

    model_config = ConfigDict(from_attributes=True)

    branch_id: int = Field(description="ID of the branch")
    branch_name: str = Field(description="Name of the branch")
    branch_city: str = Field(description="City where the branch is located")
    total_applications: int = Field(
        ge=0,
        description="Total number of applications in this branch (filtered by date range)",
    )
    enrolled_count: int = Field(
        ge=0,
        description="Number of applications enrolled (terminal stage)",
    )
    rejected_count: int = Field(
        ge=0,
        description="Number of applications rejected (terminal stage)",
    )
    withdrawn_count: int = Field(
        ge=0,
        description="Number of applications withdrawn (terminal stage)",
    )
    active_count: int = Field(
        ge=0,
        description="Number of applications still in active stages (not yet terminal)",
    )


class BranchComparisonResponse(BaseModel):
    """Response for GET /analytics/branch-comparison (E42; Journey J35).

    Returns aggregated metrics for all branches in the consultancy,
    allowing owners to compare branch performance. Each branch bucket
    includes total application counts and breakdowns by terminal status.

    The response is ordered by total_applications descending (highest
    volume branches first).

    Counts reflect applications at their CURRENT stage as of the query
    time, filtered by the optional date range (created_at between start
    and end dates).
    """

    branches: list[BranchComparisonBucket] = Field(
        description="List of branch metrics, ordered by total_applications descending"
    )
    total_branches: int = Field(
        ge=0,
        description="Number of branches in the consultancy",
    )
    total_applications: int = Field(
        ge=0,
        description="Total applications across all branches (filtered by date range)",
    )
