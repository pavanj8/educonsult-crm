"""Shared CSV/Excel export helper utilities.

This module provides common functions for generating CSV and Excel exports
with security protections (CSV/Excel injection prevention) and consistent
formatting across all export endpoints.
"""

import csv
from datetime import datetime
from io import BytesIO, StringIO

from fastapi import Response
from openpyxl import Workbook
from openpyxl.styles import Font


def sanitize_cell_value(value) -> str:
    """Sanitize cell values to prevent CSV/Excel injection attacks.
    
    Cells starting with =, +, -, @ are potential formula injection vectors.
    Prefix them with a single quote to force Excel/CSV parsers to treat them
    as literal text rather than executable formulas.
    
    Args:
        value: Any value to sanitize (typically str, but handles other types)
        
    Returns:
        Sanitized string value safe for CSV/Excel export
        
    Reference:
        https://owasp.org/www-community/attacks/CSV_Injection
    """
    if not isinstance(value, str):
        return value
    if value and value[0] in ("=", "+", "-", "@"):
        return f"'{value}"
    return value


def generate_timestamped_filename(base_name: str, extension: str) -> str:
    """Generate a filename with timestamp for export files.
    
    Args:
        base_name: Base name for the file (e.g., "students", "conversion_funnel")
        extension: File extension without dot (e.g., "csv", "xlsx")
        
    Returns:
        Filename string with timestamp, e.g., "students-20250115_143022.csv"
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}-{timestamp}.{extension}"


def write_csv_response(
    rows: list[dict],
    base_filename: str,
) -> Response:
    """Generate CSV export response with injection protection.
    
    Args:
        rows: List of dictionaries with consistent keys (column headers)
        base_filename: Base name for the file (without extension)
        
    Returns:
        FastAPI Response with CSV content and appropriate headers
    """
    if not rows:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["No data available"])
        csv_content = output.getvalue()
    else:
        output = StringIO()
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        # Sanitize each row's values to prevent CSV injection
        sanitized_rows = []
        for row in rows:
            sanitized_row = {
                key: sanitize_cell_value(str(value)) if value is not None else ""
                for key, value in row.items()
            }
            sanitized_rows.append(sanitized_row)
        
        writer.writerows(sanitized_rows)
        csv_content = output.getvalue()

    filename = generate_timestamped_filename(base_filename, "csv")
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


def write_excel_response(
    rows: list[dict],
    base_filename: str,
    sheet_title: str = "Sheet1",
) -> Response:
    """Generate Excel export response with injection protection.
    
    Args:
        rows: List of dictionaries with consistent keys (column headers)
        base_filename: Base name for the file (without extension)
        sheet_title: Title for the Excel worksheet (default: "Sheet1")
        
    Returns:
        FastAPI Response with Excel content and appropriate headers
    """
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title

    if not rows:
        ws.append(["No data available"])
    else:
        # Write header row with bold font
        headers = list(rows[0].keys())
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Write data rows with sanitization
        for row in rows:
            sanitized_values = [
                sanitize_cell_value(str(value)) if value is not None else ""
                for value in row.values()
            ]
            ws.append(sanitized_values)

    # Save to bytes
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    excel_content = output.getvalue()

    filename = generate_timestamped_filename(base_filename, "xlsx")
    
    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
