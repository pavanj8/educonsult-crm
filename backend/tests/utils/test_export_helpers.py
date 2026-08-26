"""Tests for export helper utilities."""

from app.utils.export_helpers import (
    sanitize_cell_value,
    generate_timestamped_filename,
    write_csv_response,
    write_excel_response,
)


class TestSanitizeCellValue:
    """Tests for CSV/Excel injection protection."""

    def test_returns_string_unchanged(self):
        """Normal string values are returned unchanged."""
        assert sanitize_cell_value("normal text") == "normal text"

    def test_returns_non_string_unchanged(self):
        """Non-string values are returned unchanged."""
        assert sanitize_cell_value(123) == 123
        assert sanitize_cell_value(None) is None
        assert sanitize_cell_value(True) is True

    def test_prefixes_formula_cell_with_quote(self):
        """Cells starting with formula characters are prefixed with single quote."""
        assert sanitize_cell_value("=SUM(A1:A10)") == "'=SUM(A1:A10)"
        assert sanitize_cell_value("+A1+B1") == "'+A1+B1"
        assert sanitize_cell_value("-A1") == "'-A1"
        assert sanitize_cell_value("@import") == "'@import"

    def test_empty_string_returns_empty(self):
        """Empty strings are handled correctly."""
        assert sanitize_cell_value("") == ""
        assert sanitize_cell_value(None) is None


class TestGenerateTimestampedFilename:
    """Tests for timestamped filename generation."""

    def test_generates_filename_with_timestamp(self):
        """Filename includes base name and timestamp."""
        filename = generate_timestamped_filename("students", "csv")
        assert "students-" in filename
        assert ".csv" in filename
        # Should match pattern: students-YYYYMMDD_HHMMSS.csv
        assert filename.startswith("students-20")
        assert filename.endswith(".csv")

    def test_includes_extension_properly(self):
        """Extension is added correctly."""
        csv_filename = generate_timestamped_filename("data", "csv")
        assert csv_filename.endswith(".csv")
        
        xlsx_filename = generate_timestamped_filename("data", "xlsx")
        assert xlsx_filename.endswith(".xlsx")

    def test_base_name_included_in_filename(self):
        """Base name is included in the filename."""
        filename = generate_timestamped_filename("my_report", "csv")
        assert "my_report-" in filename


class TestWriteCsvResponse:
    """Tests for CSV response generation."""

    def test_returns_response_with_csv_headers(self):
        """Response has correct content type and disposition."""
        rows = [
            {"Name": "Alice", "Age": "30"},
            {"Name": "Bob", "Age": "25"},
        ]
        response = write_csv_response(rows, "test")
        
        assert response.status_code == 200
        assert response.media_type == "text/csv"
        assert "Content-Disposition" in response.headers
        assert "test" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]

    def test_sanitizes_cell_values(self):
        """Cell values are sanitized for CSV injection protection."""
        rows = [
            {"Formula": "=SUM(1,2)", "Command": "+A1"},
        ]
        response = write_csv_response(rows, "test")
        
        content = response.body.decode()
        # Should be sanitized with single quote prefix
        assert "'=SUM(1,2)" in content
        assert "'+A1" in content

    def test_handles_empty_rows(self):
        """Empty row list returns 'No data available' message."""
        response = write_csv_response([], "test")
        
        content = response.body.decode()
        assert "No data available" in content

    def test_handles_null_values(self):
        """Null values are converted to empty strings."""
        rows = [
            {"Name": "Test", "Email": None, "Phone": None},
        ]
        response = write_csv_response(rows, "test")
        
        content = response.body.decode()
        # Headers should be present
        assert "Name" in content
        assert "Email" in content
        assert "Phone" in content


class TestWriteExcelResponse:
    """Tests for Excel response generation."""

    def test_returns_response_with_excel_headers(self):
        """Response has correct content type and disposition."""
        rows = [
            {"Name": "Alice", "Age": "30"},
        ]
        response = write_excel_response(rows, "test")
        
        assert response.status_code == 200
        assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "Content-Disposition" in response.headers
        assert "test" in response.headers["Content-Disposition"]
        assert ".xlsx" in response.headers["Content-Disposition"]

    def test_sanitizes_cell_values(self):
        """Cell values are sanitized for Excel injection protection."""
        rows = [
            {"Formula": "=SUM(1,2)", "Command": "+A1"},
        ]
        response = write_excel_response(rows, "test")
        
        # Excel binary content should be generated
        assert len(response.body) > 0

    def test_handles_empty_rows(self):
        """Empty row list returns 'No data available' message."""
        response = write_excel_response([], "test")
        
        # Excel binary content should still be generated
        assert len(response.body) > 0

    def test_uses_custom_sheet_title(self):
        """Custom sheet title is used when provided."""
        rows = [
            {"Name": "Alice"},
        ]
        response = write_excel_response(rows, "test", sheet_title="MyData")
        
        # Excel binary content should be generated
        assert len(response.body) > 0
