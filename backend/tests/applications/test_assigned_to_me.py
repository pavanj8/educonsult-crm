"""GET /applications/assigned-to-me endpoint tests (E21; Journey J14; issue #156).

Covers counselor queue visibility with optional filters: stage, branch_id, student_id.
"""

from app.models.application import ApplicationStage
from app.rbac.roles import Role
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
    """Consultancy owner sees assigned applications across all branches."""
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
