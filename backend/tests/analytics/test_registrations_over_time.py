"""Tests for registrations-over-time analytics endpoint (E41; Journey J34)."""

<<<<<<< HEAD
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status

from app.auth import create_access_token
from app.rbac.roles import Role
from tests.conftest import make_auth_headers
from tests.factories.users import make_authenticated_user


@pytest.fixture
def branch_manager_auth_headers(branch_manager_auth_headers):
    """Branch manager auth headers for analytics requests."""
    return branch_manager_auth_headers


@pytest.fixture
def owner_auth_headers(owner_auth_headers):
    """Consultancy owner auth headers (should see all branches)."""
    return owner_auth_headers


@pytest.fixture
def students_in_branch(make_user, branch_manager):
    """Create a set of student users with known registration dates."""
    base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    students = []

    # Create students on different dates
    offsets = [-15, -10, -5, -1, 0, 1, 2, 3, 10, 20]  # Days from base_time
    for offset in offsets:
        user = make_user(
            role=Role.STUDENT,
            tenant_id=branch_manager.tenant_id,
            branch_id=branch_manager.branch_id,
            created_at=base_time + timedelta(days=offset),
        )
        students.append(user)

    return students


def test_registrations_over_time_requires_permission(client, make_user):
    """Test that ANALYTICS_BRANCH permission is required."""
    # Create a counselor (no analytics permission)
    counselor = make_user(role=Role.COUNSELOR)
    counselor_auth = make_authenticated_user(
        Role.COUNSELOR,
        user_id=counselor.id,
        tenant_id=counselor.tenant_id,
        branch_id=counselor.branch_id,
    )
    token = create_access_token(counselor_auth)
    headers = make_auth_headers(token)

    response = client.get(
        "/analytics/registrations-over-time",
        headers=headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_registrations_over_time_branch_manager_sees_own_branch_only(
    client,
    branch_manager,
    branch_manager_auth_headers,
    students_in_branch,
    make_user,
):
    """Branch manager sees registrations only for their own branch."""
    # Create students in another branch (branch_id=2, not visible to branch_id=1 manager)
    other_base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    for offset in [-5, 0, 5]:
        make_user(
            role=Role.STUDENT,
            tenant_id=branch_manager.tenant_id,
            branch_id=2,  # Explicitly use branch 2, different from branch_manager.branch_id
            created_at=other_base_time + timedelta(days=offset),
        )

    # Query with a wide date range to capture all test data
    # Use date-only format for clarity
    # Start one day earlier to include the student at offset -15 (created on 2024-12-31)
    start_date = "2024-12-31"
    end_date = "2025-02-28"

    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)

    # Count total registrations in response
    total_count = sum(item["count"] for item in data)

    # Should only see students from own branch
    assert total_count == len(students_in_branch)


def test_registrations_over_time_owner_sees_all_branches(
    client,
    consultancy_owner,
    owner_auth_headers,
    branch_manager,
    other_branch_manager,
    students_in_branch,
    make_user,
):
    """Consultancy owner sees registrations across all branches in their tenant."""
    # Create students in first branch (already done via students_in_branch fixture)
    # Create students in second branch
    other_base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    other_students = []
    for offset in [-5, 0, 5]:
        student = make_user(
            role=Role.STUDENT,
            tenant_id=consultancy_owner.tenant_id,
            branch_id=other_branch_manager.branch_id,
            created_at=other_base_time + timedelta(days=offset),
        )
        other_students.append(student)

    # Query with owner token using date range that includes test data
    # Start one day earlier to include the student at offset -15 (created on 2024-12-31)
    start_date = "2024-12-31"
    end_date = "2025-02-28"
    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=owner_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    total_count = sum(item["count"] for item in data)

    # Owner should see students from both branches
    expected_total = len(students_in_branch) + len(other_students)
    assert total_count == expected_total


def test_registrations_over_time_default_date_range(
    client,
    branch_manager_auth_headers,
    students_in_branch,
):
    """Test default date range (last 30 days)."""
    # The students_in_branch fixture creates students around 2025-01-15
    # Default range should return data, but may not include the test data
    # depending on when the test runs. We just verify the endpoint works.
    response = client.get(
        "/analytics/registrations-over-time",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)

    # With 30-day window, we should get exactly 31 data points (one per day)
    # even if some have zero registrations
    assert len(data) == 31

    # All items should have 'date' and 'count' keys
    for item in data:
        assert "date" in item
        assert "count" in item
        assert isinstance(item["date"], str)
        assert isinstance(item["count"], int)


def test_registrations_over_time_custom_date_range(
    client,
    branch_manager_auth_headers,
    students_in_branch,
):
    """Test custom start_date and end_date parameters."""
    # Use date-only format for simplicity
    start_date = "2025-01-01"
    end_date = "2025-01-31"

    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)

    # Should have data for the custom range (31 days)
    assert len(data) == 31


