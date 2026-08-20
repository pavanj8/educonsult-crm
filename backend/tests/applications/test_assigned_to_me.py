"""GET /applications/assigned-to-me endpoint tests (E21; Journey J14; issue #156).

Covers counselor queue visibility with optional filters: stage, branch_id, student_id.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.application import ApplicationStage
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


def test_assigned_to_me_returns_only_counselors_applications(
    client, db_session, override_authenticated_user
):
    """Counselor sees only their assigned applications."""
    branch = seed_branch(db_session, tenant_id=1, name="Counselor Branch", city="Mumbai")
    counselor_user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    other_counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="other-counselor@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    my_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor_user.id,
        university="MIT",
        program="MS CS",
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=other_counselor.id,
        university="Stanford",
        program="MBA",
    )

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor_user.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == my_app.id
    assert data[0]["assigned_counselor_id"] == counselor_user.id


def test_assigned_to_me_empty_when_no_assignments(
    client, db_session, override_authenticated_user
):
    """Counselor with no assigned applications gets empty list."""
    branch = seed_branch(db_session, tenant_id=1, name="Empty Branch", city="Delhi")
    counselor_user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="empty.counselor@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    # Create application assigned to a different counselor
    other_counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="other@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=other_counselor.id,
    )

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor_user.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    assert response.json() == []


def test_assigned_to_me_rejects_unauthenticated_request(client):
    """Unauthenticated requests are rejected."""
    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_assigned_to_me_rejects_student_role(client, db_session, override_authenticated_user):
    """Students cannot access the counselor queue."""
    student = make_db_user(db_session, Role.STUDENT, email="student@example.test", tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=student.id, tenant_id=1, branch_id=1)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_assigned_to_me_filters_by_stage(client, db_session, override_authenticated_user):
    """Stage filter returns only matching applications."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_db_user(db_session, Role.COUNSELOR, email="filter@example.test", tenant_id=1, branch_id=branch.id)

    registered_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university="MIT",
        program="MS CS",
        stage=ApplicationStage.REGISTERED,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university="Stanford",
        program="MBA",
        stage=ApplicationStage.COUNSELING,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university="Harvard",
        program="BA",
        stage=ApplicationStage.APPLICATION_SUBMITTED,
    )

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get("/applications/assigned-to-me?stage=registered")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == registered_app.id
    assert data[0]["stage"] == "registered"


def test_assigned_to_me_filters_by_student_id(client, db_session, override_authenticated_user):
    """student_id filter returns only applications for that student."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_db_user(db_session, Role.COUNSELOR, email="sid@example.test", tenant_id=1, branch_id=branch.id)

    student_a = make_db_user(db_session, Role.STUDENT, email="student-a@example.test", tenant_id=1, branch_id=branch.id)
    student_b = make_db_user(db_session, Role.STUDENT, email="student-b@example.test", tenant_id=1, branch_id=branch.id)

    app_a = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student_a.id,
        university="MIT",
        program="MS CS",
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student_b.id,
        university="Stanford",
        program="MBA",
    )

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get(f"/applications/assigned-to-me?student_id={student_a.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == app_a.id
    assert data[0]["student_id"] == student_a.id


def test_assigned_to_me_combines_stage_and_student_id_filters(
    client, db_session, override_authenticated_user
):
    """Both stage and student_id filters can be combined."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_db_user(db_session, Role.COUNSELOR, email="combo@example.test", tenant_id=1, branch_id=branch.id)

    student_a = make_db_user(db_session, Role.STUDENT, email="combo-a@example.test", tenant_id=1, branch_id=branch.id)

    app_a_registered = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student_a.id,
        university="MIT",
        program="MS CS",
        stage=ApplicationStage.REGISTERED,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        student_id=student_a.id,
        university="Stanford",
        program="MBA",
        stage=ApplicationStage.COUNSELING,
    )

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get(f"/applications/assigned-to-me?stage=registered&student_id={student_a.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == app_a_registered.id
    assert data[0]["stage"] == "registered"


def test_assigned_to_me_returns_all_stages_when_no_filter(
    client, db_session, override_authenticated_user
):
    """Without a stage filter, all stages are returned."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_db_user(db_session, Role.COUNSELOR, email="allstages@example.test", tenant_id=1, branch_id=branch.id)

    stages = [
        ApplicationStage.REGISTERED,
        ApplicationStage.COUNSELING,
        ApplicationStage.UNIVERSITY_SHORTLISTING,
        ApplicationStage.APPLICATION_SUBMITTED,
    ]
    app_ids = []
    for i, stage in enumerate(stages):
        app = seed_application(
            db_session,
            tenant_id=1,
            branch_id=branch.id,
            assigned_counselor_id=counselor.id,
            university=f"University {i}",
            program=f"Program {i}",
            stage=stage,
        )
        app_ids.append(app.id)

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    returned_ids = {item["id"] for item in data}
    assert returned_ids == set(app_ids)


def test_assigned_to_me_ordered_by_application_id(
    client, db_session, override_authenticated_user
):
    """Results are ordered by application id ascending."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_db_user(db_session, Role.COUNSELOR, email="ordered@example.test", tenant_id=1, branch_id=branch.id)

    app_ids = []
    for i in range(3):
        app = seed_application(
            db_session,
            tenant_id=1,
            branch_id=branch.id,
            assigned_counselor_id=counselor.id,
            university=f"U{i}",
            program=f"P{i}",
        )
        app_ids.append(app.id)

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    returned_ids = [item["id"] for item in data]
    assert returned_ids == sorted(app_ids)


def test_assigned_to_me_branch_manager_own_branch_only(
    client, db_session, override_authenticated_user
):
    """Branch manager can only see applications in their own branch."""
    branch_a = seed_branch(db_session, tenant_id=1, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=1, name="Branch B", city="Delhi")

    bm = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="bm@example.test",
        tenant_id=1,
        branch_id=branch_a.id,
    )
    counselor_in_b = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="c-b@example.test",
        tenant_id=1,
        branch_id=branch_b.id,
    )

    app_in_a = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_a.id,
        assigned_counselor_id=counselor_in_b.id,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_b.id,
        assigned_counselor_id=counselor_in_b.id,
    )

    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, user_id=bm.id, tenant_id=1, branch_id=branch_a.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == app_in_a.id


