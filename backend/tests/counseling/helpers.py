"""Counseling test helpers."""

from datetime import datetime, timezone

from app.models.application import Application


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

    The Application model is registered via app.models in conftest so its table
    is created alongside all other app tables.

    Note: student_id has a NOT NULL FK constraint to users.id. If not provided,
    a placeholder value (999999) is used for integration tests that don't need
    actual student records (the FK is not enforced with in-memory SQLite in tests).
    """
    now = datetime.now(timezone.utc)
    app = Application(
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_name=student_name,
        stage=stage,
        assigned_counselor_id=assigned_counselor_id,
        student_id=student_id if student_id is not None else 999999,
        created_at=now,
        updated_at=now,
    )
    db_session.add(app)
    db_session.flush()
    return app


def counseling_queue_url() -> str:
    return "/counseling/queue"
