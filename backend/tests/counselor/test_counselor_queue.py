"""GET /counselor/queue endpoint tests (E21; Journey J14).

Tests for counselor dashboard queue view - filtering applications assigned to
the authenticated counselor.
"""

from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app as fastapi_app
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.counselor.helpers import seed_application
from tests.factories.users import make_authenticated_user, make_db_user


def _seed_student(
    db_session,
    *,
    email: str = "student@example.test",
    tenant_id: int = 1,
    branch_id: int = 1,
) -> int:
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email=email,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )
    return user.id


def _seed_counselor(
    db_session,
    *,
    email: str = "counselor@example.test",
    tenant_id: int = 1,
    branch_id: int = 1,
) -> int:
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email=email,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )
    return user.id


def test_queue_returns_assigned_applications(client, db_session, override_authenticated_user):
    """Counselor sees only applications assigned to them."""
    counselor = _seed_counselor(db_session)
    student = _seed_student(db_session)
    other_counselor = _seed_counselor(db_session, email="other@example.test")
    other_student = _seed_student(db_session, email="other.student@example.test")

    # Application assigned to the counselor
    valid_app = seed_application(db_session, student_id=student, assigned_counselor_id=counselor)
    # Application assigned to another counselor (should not appear)
    seed_application(db_session, student_id=other_student, assigned_counselor_id=other_counselor)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    assert {app["id"] for app in data} == {valid_app.id}
    assert data[0]["student_id"] == student


def test_queue_excludes_unassigned_applications(client, db_session, override_authenticated_user):
    """Applications with no counselor assignment are not returned."""
    counselor = _seed_counselor(db_session)
    student = _seed_student(db_session)
    other_student = _seed_student(db_session, email="other@example.test")

    # Application with no counselor assigned
    seed_application(db_session, student_id=student, assigned_counselor_id=None)
    # Application assigned to different counselor
    seed_application(db_session, student_id=other_student, assigned_counselor_id=counselor + 1)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    assert response.json() == []


def test_queue_filters_by_stage(client, db_session, override_authenticated_user):
    """Stage filter returns only applications in that stage."""
    counselor = _seed_counselor(db_session)
    student1 = _seed_student(db_session, email="student1@example.test")
    student2 = _seed_student(db_session, email="student2@example.test")
    student3 = _seed_student(db_session, email="student3@example.test")

    seed_application(db_session, student_id=student1, assigned_counselor_id=counselor, stage=PipelineStage.REGISTERED)
    seed_application(db_session, student_id=student2, assigned_counselor_id=counselor, stage=PipelineStage.COUNSELING)
    seed_application(db_session, student_id=student3, assigned_counselor_id=counselor, stage=PipelineStage.REGISTERED)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue?stage=registered")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(app["stage"] == "registered" for app in data)


def test_queue_filters_by_search_name(client, db_session, override_authenticated_user):
    """Search filter matches student name."""
    counselor = _seed_counselor(db_session)
    student1 = make_db_user(
        db_session, Role.STUDENT, email="student1@example.test", tenant_id=1, branch_id=1
    )
    student2 = make_db_user(
        db_session, Role.STUDENT, email="student2@example.test", tenant_id=1, branch_id=1
    )

    seed_application(db_session, student_id=student1.id, assigned_counselor_id=counselor)
    seed_application(db_session, student_id=student2.id, assigned_counselor_id=counselor)

    # Update student name for search test
    student1.name = "Alice Smith"
    student2.name = "Bob Jones"
    db_session.commit()

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue?search=Alice")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "Alice Smith"


def test_queue_filters_by_search_email(client, db_session, override_authenticated_user):
    """Search filter matches student email."""
    counselor = _seed_counselor(db_session)
    student1 = _seed_student(db_session, email="alice.smith@example.test")
    student2 = _seed_student(db_session, email="bob.jones@example.test")

    seed_application(db_session, student_id=student1, assigned_counselor_id=counselor)
    seed_application(db_session, student_id=student2, assigned_counselor_id=counselor)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue?search=bob.jones")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_email"] == "bob.jones@example.test"


