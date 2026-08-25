"""Analytics routes (E41, E42, E44; Journey J34, J35, J37)."""

import csv
from datetime import datetime
from io import StringIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from openpyxl import Workbook
from openpyxl.styles import Font
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
from app.routers.analytics_export import export_student_list
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

# Add export endpoint
router.add_api_route("/export/students", export_student_list, methods=["GET"])


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


@router.get("/registrations", response_model=RegistrationsOverTimeResponse)
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


def _write_csv_response(rows: list[dict], filename: str) -> Response:
    """Helper to write CSV data to a FastAPI response with appropriate headers."""
    if not rows:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["No data available"])
        csv_content = output.getvalue()
    else:
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        csv_content = output.getvalue()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


def _write_excel_response(rows: list[dict], filename: str) -> Response:
    """Helper to write Excel data to a FastAPI response with appropriate headers."""
    wb = Workbook()
    ws = wb.active

    if not rows:
        ws.append(["No data available"])
    else:
        # Write header row with bold font
        headers = list(rows[0].keys())
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Write data rows
        for row in rows:
            ws.append([row[key] for key in headers])

    # Save to bytes
    from io import BytesIO

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    excel_content = output.getvalue()

    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/funnel/export", response_class=Response)
def export_conversion_funnel(
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
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    format: Annotated[Literal["csv", "excel"], Query()] = "csv",
    db: Session = Depends(get_db),
) -> Response:
    """Export conversion funnel analytics to CSV/Excel (E44; Journey J37).

    Returns a CSV or Excel file containing the conversion funnel breakdown by stage.
    The data is the same as GET /analytics/funnel but formatted for download.

    **Permission**: ``ANALYTICS_BRANCH`` (branch manager and above)

    **Query Parameters**:
    - ``format``: Export format, either "csv" (default) or "excel"

    **Response**: ``text/csv`` or Excel MIME type with ``Content-Disposition: attachment``
    """
    funnel_data = conversion_funnel(
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        db=db,
    )

    rows = [
        {
            "Stage": bucket.stage,
            "Count": bucket.count,
        }
        for bucket in funnel_data.funnel
    ]

    rows.append(
        {
            "Stage": "TOTAL",
            "Count": funnel_data.total_applications,
        }
    )

    if format == "excel":
        filename = "conversion_funnel.xlsx"
        return _write_excel_response(rows, filename)
    else:
        filename = "conversion_funnel.csv"
        return _write_csv_response(rows, filename)


@router.get("/registrations/export", response_class=Response)
def export_registrations_over_time(
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
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    format: Annotated[Literal["csv", "excel"], Query()] = "csv",
    db: Session = Depends(get_db),
) -> Response:
    """Export registrations-over-time analytics to CSV/Excel (E44; Journey J37).

    Returns a CSV or Excel file containing the time-series of student registrations.
    The data is the same as GET /analytics/registrations but formatted for download.

    **Permission**: ``ANALYTICS_BRANCH`` (branch manager and above)

    **Query Parameters**:
    - ``format``: Export format, either "csv" (default) or "excel"

    **Response**: ``text/csv`` or Excel MIME type with ``Content-Disposition: attachment``
    """
    registrations_data = registrations_over_time(
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        db=db,
    )

    rows = [
        {
            "Date": bucket.date,
            "Count": bucket.count,
        }
        for bucket in registrations_data.data
    ]

    rows.append(
        {
            "Date": "TOTAL",
            "Count": registrations_data.total_registrations,
        }
    )

    if format == "excel":
        filename = "registrations_over_time.xlsx"
        return _write_excel_response(rows, filename)
    else:
        filename = "registrations_over_time.csv"
        return _write_csv_response(rows, filename)