def test_registrations_over_time_chronological_order(
    client,
    branch_manager_auth_headers,
    students_in_branch,
):
    """Results should be in chronological order."""
    # Use a specific date range that includes our test data
    start_date = "2025-01-01"
    end_date = "2025-02-28"

    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # Verify dates are in ascending order
    dates = [item["date"] for item in data]
    assert dates == sorted(dates)


def test_registrations_over_time_zero_counts_for_empty_days(
    client,
    branch_manager_auth_headers,
    students_in_branch,
):
    """Days with no registrations should have count=0."""
    # Use a wide date range that includes our test data
    start_date = "2025-01-01"
    end_date = "2025-02-28"

    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # With 10 students spread over ~59 days, there should be days with zero count
    zero_count_days = [item for item in data if item["count"] == 0]
    assert len(zero_count_days) > 0


def test_registrations_over_time_non_student_users_excluded(
    client,
    branch_manager,
    branch_manager_auth_headers,
    make_user,
):
    """Non-student users (counselors, verifiers, etc.) should not be counted."""
    base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Create various staff roles
    for role in [Role.COUNSELOR, Role.DOCUMENT_VERIFIER, Role.VISA_PROCESSOR]:
        make_user(
            role=role,
            tenant_id=branch_manager.tenant_id,
            branch_id=branch_manager.branch_id,
            created_at=base_time,
        )

    # Create some students
    for _ in range(3):
        make_user(
            role=Role.STUDENT,
            tenant_id=branch_manager.tenant_id,
            branch_id=branch_manager.branch_id,
            created_at=base_time,
        )

    # Query analytics with date range that includes the test data
    start_date = "2025-01-01"
    end_date = "2025-01-31"
    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # Count registrations for the specific date
    base_date_str = base_time.date().isoformat()
    registrations_on_date = next(
        (item for item in data if item["date"] == base_date_str),
        None,
    )

    assert registrations_on_date is not None
    # Should only count students, not staff
    assert registrations_on_date["count"] == 3


def test_registrations_over_time_isolated_by_tenant(
    client,
    branch_manager,
    branch_manager_auth_headers,
    make_user,
):
    """Users should only see registrations within their tenant."""
    # Create students in another tenant
    other_tenant_id = branch_manager.tenant_id + 999
    other_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    for _ in range(5):
        make_user(
            role=Role.STUDENT,
            tenant_id=other_tenant_id,
            branch_id=999,  # Different tenant, different branch
            created_at=other_time,
        )

    # Query with branch manager token
    response = client.get(
        "/analytics/registrations-over-time",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    total_count = sum(item["count"] for item in data)

    # Should not see students from other tenant
    # (we haven't created any in the branch manager's tenant in this test)
    assert total_count == 0


def test_registrations_over_time_includes_only_students(
    client,
    branch_manager,
    branch_manager_auth_headers,
    make_user,
):
    """Verify the query filters specifically for role='student'."""
    base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Create mix of users
    make_user(
        role=Role.STUDENT,
        tenant_id=branch_manager.tenant_id,
        branch_id=branch_manager.branch_id,
        created_at=base_time,
    )
    make_user(
        role=Role.COUNSELOR,
        tenant_id=branch_manager.tenant_id,
        branch_id=branch_manager.branch_id,
        created_at=base_time,
    )

    # Query analytics with date range that includes the test data
    start_date = "2025-01-01"
    end_date = "2025-01-31"
    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    base_date_str = base_time.date().isoformat()
    day_data = next((item for item in data if item["date"] == base_date_str), None)

    assert day_data is not None
    assert day_data["count"] == 1  # Only the student, not the counselor


def test_registrations_over_time_invalid_date_format_returns_422(
    client,
    branch_manager_auth_headers,
):
    """Test that invalid date format returns HTTP 422 validation error."""
    # Test with invalid start_date
    response = client.get(
        "/analytics/registrations-over-time?start_date=invalid-date",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid date format" in response.json()["detail"]

    # Test with invalid end_date
    response = client.get(
        "/analytics/registrations-over-time?end_date=not-a-date",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid date format" in response.json()["detail"]

    # Test with malformed ISO-8601 date
    response = client.get(
        "/analytics/registrations-over-time?start_date=2025-13-01",  # Invalid month
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid date format" in response.json()["detail"]
=======
from datetime import datetime, timedelta

from app.main import app
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


class TestRegistrationsOverTime:
    """Black-box tests for GET /analytics/registrations (E41; Journey J34)."""

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
        response = client.get("/analytics/registrations")

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
            f"/analytics/registrations?start_date={start_date}&end_date={end_date}"
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

        response = client.get("/analytics/registrations")

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

        response = client.get("/analytics/registrations")

        assert response.status_code == 403

    def test_unauthenticated_request_denied(
        self,
        client,
        override_authenticated_user,
    ):
        """Unauthenticated requests are rejected."""
        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/analytics/registrations")

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

        response = client.get("/analytics/registrations")

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

        response = client.get("/analytics/registrations")

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
        response = client.get("/analytics/registrations")

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

        response = client.get("/analytics/registrations")

        assert response.status_code == 200
        data = response.json()

        # Should only count the student
        assert data["total_registrations"] == 1
>>>>>>> origin/main
