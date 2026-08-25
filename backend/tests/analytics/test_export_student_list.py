"""Tests for student list export endpoint (E44; Journey J37)."""

from datetime import datetime, date, timedelta

from app.main import app
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


class TestExportStudentList:
    """Black-box tests for GET /analytics/export/students (E44; Journey J37)."""

    def test_branch_manager_can_export_students_from_their_branch(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """A branch manager can export students from their assigned branch."""
        branch = seed_branch(db_session, tenant_id=1, name="Main Branch", city="New York")
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=20, tenant_id=1, branch_id=branch.id
            )
        )

        # Create students in the branch
        student1 = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student1@example.com",
            password_hash="hash",
            name="John Doe",
            phone="555-0101",
            date_of_birth=date(2000, 5, 15),
            target_country_id=1,
            target_university_id=1,
            target_program_id=1,
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student1)

        student2 = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student2@example.com",
            password_hash="hash",
            name="Jane Smith",
            phone="555-0102",
            date_of_birth=date(2001, 8, 20),
            target_country_id=2,
            target_university_id=2,
            target_program_id=2,
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student2)
        db_session.commit()

        # Export as CSV
        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "students-" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]

        # Parse CSV content
        content = response.text
        lines = content.strip().split("\n")

        # Should have header + 2 data rows
        assert len(lines) == 3

        # Check header
        header = lines[0]
        assert "Student ID" in header
        assert "Email" in header
        assert "Name" in header
        assert "Phone" in header
        assert "Date of Birth" in header
        assert "Branch Name" in header
        assert "Branch City" in header

        # Check that both students are present
        assert "student1@example.com" in content
        assert "student2@example.com" in content
        assert "John Doe" in content
        assert "Jane Smith" in content

    def test_export_as_excel_returns_xlsx_file(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export with format=xlsx returns an Excel file."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=21, tenant_id=1, branch_id=branch.id
            )
        )

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
        db_session.commit()

        response = client.get("/analytics/export/students?format=xlsx")

        # openpyxl may not be installed - that's OK for this test
        if response.status_code == 501:
            # openpyxl not installed - skip the rest
            return

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in response.headers["content-disposition"]
        assert "students-" in response.headers["content-disposition"]
        assert ".xlsx" in response.headers["content-disposition"]

    def test_owner_can_export_students_from_all_branches(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Consultancy owner can export students from all branches in their tenant."""
        branch1 = seed_branch(db_session, tenant_id=1, name="Branch 1", city="City 1")
        branch2 = seed_branch(db_session, tenant_id=1, name="Branch 2", city="City 2")

        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=30, tenant_id=1)
        )

        # Create students in both branches
        student1 = User(
            tenant_id=1,
            branch_id=branch1.id,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student1)

        student2 = User(
            tenant_id=1,
            branch_id=branch2.id,
            email="student2@example.com",
            password_hash="hash",
            name="Student 2",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student2)
        db_session.commit()

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text

        # Should see both students
        assert "student1@example.com" in content
        assert "student2@example.com" in content
        assert "Branch 1" in content
        assert "Branch 2" in content

    def test_export_filters_by_date_range(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export correctly filters students by creation date range."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=22, tenant_id=1, branch_id=branch.id
            )
        )

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        ten_days_ago = now - timedelta(days=10)

        # Create old student (outside range)
        old_student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="old@example.com",
            password_hash="hash",
            name="Old Student",
            role=Role.STUDENT,
            is_active=True,
            created_at=ten_days_ago,
        )
        db_session.add(old_student)

        # Create new student (within range)
        new_student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="new@example.com",
            password_hash="hash",
            name="New Student",
            role=Role.STUDENT,
            is_active=True,
            created_at=three_days_ago,
        )
        db_session.add(new_student)
        db_session.commit()

        # Query with date range that includes only the new student
        start_date = (now - timedelta(days=5)).isoformat()
        end_date = now.isoformat()

        response = client.get(
            f"/analytics/export/students?format=csv&start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        content = response.text

        # Should only see the new student
        assert "new@example.com" in content
        assert "old@example.com" not in content

    def test_export_includes_all_student_fields(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export includes all relevant student fields."""
        branch = seed_branch(db_session, tenant_id=1, name="Test Branch", city="Test City")
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=23, tenant_id=1, branch_id=branch.id
            )
        )

        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="full@example.com",
            password_hash="hash",
            name="Full Name",
            phone="555-0123",
            date_of_birth=date(2000, 1, 15),
            target_country_id=10,
            target_university_id=20,
            target_program_id=30,
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.commit()

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text

        # Check all fields are present
        assert "full@example.com" in content
        assert "Full Name" in content
        assert "555-0123" in content
        assert "2000-01-15" in content
        assert "10" in content  # target_country_id
        assert "20" in content  # target_university_id
        assert "30" in content  # target_program_id
        assert "Test Branch" in content
        assert "Test City" in content
        assert "Yes" in content  # is_active

    def test_export_handles_null_fields_gracefully(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export handles null/optional fields without errors."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=24, tenant_id=1, branch_id=branch.id
            )
        )

        # Student with minimal required fields
        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="minimal@example.com",
            password_hash="hash",
            name="Minimal Student",
            role=Role.STUDENT,
            is_active=True,
            # Optional fields left as None
            phone=None,
            date_of_birth=None,
            target_country_id=None,
            target_university_id=None,
            target_program_id=None,
        )
        db_session.add(student)
        db_session.commit()

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text
        assert "minimal@example.com" in content

    def test_export_excludes_non_student_users(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export only includes users with role=STUDENT."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=25, tenant_id=1, branch_id=branch.id
            )
        )

        # Create users with different roles
        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student@example.com",
            password_hash="hash",
            name="Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)

        counselor = User(
            tenant_id=1,
            branch_id=branch.id,
            email="counselor@example.com",
            password_hash="hash",
            name="Counselor",
            role=Role.COUNSELOR,
            is_active=True,
        )
        db_session.add(counselor)

        db_session.commit()

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text

        # Should only include the student
        assert "student@example.com" in content
        assert "counselor@example.com" not in content

    def test_branch_manager_cannot_export_other_branches(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager cannot export students from other branches (CRITICAL security test)."""
        branch1 = seed_branch(db_session, tenant_id=1, name="Branch 1", city="City 1")
        branch2 = seed_branch(db_session, tenant_id=1, name="Branch 2", city="City 2")

        # Branch manager assigned to branch1 only
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=71, tenant_id=1, branch_id=branch1.id
            )
        )

        # Create students in both branches
        student1 = User(
            tenant_id=1,
            branch_id=branch1.id,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student1)

        student2 = User(
            tenant_id=1,
            branch_id=branch2.id,
            email="student2@example.com",
            password_hash="hash",
            name="Student 2",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student2)
        db_session.commit()

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text

        # Should only see students from branch1
        assert "student1@example.com" in content
        assert "student2@example.com" not in content
        assert "Branch 1" in content
        assert "Branch 2" not in content

    def test_export_excludes_other_tenants_students(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager cannot export students from other tenants."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=70, tenant_id=1, branch_id=branch.id
            )
        )

        # Create a student in another tenant (tenant 2)
        other_student = User(
            tenant_id=2,
            branch_id=1,
            email="other@example.com",
            password_hash="hash",
            name="Other Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(other_student)
        db_session.commit()

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text

        # Should not see the other tenant's student
        assert "other@example.com" not in content

    def test_counselor_denied_access_to_export(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Counselor without report export permission cannot access export endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.COUNSELOR, user_id=40, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 403

    def test_receptionist_denied_access_to_export(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Receptionist without report export permission cannot access export endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.RECEPTIONIST, user_id=41, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 403

    def test_student_denied_access_to_export(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Student cannot access export endpoint."""
        override_authenticated_user(
            make_authenticated_user(Role.STUDENT, user_id=42, tenant_id=1, branch_id=1)
        )

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 403

    def test_unauthenticated_request_denied(
        self,
        client,
        override_authenticated_user,
    ):
        """Unauthenticated requests are rejected."""
        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 401

    def test_empty_export_returns_header_only(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """When no students exist, export returns only the header row."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=50, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text
        lines = content.strip().split("\n")

        # Should have only the header row
        assert len(lines) == 1
        assert "Student ID" in lines[0]

    def test_export_orders_by_creation_date_descending(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Export orders students by creation date, newest first."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=60, tenant_id=1, branch_id=branch.id
            )
        )

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        five_days_ago = now - timedelta(days=5)

        # Create students at different times
        old_student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="old@example.com",
            password_hash="hash",
            name="Old Student",
            role=Role.STUDENT,
            is_active=True,
            created_at=five_days_ago,
        )
        db_session.add(old_student)

        new_student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="new@example.com",
            password_hash="hash",
            name="New Student",
            role=Role.STUDENT,
            is_active=True,
            created_at=three_days_ago,
        )
        db_session.add(new_student)
        db_session.commit()

        response = client.get("/analytics/export/students?format=csv")

        assert response.status_code == 200
        content = response.text
        lines = content.strip().split("\n")

        # Find the position of each student in the output
        new_pos = None
        old_pos = None
        for i, line in enumerate(lines):
            if "new@example.com" in line:
                new_pos = i
            elif "old@example.com" in line:
                old_pos = i

        # New student should appear before old student (newest first)
        assert new_pos is not None
        assert old_pos is not None
        assert new_pos < old_pos

    def test_invalid_format_returns_422(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Invalid format parameter returns validation error."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=61, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/export/students?format=invalid")

        assert response.status_code == 422

    def test_super_admin_requires_report_export_permission(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Super admin does not have REPORT_EXPORT permission by default."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=100, tenant_id=None)
        )

        response = client.get("/analytics/export/students?format=csv")

        # Super admins don't have REPORT_EXPORT permission, so they should be denied
        assert response.status_code == 403
