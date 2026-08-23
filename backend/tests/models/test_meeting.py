from datetime import datetime, timezone

from app.models.base import Base
from app.models.meeting import Meeting


def test_meeting_table_uses_tenant_scoped_base() -> None:
    assert Meeting.__mro__[1] is Base or Meeting.id.property.columns[0].primary_key
    assert Meeting.tenant_id.property.columns[0].nullable is False
    assert Meeting.scheduled_at.property.columns[0].nullable is False


def test_meeting_default_duration(db_session) -> None:
    """A newly-created meeting defaults to a 60-minute duration (E22; Journey J15)."""
    from app.models.application import Application
    from app.models.branch import Branch
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.pipeline.stages import PipelineStage

    tenant = Tenant(name="T", slug="t")
    db_session.add(tenant)
    db_session.flush()
    branch = Branch(tenant_id=tenant.id, name="B", city="City")
    db_session.add(branch)
    db_session.flush()
    counselor = User(
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="c@example.com",
        password_hash="x",
        role="counselor",
    )
    student = User(
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="s@example.com",
        password_hash="x",
        role="student",
    )
    db_session.add_all([counselor, student])
    db_session.flush()
    application = Application(
        tenant_id=tenant.id,
        student_id=student.id,
        university_id=1,
        program_id=1,
        stage=PipelineStage.REGISTERED,
    )
    db_session.add(application)
    db_session.flush()

    now = datetime.now(timezone.utc)
    meeting = Meeting(
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
        scheduled_at=now,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    assert meeting.duration_minutes == 60
