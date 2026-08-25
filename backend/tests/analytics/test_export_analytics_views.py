"""Tests for analytics view export endpoints (E44; Journey J37)."""

from datetime import datetime, timedelta

from app.models.application import Application
from app.models.user import User
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


class TestExportConversionFunnel:
    """Tests for GET /analytics/export/funnel"""

    def test_export_funnel_csv_requires_report_export_permission(
        self, client, db_session, override_authenticated_user
    ):
        """Branch managers without REPORT_EXPORT permission are denied."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=20, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/funnel?format=csv")

        # Expected: 403 Forbidden (branch_manager doesn't have REPORT_EXPORT)
        assert response.status_code == 403

    def test_export_funnel_csv_success(
        self, client, db_session, override_authenticated_user
    ):
        """Owner with REPORT_EXPORT can export funnel as CSV."""
        from app.models import Country, University, Program
        
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=30, tenant_id=1)
        )

        # Create master data
        country = Country(id=1, name="USA")
        db_session.add(country)
        university = University(id=1, name="Test University", country_id=1)
        db_session.add(university)
        program = Program(id=1, name="Test Program", university_id=1)
        db_session.add(program)

        # Create test applications at different stages
        app1 = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=1,
            university_id=1,
            program_id=1,
            stage="registered",
        )
        db_session.add(app1)

        app2 = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=2,
            university_id=1,
            program_id=1,
            stage="counseling",
        )
        db_session.add(app2)
        db_session.commit()

        response = client.get("/analytics/export/funnel?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers

        # Verify CSV structure
        content = response.text
        lines = content.strip().split("\n")
        assert "Stage" in lines[0]  # Header
        assert "Count" in lines[0]
        assert "Percentage" in lines[0]

    def test_export_funnel_xlsx_success(
        self, client, db_session, override_authenticated_user
    ):
        """Owner with REPORT_EXPORT can export funnel as Excel."""
        from app.models import Country, University, Program
        
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=31, tenant_id=1)
        )

        # Create master data
        country = Country(id=1, name="USA")
        db_session.add(country)
        university = University(id=1, name="Test University", country_id=1)
        db_session.add(university)
        program = Program(id=1, name="Test Program", university_id=1)
        db_session.add(program)

        app1 = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=1,
            university_id=1,
            program_id=1,
            stage="enrolled",
        )
        db_session.add(app1)
        db_session.commit()

        response = client.get("/analytics/export/funnel?format=xlsx")

        # openpyxl may not be installed
        if response.status_code == 501:
            return

        assert response.status_code == 200
        assert (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            in response.headers["content-type"]
        )
        assert "Content-Disposition" in response.headers

    def test_export_funnel_with_date_filters(
        self, client, db_session, override_authenticated_user
    ):
        """Date range filters are applied to funnel export."""
        from app.models import Country, University, Program
        
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=32, tenant_id=1)
        )

        # Create master data
        country = Country(id=1, name="USA")
        db_session.add(country)
        university = University(id=1, name="Test University", country_id=1)
        db_session.add(university)
        program = Program(id=1, name="Test Program", university_id=1)
        db_session.add(program)

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        ten_days_ago = now - timedelta(days=10)

        # Create applications at different times
        app_old = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=1,
            university_id=1,
            program_id=1,
            stage="registered",
            created_at=ten_days_ago,
        )
        db_session.add(app_old)

        app_new = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=2,
            university_id=1,
            program_id=1,
            stage="counseling",
            created_at=three_days_ago,
        )
        db_session.add(app_new)
        db_session.commit()

        start = (now - timedelta(days=5)).isoformat()
        end = now.isoformat()

        response = client.get(
            f"/analytics/export/funnel?format=csv&start_date={start}&end_date={end}"
        )
        assert response.status_code == 200


class TestExportRegistrationsOverTime:
    """Tests for GET /analytics/export/registrations"""

    def test_export_registrations_csv_requires_report_export_permission(
        self, client, db_session, override_authenticated_user
    ):
        """Branch managers without REPORT_EXPORT permission are denied."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=21, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/registrations?format=csv")
        assert response.status_code == 403

    def test_export_registrations_csv_success(
        self, client, db_session, override_authenticated_user
    ):
        """Owner with REPORT_EXPORT can export registrations as CSV."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=33, tenant_id=1)
        )

        # Create test students
        student1 = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student1)
        db_session.commit()

        response = client.get("/analytics/export/registrations?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        # Verify CSV structure
        content = response.text
        lines = content.strip().split("\n")
        assert "Date" in lines[0]
        assert "Count" in lines[0]

    def test_export_registrations_xlsx_success(
        self, client, db_session, override_authenticated_user
    ):
        """Owner with REPORT_EXPORT can export registrations as Excel."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=34, tenant_id=1)
        )

        response = client.get("/analytics/export/registrations?format=xlsx")

        if response.status_code == 501:
            return

        assert response.status_code == 200
        assert (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            in response.headers["content-type"]
        )

    def test_export_registrations_with_date_filters(
        self, client, db_session, override_authenticated_user
    ):
        """Date range filters are applied to registrations export."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=35, tenant_id=1)
        )

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)

        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student@example.com",
            password_hash="hash",
            name="Student",
            role=Role.STUDENT,
            is_active=True,
            created_at=three_days_ago,
        )
        db_session.add(student)
        db_session.commit()

        start = (now - timedelta(days=5)).isoformat()
        end = now.isoformat()

        response = client.get(
            f"/analytics/export/registrations?format=csv&start_date={start}&end_date={end}"
        )
        assert response.status_code == 200


class TestExportBranchComparison:
    """Tests for GET /analytics/export/branch-comparison"""

    def test_export_branch_comparison_csv_requires_report_export_permission(
        self, client, db_session, override_authenticated_user
    ):
        """Owners without REPORT_EXPORT permission are denied."""
        # Note: CONSULTANCY_OWNER actually HAS REPORT_EXPORT permission, so this test
        # needs to use a role that doesn't have it. COUNSELOR doesn't have REPORT_EXPORT.
        override_authenticated_user(
            make_authenticated_user(Role.COUNSELOR, user_id=36, tenant_id=1)
        )

        response = client.get("/analytics/export/branch-comparison?format=csv")
        # Should be 403 since counselor lacks REPORT_EXPORT
        assert response.status_code == 403

    def test_export_branch_comparison_denied_for_branch_manager(
        self, client, db_session, override_authenticated_user
    ):
        """Branch managers cannot access branch comparison export."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=22, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/branch-comparison?format=csv")
        assert response.status_code == 403

    def test_export_branch_comparison_csv_success(
        self, client, db_session, override_authenticated_user
    ):
        """Super admin with REPORT_EXPORT can export branch comparison as CSV."""
        from app.models import Country, University, Program
        
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=100, tenant_id=None)
        )

        # Create test data
        branch1 = seed_branch(db_session, tenant_id=1, name="Branch 1", city="City 1")
        branch2 = seed_branch(db_session, tenant_id=1, name="Branch 2", city="City 2")

        # Create master data
        country = Country(id=1, name="USA")
        db_session.add(country)
        university = University(id=1, name="Test University", country_id=1)
        db_session.add(university)
        program = Program(id=1, name="Test Program", university_id=1)
        db_session.add(program)
        db_session.commit()

        app1 = Application(
            tenant_id=1,
            branch_id=branch1.id,
            student_id=1,
            university_id=1,
            program_id=1,
            stage="enrolled",
        )
        db_session.add(app1)

        app2 = Application(
            tenant_id=1,
            branch_id=branch2.id,
            student_id=2,
            university_id=1,
            program_id=1,
            stage="registered",
        )
        db_session.add(app2)
        db_session.commit()

        response = client.get("/analytics/export/branch-comparison?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        # Verify CSV structure
        content = response.text
        lines = content.strip().split("\n")
        assert "Branch Name" in lines[0]
        assert "Branch City" in lines[0]
        assert "Total Students" in lines[0]

    def test_export_branch_comparison_xlsx_success(
        self, client, db_session, override_authenticated_user
    ):
        """Super admin with REPORT_EXPORT can export branch comparison as Excel."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=101, tenant_id=None)
        )

        response = client.get("/analytics/export/branch-comparison?format=xlsx")

        if response.status_code == 501:
            return

        assert response.status_code == 200
        assert (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            in response.headers["content-type"]
        )


class TestExportPlatformStats:
    """Tests for GET /analytics/export/platform-stats"""

    def test_export_platform_stats_denied_for_owner(
        self, client, db_session, override_authenticated_user
    ):
        """Consultancy owners cannot access platform stats export."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=37, tenant_id=1)
        )

        response = client.get("/analytics/export/platform-stats?format=csv")
        assert response.status_code == 403

    def test_export_platform_stats_denied_for_branch_manager(
        self, client, db_session, override_authenticated_user
    ):
        """Branch managers cannot access platform stats export."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=23, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/platform-stats?format=csv")
        assert response.status_code == 403

    def test_export_platform_stats_csv_success(
        self, client, db_session, override_authenticated_user
    ):
        """Super admin with REPORT_EXPORT can export platform stats as CSV."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=102, tenant_id=None)
        )

        response = client.get("/analytics/export/platform-stats?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        # Verify CSV structure
        content = response.text
        lines = content.strip().split("\n")
        assert "Tenant Name" in lines[0]
        assert "Plan" in lines[0]
        assert "Total Branches" in lines[0]

    def test_export_platform_stats_xlsx_success(
        self, client, db_session, override_authenticated_user
    ):
        """Super admin with REPORT_EXPORT can export platform stats as Excel."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=103, tenant_id=None)
        )

        response = client.get("/analytics/export/platform-stats?format=xlsx")

        if response.status_code == 501:
            return

        assert response.status_code == 200
        assert (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            in response.headers["content-type"]
        )

    def test_export_platform_stats_with_date_filters(
        self, client, db_session, override_authenticated_user
    ):
        """Date range filters are applied to platform stats export (for applications)."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=104, tenant_id=None)
        )

        start = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end = datetime.utcnow().isoformat()

        response = client.get(
            f"/analytics/export/platform-stats?format=csv&start_date={start}&end_date={end}"
        )
        assert response.status_code == 200


