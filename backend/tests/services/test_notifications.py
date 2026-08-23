"""Unit tests for the notification-creation service (E48; J41; issue #230).

Exercises the :func:`app.services.notifications` module in isolation:

* :func:`create_notification` persists a :class:`Notification` row with
  the supplied tenant / user / title / message, and returns the row.
* :func:`notify_application_stage_changed` writes one notification for
  the application's student and a second for the assigned counselor,
  skipping the actor and the student-self-as-counselor edge case.
* :func:`notify_document_approved` writes a notification for the
  application student, optionally embedding the verifier's comment.
* :func:`notify_document_rejected` writes a notification for the
  application student, embedding the required rejection reason.
* :func:`notify_meeting_scheduled` writes a notification for the
  meeting's student (J16), with the scheduling time + location in
  the message body.
* All helpers are no-throw wrappers — a flush failure logs and returns
  ``None`` but never raises, so a flaky notification path cannot break
  the originating event.

The router-level integration tests (verifying the hooks actually fire
from the E25 advance-stage and E29 / E30 verifier endpoints) live in:

* ``tests/applications/test_advance_stage.py`` — the
  ``test_*_notification_*`` cases there.
* ``tests/verifier/test_approve_document.py`` —
  ``test_approve_*_notification_*`` cases there.
* ``tests/verifier/test_reject_document.py`` —
  ``test_reject_*_notification_*`` cases there.

Sibling ticket #231 owns additional black-box tests derived only from
``docs/requirements.md`` / ``docs/journeys.md`` / ``docs/epics.md`` /
the issue body.
"""

from __future__ import annotations


from sqlalchemy.exc import OperationalError

from app.models.notification import Notification
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.services.notifications import (
    create_notification,
    notify_application_stage_changed,
    notify_document_approved,
    notify_document_rejected,
    notify_meeting_scheduled,
)
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.counseling.helpers import seed_meeting
from tests.factories.users import make_db_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _student(db_session, *, tenant_id: int, branch_id: int | None):
    return make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )


def _counselor(db_session, *, tenant_id: int, branch_id: int | None):
    return make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )


def _pending_document(
    db_session,
    *,
    tenant_id: int,
    branch_id: int,
    student_id: int,
) -> StudentDocument:
    application = seed_application(
        db_session,
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        university_id=11,
        program_id=21,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    from datetime import datetime, timezone

    document = StudentDocument(
        tenant_id=tenant_id,
        application_id=application.id,
        status=StudentDocumentStatus.PENDING,
        original_filename="doc.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        storage_path=f"tenants/{tenant_id}/applications/{application.id}/doc.pdf",
        uploaded_by_user_id=student_id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


# ---------------------------------------------------------------------------
# create_notification
# ---------------------------------------------------------------------------


def test_create_notification_persists_a_row(db_session):
    """``create_notification`` writes a Notification row and returns it."""
    tenant = _create_tenant(db_session, name="Notif Basic", slug="notif-basic")
    student = _student(db_session, tenant_id=tenant.id, branch_id=None)

    notification = create_notification(
        db_session,
        tenant_id=tenant.id,
        user_id=student.id,
        title="Hello",
        message="World",
    )

    assert notification is not None
    assert notification.id is not None
    assert notification.tenant_id == tenant.id
    assert notification.user_id == student.id
    assert notification.title == "Hello"
    assert notification.message == "World"
    assert notification.read_at is None
    assert notification.created_at is not None


def test_create_notification_flush_failure_is_swallowed(db_session, caplog):
    """A flush failure logs a warning and returns ``None``; it does not raise."""
    tenant = _create_tenant(db_session, name="Notif Flush Fail", slug="notif-flush-fail")
    student = _student(db_session, tenant_id=tenant.id, branch_id=None)

    class _FlakyFlushSession:
        def __init__(self, real):
            self._real = real

        def add(self, *_args, **_kwargs):
            return self._real.add(*_args, **_kwargs)

        def flush(self, *_args, **_kwargs):
            raise OperationalError("stmt", {}, Exception("disk full"))

        def rollback(self, *_args, **_kwargs):
            return self._real.rollback(*_args, **_kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    flaky = _FlakyFlushSession(db_session)

    # The contract under test is that a flush failure is SWALLOWED: the service
    # returns None and does not propagate, so an otherwise-successful event (stage
    # progression / document approval) is never broken by a flaky notification
    # write. (We deliberately do not assert on the warning log line — capturing it
    # is flaky when tests/database/test_alembic.py's importlib.reload has rebound
    # logging handlers earlier in a full-suite run; the return value is the
    # observable contract.)
    result = create_notification(
        flaky,
        tenant_id=tenant.id,
        user_id=student.id,
        title="x",
        message="y",
    )

    assert result is None


# ---------------------------------------------------------------------------
# notify_application_stage_changed
# ---------------------------------------------------------------------------


def test_stage_change_notifies_student_and_counselor(db_session):
    """A stage transition notifies the student and the assigned counselor."""
    tenant = _create_tenant(db_session, name="Notif Stage", slug="notif-stage")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    counselor = _counselor(db_session, tenant_id=tenant.id, branch_id=branch.id)
    # The actor is a different user (a branch manager / owner) so the
    # assigned counselor is not silently suppressed by the
    # "actor == counselor" guard.
    actor = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )

    notify_application_stage_changed(
        db_session,
        application=application,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        actor_user_id=actor.id,
    )
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .order_by(Notification.id)
        .all()
    )
    assert len(rows) == 2
    recipients = {row.user_id for row in rows}
    assert recipients == {student.id, counselor.id}
    titles = {row.title for row in rows}
    assert "Application moved to counseling" in titles
    for row in rows:
        assert "counseling" in row.message.lower()
        assert row.read_at is None


def test_stage_change_skips_counselor_when_actor_is_counselor(db_session):
    """The assigned counselor does not receive a notification for their own action."""
    tenant = _create_tenant(db_session, name="Notif Self", slug="notif-self")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    counselor = _counselor(db_session, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.REGISTERED,
    )

    notify_application_stage_changed(
        db_session,
        application=application,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        actor_user_id=counselor.id,
    )
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].user_id == student.id


