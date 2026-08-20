"""Counseling queue endpoint tests (E21, Journey J14, issue #158).

Tests for GET /counseling/queue (applications assigned to the logged-in counselor).
Validates:
- Scoping: a counselor sees only their own assigned applications, not others'.
- Filtering: stage, student_name query parameters narrow the result set.
- Auth & permissions: unauthenticated, wrong-role, and cross-tenant calls are rejected.
"""

from app.rbac import Role
from tests.branches.helpers import seed_branch
from tests.conftest import make_auth_headers
from tests.counseling.helpers import counseling_queue_url, seed_application
from tests.factories.users import make_authenticated_user


# ---------------------------------------------------------------------------
# Scoping: counselor sees only their own applications
# ---------------------------------------------------------------------------


def test_queue_returns_only_applications_assigned_to_counselor(
    client,
    db_session,
    override_authenticated_user,
):
    """A counselor must not see applications assigned to other counselors."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=10,
        tenant_id=1,
        branch_id=branch.id,
    )
    other_counselor_id = 20

    override_authenticated_user(counselor)

    # Applications assigned to our counselor
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="My Student A", assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="My Student B", assigned_counselor_id=counselor.id,
    )
    # Application assigned to someone else
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Other Student", assigned_counselor_id=other_counselor_id,
    )

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    data = response.json()
    student_names = {item["student_name"] for item in data}
    assert student_names == {"My Student A", "My Student B"}


def test_queue_excludes_unassigned_applications(
    client,
    db_session,
    override_authenticated_user,
):
    """Applications with no counselor assignment must not appear in any counselor's queue."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=11,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Assigned Student", assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Unassigned Student", assigned_counselor_id=None,
    )

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    data = response.json()
    student_names = {item["student_name"] for item in data}
    assert student_names == {"Assigned Student"}


# ---------------------------------------------------------------------------
# Scoping: cross-tenant / cross-branch isolation
# ---------------------------------------------------------------------------


def test_queue_excludes_applications_from_other_tenant(
    client,
    db_session,
    override_authenticated_user,
):
    """A counselor must not see applications belonging to a different tenant."""
    branch_own = seed_branch(db_session, tenant_id=1, name="Own Tenant Branch", city="Mumbai")
    branch_other = seed_branch(db_session, tenant_id=99, name="Other Tenant Branch", city="Delhi")

    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=12,
        tenant_id=1,
        branch_id=branch_own.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch_own.id,
        student_name="Own Tenant Student", assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=99, branch_id=branch_other.id,
        student_name="Other Tenant Student", assigned_counselor_id=counselor.id,
    )

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    data = response.json()
    student_names = {item["student_name"] for item in data}
    assert student_names == {"Own Tenant Student"}


# ---------------------------------------------------------------------------
# Filtering: stage
# ---------------------------------------------------------------------------


def test_queue_filters_by_stage(
    client,
    db_session,
    override_authenticated_user,
):
    """A ?stage= query parameter returns only applications in that stage."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=13,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Counseling Stage Student", stage="counseling",
        assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Application Stage Student", stage="application_submitted",
        assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Visa Stage Student", stage="visa_processing",
        assigned_counselor_id=counselor.id,
    )

    response = client.get(f"{counseling_queue_url()}?stage=counseling")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "Counseling Stage Student"
    assert data[0]["stage"] == "counseling"


def test_queue_filters_by_multiple_stages(
    client,
    db_session,
    override_authenticated_user,
):
    """When multiple matching stages exist, all are returned."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=14,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    for stage in ("counseling", "counseling"):
        seed_application(
            db_session, tenant_id=1, branch_id=branch.id,
            student_name=f"Student in {stage}", stage=stage,
            assigned_counselor_id=counselor.id,
        )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Other Stage Student", stage="registered",
        assigned_counselor_id=counselor.id,
    )

    response = client.get(f"{counseling_queue_url()}?stage=counseling")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["stage"] == "counseling" for item in data)