def test_assigned_to_me_consultancy_owner_sees_all_branches(
    client, db_session, override_authenticated_user
):
    """Consultancy owner sees applications across all branches."""
    branch_a = seed_branch(db_session, tenant_id=1, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=1, name="Branch B", city="Delhi")

    owner = make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@example.test",
        tenant_id=1,
    )
    counselor_a = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="c-a@example.test",
        tenant_id=1,
        branch_id=branch_a.id,
    )
    counselor_b = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="c-b@example.test",
        tenant_id=1,
        branch_id=branch_b.id,
    )

    app_a = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_a.id,
        assigned_counselor_id=counselor_a.id,
    )
    app_b = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_b.id,
        assigned_counselor_id=counselor_b.id,
    )

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=1)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    returned_ids = {item["id"] for item in data}
    assert returned_ids == {app_a.id, app_b.id}


def test_assigned_to_me_consultancy_owner_can_filter_by_branch(
    client, db_session, override_authenticated_user
):
    """Consultancy owner can filter applications by branch."""
    branch_a = seed_branch(db_session, tenant_id=1, name="Branch A", city="Mumbai")
    branch_b = seed_branch(db_session, tenant_id=1, name="Branch B", city="Delhi")

    owner = make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="filter-owner@example.test",
        tenant_id=1,
    )
    counselor_a = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="fca@example.test",
        tenant_id=1,
        branch_id=branch_a.id,
    )
    counselor_b = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="fcb@example.test",
        tenant_id=1,
        branch_id=branch_b.id,
    )

    app_a = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_a.id,
        assigned_counselor_id=counselor_a.id,
    )
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_b.id,
        assigned_counselor_id=counselor_b.id,
    )

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=1)
    )

    response = client.get(f"/applications/assigned-to-me?branch_id={branch_a.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == app_a.id


def test_assigned_to_me_cross_tenant_isolation(client, db_session, override_authenticated_user):
    """Counselor cannot see applications from another tenant."""
    branch_t1 = seed_branch(db_session, tenant_id=1, name="T1 Branch", city="Mumbai")
    branch_t2 = seed_branch(db_session, tenant_id=2, name="T2 Branch", city="Delhi")

    counselor_t1 = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="c-t1@example.test",
        tenant_id=1,
        branch_id=branch_t1.id,
    )
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="c-t2@example.test",
        tenant_id=2,
        branch_id=branch_t2.id,
    )

    app_t1 = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_t1.id,
        assigned_counselor_id=counselor_t1.id,
    )
    seed_application(
        db_session,
        tenant_id=2,
        branch_id=branch_t2.id,
        assigned_counselor_id=counselor_t1.id,  # Same user ID - should still be filtered by tenant
    )

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor_t1.id, tenant_id=1, branch_id=branch_t1.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    # Only tenant 1's application should be visible
    assert len(data) == 1
    assert data[0]["id"] == app_t1.id
    assert data[0]["tenant_id"] == 1


