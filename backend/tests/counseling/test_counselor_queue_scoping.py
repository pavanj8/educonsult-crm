"""Counselor queue scoping tests (E21; Journey J14; issue #158).

Complements ``backend/tests/applications/test_assigned_to_me.py`` (issue #156,
the backend endpoint task) with tests that pin down the **counselor-specific**
queue scoping rules required by J14: a counselor sees only applications
that are both

  * assigned to them (``Application.assigned_counselor_id == caller.id``), AND
  * in their own branch (``Application.branch_id == caller.branch_id``).

Both filters are enforced server-side regardless of query parameters; a
counselor cannot bypass them via ``branch_id=...``, ``stage=...``, or
``student_id=...`` query strings. These tests assert the cross-tenant
and cross-branch isolation boundaries that #156's broader
``test_assigned_to_me.py`` only covers from the branch-manager /
consultancy-owner angle.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.application import ApplicationStage
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Cross-branch isolation (the explicit gap called out by the Test Engineer's
# MEDIUM finding on iteration 3 of issue #158): a counselor must NEVER see an
# application that is assigned to them in a SIBLING branch of the same tenant.
# ---------------------------------------------------------------------------


def test_counselor_queue_excludes_applications_assigned_to_them_in_sibling_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Counselor in branch A cannot see an application assigned to them in branch B.

    Concretely: the counselor's user.id is used as ``assigned_counselor_id``
    for an application that lives in a sibling branch (the "before-reassignment"
    real-world state). When the counselor queries their queue from branch A,
    that application must NOT appear, even though the assignee id matches
    and they are explicitly trying to view their own work.
    """
    branch_a = seed_branch(db_session, tenant_id=1, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=1, name="Branch B", city="Delhi")

    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-crossbranch@example.test",
        tenant_id=1,
        branch_id=branch_a.id,
    )

    # Application assigned to the counselor, but in the sibling branch.
    # Real-world cause: the student transferred branches before counselor
    # reassignment ran. The queue must NOT show this row to the counselor
    # while the counselor's branch_id is branch_a.
    sibling_branch_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_b.id,
        assigned_counselor_id=counselor.id,
        university_id=11,
        program_id=21,
    )
    # Application assigned to the counselor, in their OWN branch. This
    # one SHOULD appear.
    own_branch_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_a.id,
        assigned_counselor_id=counselor.id,
        university_id=12,
        program_id=22,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=1,
            branch_id=branch_a.id,
        )
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
    returned_ids = {item["id"] for item in response.json()}
    assert own_branch_app.id in returned_ids, (
        "Counselor's own-branch application must be visible"
    )
    assert sibling_branch_app.id not in returned_ids, (
        "Counselor must NOT see an application assigned to them in a sibling branch"
    )


def test_counselor_queue_branch_id_filter_cannot_reach_sibling_branch(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A counselor's branch_id filter is pinned to their own branch.

    Even when the caller passes ``?branch_id=<sibling>``, the queue must
    still be empty for the counselor. Counselors do not get to pick the
    branch they are viewing; branch scoping is enforced by the server.
    """
    branch_a = seed_branch(db_session, tenant_id=1, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=1, name="Branch B", city="Delhi")

    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-branchfilter@example.test",
        tenant_id=1,
        branch_id=branch_a.id,
    )

    # Application in branch_b, assigned to the same counselor user.id
    # (so the only thing keeping it out of the queue is the branch filter).
    sibling_branch_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_b.id,
        assigned_counselor_id=counselor.id,
        university_id=11,
        program_id=21,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=1,
            branch_id=branch_a.id,
        )
    )

    response = client.get(f"/applications/assigned-to-me?branch_id={branch_b.id}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data == [], (
        f"branch_id=<sibling> must return an empty list for a counselor, "
        f"but got {data}"
    )
    # And the row is genuinely in branch_b so the test is meaningful.
    assert sibling_branch_app.branch_id == branch_b.id


# ---------------------------------------------------------------------------
# Cross-tenant isolation for counselors (Issue #158, J14, E21).
# The endpoint must enforce tenant_id scoping on top of the role check.
# ---------------------------------------------------------------------------


def test_counselor_queue_excludes_applications_from_other_tenant(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Counselor in tenant 1 cannot see their assignee-row in tenant 2."""
    branch_t1 = seed_branch(db_session, tenant_id=1, name="T1 Branch", city="Mumbai")
    branch_t2 = seed_branch(db_session, tenant_id=2, name="T2 Branch", city="Delhi")

    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-tenant@example.test",
        tenant_id=1,
        branch_id=branch_t1.id,
    )

    own_tenant_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_t1.id,
        assigned_counselor_id=counselor.id,
        university_id=11,
        program_id=21,
    )
    # Same user.id is used as the assignee in another tenant. The
    # tenant-scope filter must keep this row out of the queue.
    other_tenant_app = seed_application(
        db_session,
        tenant_id=2,
        branch_id=branch_t2.id,
        assigned_counselor_id=counselor.id,
        university_id=12,
        program_id=22,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=1,
            branch_id=branch_t1.id,
        )
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()}
    assert returned_ids == {own_tenant_app.id}, (
        f"Counselor must only see their own-tenant assigned row, "
        f"but got {returned_ids}; cross-tenant row {other_tenant_app.id} leaked"
    )