@router.get("/branch-comparison/export", response_class=Response)
def export_branch_comparison(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(
            require_role(
                Role.CONSULTANCY_OWNER,
                Role.SUPER_ADMIN,
            )
        ),
    ],
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    format: Annotated[Literal["csv", "excel"], Query()] = "csv",
    db: Session = Depends(get_db),
) -> Response:
    """Export cross-branch comparison analytics to CSV/Excel (E44; Journey J37).

    Returns a CSV or Excel file containing branch comparison metrics.
    The data is the same as GET /analytics/branch-comparison but formatted for download.

    **Permission**: ``ANALYTICS_CROSS_BRANCH`` (consultancy owner and super admin)

    **Query Parameters**:
    - ``format``: Export format, either "csv" (default) or "excel"

    **Response**: ``text/csv`` or Excel MIME type with ``Content-Disposition: attachment``
    """
    comparison_data = branch_comparison(
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        db=db,
    )

    rows = [
        {
            "Branch ID": bucket.branch_id,
            "Branch Name": bucket.branch_name,
            "Branch City": bucket.branch_city,
            "Total Applications": bucket.total_applications,
            "Enrolled": bucket.enrolled_count,
            "Rejected": bucket.rejected_count,
            "Withdrawn": bucket.withdrawn_count,
            "Active": bucket.active_count,
        }
        for bucket in comparison_data.branches
    ]

    rows.append(
        {
            "Branch ID": "TOTAL",
            "Branch Name": f"{comparison_data.total_branches} branches",
            "Branch City": "",
            "Total Applications": comparison_data.total_applications,
            "Enrolled": "",
            "Rejected": "",
            "Withdrawn": "",
            "Active": "",
        }
    )

    if format == "excel":
        filename = "branch_comparison.xlsx"
        return _write_excel_response(rows, filename)
    else:
        filename = "branch_comparison.csv"
        return _write_csv_response(rows, filename)


@router.get("/platform-wide-stats/export", response_class=Response)
def export_platform_wide_stats(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.SUPER_ADMIN)),
    ],
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    format: Annotated[Literal["csv", "excel"], Query()] = "csv",
    db: Session = Depends(get_db),
) -> Response:
    """Export platform-wide tenant stats to CSV/Excel (E44; Journey J37).

    Returns a CSV or Excel file containing platform-wide tenant metrics.
    The data is the same as GET /analytics/platform-wide-stats but formatted for download.

    **Permission**: ``SUPER_ADMIN`` only

    **Query Parameters**:
    - ``format``: Export format, either "csv" (default) or "excel"

    **Response**: ``text/csv`` or Excel MIME type with ``Content-Disposition: attachment``
    """
    stats_data = platform_wide_stats(
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        db=db,
    )

    rows = [
        {
            "Tenant ID": bucket.tenant_id,
            "Tenant Name": bucket.tenant_name,
            "Tenant Slug": bucket.tenant_slug,
            "Plan Code": bucket.plan_code or "",
            "Branches Count": bucket.branches_count,
            "Staff Count": bucket.staff_count,
            "Students Count": bucket.students_count,
            "Applications Count": bucket.applications_count,
            "Enrolled": bucket.enrolled_count,
            "Rejected": bucket.rejected_count,
            "Withdrawn": bucket.withdrawn_count,
            "Active": bucket.active_count,
        }
        for bucket in stats_data.tenants
    ]

    rows.append(
        {
            "Tenant ID": "TOTAL",
            "Tenant Name": f"{stats_data.total_tenants} tenants",
            "Tenant Slug": "",
            "Plan Code": "",
            "Branches Count": stats_data.total_branches,
            "Staff Count": stats_data.total_staff,
            "Students Count": stats_data.total_students,
            "Applications Count": stats_data.total_applications,
            "Enrolled": "",
            "Rejected": "",
            "Withdrawn": "",
            "Active": "",
        }
    )

    if format == "excel":
        filename = "platform_wide_stats.xlsx"
        return _write_excel_response(rows, filename)
    else:
        filename = "platform_wide_stats.csv"
        return _write_csv_response(rows, filename)
