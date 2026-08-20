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
from app.models.application import PipelineStage
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
    seed_application(db_session, student_id=student, assigned_counselor_id=counselor)
    # Application assigned to another counselor (should not appear)
    seed_application(db_session, student_id=other_student, assigned_counselor_id=other_counselor)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
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
    assert len(response.json()) == 0


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


def test_queue_requires_counselor_permission(client, db_session, override_authenticated_user):
    """Users without APPLICATION_READ_ASSIGNED permission are rejected."""
    # Create a student (who doesn't have the counselor permission)
    student = _seed_student(db_session)
    override_authenticated_user(make_authenticated_user(Role.STUDENT, user_id=student))

    response = client.get("/counselor/queue")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_queue_respects_tenant_isolation(client, db_session, override_authenticated_user):
    """Counselor only sees applications within their tenant."""
    counselor = _seed_counselor(db_session, tenant_id=1)
    tenant2_counselor = _seed_counselor(db_session, email="t2.counselor@example.test", tenant_id=2)
    tenant1_student = _seed_student(db_session, tenant_id=1, email="t1.student@example.test")
    tenant2_student = _seed_student(db_session, tenant_id=2, email="t2.student@example.test")

    seed_application(db_session, tenant_id=1, student_id=tenant1_student, assigned_counselor_id=counselor)
    seed_application(db_session, tenant_id=2, student_id=tenant2_student, assigned_counselor_id=tenant2_counselor)

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor, tenant_id=1))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["student_email"] == "t1.student@example.test"


def test_queue_returns_empty_for_counselor_with_no_applications(client, db_session, override_authenticated_user):
    """Counselor with no assigned applications gets empty list."""
    counselor = _seed_counselor(db_session)
    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    assert response.json() == []


def test_queue_orders_by_created_at_desc(client, db_session, override_authenticated_user):
    """Queue returns applications ordered by created_at descending (newest first)."""
    counselor = _seed_counselor(db_session)

    # Create applications with different timestamps
    now = datetime.now(timezone.utc)
    student1 = _seed_student(db_session, email="first@example.test")
    student2 = _seed_student(db_session, email="second@example.test")
    student3 = _seed_student(db_session, email="third@example.test")

    # Create apps with controlled timestamps
    app1 = seed_application(db_session, student_id=student1, assigned_counselor_id=counselor)
    app2 = seed_application(db_session, student_id=student2, assigned_counselor_id=counselor)
    app3 = seed_application(db_session, student_id=student3, assigned_counselor_id=counselor)

    # Set timestamps: oldest first, newest last
    app1.created_at = now - timedelta(hours=3)
    app2.created_at = now - timedelta(hours=1)
    app3.created_at = now
    db_session.commit()

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Newest first (app3), then app2, then app1
    assert data[0]["student_email"] == "third@example.test"
    assert data[1]["student_email"] == "second@example.test"
    assert data[2]["student_email"] == "first@example.test"


def test_queue_skips_applications_with_missing_student(client, db_session, override_authenticated_user):
    """Applications whose student was deleted (FK CASCADE) or has invalid student_id are silently omitted."""
    counselor = _seed_counselor(db_session)
    student = _seed_student(db_session, email="orphan.student@example.test")

    # Create a valid application
    seed_application(db_session, student_id=student, assigned_counselor_id=counselor)

    # Insert an application with a non-existent student_id via raw SQL.
    # This bypasses the ORM so we can create an orphaned record that the FK
    # constraint (ON DELETE CASCADE) would normally prevent.
    now = datetime.now(timezone.utc)
    with db_session.bind.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO applications "
                "(tenant_id, student_id, assigned_counselor_id, stage, "
                "loan_opted_in, created_at, updated_at) "
                "VALUES (:t, :s, :c, :st, :lo, :ca, :ua)"
            ),
            {
                "t": 1,
                "s": 999999,  # student does not exist
                "c": counselor,
                "st": PipelineStage.REGISTERED.value,
                "lo": False,
                "ca": now,
                "ua": now,
            },
        )
    db_session.commit()

    override_authenticated_user(make_authenticated_user(Role.COUNSELOR, user_id=counselor))

    response = client.get("/counselor/queue")

    assert response.status_code == 200
    data = response.json()
    # The orphan application (student_id=999999) must be absent
    assert all(app["student_id"] != 999999 for app in data)


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