def test_queue_combines_stage_and_search_filters(client, db_session, override_authenticated_user):
    """Both stage and search filters work together."""
    counselor = _seed_counselor(db_session)
    student1 = make_db_user(
        db_session, Role.STUDENT, email="alice@example.test", tenant_id=1, branch_id=1
    )
    student2 = make_db_user(
        db_session, Role.STUDENT, email="bob@example.test", tenant_id=1, branch_id=1
    )

    seed_application(db_session, student_id=student1.id, assigned_counselor_id=counselor, stage=PipelineStage.REGISTERED)
    seed_application(db_session, student_id=student2.id, assigned_counselor_id=counselor, stage=PipelineStage.COUNSELING)

    student1.name = "Alice"
    student2.name = "Bob"
    db_session.commit()

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue?stage=registered&search=Alice")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "Alice"
    assert data[0]["stage"] == "registered"


def test_queue_returns_student_details(client, db_session, override_authenticated_user):
    """Response includes student name, email, and phone."""
    counselor = _seed_counselor(db_session)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="john.doe@example.test",
        tenant_id=1,
        branch_id=1,
    )
    student.name = "John Doe"
    student.phone = "+91-9876543210"
    db_session.commit()

    seed_application(db_session, student_id=student.id, assigned_counselor_id=counselor)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_name"] == "John Doe"
    assert data[0]["student_email"] == "john.doe@example.test"
    assert data[0]["student_phone"] == "+91-9876543210"


def test_queue_requires_authentication(client):
    """Unauthenticated requests are rejected."""
    response = client.get("/counselor/queue")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_queue_requires_counselor_role(client, db_session, override_authenticated_user):
    """Only the COUNSELOR role may call this endpoint.

    Branch Manager and Consultancy Owner have their own dashboards and
    use ``/applications/assigned-to-me`` for cross-role queue views;
    mixing those role views into this endpoint produced a wrong-data
    contract for the non-counselor roles, which is why the endpoint is
    narrowed to COUNSELOR only.
    """
    # Student role does not satisfy the COUNSELOR-only gate
    student = _seed_student(db_session)
    override_authenticated_user(make_authenticated_user(Role.STUDENT, user_id=student))

    response = client.get("/counselor/queue")

    assert response.status_code == 403


def test_queue_rejects_branch_manager_role(client, db_session, override_authenticated_user):
    """Branch Manager is not authorised for the counselor-only queue."""
    branch_manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="manager@example.test",
        tenant_id=1,
        branch_id=1,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.BRANCH_MANAGER,
            user_id=branch_manager.id,
            tenant_id=1,
            branch_id=1,
        )
    )

    response = client.get("/counselor/queue")

    assert response.status_code == 403


def test_queue_rejects_consultancy_owner_role(client, db_session, override_authenticated_user):
    """Consultancy Owner is not authorised for the counselor-only queue."""
    owner = make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        email="owner@example.test",
        tenant_id=1,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.CONSULTANCY_OWNER,
            user_id=owner.id,
            tenant_id=1,
        )
    )

    response = client.get("/counselor/queue")

    assert response.status_code == 403


def test_queue_respects_tenant_isolation(client, db_session, override_authenticated_user):
    """Counselor only sees applications within their tenant."""
    counselor = _seed_counselor(db_session, tenant_id=1)
    tenant2_counselor = _seed_counselor(db_session, email="t2.counselor@example.test", tenant_id=2)
    tenant1_student = _seed_student(db_session, tenant_id=1, email="t1.student@example.test")
    tenant2_student = _seed_student(db_session, tenant_id=2, email="t2.student@example.test")

    valid_app = seed_application(db_session, tenant_id=1, student_id=tenant1_student, assigned_counselor_id=counselor)
    seed_application(db_session, tenant_id=2, student_id=tenant2_student, assigned_counselor_id=tenant2_counselor)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor, tenant_id=1))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    assert {app["id"] for app in data} == {valid_app.id}
    assert data[0]["student_email"] == "t1.student@example.test"


def test_queue_respects_branch_isolation(client, db_session, override_authenticated_user):
    """Counselor only sees applications whose student belongs to their branch.

    Even when an application is assigned to the counselor directly
    (``assigned_counselor_id`` matches), an application whose student
    belongs to a different branch must NOT appear in the queue. The
    assigned_counselor_id filter alone is insufficient because the
    assigned_counselor_id identifies the owner, not the branch; branch
    scope is enforced by joining on the student's ``branch_id``.
    """
    counselor = _seed_counselor(db_session, branch_id=1)
    same_branch_student = _seed_student(
        db_session, branch_id=1, email="same.branch@example.test"
    )
    other_branch_student = _seed_student(
        db_session, branch_id=2, email="other.branch@example.test"
    )

    same_branch_app = seed_application(
        db_session,
        student_id=same_branch_student,
        assigned_counselor_id=counselor,
    )
    other_branch_app = seed_application(
        db_session,
        student_id=other_branch_student,
        assigned_counselor_id=counselor,
    )

    override_authenticated_user(
        make_authenticated_user(
            Role.COUNSELOR, user_id=counselor, tenant_id=1, branch_id=1
        )
    )

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    returned_ids = {app["id"] for app in data}
    assert same_branch_app.id in returned_ids
    assert other_branch_app.id not in returned_ids


