<<<<<<< HEAD
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
=======
"""Tests for the Meeting ORM model (E22; Journey J15)."""

from datetime import datetime, timezone

from sqlalchemy import inspect

from app.models.meeting import Meeting


def test_meeting_model_has_required_columns():
    assert {column.key for column in inspect(Meeting).columns} == {
        "id", "tenant_id", "application_id", "counselor_id", "student_id",
        "scheduled_at", "duration_minutes", "location", "notes", "created_at", "updated_at",
    }


def test_meeting_persists_row(db_session):
    now = datetime.now(timezone.utc)
    meeting = Meeting(
        tenant_id=1,
        application_id=10,
        counselor_id=11,
        student_id=12,
        scheduled_at=now,
        duration_minutes=45,
        location="Room 2",
        notes="Bring academic documents",
        created_at=now,
        updated_at=now,
>>>>>>> origin/main
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

<<<<<<< HEAD
    assert meeting.duration_minutes == 60
=======
    assert meeting.id is not None
    assert meeting.tenant_id == 1
    assert meeting.application_id == 10
    assert meeting.counselor_id == 11
    assert meeting.student_id == 12
    assert meeting.scheduled_at.replace(tzinfo=timezone.utc) == now
    assert meeting.duration_minutes == 45
    assert meeting.location == "Room 2"
    assert meeting.notes == "Bring academic documents"


def test_meeting_optional_details_are_nullable(db_session):
    now = datetime.now(timezone.utc)
    meeting = Meeting(
        tenant_id=1,
        application_id=10,
        counselor_id=11,
        student_id=12,
        scheduled_at=now,
        duration_minutes=30,
        created_at=now,
        updated_at=now,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    assert meeting.location is None
    assert meeting.notes is None
>>>>>>> origin/main