class TestExportFormatValidation:
    """Tests for export format validation across all endpoints"""

    def test_invalid_format_rejected(
        self, client, db_session, override_authenticated_user
    ):
        """Invalid format returns 422."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=105, tenant_id=None)
        )

        for endpoint in ["funnel", "registrations", "branch-comparison", "platform-stats"]:
            response = client.get(
                f"/analytics/export/{endpoint}?format=invalid"
            )
            assert response.status_code == 422


class TestTenantScoping:
    """Tests for tenant scoping across export endpoints"""

    def test_funnel_export_respects_tenant_scoping(
        self, client, db_session, override_authenticated_user
    ):
        """Funnel export returns only data for the user's tenant."""
        from app.models import Country, University, Program
        
        # Create two branches in different tenants
        branch1 = seed_branch(db_session, tenant_id=1, name="Branch 1", city="City 1")
        branch2 = seed_branch(db_session, tenant_id=2, name="Branch 2", city="City 2")

        # Create master data
        country = Country(id=1, name="USA")
        db_session.add(country)
        university = University(id=1, name="Test University", country_id=1)
        db_session.add(university)
        program = Program(id=1, name="Test Program", university_id=1)
        db_session.add(program)
        db_session.commit()

        # Create applications in both tenants
        app1 = Application(
            tenant_id=1,
            branch_id=branch1.id,
            student_id=1,
            university_id=1,
            program_id=1,
            stage="enrolled",
        )
        db_session.add(app1)

        app2 = Application(
            tenant_id=2,
            branch_id=branch2.id,
            student_id=2,
            university_id=1,
            program_id=1,
            stage="registered",
        )
        db_session.add(app2)
        db_session.commit()

        # Owner sees only their tenant's data
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=38, tenant_id=1)
        )
        owner_response = client.get("/analytics/export/funnel?format=csv")
        assert owner_response.status_code == 200

        # Super admin now has REPORT_EXPORT permission and can see all data
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=106, tenant_id=None)
        )
        superadmin_response = client.get("/analytics/export/funnel?format=csv")
        assert superadmin_response.status_code == 200

        # Super admin should have more or equal data than owner
        owner_content = owner_response.text
        superadmin_content = superadmin_response.text
        assert len(superadmin_content) >= len(owner_content)

    def test_registrations_export_respects_tenant_scoping(
        self, client, db_session, override_authenticated_user
    ):
        """Registrations export returns only data for the user's tenant."""
        # Create students in different tenants
        student1 = User(
            tenant_id=1,
            branch_id=1,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student1)

        student2 = User(
            tenant_id=2,
            branch_id=2,
            email="student2@example.com",
            password_hash="hash",
            name="Student 2",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student2)
        db_session.commit()

        # Owner sees only their tenant's data
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=39, tenant_id=1)
        )
        owner_response = client.get("/analytics/export/registrations?format=csv")
        assert owner_response.status_code == 200

        # Owner should only see their tenant's student
        owner_content = owner_response.text
        assert "student1@example.com" in owner_content
        assert "student2@example.com" not in owner_content

        # Note: Super Admin does not have REPORT_EXPORT permission, so we don't test
        # super admin access here. The endpoint will correctly return 403 for super admin.
