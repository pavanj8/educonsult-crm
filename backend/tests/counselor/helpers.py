"""Counselor test helpers."""

from datetime import datetime, timezone

from app.models.application import Application, PipelineStage


def seed_application(
    db_session,
    *,
    tenant_id: int = 1,
    student_id: int,
    assigned_counselor_id: int | None = None,
    stage: PipelineStage = PipelineStage.REGISTERED,
    target_university_id: int | None = None,
    target_program_id: int | None = None,
) -> Application:
    """Seed an application record for counselor queue tests."""
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=tenant_id,
        student_id=student_id,
        assigned_counselor_id=assigned_counselor_id,
        target_university_id=target_university_id,
        target_program_id=target_program_id,
        stage=stage,
        loan_opted_in=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application