# ---------------------------------------------------------------------------
# Filtering behavior that the counselor queue MUST support (J14: filters).
# ---------------------------------------------------------------------------


def test_counselor_queue_stage_filter_is_case_insensitive(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Stage filter accepts the canonical lowercase value (the stage enum)."""
    branch = seed_branch(db_session, tenant_id=1, name="Branch", city="Mumbai")
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-stagefilter@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    counseling_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university_id=11,
        program_id=21,
        stage=ApplicationStage.COUNSELING,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university_id=12,
        program_id=22,
        stage=ApplicationStage.REGISTERED,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.get("/applications/assigned-to-me?stage=counseling")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == counseling_app.id
    assert data[0]["stage"] == "counseling"


def test_counselor_queue_combined_filters_use_and_semantics(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """stage + student_id filters AND together (both must match)."""
    branch = seed_branch(db_session, tenant_id=1, name="Branch", city="Mumbai")
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-combined@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        email="student-a-combined@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        email="student-b-combined@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    # Matches both filters
    target = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student_a.id,
        university_id=11,
        program_id=21,
        stage=ApplicationStage.COUNSELING,
    )
    # Wrong stage for student_a
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student_a.id,
        university_id=12,
        program_id=22,
        stage=ApplicationStage.REGISTERED,
    )
    # Right stage, wrong student
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student_b.id,
        university_id=13,
        program_id=23,
        stage=ApplicationStage.COUNSELING,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.get(
        f"/applications/assigned-to-me?stage=counseling&student_id={student_a.id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == target.id


def test_counselor_queue_unmatched_filter_returns_empty(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A filter that matches no rows returns an empty list, not an error."""
    branch = seed_branch(db_session, tenant_id=1, name="Branch", city="Mumbai")
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-unmatched@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="student-unmatched@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student.id,
        university_id=11,
        program_id=21,
        stage=ApplicationStage.REGISTERED,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    # No applications at the enrolled stage for this counselor.
    response = client.get("/applications/assigned-to-me?stage=enrolled")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Counselor without a branch assignment (defense-in-depth guard).
# ---------------------------------------------------------------------------


def test_counselor_without_branch_scope_is_rejected(
    client: TestClient,
) -> None:
    """A counselor with branch_id=None gets 403 'User has no branch scope'.

    The endpoint must not return rows to a counselor who is missing a
    branch assignment — they have no queue to show.
    """
    user = AuthenticatedUser(
        id=4242,
        role=Role.COUNSELOR,
        tenant_id=1,
        branch_id=None,
    )
    from app.main import app
    from app.rbac.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get("/applications/assigned-to-me")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403, (
        f"Expected 403 for counselor with branch_id=None, got {response.status_code}"
    )
    assert response.json()["detail"] == "User has no branch scope"


# ---------------------------------------------------------------------------
# Counselor queue response schema — only the assigned counselor's rows.
# ---------------------------------------------------------------------------


def test_counselor_queue_response_includes_only_own_assignments(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Every row returned to a counselor must have them as assigned_counselor_id."""
    branch = seed_branch(db_session, tenant_id=1, name="Branch", city="Mumbai")
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-own@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    other_counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-other@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university_id=11,
        program_id=21,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=other_counselor.id,
        university_id=12,
        program_id=22,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR,
            user_id=counselor.id,
            tenant_id=1,
            branch_id=branch.id,
        )
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["assigned_counselor_id"] == counselor.id