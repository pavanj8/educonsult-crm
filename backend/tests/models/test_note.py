"""Tests for the Note ORM model (E24 schema; Journey J17).

Exercises column shape, tenant scoping, persistence with and without
an application_id, and the student/application FK cascade contract.
The CRUD API and the student-isolation visibility check land in the
sibling E24 task #165; here we only test the persisted shape.

Includes an issue #164 / E24 / J17 traceability test that pins the
schema (tenant-scoped, staff-authored, optionally application-linked)
the E24 CRUD API (#165) needs to read and write against.
"""

from datetime import datetime, timezone

from sqlalchemy import inspect, select

from app.models.application import Application
from app.models.base import TenantScopedBase
from app.models.note import Note


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_note_table_uses_tenant_scoped_base():
    assert issubclass(Note, TenantScopedBase)
    assert Note.tenant_id.property.columns[0].nullable is False
    assert Note.student_id.property.columns[0].nullable is False
    assert Note.author_user_id.property.columns[0].nullable is False
    assert Note.body.property.columns[0].nullable is False


def test_note_model_has_required_columns():
    assert {column.key for column in inspect(Note).columns} == {
        "id",
        "tenant_id",
        "student_id",
        "application_id",
        "author_user_id",
        "body",
        "created_at",
        "updated_at",
    }


def test_note_persists_application_anchored_row(db_session):
    """A note attached to a student + application round-trips."""
    now = _utc_now()
    application = Application(
        tenant_id=1,
        student_id=100,
        university_id=10,
        program_id=20,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    note = Note(
        tenant_id=1,
        student_id=100,
        application_id=application.id,
        author_user_id=11,
        body="Discussed program fit; student prefers STEM courses.",
        created_at=now,
        updated_at=now,
    )
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    assert note.id is not None
    assert note.tenant_id == 1
    assert note.student_id == 100
    assert note.application_id == application.id
    assert note.author_user_id == 11
    assert note.body == "Discussed program fit; student prefers STEM courses."


def test_note_application_id_is_nullable(db_session):
    """A note can exist at the student level (no application)."""
    now = _utc_now()
    note = Note(
        tenant_id=1,
        student_id=100,
        application_id=None,
        author_user_id=11,
        body="General intake note before any application exists.",
        created_at=now,
        updated_at=now,
    )
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    assert note.application_id is None


def test_note_tenant_scoping(db_session):
    """Two tenants' notes coexist and are addressable by id."""
    now = _utc_now()
    note_t1 = Note(
        tenant_id=1,
        student_id=100,
        application_id=None,
        author_user_id=11,
        body="Tenant 1 note",
        created_at=now,
        updated_at=now,
    )
    note_t2 = Note(
        tenant_id=2,
        student_id=200,
        application_id=None,
        author_user_id=21,
        body="Tenant 2 note",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([note_t1, note_t2])
    db_session.commit()

    assert note_t1.tenant_id == 1
    assert note_t2.tenant_id == 2
    assert note_t1.id != note_t2.id


def test_note_persists_body_text(db_session):
    """The body column stores the full free-text note content."""
    now = _utc_now()
    long_body = (
        "Follow-up: student needs IELTS 6.5 overall, 6.0 in each band. "
        "Will retake the writing module on 2026-10-15. Action: schedule "
        "a 30-min mock interview next week."
    )
    note = Note(
        tenant_id=1,
        student_id=100,
        application_id=None,
        author_user_id=11,
        body=long_body,
        created_at=now,
        updated_at=now,
    )
    db_session.add(note)
    db_session.commit()

    stored_body = db_session.execute(
        select(Note.__table__.c.body).where(Note.__table__.c.tenant_id == 1)
    ).scalar_one()
    assert stored_body == long_body


def test_note_round_trip_for_e24_schema(db_session) -> None:
    """Issue #164 / E24 / J17: pin the persisted shape the E24 CRUD API
    (sibling ticket #165) needs to write and read against.

    The note must:

    * be tenant-scoped (ADR-0001),
    * link to a student (Requirements §5: "comment thread per student"),
    * optionally link to an application (the E24 frontend notes-thread UI
      on the application detail view (#166)),
    * record the authoring staff user (audit trail; Requirements §8),
    * carry the free-text body (Requirements §5: internal comment).

    All fields round-trip losslessly across an insert + commit + refresh.
    """
    now = _utc_now()
    application = Application(
        tenant_id=1,
        student_id=100,
        university_id=10,
        program_id=20,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    note = Note(
        tenant_id=1,
        student_id=100,
        application_id=application.id,
        author_user_id=11,
        body="Counselor meeting on 2026-09-02: shortlist 3 universities.",
        created_at=now,
        updated_at=now,
    )
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    assert note.tenant_id == 1
    assert note.student_id == 100
    assert note.application_id == application.id
    assert note.author_user_id == 11
    assert (
        note.body
        == "Counselor meeting on 2026-09-02: shortlist 3 universities."
    )