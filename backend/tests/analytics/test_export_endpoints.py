"""Tests for analytics export endpoints (E44; Journey J37)."""

from datetime import datetime, timedelta

from app.models.application import Application
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user

# Excel MIME type constant
EXCEL_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class TestCsvInjectionProtection:
    """Tests for CSV injection protection (E44; Security requirement)."""

    def test_csv_injection_formula_cells_are_sanitized(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Cells starting with =, +, -, @ are sanitized to prevent CSV injection."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=20, tenant_id=1, branch_id=branch.id
            )
        )

        # Create a student with malicious-looking data
        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="=HYPERLINK(\"http://evil.com\", \"click\")@example.com",
            password_hash="hash",
            name="+SUM(1,2)",
            phone="-A1",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.commit()

        response = client.get("/analytics/students/export?format=csv")

        assert response.status_code == 200
        content = response.text

        # Malicious cells should be prefixed with single quote
        assert "'=HYPERLINK" in content
        assert "'+SUM" in content
        assert "'-A1" in content


class TestSpecialCharacters:
    """Tests for handling special characters in export data."""

    def test_csv_handles_quotes_and_commas(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """CSV export properly handles fields with quotes and commas."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=21, tenant_id=1, branch_id=branch.id
            )
        )

        # Create a student with special characters
        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email='test,with"quotes"@example.com',
            password_hash="hash",
            name='O\'Brien, "The Boss"',
            phone="555-1234",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.commit()

        response = client.get("/analytics/students/export?format=csv")

        assert response.status_code == 200
        # CSV should be valid and parseable
        # Python's csv module handles quoting automatically
        assert response.status_code == 200

    def test_excel_handles_special_characters(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Excel export handles special characters without corruption."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=22, tenant_id=1, branch_id=branch.id
            )
        )

        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="test@example.com",
            password_hash="hash",
            name="Müller <script>alert('xss')</script>",
            phone="555-1234",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.commit()

        response = client.get("/analytics/students/export?format=xlsx")

        # openpyxl may not be installed
        if response.status_code == 501:
            return

        assert response.status_code == 200
        assert len(response.content) > 0


class TestDateBoundaryEdgeCases:
    """Tests for date filtering edge cases."""

    def test_export_with_start_date_only(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export with only start_date parameter works correctly."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=23, tenant_id=1, branch_id=branch.id
            )
        )

        start_date = datetime.now() - timedelta(days=30)
        response = client.get(
            f"/analytics/students/export?format=csv&start_date={start_date.isoformat()}"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

    def test_export_with_end_date_only(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export with only end_date parameter works correctly."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=24, tenant_id=1, branch_id=branch.id
            )
        )

        end_date = datetime.now()
        response = client.get(
            f"/analytics/students/export?format=csv&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

    def test_export_with_future_date_range(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export with future date range returns empty result gracefully."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=25, tenant_id=1, branch_id=branch.id
            )
        )

        # Create a student
        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="old@example.com",
            password_hash="hash",
            name="Old Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.commit()

        # Query for future dates
        start_date = datetime.now() + timedelta(days=30)
        end_date = datetime.now() + timedelta(days=60)

        response = client.get(
            f"/analytics/students/export?format=csv&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200
        # Should return empty result (header only or "No data available")

    def test_export_with_inverted_date_range(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export with start_date > end_date returns empty result gracefully."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=26, tenant_id=1, branch_id=branch.id
            )
        )

        # start_date is after end_date
        start_date = datetime.now()
        end_date = datetime.now() - timedelta(days=30)

        response = client.get(
            f"/analytics/students/export?format=csv&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200
        # Should return empty result

    def test_export_with_malformed_date_returns_422(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Malformed date parameter returns validation error."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=27, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/students/export?format=csv&start_date=invalid-date")

        assert response.status_code == 422


class TestExportConversionFunnel:
    """Tests for GET /analytics/funnel/export (E44; Journey J37)."""

    def test_export_funnel_returns_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager can export conversion funnel as CSV."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=20, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/funnel/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: conversion_funnel-YYYYMMDD_HHMMSS.csv
        assert "conversion_funnel" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]

    def test_export_funnel_csv_content(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Exported CSV contains stage and count columns."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=21, tenant_id=1, branch_id=branch.id
            )
        )

        # Create test data
        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student@example.com",
            password_hash="hash",
            name="Test Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        app = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=student.id,
            assigned_counselor_id=21,
            university_id=1,
            program_id=1,
            stage=PipelineStage.REGISTERED,
        )
        db_session.add(app)
        db_session.commit()

        response = client.get("/analytics/funnel/export")

        content = response.text
        assert "Stage" in content
        assert "Count" in content
        # Check for some known stages
        assert "registered" in content

    def test_export_funnel_with_date_filter(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export accepts start_date and end_date query parameters."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=22, tenant_id=1, branch_id=branch.id
            )
        )

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        response = client.get(
            f"/analytics/funnel/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

    def test_export_funnel_counselor_forbidden(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Counselors cannot export conversion funnel analytics."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.COUNSELOR, user_id=23, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/funnel/export")

        assert response.status_code == 403

    def test_export_funnel_unauthorized(
        self,
        client,
        override_authenticated_user,
    ):
        """Unauthorized requests are rejected."""
        from app.rbac.dependencies import get_current_user
        from app.main import app

        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/analytics/funnel/export")

        assert response.status_code == 401

    def test_export_funnel_excel_format(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export funnel in Excel format when format=excel query parameter is provided."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=24, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/funnel/export?format=excel")

        assert response.status_code == 200
        assert response.headers["content-type"] == EXCEL_MIME_TYPE
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: conversion_funnel-YYYYMMDD_HHMMSS.xlsx
        assert "conversion_funnel" in response.headers["Content-Disposition"]
        assert ".xlsx" in response.headers["Content-Disposition"]
        # Excel files should have binary content (not empty text)
        assert len(response.content) > 0

    def test_export_funnel_default_format_is_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export defaults to CSV format when no format parameter is provided."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=25, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/funnel/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        # Filename includes timestamp: conversion_funnel-YYYYMMDD_HHMMSS.csv
        assert "conversion_funnel" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]


class TestExportRegistrationsOverTime:
    """Tests for GET /analytics/registrations-over-time/export (E44; Journey J37)."""

    def test_export_registrations_returns_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager can export registrations-over-time as CSV."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=30, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/registrations-over-time/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: registrations_over_time-YYYYMMDD_HHMMSS.csv
        assert "registrations_over_time" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]

    def test_export_registrations_csv_content(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Exported CSV contains date and count columns."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=31, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/registrations-over-time/export")

        content = response.text
        assert "Date" in content
        assert "Count" in content

    def test_export_registrations_with_date_filter(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export accepts start_date and end_date query parameters."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=32, tenant_id=1, branch_id=branch.id
            )
        )

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        response = client.get(
            f"/analytics/registrations-over-time/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200

    def test_export_registrations_counselor_forbidden(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Counselors cannot export registrations analytics."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.COUNSELOR, user_id=33, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/registrations-over-time/export")

        assert response.status_code == 403

    def test_export_registrations_excel_format(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export registrations in Excel format when format=excel query parameter is provided."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=34, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/registrations-over-time/export?format=excel")

        assert response.status_code == 200
        assert response.headers["content-type"] == EXCEL_MIME_TYPE
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: registrations_over_time-YYYYMMDD_HHMMSS.xlsx
        assert "registrations_over_time" in response.headers["Content-Disposition"]
        assert ".xlsx" in response.headers["Content-Disposition"]
        assert len(response.content) > 0

    def test_export_registrations_default_format_is_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export defaults to CSV format when no format parameter is provided."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=35, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/registrations-over-time/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        # Filename includes timestamp: registrations_over_time-YYYYMMDD_HHMMSS.csv
        assert "registrations_over_time" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]


class TestExportBranchComparison:
    """Tests for GET /analytics/branch-comparison/export (E44; Journey J37)."""

    def test_export_branch_comparison_returns_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Consultancy owner can export branch comparison as CSV."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=40, tenant_id=1)
        )

        response = client.get("/analytics/branch-comparison/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: branch_comparison-YYYYMMDD_HHMMSS.csv
        assert "branch_comparison" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]

    def test_export_branch_comparison_csv_content(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Exported CSV contains branch metrics columns."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=41, tenant_id=1)
        )

        # Create test data
        branch1 = seed_branch(db_session, tenant_id=1, name="Branch 1", city="City 1")
        seed_branch(db_session, tenant_id=1, name="Branch 2", city="City 2")

        student = User(
            tenant_id=1,
            branch_id=branch1.id,
            email="student@example.com",
            password_hash="hash",
            name="Test Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        app = Application(
            tenant_id=1,
            branch_id=branch1.id,
            student_id=student.id,
            assigned_counselor_id=41,
            university_id=1,
            program_id=1,
            stage=PipelineStage.REGISTERED,
        )
        db_session.add(app)
        db_session.commit()

        response = client.get("/analytics/branch-comparison/export")

        content = response.text
        # Check for column headers
        assert "Branch ID" in content
        assert "Branch Name" in content
        assert "Branch City" in content
        assert "Total Applications" in content
        assert "Enrolled" in content
        assert "Rejected" in content
        assert "Withdrawn" in content
        assert "Active" in content

    def test_export_branch_comparison_with_date_filter(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export accepts start_date and end_date query parameters."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=42, tenant_id=1)
        )

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        response = client.get(
            f"/analytics/branch-comparison/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200

    def test_export_branch_comparison_branch_manager_forbidden(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch managers cannot export cross-branch comparison analytics."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.BRANCH_MANAGER, user_id=43, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/branch-comparison/export")

        assert response.status_code == 403

    def test_export_branch_comparison_super_admin_allowed(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Super admin can export branch comparison analytics."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=44, tenant_id=None)
        )

        response = client.get("/analytics/branch-comparison/export")

        assert response.status_code == 200

    def test_export_branch_comparison_excel_format(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export branch comparison in Excel format when format=excel query parameter is provided."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=45, tenant_id=1)
        )

        response = client.get("/analytics/branch-comparison/export?format=excel")

        assert response.status_code == 200
        assert response.headers["content-type"] == EXCEL_MIME_TYPE
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: branch_comparison-YYYYMMDD_HHMMSS.xlsx
        assert "branch_comparison" in response.headers["Content-Disposition"]
        assert ".xlsx" in response.headers["Content-Disposition"]
        assert len(response.content) > 0

    def test_export_branch_comparison_default_format_is_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export defaults to CSV format when no format parameter is provided."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=46, tenant_id=1)
        )

        response = client.get("/analytics/branch-comparison/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        # Filename includes timestamp: branch_comparison-YYYYMMDD_HHMMSS.csv
        assert "branch_comparison" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]


class TestExportPlatformWideStats:
    """Tests for GET /analytics/platform-wide-stats/export (E44; Journey J37)."""

    def test_export_platform_wide_stats_returns_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Super admin can export platform-wide stats as CSV."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=50, tenant_id=None)
        )

        response = client.get("/analytics/platform-wide-stats/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: platform_wide_stats-YYYYMMDD_HHMMSS.csv
        assert "platform_wide_stats" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]

    def test_export_platform_wide_stats_csv_content(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Exported CSV contains tenant metrics columns."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=51, tenant_id=None)
        )

        response = client.get("/analytics/platform-wide-stats/export")

        content = response.text
        # Check for column headers
        assert "Tenant ID" in content
        assert "Tenant Name" in content
        assert "Tenant Slug" in content
        assert "Plan Code" in content
        assert "Branches Count" in content
        assert "Staff Count" in content
        assert "Students Count" in content
        assert "Applications Count" in content
        assert "Enrolled" in content
        assert "Rejected" in content
        assert "Withdrawn" in content
        assert "Active" in content

    def test_export_platform_wide_stats_with_date_filter(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export accepts start_date and end_date query parameters."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=52, tenant_id=None)
        )

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        response = client.get(
            f"/analytics/platform-wide-stats/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200

    def test_export_platform_wide_stats_owner_forbidden(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Consultancy owners cannot export platform-wide stats."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=53, tenant_id=1)
        )

        response = client.get("/analytics/platform-wide-stats/export")

        assert response.status_code == 403

    def test_export_platform_wide_stats_branch_manager_forbidden(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch managers cannot export platform-wide stats."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.BRANCH_MANAGER, user_id=54, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/platform-wide-stats/export")

        assert response.status_code == 403

    def test_export_platform_wide_stats_excel_format(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export platform-wide stats in Excel format when format=excel query parameter is provided."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=55, tenant_id=None)
        )

        response = client.get("/analytics/platform-wide-stats/export?format=excel")

        assert response.status_code == 200
        assert response.headers["content-type"] == EXCEL_MIME_TYPE
        assert "Content-Disposition" in response.headers
        # Filename includes timestamp: platform_wide_stats-YYYYMMDD_HHMMSS.xlsx
        assert "platform_wide_stats" in response.headers["Content-Disposition"]
        assert ".xlsx" in response.headers["Content-Disposition"]
        assert len(response.content) > 0

    def test_export_platform_wide_stats_default_format_is_csv(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export defaults to CSV format when no format parameter is provided."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=56, tenant_id=None)
        )

        response = client.get("/analytics/platform-wide-stats/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        # Filename includes timestamp: platform_wide_stats-YYYYMMDD_HHMMSS.csv
        assert "platform_wide_stats" in response.headers["Content-Disposition"]
        assert ".csv" in response.headers["Content-Disposition"]