# ---------------------------------------------------------------------------
# New tests added in iteration 3 to address Review Agent feedback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.SUPER_ADMIN,
    ],
)
def test_assigned_to_me_rejects_disallowed_roles(
    client: TestClient, db_session: Session, override_authenticated_user, role: Role
) -> None:
    """All non-counselor/owner/manager roles get 403 with 'Insufficient permissions'."""
    user = make_db_user(
        db_session,
        role,
        email=f"{role.value}@example.test",
        tenant_id=1,
        branch_id=1,
    )
    override_authenticated_user(
        make_authenticated_user(role, user_id=user.id, tenant_id=1, branch_id=1)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_assigned_to_me_branch_manager_sees_unassigned_applications(
    client: TestClient, db_session: Session, override_authenticated_user
) -> None:
    """Branch manager sees unassigned applications (assigned_counselor_id IS NULL)."""
    branch = seed_branch(db_session, tenant_id=1, name="BM Branch", city="Mumbai")
    bm = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="bm-unassigned@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    # Unassigned application in the manager's branch
    unassigned_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=None,  # explicitly unassigned
        university="Oxford",
        program="MA History",
    )
    # Assigned application in the same branch
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-unassigned@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    assigned_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university="Cambridge",
        program="MSc Economics",
    )

    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, user_id=bm.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    returned_ids = {item["id"] for item in data}
    # Manager sees BOTH the assigned and unassigned applications
    assert returned_ids == {unassigned_app.id, assigned_app.id}


def test_assigned_to_me_consultancy_owner_sees_unassigned_applications(
    client: TestClient, db_session: Session, override_authenticated_user
) -> None:
    """Consultancy owner sees unassigned applications across all branches."""
    branch = seed_branch(db_session, tenant_id=1, name="Owner Branch", city="Mumbai")
    owner = make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner-unassigned@example.test",
        tenant_id=1,
    )

    unassigned_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=None,
        university="Yale",
        program="JD",
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-owner@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    assigned_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university="Princeton",
        program="PhD Math",
    )

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=owner.id, tenant_id=1)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    returned_ids = {item["id"] for item in data}
    # Owner sees BOTH assigned and unassigned applications
    assert returned_ids == {unassigned_app.id, assigned_app.id}


def test_assigned_to_me_counselor_does_not_see_unassigned_applications(
    client: TestClient, db_session: Session, override_authenticated_user
) -> None:
    """Counselors do NOT see unassigned applications (only their own)."""
    branch = seed_branch(db_session, tenant_id=1, name="Counselor No Unassigned", city="Mumbai")
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor-no-unassigned@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )

    # Unassigned application
    seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=None,
        university="Unseen U",
        program="Unseen P",
    )
    # Assigned to this counselor
    my_app = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        university="My U",
        program="My P",
    )

    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    response = client.get("/applications/assigned-to-me")

    assert response.status_code == 200
    data = response.json()
    # Counselor sees ONLY their assigned application, not the unassigned one
    assert len(data) == 1
    assert data[0]["id"] == my_app.id


@pytest.mark.parametrize(
    "params,expected_status",
    [
        # Invalid branch_id values
        ({"branch_id": "abc"}, 422),  # type: ignore[dict-item]
        ({"branch_id": 0}, 422),
        ({"branch_id": -1}, 422),
        # Invalid stage
        ({"stage": "invalid_stage"}, 422),
        ({"stage": ""}, 422),
        # Invalid student_id
        ({"student_id": 0}, 422),
        ({"student_id": -5}, 422),
        ({"student_id": "xyz"}, 422),  # type: ignore[dict-item]
    ],
)
def test_assigned_to_me_rejects_invalid_query_params(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    params: dict,
    expected_status: int,
) -> None:
    """Query parameters outside valid ranges or types return 422 Unprocessable Entity."""
    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="invalid-params@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    query = "&".join(f"{k}={v}" for k, v in params.items())
    response = client.get(f"/applications/assigned-to-me?{query}")

    assert response.status_code == expected_status, f"Expected {expected_status} for params {params}"