def test_stage_change_works_without_assigned_counselor(db_session):
    """When there is no assigned counselor, only the student is notified."""
    tenant = _create_tenant(db_session, name="Notif No Counsel", slug="notif-no-counsel")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=None,
        stage=PipelineStage.REGISTERED,
    )

    notify_application_stage_changed(
        db_session,
        application=application,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        actor_user_id=999_999,
    )
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].user_id == student.id


def test_stage_change_when_student_is_assigned_counselor_does_not_double_notify(db_session):
    """If the assigned counselor id equals the student id (defensive), only
    one notification is written (for the student) and no double-notify."""
    tenant = _create_tenant(db_session, name="Notif Self Counsel", slug="notif-self-counsel")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=student.id,  # pathological but guarded
        stage=PipelineStage.REGISTERED,
    )

    notify_application_stage_changed(
        db_session,
        application=application,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        actor_user_id=999_999,
    )
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .all()
    )
    # Student-as-counselor must not produce a duplicate notification.
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# notify_document_approved / notify_document_rejected
# ---------------------------------------------------------------------------


def test_document_approved_notifies_student_with_comment(db_session):
    """A document approval writes a notification for the student, embedding the comment."""
    tenant = _create_tenant(db_session, name="Notif Approve", slug="notif-approve")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    document = _pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    application = (
        db_session.query(__import__("app.models.application", fromlist=["Application"]).Application)
        .filter_by(id=document.application_id)
        .one()
    )

    notify_document_approved(
        db_session,
        document=document,
        application=application,
        comment="Looks good",
    )
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].user_id == student.id
    assert rows[0].title == "Document approved"
    assert "approved" in rows[0].message.lower()
    assert "Looks good" in rows[0].message


def test_document_approved_without_comment_omits_reason_text(db_session):
    """When the verifier passes ``None`` (or empty) the message has no 'Comment:' suffix."""
    tenant = _create_tenant(db_session, name="Notif Approve NC", slug="notif-approve-nc")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    document = _pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    from app.models.application import Application

    application = db_session.query(Application).filter_by(id=document.application_id).one()

    notify_document_approved(
        db_session,
        document=document,
        application=application,
        comment=None,
    )
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Document approved"
    assert "Comment:" not in rows[0].message


def test_document_rejected_notifies_student_with_reason(db_session):
    """A document rejection writes a notification for the student, embedding the reason."""
    tenant = _create_tenant(db_session, name="Notif Reject", slug="notif-reject")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    document = _pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    from app.models.application import Application

    application = db_session.query(Application).filter_by(id=document.application_id).one()

    notify_document_rejected(
        db_session,
        document=document,
        application=application,
        comment="Image too blurry",
    )
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].user_id == student.id
    assert rows[0].title == "Document rejected"
    assert "Image too blurry" in rows[0].message


# ---------------------------------------------------------------------------
# Recipients are tenant-scoped
# ---------------------------------------------------------------------------


def test_stage_change_notification_rows_carry_correct_tenant_id(db_session):
    """The persisted notifications are stamped with the application's tenant_id."""
    tenant = _create_tenant(db_session, name="Notif Tenant", slug="notif-tenant")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=None,
        stage=PipelineStage.REGISTERED,
    )

    notify_application_stage_changed(
        db_session,
        application=application,
        from_stage=PipelineStage.REGISTERED,
        to_stage=PipelineStage.COUNSELING,
        actor_user_id=999_999,
    )
    db_session.commit()

    row = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .one()
    )
    assert row.tenant_id == application.tenant_id
    assert row.user_id == student.id


