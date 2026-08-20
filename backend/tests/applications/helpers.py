"""Application test helpers."""

from datetime import datetime, timezone

from app.models.application import Application, ApplicationStage
from app.rbac.roles import Role
from tests.factories.ids import next_test_id
from tests.factories.users import make_db_user


def seed_application(
    db_session,
    *,
    tenant_id: int = 1,
    branch_id: int = 1,
    student_id: int | None = None,
    assigned_counselor_id: int | None = None,
    university: str = "MIT",
    program: str = "MS Computer Science",
    stage: ApplicationStage = ApplicationStage.REGISTERED,
) -> Application:
    """Create and persist an application row."""
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
    app = Application(
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        assigned_counselor_id=assigned_counselor_id,
        university=university,
        program=program,
        stage=stage,
        created_at=now,
        updated_at=now,
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    return app
