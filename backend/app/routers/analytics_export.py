"""Analytics export endpoint for student lists (E44; Journey J37)."""

from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.branch_scope import BranchScopeError, apply_branch_scope
from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.branch import Branch
from app.models.user import User
from app.rbac.dependencies import require_permission
from app.rbac.permissions import Permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.utils.export_helpers import (
    write_csv_response as write_csv_util,
)
from app.utils.export_helpers import (
    write_excel_response as write_excel_util,
)

router = None  # Will be included by main analytics router
_DB_UNAVAILABLE_DETAIL = "Analytics service is temporarily unavailable"


def export_student_list(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(
            require_permission(Permission.REPORT_EXPORT),
        ),
    ],
    format: Annotated[
        str,
        Query(
            description="Export format: 'csv' or 'xlsx'",
            pattern="^(csv|xlsx)$",
        ),
    ] = "csv",
    start_date: Annotated[
        datetime | None,
        Query(
            description=(
                "Filter students created on or after this date/time "
                "(ISO 8601 format). Defaults to beginning of available data."
            )
        ),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(
            description=(
                "Filter students created before or on this date/time "
                "(ISO 8601 format). Defaults to current time."
            )
        ),
    ] = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export student list to CSV or Excel (E44; Journey J37).

    Returns a downloadable file containing all students scoped to the
    caller's tenant/branch, with optional date range filtering on
    student creation date.

    **Permission**: ``REPORT_EXPORT`` (branch manager and above)

    **Scoping**:
    - Branch managers see only students from their assigned branch
    - Consultancy owners see all branches in their tenant
    - Super admins see all tenants (platform-wide view)

    **Date filtering**:
    - Both ``start_date`` and ``end_date`` are optional
    - When provided, filters students by ``created_at`` timestamp
    - ``start_date`` is inclusive (>=), ``end_date`` is inclusive (<=)

    **Export columns**:
    - Student ID
    - Email
    - Name
    - Phone
    - Date of Birth
    - Branch Name
    - Branch City
    - Target Country (ID or empty)
    - Target University (ID or empty)
    - Target Program (ID or empty)
    - Created At (ISO 8601)
    - Is Active

    **Response**:
    - CSV: ``text/csv`` with header row
    - Excel (``xlsx``): ``application/vnd.openxmlformats-officedocument.spreadsheetml.sheet``
    - filename includes ``students-`` and timestamp
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

        # Join with Branch to get branch name and city
        statement = statement.outerjoin(Branch, User.branch_id == Branch.id).add_columns(
            User.id,
            User.email,
            User.name,
            User.phone,
            User.date_of_birth,
            User.target_country_id,
            User.target_university_id,
            User.target_program_id,
            User.created_at,
            User.is_active,
            Branch.name.label("branch_name"),
            Branch.city.label("branch_city"),
        )

        # Order by creation date (newest first)
        statement = statement.order_by(User.created_at.desc())

        result = db.execute(statement).all()

        # Convert query results to list of dicts for export helpers
        rows = []
        for row in result:
            rows.append({
                "Student ID": str(row.id),
                "Email": row.email,
                "Name": row.name or "",
                "Phone": row.phone or "",
                "Date of Birth": str(row.date_of_birth) if row.date_of_birth else "",
                "Branch Name": row.branch_name or "",
                "Branch City": row.branch_city or "",
                "Target Country ID": str(row.target_country_id) if row.target_country_id else "",
                "Target University ID": str(row.target_university_id) if row.target_university_id else "",
                "Target Program ID": str(row.target_program_id) if row.target_program_id else "",
                "Created At": row.created_at.isoformat() if row.created_at else "",
                "Is Active": "Yes" if row.is_active else "No",
            })

        if format == "csv":
            return write_csv_util(rows, "students")
        else:  # format == "xlsx"
            return write_excel_util(rows, "students", sheet_title="Students")

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