# ---------------------------------------------------------------------------
# Read_at behaviour (Journey J43 / E50 contract)
# ---------------------------------------------------------------------------


def test_new_notification_has_null_read_at(db_session):
    """A freshly created notification has ``read_at IS NULL`` (unread)."""
    tenant = _create_tenant(db_session, name="Notif Read At", slug="notif-read-at")
    student = _student(db_session, tenant_id=tenant.id, branch_id=None)
    notification = create_notification(
        db_session,
        tenant_id=tenant.id,
        user_id=student.id,
        title="t",
        message="m",
    )
    db_session.commit()
    db_session.refresh(notification)
    assert notification.read_at is None


# ---------------------------------------------------------------------------
# notify_meeting_scheduled (E23; Journey J16; issue #163)
# ---------------------------------------------------------------------------


def _meeting_for(db_session, *, tenant_id: int, branch_id: int, student_id: int, counselor_id: int):
    application = seed_application(
        db_session,
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        assigned_counselor_id=counselor_id,
    )
    return seed_meeting(
        db_session,
        tenant_id=tenant_id,
        application_id=application.id,
        student_id=student_id,
        counselor_id=counselor_id,
        location="Room 1",
    )


def test_meeting_scheduled_notifies_student(db_session):
    """``notify_meeting_scheduled`` writes one notification for the student."""
    tenant = _create_tenant(db_session, name="Notif Meeting", slug="notif-meeting")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    counselor = _counselor(db_session, tenant_id=tenant.id, branch_id=branch.id)
    meeting = _meeting_for(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )

    notify_meeting_scheduled(db_session, meeting=meeting)
    db_session.commit()

    rows = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .all()
    )
    # Student is the sole recipient. The counselor is the actor and is
    # not notified about their own scheduling action.
    assert len(rows) == 1
    assert rows[0].user_id == student.id
    assert rows[0].title == "Meeting scheduled"
    assert rows[0].read_at is None


def test_meeting_scheduled_message_includes_location_and_time(db_session):
    """The notification message carries the meeting time and location."""
    tenant = _create_tenant(db_session, name="Notif Meeting Loc", slug="notif-meeting-loc")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    counselor = _counselor(db_session, tenant_id=tenant.id, branch_id=branch.id)
    meeting = _meeting_for(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )

    notify_meeting_scheduled(db_session, meeting=meeting)
    db_session.commit()

    row = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .one()
    )
    assert "Room 1" in row.message
    assert "UTC" in row.message


def test_meeting_scheduled_without_location_omits_location_phrase(db_session):
    """When the meeting has no ``location``, the message has no 'at <location>' suffix."""
    tenant = _create_tenant(db_session, name="Notif Meeting NoLoc", slug="notif-meeting-noloc")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    counselor = _counselor(db_session, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = seed_meeting(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
        location=None,
    )

    notify_meeting_scheduled(db_session, meeting=meeting)
    db_session.commit()

    row = (
        db_session.query(Notification)
        .filter(Notification.tenant_id == tenant.id)
        .one()
    )
    assert row.title == "Meeting scheduled"
    # The message should not contain 'at ' (which would imply a location).
    assert " at " not in row.message


def test_meeting_scheduled_notification_carries_meeting_tenant_id(db_session):
    """The persisted notification's tenant_id matches the meeting's tenant_id (J16 + ADR-0001)."""
    tenant = _create_tenant(db_session, name="Notif Meeting Tenant", slug="notif-meeting-tenant")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    counselor = _counselor(db_session, tenant_id=tenant.id, branch_id=branch.id)
    meeting = _meeting_for(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )

    notify_meeting_scheduled(db_session, meeting=meeting)
    db_session.commit()

    row = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .one()
    )
    assert row.tenant_id == meeting.tenant_id


def test_meeting_scheduled_does_not_notify_counselor(db_session):
    """The scheduling counselor (the actor) is not self-notified."""
    tenant = _create_tenant(db_session, name="Notif Meeting Self", slug="notif-meeting-self")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = _student(db_session, tenant_id=tenant.id, branch_id=branch.id)
    counselor = _counselor(db_session, tenant_id=tenant.id, branch_id=branch.id)
    meeting = _meeting_for(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        counselor_id=counselor.id,
    )

    notify_meeting_scheduled(db_session, meeting=meeting)
    db_session.commit()

    counselor_rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == counselor.id)
        .all()
    )
    assert counselor_rows == []