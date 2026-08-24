"""Analytics routes (E41; Journey J34)."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Analytics service is temporarily unavailable"


@router.get("/registrations-over-time")
def get_registrations_over_time(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.ANALYTICS_BRANCH))
    ],
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
        # Parse ISO-8601 string to datetime (handles both 'T' and space separators)
        # Python's isoformat() can produce space-separated format
        end_date = end_date.replace(" ", "T", 1) if " " in end_date else end_date
        end_datetime = datetime.fromisoformat(end_date)
        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(tzinfo=timezone.utc)

    if start_date is None:
        # 30 days before end_date
        start_datetime = end_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Subtract 30 days
        start_datetime = start_datetime - timedelta(days=30)
    else:
        # Parse ISO-8601 string to datetime
        start_date = start_date.replace(" ", "T", 1) if " " in start_date else start_date
        start_datetime = datetime.fromisoformat(start_date)
        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(tzinfo=timezone.utc)

    # Normalize to UTC midnight for consistent grouping
    start_datetime = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end_datetime = end_datetime.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)

    try:
        # Build base query with tenant/branch scoping
        statement = select(User).where(
            User.role == "student",
            User.created_at >= start_datetime,
            User.created_at <= end_datetime,
        )

        # Apply scoping: branch manager sees only their branch, owner sees all
        statement = apply_tenant_scope(statement, User, current_user)

        # Execute query
        users = list(db.scalars(statement).all())
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
