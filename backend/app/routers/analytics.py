"""Analytics routes (E41; Journey J34)."""

<<<<<<< HEAD
from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.branch_scope import apply_branch_scope
from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser

router = APIRouter()


def _require_analytics_permission(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """Check that user has either ANALYTICS_BRANCH or ANALYTICS_TENANT permission."""
    from app.rbac.permissions import get_permissions_for_role

    user_permissions = get_permissions_for_role(current_user.role)
    has_branch_analytics = Permission.ANALYTICS_BRANCH in user_permissions
    has_tenant_analytics = Permission.ANALYTICS_TENANT in user_permissions

    if not (has_branch_analytics or has_tenant_analytics):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user

_DB_UNAVAILABLE_DETAIL = "Analytics service is temporarily unavailable"


@router.get("/registrations-over-time")
def get_registrations_over_time(
    current_user: Annotated[AuthenticatedUser, Depends(_require_analytics_permission)],
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[
        str | None,
        Query(description="Start date (inclusive) in ISO-8601 format. Defaults to 30 days before end_date."),
    ] = None,
    end_date: Annotated[
        str | None,
        Query(description="End date (inclusive) in ISO-8601 format. Defaults to now (UTC)."),
    ] = None,
) -> list[dict]:
    """Get registration counts grouped by day for the caller's branch.

    Branch managers see their branch only; consultancy owners see all branches
    in their tenant. Results are returned in chronological order.

    Query parameters:
    - start_date: ISO-8601 datetime (inclusive). If omitted, defaults to 30 days before end_date.
    - end_date: ISO-8601 datetime (inclusive). If omitted, defaults to now (UTC).

    Returns:
        A list of dicts with keys: date (ISO-8601 date string), count (integer).
    """
    # Default date range: last 30 days
    if end_date is None:
        end_datetime = datetime.now(timezone.utc)
    else:
        # Parse ISO-8601 string to datetime with validation
        try:
            # Handles formats like: 2025-01-15T12:00:00+00:00 or 2025-01-15
            if "T" in end_date:
                # Full datetime with timezone
                end_datetime = datetime.fromisoformat(end_date)
                if end_datetime.tzinfo is None:
                    end_datetime = end_datetime.replace(tzinfo=timezone.utc)
            else:
                # Date only, treat as end of day UTC
                end_datetime = datetime.combine(
                    datetime.fromisoformat(end_date).date(),
                    time.max,
                    tzinfo=timezone.utc
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid date format for end_date. Expected ISO-8601 format (e.g., 2025-01-15 or 2025-01-15T12:00:00Z). Error: {str(e)}",
            ) from e

    if start_date is None:
        # 30 days before end_date
        start_datetime = end_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Subtract 30 days
        start_datetime = start_datetime - timedelta(days=30)
    else:
        # Parse ISO-8601 string to datetime with validation
        try:
            if "T" in start_date:
                start_datetime = datetime.fromisoformat(start_date)
                if start_datetime.tzinfo is None:
                    start_datetime = start_datetime.replace(tzinfo=timezone.utc)
            else:
                # Date only, treat as start of day UTC
                start_datetime = datetime.combine(
                    datetime.fromisoformat(start_date).date(),
                    time.min,
                    tzinfo=timezone.utc
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid date format for start_date. Expected ISO-8601 format (e.g., 2025-01-15 or 2025-01-15T12:00:00Z). Error: {str(e)}",
            ) from e

    # For grouping purposes, normalize both to start of day (inclusive) and end of day (inclusive)
    # Both datetimes should already have timezone info from the parsing above
    start_datetime = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_datetime = end_datetime.replace(hour=23, minute=59, second=59, microsecond=999999)

    try:
        # Build base query with tenant/branch scoping
        # SQLite stores datetimes as timezone-naive, so we need to strip timezone info from query parameters
        # for comparison to work correctly
        start_datetime_naive = start_datetime.replace(tzinfo=None)
        end_datetime_naive = end_datetime.replace(tzinfo=None)

        statement = select(User).where(
            User.role == Role.STUDENT,
            User.created_at >= start_datetime_naive,
            User.created_at <= end_datetime_naive,
        )

        # Apply scoping: branch manager sees only their branch, owner sees all
        statement = apply_tenant_scope(statement, User, current_user)
        statement = apply_branch_scope(statement, User, current_user)

        # Execute query
        users = list(db.scalars(statement).all())
=======
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application
from app.pipeline.stages import PipelineStage
from app.rbac.dependencies import require_role
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.analytics import ConversionFunnelBucket, ConversionFunnelResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Analytics service is temporarily unavailable"


@router.get("/funnel", response_model=ConversionFunnelResponse)
def conversion_funnel(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(
            require_role(
                Role.BRANCH_MANAGER,
                Role.CONSULTANCY_OWNER,
                Role.SUPER_ADMIN,
            )
        ),
    ],
    start_date: Annotated[
        datetime | None,
        Query(
            description=(
                "Filter applications created on or after this date/time "
                "(ISO 8601 format). Defaults to beginning of available data."
            )
        ),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(
            description=(
                "Filter applications created before or on this date/time "
                "(ISO 8601 format). Defaults to current time."
            )
        ),
    ] = None,
    db: Session = Depends(get_db),
) -> ConversionFunnelResponse:
    """Get conversion funnel by stage for branch manager analytics (E41; J34).

    Returns counts of applications grouped by their current pipeline stage,
    filtered by creation date range and scoped to the caller's branch.

    **Permission**: ``ANALYTICS_BRANCH`` (branch manager and above)

    **Scoping**:
    - Branch managers see only applications from their assigned branch
    - Consultancy owners see all branches in their tenant
    - Super admins see all tenants (platform-wide view)

    **Date filtering**:
    - Both ``start_date`` and ``end_date`` are optional
    - When provided, filters applications by ``created_at`` timestamp
    - ``start_date`` is inclusive (>=), ``end_date`` is inclusive (<=)

    **Response structure**:
    - ``funnel``: list of stage buckets ordered by pipeline progression
    - ``total_applications``: sum of all counts in the funnel

    **Example**:
    ```json
    {
      "funnel": [
        {"stage": "registered", "count": 120},
        {"stage": "counseling", "count": 85},
        {"stage": "university_shortlisting", "count": 60},
        {"stage": "application_submitted", "count": 45},
        {"stage": "document_verification", "count": 30},
        {"stage": "offer_letter", "count": 20},
        {"stage": "visa_processing", "count": 15},
        {"stage": "loan_processing", "count": 5},
        {"stage": "enrolled", "count": 10},
        {"stage": "rejected", "count": 8},
        {"stage": "withdrawn", "count": 4}
      ],
      "total_applications": 402
    }
    ```
    """
    try:
        # Build the base query with tenant/branch scoping
        statement = apply_tenant_scope(select(Application), Application, current_user)

        # Apply date range filters if provided
        if start_date is not None:
            statement = statement.where(Application.created_at >= start_date)
        if end_date is not None:
            statement = statement.where(Application.created_at <= end_date)

        # Group by stage and count
        stage_counts = (
            statement.add_columns(
                Application.stage,
                func.count(Application.id).label("count"),
            )
            .group_by(Application.stage)
            .order_by(Application.stage)
        )

        result = db.execute(stage_counts).all()

        # Convert to dict for easy lookup
        # result is list of Row objects; access by index or key
        counts_by_stage = {row.stage: row.count for row in result}

        # Build ordered funnel list based on PipelineStage enum order
        # We iterate through all enum values to ensure consistent ordering
        funnel = []
        for stage in PipelineStage:
            count = counts_by_stage.get(stage.value, 0)
            funnel.append(
                ConversionFunnelBucket(
                    stage=stage.value,
                    count=count,
                )
            )

        total_applications = sum(counts_by_stage.values())

        return ConversionFunnelResponse(
            funnel=funnel,
            total_applications=total_applications,
        )

>>>>>>> origin/main
    except TenantScopeError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None
<<<<<<< HEAD

    # Group by date in Python (simpler than database-specific date_trunc)

    # Initialize all dates in range with count 0
    counts_by_date: dict[str, int] = {}
    current = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = end_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

    while current <= end_day:
        date_key = current.date().isoformat()
        counts_by_date[date_key] = 0
        current += timedelta(days=1)

    # Count registrations per date
    for user in users:
        # Convert to user's date (UTC)
        user_date = user.created_at.replace(tzinfo=timezone.utc).date().isoformat()
        counts_by_date[user_date] = counts_by_date.get(user_date, 0) + 1

    # Convert to sorted list of dicts
    result = [
        {"date": date_str, "count": count}
        for date_str, count in sorted(counts_by_date.items())
    ]

    return result
=======
>>>>>>> origin/main