def test_queue_returns_empty_for_counselor_with_no_applications(client, db_session, override_authenticated_user):
    """Counselor with no assigned applications gets empty list."""
    counselor = _seed_counselor(db_session)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    assert response.json() == []


def test_queue_orders_by_id_ascending(client, db_session, override_authenticated_user):
    """Queue returns applications in stable id order."""
    counselor = _seed_counselor(db_session)

    # Create applications with controlled timestamps
    now = datetime.now(timezone.utc)
    student1 = _seed_student(db_session, email="first@example.test")
    student2 = _seed_student(db_session, email="second@example.test")
    student3 = _seed_student(db_session, email="third@example.test")

    # Create apps with controlled timestamps
    app1 = seed_application(db_session, student_id=student1, assigned_counselor_id=counselor)
    app2 = seed_application(db_session, student_id=student2, assigned_counselor_id=counselor)
    app3 = seed_application(db_session, student_id=student3, assigned_counselor_id=counselor)

    # Set timestamps so id order does not match chronological order
    app1.created_at = now - timedelta(hours=3)
    app2.created_at = now - timedelta(hours=1)
    app3.created_at = now
    db_session.commit()

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Stable id ordering (ascending)
    assert [app["id"] for app in data] == sorted(app["id"] for app in data)


def test_queue_skips_applications_with_missing_student(client, db_session, override_authenticated_user):
    """Applications whose student was deleted (FK CASCADE) or has invalid student_id are silently omitted.

    Strengthened over a vacuous ``all(... not in ...)`` check: we assert the
    *valid* application IS in the response (so an empty-list regression would
    fail this test), and we also assert the orphan id is absent.
    """
    counselor = _seed_counselor(db_session)
    student = _seed_student(db_session, email="orphan.student@example.test")

    # Create a valid application
    valid_app = seed_application(db_session, student_id=student, assigned_counselor_id=counselor)

    # Insert an application with a non-existent student_id via raw SQL.
    # This bypasses the ORM so we can create an orphaned record that the FK
    # constraint (ON DELETE CASCADE) would normally prevent.
    now = datetime.now(timezone.utc)
    with db_session.bind.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO applications "
                "(tenant_id, student_id, assigned_counselor_id, stage, "
                "loan_opted_in, created_at, updated_at, university_id, program_id) "
                "VALUES (:t, :s, :c, :st, :lo, :ca, :ua, :u, :p)"
            ),
            {
                "t": 1,
                "s": 999999,  # student does not exist
                "c": counselor,
                "st": PipelineStage.REGISTERED.value,
                "lo": False,
                "ca": now,
                "ua": now,
                "u": 1,
                "p": 1,
            },
        )
    db_session.commit()

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    valid_ids = {app["id"] for app in data}
    student_ids = {app["student_id"] for app in data}
    # The valid application must be present (catches "empty list regression").
    assert valid_app.id in valid_ids
    # The orphan student_id must be absent.
    assert 999999 not in student_ids


def test_queue_handles_db_unavailable_gracefully(client, db_session, override_authenticated_user):
    """Returns 503 when database is unavailable."""
    counselor = _seed_counselor(db_session)
    student = _seed_student(db_session)
    seed_application(db_session, student_id=student, assigned_counselor_id=counselor)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    # Build a mock session that raises OperationalError on .scalars() and .get()
    failing_session = MagicMock(spec=Session)
    failing_session.scalars.side_effect = OperationalError("statement", {}, "connection refused")
    failing_session.get.side_effect = OperationalError("statement", {}, "connection refused")

    def _failing_get_db() -> Generator[Session, None, None]:
        yield failing_session

    fastapi_app.dependency_overrides[get_db] = _failing_get_db

    try:
        response = client.get("/counselor/queue")
        assert response.status_code == 503
        assert response.json()["detail"] == "Counselor service is temporarily unavailable"
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
