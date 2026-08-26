"""Pydantic schemas for analytics endpoints (E41, E42; Journey J34, J35)."""

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
    """Response for GET /analytics/registrations-over-time (E41; Journey J34).

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


class TenantStatsBucket(BaseModel):
    """Metrics for a single tenant in platform-wide stats (E43; Journey J36).

    Represents aggregated metrics for one consultancy tenant on the platform,
    used by Super Admins to monitor overall platform health and tenant growth.
    """

    model_config = ConfigDict(from_attributes=True)

    tenant_id: int = Field(description="ID of the tenant")
    tenant_name: str = Field(description="Name of the tenant consultancy")
    tenant_slug: str = Field(description="URL-friendly slug identifier of the tenant")
    plan_code: str | None = Field(
        description="Subscription plan code (starter/growth/enterprise) if assigned"
    )
    branches_count: int = Field(
        ge=0,
        description="Number of branches in this tenant",
    )
    staff_count: int = Field(
        ge=0,
        description="Number of staff accounts in this tenant",
    )
    students_count: int = Field(
        ge=0,
        description="Number of student accounts in this tenant",
    )
    applications_count: int = Field(
        ge=0,
        description="Total number of applications in this tenant",
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


class PlatformWideStatsResponse(BaseModel):
    """Response for GET /analytics/platform-wide-stats (E43; Journey J36).

    Returns aggregated metrics for all tenants on the platform,
    allowing Super Admins to monitor overall platform health, tenant
    growth, and usage patterns.

    The response is ordered by applications_count descending (highest
    volume tenants first).

    Counts reflect the current state as of the query time, filtered by
    the optional date range (created_at between start and end dates)
    which applies to applications and students only.
    """

    tenants: list[TenantStatsBucket] = Field(
        description="List of tenant metrics, ordered by applications_count descending"
    )
    total_tenants: int = Field(
        ge=0,
        description="Total number of tenants on the platform",
    )
    total_branches: int = Field(
        ge=0,
        description="Total number of branches across all tenants",
    )
    total_staff: int = Field(
        ge=0,
        description="Total number of staff across all tenants",
    )
    total_students: int = Field(
        ge=0,
        description="Total number of students across all tenants",
    )
    total_applications: int = Field(
        ge=0,
        description="Total number of applications across all tenants",
    )
