"""Counseling queue endpoint tests (E21, Journey J14, issue #158).

Tests for GET /counseling/queue (applications assigned to the logged-in counselor).
Validates:
- Scoping: a counselor sees only their own assigned applications, not others'.
- Filtering: stage, student_name query parameters narrow the result set.
- Auth & permissions: unauthenticated, wrong-role, and cross-tenant calls are rejected.
- Input validation: stage enum and length limits on query parameters.
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


def test_queue_excludes_applications_from_other_branch(
    client,
    db_session,
    override_authenticated_user,
):
    """A counselor must not see applications assigned to them that belong to a different branch."""
    branch_a = seed_branch(db_session, tenant_id=1, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=1, name="Branch B", city="Delhi")

    # Same counselor exists in both branches (their auth user is scoped to branch_a)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=13,
        tenant_id=1,
        branch_id=branch_a.id,
    )
    override_authenticated_user(counselor)

    # Application assigned to the same counselor but in branch A — must appear
    seed_application(
        db_session, tenant_id=1, branch_id=branch_a.id,
        student_name="Branch A Student", assigned_counselor_id=counselor.id,
    )
    # Application assigned to the same counselor but in branch B — must NOT appear
    seed_application(
        db_session, tenant_id=1, branch_id=branch_b.id,
        student_name="Branch B Student", assigned_counselor_id=counselor.id,
    )

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    data = response.json()
    student_names = {item["student_name"] for item in data}
    assert student_names == {"Branch A Student"}


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
        user_id=14,
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


def test_queue_returns_all_matching_applications_for_single_stage(
    client,
    db_session,
    override_authenticated_user,
):
    """When multiple applications match a single stage filter, all are returned."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=15,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    for i in range(3):
        seed_application(
            db_session, tenant_id=1, branch_id=branch.id,
            student_name=f"Student in counseling #{i}", stage="counseling",
            assigned_counselor_id=counselor.id,
        )
    # Application in a different stage must not be returned
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Other Stage Student", stage="registered",
        assigned_counselor_id=counselor.id,
    )

    response = client.get(f"{counseling_queue_url()}?stage=counseling")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
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
        user_id=16,
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


def test_queue_rejects_invalid_stage(
    client,
    db_session,
    override_authenticated_user,
):
    """Invalid stage values return 422 with a structured error detail."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=50,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    response = client.get(f"{counseling_queue_url()}?stage=invalid_stage")

    assert response.status_code == 422
    data = response.json()
    # Structured error: consumers can parse allowed_values programmatically
    assert data["detail"]["error"] == "invalid_stage"
    assert isinstance(data["detail"]["allowed_values"], list)
    assert len(data["detail"]["allowed_values"]) > 0


def test_queue_invalid_stage_error_shows_pipeline_order(
    client,
    db_session,
    override_authenticated_user,
):
    """Invalid-stage error returns allowed_values in natural pipeline order, not alphabetical."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=54,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    response = client.get(f"{counseling_queue_url()}?stage=not_a_stage")

    assert response.status_code == 422
    data = response.json()
    allowed = data["detail"]["allowed_values"]
    # Pipeline order: registered → counseling → ... → withdrawn
    assert allowed[0] == "registered"
    assert allowed[-1] == "withdrawn"
    # Not alphabetical: "application_submitted" must come before "counseling"
    assert allowed.index("counseling") < allowed.index("application_submitted")


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
        user_id=17,
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
        user_id=18,
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
        user_id=19,
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


def test_queue_student_name_escapes_like_wildcards(
    client,
    db_session,
    override_authenticated_user,
):
    """LIKE wildcards (% and _) in student_name are escaped so they match literally."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=55,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Student % Name", assigned_counselor_id=counselor.id,
    )
    seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Test_Student", assigned_counselor_id=counselor.id,
    )

    # Searching for "%" returns only the student whose name literally contains %
    response = client.get(f"{counseling_queue_url()}?student_name=%")
    assert response.status_code == 200
    data = response.json()
    student_names = {item["student_name"] for item in data}
    assert student_names == {"Student % Name"}

    # Searching for "_" returns only the student whose name literally contains _
    response = client.get(f"{counseling_queue_url()}?student_name=_")
    assert response.status_code == 200
    data = response.json()
    student_names = {item["student_name"] for item in data}
    assert student_names == {"Test_Student"}


# ---------------------------------------------------------------------------
# Input validation: length limits
# ---------------------------------------------------------------------------


def test_queue_rejects_empty_student_name(
    client,
    db_session,
    override_authenticated_user,
):
    """Empty student_name query parameter returns 422."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=51,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    response = client.get(f"{counseling_queue_url()}?student_name=")

    assert response.status_code == 422


def test_queue_rejects_student_name_exceeds_max_length(
    client,
    db_session,
    override_authenticated_user,
):
    """student_name exceeding max length returns 422."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=52,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    long_name = "A" * 300  # exceeds 255 char limit
    response = client.get(f"{counseling_queue_url()}?student_name={long_name}")

    assert response.status_code == 422


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
        Role.CONSULTANCY_OWNER,
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
    """Each queue item exposes the six ApplicationQueueItem schema fields.

    Fields: id, student_id, student_name, stage, branch_id, assigned_counselor_id.
    """
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_authenticated_user(
        Role.COUNSELOR,
        user_id=20,
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(counselor)

    app = seed_application(
        db_session, tenant_id=1, branch_id=branch.id,
        student_name="Test Student", stage="counseling",
        assigned_counselor_id=counselor.id,
    )

    response = client.get(counseling_queue_url())

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    # Verify all six schema fields are present and hold the expected values
    assert "id" in item
    assert "student_id" in item
    assert "student_name" in item
    assert "stage" in item
    assert "branch_id" in item
    assert "assigned_counselor_id" in item
    assert item["id"] == app.id
    assert item["student_id"] == app.student_id
    assert item["student_name"] == "Test Student"
    assert item["stage"] == "counseling"
    assert item["branch_id"] == branch.id
    assert item["assigned_counselor_id"] == counselor.id


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
        user_id=21,
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
        user_id=22,
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