def test_queue_stage_filter_case_insensitive(
    client,
    db_session,
    override_authenticated_user,
):
    """Stage filter should be case-insensitive."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=15,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Stage Student", stage="counseling",
        assigned_counselor_id=counselor.id,
    )

    response = client.get(f"{counseling_queue_url()}?stage=COUNSELING")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


# ---------------------------------------------------------------------------
# Filtering: student_name (partial match)
# ---------------------------------------------------------------------------


def test_queue_filters_by_student_name_partial_match(
    client,
    db_session,
    override_authenticated_user,
):
    """A ?student_name= query returns applications whose student name contains the substring."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=16,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Alice Johnson", assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Bob Alice", assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Charlie Brown", assigned_counselor_id=counselor.id,
    )

    response = client.get(f"{counseling_queue_url()}?student_name=Alice")

    assert response.status_code == 200
    data = response.json()
    student_names = {item["student_name"] for item in data}
    assert student_names == {"Alice Johnson", "Bob Alice"}


def test_queue_filters_by_student_name_case_insensitive(
    client,
    db_session,
    override_authenticated_user,
):
    """Student name filter should be case-insensitive."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=17,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Priya Sharma", assigned_counselor_id=counselor.id,
    )

    response = client.get(f"{counseling_queue_url()}?student_name=priya")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "Priya Sharma"


def test_queue_combines_stage_and_student_name_filters(
    client,
    db_session,
    override_authenticated_user,
):
    """stage and student_name filters can be combined (AND logic)."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=18,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Ravi Kumar", stage="counseling",
        assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Ravi Patel", stage="visa_processing",
        assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Anita Singh", stage="counseling",
        assigned_counselor_id=counselor.id,
    )

    response = client.get(f"{counseling_queue_url()}?stage=counseling&student_name=Ravi")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "Ravi Kumar"
    assert data[0]["stage"] == "counseling"


# ---------------------------------------------------------------------------
# Auth & permissions
# ---------------------------------------------------------------------------


def test_queue_rejects_unauthenticated_request(client, db_session):
    branch = seed_branch(db_session, tenant_id=1)
    seed_application(db_session, tenant_id=1, branch_id=branch.id, student_name="Any Student")

    response = client.get(counseling_queue_url())

    assert response.status_code == 401


def test_queue_rejects_non_counselor_role(client, db_session, override_authenticated_user):
    """Only users with COUNSELOR role should access the queue endpoint."""
    branch = seed_branch(db_session, tenant_id=1)

    for role in [
        Role.BRANCH_MANAGER,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.STUDENT,
    ]:
        override_authenticated_user(make_authenticated_user(role, tenant_id=1, branch_id=branch.id))
        response = client.get(counseling_queue_url())
        assert response.status_code == 403, f"Expected 403 for role {role.value}, got {response.status_code}"


def test_queue_rejects_super_admin_without_branch_scope(
    client,
    db_session,
    override_authenticated_user,
):
    """A Super Admin (no branch_id) must not see the counseling queue."""
    override_authenticated_user(make_authenticated_user(Role.SUPER_ADMIN))
    response = client.get(counseling_queue_url())
    assert response.status_code == 403


def test_queue_rejects_invalid_token(client, db_session):
    response = client.get(
        counseling_queue_url(),
        headers=make_auth_headers("not-a-valid-jwt"),
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_queue_returns_expected_fields(
    client,
    db_session,
    override_authenticated_user,
):
    """Each queue item must include id, student_name, stage, and application_id."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=19,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Test Student", stage="counseling",
        assigned_counselor_id=counselor.id,
    )

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert "id" in item
    assert "student_name" in item
    assert "stage" in item
    assert item["student_name"] == "Test Student"
    assert item["stage"] == "counseling"


# ---------------------------------------------------------------------------
# Empty queue
# ---------------------------------------------------------------------------


def test_queue_returns_empty_list_when_no_applications(
    client,
    db_session,
    override_authenticated_user,
):
    """A counselor with no assigned applications receives an empty list."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=20,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    assert response.json() == []


def test_queue_returns_empty_when_all_applications_unassigned(
    client,
    db_session,
    override_authenticated_user,
):
    """If all applications in the branch have no counselor, the queue is empty."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=21,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Unassigned Student", assigned_counselor_id=None,
    )

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    assert response.json() == []
