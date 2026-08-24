"""Analytics routes (E41; Journey J34)."""

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
