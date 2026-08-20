"""Application test helpers (E18; E21; Journey J11; J14).

Provides a small factory used by integration tests to seed an ``Application``
row without going through the public ``POST /applications`` endpoint.
"""

from datetime import datetime, timezone

from app.models.application import Application, ApplicationStage
from app.rbac.roles import Role
from tests.factories.ids import next_test_id
from tests.factories.users import make_db_user


def seed_application(
    db_session,
    *,
    tenant_id: int = 1,
    branch_id: int | None = 1,
    student_id: int | None = None,
    assigned_counselor_id: int | None = None,
    university_id: int = 1,
    program_id: int = 1,
    stage: ApplicationStage = ApplicationStage.REGISTERED,
) -> Application:
    """Create and persist an application row.

    Parameters mirror the ORM columns: ``tenant_id``, ``branch_id``,
    ``student_id``, ``assigned_counselor_id``, ``university_id``, ``program_id``,
    ``stage``. Auto-creates a STUDENT user when ``student_id`` is not
    provided so individual tests can opt out of constructing a student
    fixture. ``branch_id`` is nullable to match the E18 row shape (the
    branch is back-filled by E19 / E20).
    """
    # Auto-create a student user if student_id not provided
    if student_id is None:
        student = make_db_user(
            db_session,
            Role.STUDENT,
            email=f"student-{next_test_id()}@example.test",
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
        student_id = student.id

    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        assigned_counselor_id=assigned_counselor_id,
        university_id=university_id,
        program_id=program_id,
        stage=stage,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application
