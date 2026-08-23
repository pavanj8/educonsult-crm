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
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

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
