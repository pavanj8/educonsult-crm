"""Counseling test helpers."""

from datetime import datetime, timezone

from app.models.application import Application
from app.models.user import User
from app.rbac.roles import Role


def seed_application(
    db_session,
    *,
    tenant_id: int = 1,
    branch_id: int = 1,
    student_name: str = "Alice Student",
    stage: str = "registered",
    assigned_counselor_id: int | None = None,
    student_id: int | None = None,
) -> Application:
    """Seed an application using the real Application model.

    When student_id is not provided, a real Student User row is created first
    so that the FK is valid even if FK enforcement is enabled later.  This
    avoids the silent-failure hazard of a hardcoded placeholder id.
    """
    now = datetime.now(timezone.utc)

    if student_id is None:
        student = User(
            email=f"student-{now.timestamp()}@example.test",
            password_hash="$2b$12$placeholder",  # never verified in tests
            role=Role.STUDENT,
            tenant_id=tenant_id,
            branch_id=branch_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(student)
        db_session.flush()
        student_id = student.id

    app = Application(
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_name=student_name,
        stage=stage,
        assigned_counselor_id=assigned_counselor_id,
        student_id=student_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(app)
    db_session.flush()
    return app


def counseling_queue_url() -> str:
    return "/counseling/queue"
