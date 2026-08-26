"""Tests for registrations-over-time analytics endpoint (E41; Journey J34)."""

from datetime import datetime, timedelta

from app.main import app
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


class TestRegistrationsOverTime:
    """Black-box tests for GET /analytics/registrations-over-time (E41; Journey J34)."""

    def test_branch_manager_can_view_registrations_for_their_branch(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """A branch manager can view registrations-over-time for their assigned branch."""
        # Create a branch and branch manager
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=20, tenant_id=1, branch_id=branch.id
            )
        )

        # Create students on different dates
        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        five_days_ago = now - timedelta(days=5)

        # Create students on different dates
        student1 = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
            created_at=five_days_ago,
        )
        db_session.add(student1)

        student2 = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student2@example.com",
            password_hash="hash",
            name="Student 2",
            role=Role.STUDENT,
            is_active=True,
            created_at=three_days_ago,
        )
        db_session.add(student2)

        # Add a non-student user (should not be counted)
        counselor = User(
            tenant_id=1,
            branch_id=branch.id,
            email="counselor@example.com",
            password_hash="hash",
            name="Counselor",
            role=Role.COUNSELOR,
            is_active=True,
            created_at=three_days_ago,
        )
        db_session.add(counselor)

        db_session.commit()

        # Call the registrations endpoint
        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "data" in data
        assert "total_registrations" in data
        assert isinstance(data["data"], list)

        # Verify total count (only students, not counselor)
        assert data["total_registrations"] == 2

        # Verify we have 2 data points (one per unique date)
        assert len(data["data"]) == 2

        # Verify dates are in chronological order
        dates = [dp["date"] for dp in data["data"]]
        assert dates == sorted(dates)

    def test_registrations_filtered_by_date_range(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Date range filters correctly narrow the registrations to created_at window."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=21, tenant_id=1, branch_id=branch.id
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
            f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only see the new student
        assert data["total_registrations"] == 1
        assert len(data["data"]) == 1

    def test_owner_views_registrations_across_all_branches(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Consultancy owner sees registrations aggregated across all branches."""
        # Create two branches
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

        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 200
        data = response.json()

        # Owner should see both branches' students
        assert data["total_registrations"] == 2

    def test_counselor_denied_access_to_registrations(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Counselor without analytics permission cannot access registrations endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.COUNSELOR, user_id=40, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 403

    def test_unauthenticated_request_denied(
        self,
        client,
        override_authenticated_user,
    ):
        """Unauthenticated requests are rejected."""
        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 401

    def test_empty_registrations_returns_empty_list(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """When no students exist, returns empty data list with total 0."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=50, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 200
        data = response.json()

        # Should have empty list and zero total
        assert data["total_registrations"] == 0
        assert data["data"] == []

    def test_registrations_excludes_other_tenants_students(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager cannot see registrations from other tenants."""
        # Create a branch and branch manager in tenant 1
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

        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 200
        data = response.json()

        # Should not see the other tenant's student
        assert data["total_registrations"] == 0

    def test_branch_manager_cannot_see_other_branches_in_same_tenant(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager cannot see registrations from other branches in the same tenant (CRITICAL security test)."""
        # Create two branches in the same tenant
        branch1 = seed_branch(db_session, tenant_id=1, name="Branch 1", city="City 1")
        branch2 = seed_branch(db_session, tenant_id=1, name="Branch 2", city="City 2")

        # Branch manager assigned to branch1 only
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=71, tenant_id=1, branch_id=branch1.id
            )
        )

        # Create a student in branch1
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

        # Create a student in branch2
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

        # Branch manager of branch1 queries the registrations
        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 200
        data = response.json()

        # Should only see students from branch1 (not branch2)
        assert data["total_registrations"] == 1

    def test_registrations_excludes_non_student_users(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Registrations endpoint only counts users with role=STUDENT."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=80, tenant_id=1, branch_id=branch.id
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

        branch_manager = User(
            tenant_id=1,
            branch_id=branch.id,
            email="bm@example.com",
            password_hash="hash",
            name="Branch Manager",
            role=Role.BRANCH_MANAGER,
            is_active=True,
        )
        db_session.add(branch_manager)

        owner = User(
            tenant_id=1,
            branch_id=branch.id,
            email="owner@example.com",
            password_hash="hash",
            name="Owner",
            role=Role.CONSULTANCY_OWNER,
            is_active=True,
        )
        db_session.add(owner)

        db_session.commit()

        response = client.get("/analytics/registrations-over-time")

        assert response.status_code == 200
        data = response.json()

        # Should only count the student
        assert data["total_registrations"] == 1