def test_assigned_to_me_503_on_database_unavailable(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
    monkeypatch,
) -> None:
    """OperationalError raised by db.scalars results in 503."""
    import sqlalchemy.exc

    from app.db.database import get_db

    branch = seed_branch(db_session, tenant_id=1)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="db-err@example.test",
        tenant_id=1,
        branch_id=branch.id,
    )
    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=1, branch_id=branch.id)
    )

    # Patch the db session's scalars method to raise OperationalError,
    # simulating a database unavailable condition.
    def _raise_op_error(*args, **kwargs):
        raise sqlalchemy.exc.OperationalError("statement", {}, ConnectionError("lost connection"))

    monkeypatch.setattr(db_session, "scalars", _raise_op_error)

    # Override get_db to return the monkeypatched session
    client.app.dependency_overrides[get_db] = lambda: db_session

    try:
        response = client.get("/applications/assigned-to-me")
        assert response.status_code == 503, f"Expected 503, got {response.status_code}: {response.json()}"
        assert response.json()["detail"] == "Application service is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(get_db, None)


def test_assigned_to_me_distinct_error_messages_per_failure_mode(
    client: TestClient, db_session: Session
) -> None:
    """Each HTTPException in the router uses a distinct detail message."""

    def check_role(role: Role, user_id: int, tenant_id: int | None, branch_id: int | None, expected_detail: str) -> None:
        from app.main import app
        from app.rbac.dependencies import get_current_user

        user = make_authenticated_user(role, user_id=user_id, tenant_id=tenant_id, branch_id=branch_id)
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.get("/applications/assigned-to-me")
            assert response.status_code == 403, f"Expected 403 for {role}, got {response.status_code}"
            assert response.json()["detail"] == expected_detail, (
                f"Expected detail '{expected_detail}' for {role}, got '{response.json()['detail']}'"
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    # Role with tenant_id=None (branch-scoped role like COUNSELOR without branch) -> "User has no branch scope"
    check_role(Role.COUNSELOR, user_id=2, tenant_id=1, branch_id=None, expected_detail="User has no branch scope")

    # Unrecognised role (STUDENT has the permission check go first and returns "Insufficient permissions")
    check_role(Role.STUDENT, user_id=3, tenant_id=1, branch_id=1, expected_detail="Insufficient permissions")


# ---------------------------------------------------------------------------
# Tests added in iteration 4 to address Review Agent feedback
# ---------------------------------------------------------------------------


def test_assigned_to_me_rejects_user_without_tenant_scope(
    client: TestClient,
    db_session: Session,
) -> None:
    """User with tenant_id=None gets 403 with 'User has no tenant scope'."""
    from app.main import app
    from app.rbac.dependencies import get_current_user

    # Construct a user with tenant_id=None (simulating a role that somehow
    # ended up without tenant context before reaching this endpoint)
    user = AuthenticatedUser(
        id=999,
        role=Role.COUNSELOR,
        tenant_id=None,
        branch_id=1,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get("/applications/assigned-to-me")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        assert response.json()["detail"] == "User has no tenant scope"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_assigned_to_me_branch_manager_cross_tenant_branch_filter_returns_empty(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Branch manager filtering by branch_id in another tenant gets empty list (safe by construction)."""
    # Tenant 1 branch
    branch_t1 = seed_branch(db_session, tenant_id=1, name="T1 Branch", city="Mumbai")
    # Tenant 2 branch
    branch_t2 = seed_branch(db_session, tenant_id=2, name="T2 Branch", city="Delhi")

    # BM in tenant 1
    bm_t1 = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="bm-t1@example.test",
        tenant_id=1,
        branch_id=branch_t1.id,
    )
    counselor_t1 = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="c-t1@example.test",
        tenant_id=1,
        branch_id=branch_t1.id,
    )

    # Application in tenant 1
    app_t1 = seed_application(
        db_session,
        tenant_id=1,
        branch_id=branch_t1.id,
        assigned_counselor_id=counselor_t1.id,
        university="MIT",
        program="MS CS",
    )
    # Application in tenant 2 (should not be visible)
    counselor_t2 = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="c-t2@example.test",
        tenant_id=2,
        branch_id=branch_t2.id,
    )
    seed_application(
        db_session,
        tenant_id=2,
        branch_id=branch_t2.id,
        assigned_counselor_id=counselor_t2.id,
        university="Oxford",
        program="MBA",
    )

    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, user_id=bm_t1.id, tenant_id=1, branch_id=branch_t1.id)
    )

    # Filter by tenant 2's branch_id - should return empty (not an error, no leakage)
    response = client.get(f"/applications/assigned-to-me?branch_id={branch_t2.id}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data == [], f"Expected empty list for cross-tenant branch_id, got {data}"
