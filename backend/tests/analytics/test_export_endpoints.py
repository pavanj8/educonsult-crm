"""Tests for analytics export endpoints (E44; Journey J37)."""

from datetime import datetime, timedelta

from app.models.application import Application
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


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
        assert 'attachment; filename="conversion_funnel.csv"' in response.headers["Content-Disposition"]

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


class TestExportRegistrationsOverTime:
    """Tests for GET /analytics/registrations/export (E44; Journey J37)."""

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

        response = client.get("/analytics/registrations/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers
        assert 'attachment; filename="registrations_over_time.csv"' in response.headers["Content-Disposition"]

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

        response = client.get("/analytics/registrations/export")

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
            f"/analytics/registrations/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
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

        response = client.get("/analytics/registrations/export")

        assert response.status_code == 403


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
        assert 'attachment; filename="branch_comparison.csv"' in response.headers["Content-Disposition"]

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
        assert 'attachment; filename="platform_wide_stats.csv"' in response.headers["Content-Disposition"]

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
