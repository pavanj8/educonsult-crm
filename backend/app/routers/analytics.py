"""Analytics routes (E41, E42, E44; Journey J34, J35, J37)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.branch_scope import BranchScopeError, apply_branch_scope
from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application
from app.models.branch import Branch
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.dependencies import require_role
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.analytics import (
    BranchComparisonBucket,
    BranchComparisonResponse,
    ConversionFunnelBucket,
    ConversionFunnelResponse,
    PlatformWideStatsResponse,
    RegistrationsOverTimeBucket,
    RegistrationsOverTimeResponse,
    TenantStatsBucket,
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
        # Build the base query with tenant scoping
        statement = apply_tenant_scope(select(Application), Application, current_user)

        # Apply branch scoping (Branch Manager sees only their branch, Owner sees all)
        statement = apply_branch_scope(statement, Application, current_user)

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

    except (TenantScopeError, BranchScopeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/registrations-over-time", response_model=RegistrationsOverTimeResponse)
def registrations_over_time(
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
                "Filter registrations created on or after this date/time "
                "(ISO 8601 format). Defaults to beginning of available data."
            )
        ),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(
            description=(
                "Filter registrations created before or on this date/time "
                "(ISO 8601 format). Defaults to current time."
            )
        ),
    ] = None,
    db: Session = Depends(get_db),
) -> RegistrationsOverTimeResponse:
    """Get registrations-over-time for branch manager analytics (E41; J34).

    Returns a time-series of new student registrations grouped by date,
    filtered by creation date range and scoped to the caller's branch.

    **Permission**: ``ANALYTICS_BRANCH`` (branch manager and above)

    **Scoping**:
    - Branch managers see only registrations from their assigned branch
    - Consultancy owners see all branches in their tenant
    - Super admins see all tenants (platform-wide view)

    **Date filtering**:
    - Both ``start_date`` and ``end_date`` are optional
    - When provided, filters registrations by ``created_at`` timestamp
    - ``start_date`` is inclusive (>=), ``end_date`` is inclusive (<=)

    **Response structure**:
    - ``data``: list of date/count buckets ordered chronologically
    - ``total_registrations``: sum of all counts in the series

    **Example**:
    ```json
    {
      "data": [
        {"date": "2024-01-01", "count": 5},
        {"date": "2024-01-02", "count": 8},
        {"date": "2024-01-03", "count": 12}
      ],
      "total_registrations": 25
    }
    ```
    """
    try:
        # Build the base query with tenant scoping - filter for STUDENT role only
        statement = apply_tenant_scope(select(User), User, current_user)

        # Apply branch scoping (Branch Manager sees only their branch, Owner sees all)
        statement = apply_branch_scope(statement, User, current_user)

        # Filter for students only (role = STUDENT)
        statement = statement.where(User.role == Role.STUDENT)

        # Apply date range filters if provided
        if start_date is not None:
            statement = statement.where(User.created_at >= start_date)
        if end_date is not None:
            statement = statement.where(User.created_at <= end_date)

        # Group by date (cast created_at to date) and count
        date_counts = (
            statement.add_columns(
                func.date(User.created_at).label("date"),
                func.count(User.id).label("count"),
            )
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )

        result = db.execute(date_counts).all()

        # Convert to response format
        data = [
            RegistrationsOverTimeBucket(
                date=str(row.date),
                count=row.count,
            )
            for row in result
        ]

        total_registrations = sum(row.count for row in result)

        return RegistrationsOverTimeResponse(
            data=data,
            total_registrations=total_registrations,
        )

    except (TenantScopeError, BranchScopeError):
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


@router.get("/platform-wide-stats", response_model=PlatformWideStatsResponse)
def platform_wide_stats(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.SUPER_ADMIN)),
    ],
    start_date: Annotated[
        datetime | None,
        Query(
            description=(
                "Filter applications/students created on or after this date/time "
                "(ISO 8601 format). Defaults to beginning of available data. "
                "Does NOT filter tenants, branches, or staff counts."
            )
        ),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(
            description=(
                "Filter applications/students created before or on this date/time "
                "(ISO 8601 format). Defaults to current time. "
                "Does NOT filter tenants, branches, or staff counts."
            )
        ),
    ] = None,
    db: Session = Depends(get_db),
) -> PlatformWideStatsResponse:
    """Get platform-wide tenant stats for super admin dashboard (E43; Journey J36).

    Returns aggregated metrics for all tenants on the platform, allowing
    Super Admins to monitor overall platform health, tenant growth, and
    usage patterns. Each tenant bucket includes counts for branches,
    staff, students, applications (with terminal-stage breakdowns), and
    subscription plan code.

    **Permission**: ``SUPER_ADMIN`` only

    **Scoping**:
    - Super admins see all tenants on the platform (no filtering)

    **Date filtering**:
    - Both ``start_date`` and ``end_date`` are optional
    - When provided, filters applications and students by ``created_at`` timestamp
    - ``start_date`` is inclusive (>=), ``end_date`` is inclusive (<=)
    - Does NOT filter tenants, branches, or staff counts (these show current totals)

    **Response structure**:
    - ``tenants``: list of tenant metrics ordered by applications_count descending
    - ``total_tenants``: total number of tenants on the platform
    - ``total_branches``: total branches across all tenants
    - ``total_staff``: total staff across all tenants
    - ``total_students``: total students on the platform (filtered by date range)
    - ``total_applications``: total applications across all tenants (filtered by date range)

    **Example**:
    ```json
    {
      "tenants": [
        {
          "tenant_id": 1,
          "tenant_name": "ABC Consultancy",
          "tenant_slug": "abc-consultancy",
          "plan_code": "growth",
          "branches_count": 3,
          "staff_count": 12,
          "students_count": 150,
          "applications_count": 200,
          "enrolled_count": 40,
          "rejected_count": 20,
          "withdrawn_count": 10,
          "active_count": 130
        },
        {
          "tenant_id": 2,
          "tenant_name": "XYZ Education",
          "tenant_slug": "xyz-education",
          "plan_code": "starter",
          "branches_count": 1,
          "staff_count": 5,
          "students_count": 50,
          "applications_count": 75,
          "enrolled_count": 15,
          "rejected_count": 8,
          "withdrawn_count": 2,
          "active_count": 50
        }
      ],
      "total_tenants": 2,
      "total_branches": 4,
      "total_staff": 17,
      "total_students": 200,
      "total_applications": 275
    }
    ```
    """
    try:
        from sqlalchemy import Case

        # Get all tenants with their plan codes
        tenant_query = select(
            Tenant.id,
            Tenant.name,
            Tenant.slug,
            Plan.code.label("plan_code"),
        ).select_from(Tenant).outerjoin(Plan, Tenant.plan_id == Plan.id)

        tenants_result = db.execute(tenant_query).all()

        if not tenants_result:
            return PlatformWideStatsResponse(
                tenants=[],
                total_tenants=0,
                total_branches=0,
                total_staff=0,
                total_students=0,
                total_applications=0,
            )

        # Build list of tenant IDs for further queries
        tenant_ids = [row.id for row in tenants_result]
        tenant_map = {row.id: row for row in tenants_result}

        # Query branch counts per tenant
        branch_counts_query = (
            select(
                Branch.tenant_id,
                func.count(Branch.id).label("branches_count"),
            )
            .select_from(Branch)
            .where(Branch.tenant_id.in_(tenant_ids))
            .group_by(Branch.tenant_id)
        )
        branch_counts_result = db.execute(branch_counts_query).all()
        branch_counts_map = {row.tenant_id: row.branches_count for row in branch_counts_result}

        # Query staff counts per tenant (non-student roles)
        # Staff = all users who are NOT students
        staff_counts_query = (
            select(
                User.tenant_id,
                func.count(User.id).label("staff_count"),
            )
            .select_from(User)
            .where(User.tenant_id.in_(tenant_ids))
            .where(User.role != Role.STUDENT)
            .group_by(User.tenant_id)
        )
        staff_counts_result = db.execute(staff_counts_query).all()
        staff_counts_map = {row.tenant_id: row.staff_count for row in staff_counts_result}

        # Query student counts per tenant (with optional date filtering)
        student_counts_query = (
            select(
                User.tenant_id,
                func.count(User.id).label("students_count"),
            )
            .select_from(User)
            .where(User.tenant_id.in_(tenant_ids))
            .where(User.role == Role.STUDENT)
        )

        # Apply date filtering to students if provided
        if start_date is not None:
            student_counts_query = student_counts_query.where(User.created_at >= start_date)
        if end_date is not None:
            student_counts_query = student_counts_query.where(User.created_at <= end_date)

        student_counts_query = student_counts_query.group_by(User.tenant_id)
        student_counts_result = db.execute(student_counts_query).all()
        student_counts_map = {row.tenant_id: row.students_count for row in student_counts_result}

        # Query application counts per tenant (with optional date filtering)
        app_base_query = select(Application).where(Application.tenant_id.in_(tenant_ids))

        # Apply date filtering to applications if provided
        if start_date is not None:
            app_base_query = app_base_query.where(Application.created_at >= start_date)
        if end_date is not None:
            app_base_query = app_base_query.where(Application.created_at <= end_date)

        # Aggregate application metrics per tenant
        app_counts_query = (
            app_base_query.add_columns(
                Application.tenant_id,
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
            .group_by(Application.tenant_id)
            .subquery()
        )

        app_counts_result = db.execute(
            select(
                app_counts_query.c.tenant_id,
                app_counts_query.c.total_apps,
                app_counts_query.c.enrolled,
                app_counts_query.c.rejected,
                app_counts_query.c.withdrawn,
                app_counts_query.c.active,
            )
        ).all()

        app_counts_map = {}
        for row in app_counts_result:
            app_counts_map[row.tenant_id] = {
                "total_apps": row.total_apps if row.total_apps is not None else 0,
                "enrolled": int(row.enrolled) if row.enrolled is not None else 0,
                "rejected": int(row.rejected) if row.rejected is not None else 0,
                "withdrawn": int(row.withdrawn) if row.withdrawn is not None else 0,
                "active": int(row.active) if row.active is not None else 0,
            }

        # Build tenant buckets
        tenants_list = []
        total_branches = 0
        total_staff = 0
        total_students = 0
        total_applications = 0

        for tenant_id in tenant_ids:
            tenant_row = tenant_map[tenant_id]
            branches_count = branch_counts_map.get(tenant_id, 0)
            staff_count = staff_counts_map.get(tenant_id, 0)
            students_count = student_counts_map.get(tenant_id, 0)

            app_metrics = app_counts_map.get(tenant_id)
            if app_metrics:
                applications_count = app_metrics["total_apps"]
                enrolled_count = app_metrics["enrolled"]
                rejected_count = app_metrics["rejected"]
                withdrawn_count = app_metrics["withdrawn"]
                active_count = app_metrics["active"]
            else:
                applications_count = 0
                enrolled_count = 0
                rejected_count = 0
                withdrawn_count = 0
                active_count = 0

            tenants_list.append(
                TenantStatsBucket(
                    tenant_id=tenant_id,
                    tenant_name=tenant_row.name,
                    tenant_slug=tenant_row.slug,
                    plan_code=tenant_row.plan_code,
                    branches_count=branches_count,
                    staff_count=staff_count,
                    students_count=students_count,
                    applications_count=applications_count,
                    enrolled_count=enrolled_count,
                    rejected_count=rejected_count,
                    withdrawn_count=withdrawn_count,
                    active_count=active_count,
                )
            )

            total_branches += branches_count
            total_staff += staff_count
            total_students += students_count
            total_applications += applications_count

        # Order by applications_count descending
        tenants_list.sort(key=lambda t: t.applications_count, reverse=True)

        return PlatformWideStatsResponse(
            tenants=tenants_list,
            total_tenants=len(tenant_ids),
            total_branches=total_branches,
            total_staff=total_staff,
            total_students=total_students,
            total_applications=total_applications,
        )

    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None
