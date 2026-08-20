"""Application test helpers."""

from datetime import date, datetime, timezone

from app.models.application import Application, ApplicationStage
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
    rejection_reason: str | None = None,
    withdrawal_reason: str | None = None,
    enrolled_at: date | None = None,
) -> Application:
    """Create and persist an application row."""
    # Auto-create a student user if student_id not provided
    if student_id is None:
        student = make_db_user(
            db_session,
            role="student",  # type: ignore[arg-type]
            email=f"student-{datetime.now(timezone.utc).timestamp()}@example.test",
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
        rejection_reason=rejection_reason,
        withdrawal_reason=withdrawal_reason,
        enrolled_at=enrolled_at,
        created_at=now,
        updated_at=now,
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    return app
