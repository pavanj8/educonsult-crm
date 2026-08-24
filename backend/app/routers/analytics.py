"""Analytics routes (E41, E42; Journey J34, J35)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application
from app.models.branch import Branch
from app.pipeline.stages import PipelineStage
from app.rbac.dependencies import require_role
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.analytics import (
    BranchComparisonBucket,
    BranchComparisonResponse,
    ConversionFunnelBucket,
    ConversionFunnelResponse,
)

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


@router.get("/branch-comparison", response_model=BranchComparisonResponse)
def branch_comparison(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(
            require_role(
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
) -> BranchComparisonResponse:
    """Get cross-branch comparison for consultancy owner dashboard (E42; J35).

    Returns aggregated application metrics for all branches in the consultancy,
    allowing owners to compare performance across branches. Each branch bucket
    includes total application counts and breakdowns by terminal status
    (enrolled, rejected, withdrawn, active).

    **Permission**: ``ANALYTICS_CROSS_BRANCH`` (consultancy owner and super admin)

    **Scoping**:
    - Consultancy owners see all branches in their tenant
    - Super admins see all tenants (platform-wide view)

    **Date filtering**:
    - Both ``start_date`` and ``end_date`` are optional
    - When provided, filters applications by ``created_at`` timestamp
    - ``start_date`` is inclusive (>=), ``end_date`` is inclusive (<=)

    **Response structure**:
    - ``branches``: list of branch metrics ordered by total_applications descending
    - ``total_branches``: count of branches in the consultancy
    - ``total_applications``: sum of all applications across branches

    **Example**:
    ```json
    {
      "branches": [
        {
          "branch_id": 2,
          "branch_name": "Downtown Branch",
          "branch_city": "New York",
          "total_applications": 150,
          "enrolled_count": 30,
          "rejected_count": 15,
          "withdrawn_count": 10,
          "active_count": 95
        },
        {
          "branch_id": 1,
          "branch_name": "Uptown Branch",
          "branch_city": "New York",
          "total_applications": 100,
          "enrolled_count": 20,
          "rejected_count": 10,
          "withdrawn_count": 5,
          "active_count": 65
        }
      ],
      "total_branches": 2,
      "total_applications": 250
    }
    ```
    """
    try:
        # Build the base query for applications with tenant/branch scoping
        app_statement = apply_tenant_scope(select(Application), Application, current_user)

        # Apply date range filters if provided
        if start_date is not None:
            app_statement = app_statement.where(Application.created_at >= start_date)
        if end_date is not None:
            app_statement = app_statement.where(Application.created_at <= end_date)

        # Get all branches for this tenant
        branch_statement = apply_tenant_scope(select(Branch), Branch, current_user)
        branches = db.execute(branch_statement).scalars().all()

        if not branches:
            return BranchComparisonResponse(
                branches=[],
                total_branches=0,
                total_applications=0,
            )

        # Calculate metrics per branch using a single aggregated query
        # We'll join applications with branches and group by branch
        from sqlalchemy import Case

        # Create a subquery for application counts per branch
        app_counts = (
            app_statement.add_columns(
                Application.branch_id,
                func.count(Application.id).label("total_apps"),
                func.sum(
                    Case(
                        (Application.stage == PipelineStage.ENROLLED.value, 1),
                        else_=0,
                    )
                ).label("enrolled"),
                func.sum(
                    Case(
                        (Application.stage == PipelineStage.REJECTED.value, 1),
                        else_=0,
                    )
                ).label("rejected"),
                func.sum(
                    Case(
                        (Application.stage == PipelineStage.WITHDRAWN.value, 1),
                        else_=0,
                    )
                ).label("withdrawn"),
                func.sum(
                    Case(
                        (Application.stage == PipelineStage.ENROLLED.value, 0),
                        (Application.stage == PipelineStage.REJECTED.value, 0),
                        (Application.stage == PipelineStage.WITHDRAWN.value, 0),
                        else_=1,
                    )
                ).label("active"),
            )
            .group_by(Application.branch_id)
            .subquery()
        )

        # Join branches with application counts - apply tenant scoping to Branch query
        comparison_query = (
            select(
                Branch.id,
                Branch.name,
                Branch.city,
                app_counts.c.total_apps,
                app_counts.c.enrolled,
                app_counts.c.rejected,
                app_counts.c.withdrawn,
                app_counts.c.active,
            )
            .select_from(Branch)
            .outerjoin(app_counts, Branch.id == app_counts.c.branch_id)
            .order_by(app_counts.c.total_apps.desc())
        )

        # Apply tenant scoping to the comparison query
        comparison_query = apply_tenant_scope(comparison_query, Branch, current_user)

        results = db.execute(comparison_query).all()

        # Build branch buckets
        branches_list = []
        total_applications = 0

        for row in results:
            total_apps = row.total_apps if row.total_apps is not None else 0
            enrolled = row.enrolled if row.enrolled is not None else 0
            rejected = row.rejected if row.rejected is not None else 0
            withdrawn = row.withdrawn if row.withdrawn is not None else 0
            active = row.active if row.active is not None else 0

            branches_list.append(
                BranchComparisonBucket(
                    branch_id=row.id,
                    branch_name=row.name,
                    branch_city=row.city,
                    total_applications=total_apps,
                    enrolled_count=int(enrolled),
                    rejected_count=int(rejected),
                    withdrawn_count=int(withdrawn),
                    active_count=int(active),
                )
            )
            total_applications += total_apps

        return BranchComparisonResponse(
            branches=branches_list,
            total_branches=len(branches),
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
