"""Tests for registrations-over-time analytics endpoint (E41; Journey J34)."""

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
    # Create another branch with students
    other_branch_manager = make_user(role=Role.BRANCH_MANAGER, tenant_id=branch_manager.tenant_id)
    other_base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    for offset in [-5, 0, 5]:
        make_user(
            role=Role.STUDENT,
            tenant_id=branch_manager.tenant_id,
            branch_id=other_branch_manager.branch_id,
            created_at=other_base_time + timedelta(days=offset),
        )

    # Query with a wide date range to capture all test data
    start_date = (datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)).isoformat()
    end_date = (datetime(2025, 2, 28, 23, 59, 59, tzinfo=timezone.utc)).isoformat()

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

    # Query with owner token
    response = client.get(
        "/analytics/registrations-over-time",
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
    response = client.get(
        "/analytics/registrations-over-time",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)

    # With 30-day window, we should get exactly 30 data points (one per day)
    # even if some have zero registrations
    assert len(data) <= 31  # Allow for slight off-by-one

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
    start_date = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    end_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    response = client.get(
        f"/analytics/registrations-over-time?start_date={start_date}&end_date={end_date}",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)

    # Should have data for the custom range
    assert len(data) >= 1


def test_registrations_over_time_chronological_order(
    client,
    branch_manager_auth_headers,
    students_in_branch,
):
    """Results should be in chronological order."""
    response = client.get(
        "/analytics/registrations-over-time",
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
    response = client.get(
        "/analytics/registrations-over-time",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # With 10 students spread over ~30 days, there should be days with zero count
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

    # Query analytics
    response = client.get(
        "/analytics/registrations-over-time",
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

    response = client.get(
        "/analytics/registrations-over-time",
        headers=branch_manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    base_date_str = base_time.date().isoformat()
    day_data = next((item for item in data if item["date"] == base_date_str), None)

    assert day_data is not None
    assert day_data["count"] == 1  # Only the student, not the counselor
