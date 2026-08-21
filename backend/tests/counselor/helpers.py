"""Counselor test helpers (E21; Journey J14)."""

from datetime import datetime, timezone

from app.models.application import Application
from app.pipeline.stages import PipelineStage


def seed_application(
    db_session,
    *,
    tenant_id: int = 1,
    student_id: int,
    assigned_counselor_id: int | None = None,
    stage: PipelineStage = PipelineStage.REGISTERED,
    university_id: int = 1,
    program_id: int = 1,
) -> Application:
    """Seed an application row for counselor queue tests.

    ``university_id`` and ``program_id`` are required by the E18 model
    (NOT NULL), so the helper takes explicit defaults that satisfy the
    schema even when the E21 queue endpoint never reads them.
    """
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=tenant_id,
        student_id=student_id,
        university_id=university_id,
        program_id=program_id,
        assigned_counselor_id=assigned_counselor_id,
        stage=stage,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application
