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

router = None  # Will be included by main analytics router
_DB_UNAVAILABLE_DETAIL = "Analytics service is temporarily unavailable"


def _sanitize_cell_value(value: str) -> str:
    """Sanitize cell values to prevent CSV/Excel injection attacks.
    
    Cells starting with =, +, -, @ are potential formula injection vectors.
    Prefix them with a single quote to force Excel/CSV parsers to treat them
    as literal text rather than executable formulas.
    
    Reference: https://owasp.org/www-community/attacks/CSV_Injection
    """
    if not isinstance(value, str):
        return value
    if value and value[0] in ("=", "+", "-", "@"):
        return f"'{value}"
    return value


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
        import csv
        from io import StringIO

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

        if format == "csv":
            # Generate CSV content
            output = StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(
                [
                    "Student ID",
                    "Email",
                    "Name",
                    "Phone",
                    "Date of Birth",
                    "Branch Name",
                    "Branch City",
                    "Target Country ID",
                    "Target University ID",
                    "Target Program ID",
                    "Created At",
                    "Is Active",
                ]
            )

            # Write data rows with CSV injection protection
            for row in result:
                # Sanitize each field to prevent formula injection
                sanitized_row = [
                    _sanitize_cell_value(str(row.id)),
                    _sanitize_cell_value(row.email),
                    _sanitize_cell_value(row.name or ""),
                    _sanitize_cell_value(row.phone or ""),
                    _sanitize_cell_value(str(row.date_of_birth) if row.date_of_birth else ""),
                    _sanitize_cell_value(row.branch_name or ""),
                    _sanitize_cell_value(row.branch_city or ""),
                    _sanitize_cell_value(str(row.target_country_id) if row.target_country_id else ""),
                    _sanitize_cell_value(str(row.target_university_id) if row.target_university_id else ""),
                    _sanitize_cell_value(str(row.target_program_id) if row.target_program_id else ""),
                    _sanitize_cell_value(row.created_at.isoformat() if row.created_at else ""),
                    _sanitize_cell_value("Yes" if row.is_active else "No"),
                ]
                writer.writerow(sanitized_row)

            # Reset pointer to beginning
            output.seek(0)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"students-{timestamp}.csv"

            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
            )

        else:  # format == "xlsx"
            import io

            try:
                from openpyxl import Workbook
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="Excel export requires openpyxl library to be installed",
                ) from None

            # Create workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "Students"

            # Write header row
            headers = [
                "Student ID",
                "Email",
                "Name",
                "Phone",
                "Date of Birth",
                "Branch Name",
                "Branch City",
                "Target Country ID",
                "Target University ID",
                "Target Program ID",
                "Created At",
                "Is Active",
            ]
            ws.append(headers)

            # Write data rows with Excel injection protection
            for row in result:
                sanitized_row = [
                    _sanitize_cell_value(str(row.id)),
                    _sanitize_cell_value(row.email),
                    _sanitize_cell_value(row.name or ""),
                    _sanitize_cell_value(row.phone or ""),
                    _sanitize_cell_value(str(row.date_of_birth) if row.date_of_birth else ""),
                    _sanitize_cell_value(row.branch_name or ""),
                    _sanitize_cell_value(row.branch_city or ""),
                    _sanitize_cell_value(str(row.target_country_id) if row.target_country_id else ""),
                    _sanitize_cell_value(str(row.target_university_id) if row.target_university_id else ""),
                    _sanitize_cell_value(str(row.target_program_id) if row.target_program_id else ""),
                    _sanitize_cell_value(row.created_at.isoformat() if row.created_at else ""),
                    _sanitize_cell_value("Yes" if row.is_active else "No"),
                ]
                ws.append(sanitized_row)

            # Save to memory
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"students-{timestamp}.xlsx"

            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
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
