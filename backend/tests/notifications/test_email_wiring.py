"""E49 wiring tests — Issue #234.

The "wire email sending into existing notification triggers" ticket
extends every existing E48 notification hook so that, after the
in-app notification row is persisted, the same recipient also
receives an outbound email through :func:`app.email.service.send_email`.

These tests are the developer-authored coverage for that wiring:
they pin the contract that every hook delegates to ``send_email``
with the right ``to`` / ``subject`` / ``body_text``, and that an SMTP
delivery failure (:class:`EmailDeliveryError`) is swallowed and
logged so the originating request still succeeds. The end-to-end
mocked-SMTP coverage for the whole E49 epic (covering the routers,
the user email lookup, and the no-recipient fallback) lands in
issue #235 and is out of scope here.

The tests in this module intentionally patch ``send_email`` at the
import site of the *caller* (:mod:`app.services.notifications`) per
the contract pinned by ``tests/email/test_e49_abstraction.py``:
patching at the caller's module lets the tests verify exactly which
arguments the wiring passes without monkey-patching ``smtplib``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch


from sqlalchemy.exc import OperationalError

from app.email.service import EmailDeliveryError
from app.models.notification import Notification
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.services.notifications import (
    notify_application_stage_changed,
    notify_document_approved,
    notify_document_rejected,
    notify_meeting_scheduled,
)
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_db_user


def _seed_tenant(db_session, slug: str) -> Tenant:
    tenant = Tenant(name=slug, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


# ---------------------------------------------------------------------------
# Stage change: both the student and the assigned counselor get an email
# ---------------------------------------------------------------------------


def test_stage_change_dispatches_email_to_student(db_session):
    tenant = _seed_tenant(db_session, "wiring-stage-stu")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR,
        email="cou@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER,
        email="mgr@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        assigned_counselor_id=counselor.id, stage=PipelineStage.COUNSELING,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_application_stage_changed(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
            actor_user_id=manager.id,
        )

    # Two emails sent: one to the student, one to the assigned counselor.
    recipients = sorted(call.kwargs["to"] for call in mock_send.call_args_list)
    assert recipients == ["cou@wiring.test", "stu@wiring.test"]

    # The student's email subject + body mention the new stage.
    student_call = next(
        call for call in mock_send.call_args_list
        if call.kwargs["to"] == "stu@wiring.test"
    )
    assert "university_shortlisting" in student_call.kwargs["subject"]
    assert "counseling" in student_call.kwargs["body_text"]
    assert "university_shortlisting" in student_call.kwargs["body_text"]


def test_stage_change_dispatches_counselor_only_when_not_actor(db_session):
    tenant = _seed_tenant(db_session, "wiring-stage-actor")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR,
        email="cou@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        assigned_counselor_id=counselor.id, stage=PipelineStage.COUNSELING,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        # Counselor is the actor: only the student gets an email.
        notify_application_stage_changed(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
            actor_user_id=counselor.id,
        )

    recipients = [call.kwargs["to"] for call in mock_send.call_args_list]
    assert recipients == ["stu@wiring.test"]


def test_stage_change_swallows_email_delivery_error(db_session):
    """An EmailDeliveryError must not break the originating in-app notification."""
    tenant = _seed_tenant(db_session, "wiring-stage-smtp")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    manager = make_db_user(
        db_session, Role.BRANCH_MANAGER,
        email="mgr@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        stage=PipelineStage.COUNSELING,
    )

    def _boom(**_kwargs):
        raise EmailDeliveryError("connection refused")

    with patch("app.services.notifications.send_email", side_effect=_boom):
        # Must NOT raise — the hook swallows EmailDeliveryError so the
        # originating endpoint's response is unaffected.
        notify_application_stage_changed(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
            actor_user_id=manager.id,
        )

    # The in-app notification was still persisted despite the SMTP failure.
    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert len(rows) == 1
    assert "university_shortlisting" in rows[0].title


def test_stage_change_skips_email_when_recipient_has_no_email(db_session):
    """A recipient User with no email address must not crash the wiring."""
    tenant = _seed_tenant(db_session, "wiring-stage-noemail")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    # Build the student row directly so we can leave email blank.
    student = make_db_user(
        db_session, Role.STUDENT,
        tenant_id=tenant.id, branch_id=branch.id,
    )
    student.email = ""  # type: ignore[assignment]
    db_session.commit()
    db_session.refresh(student)

    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        stage=PipelineStage.COUNSELING,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_application_stage_changed(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
            actor_user_id=student.id,
        )

    # No email is dispatched for a recipient without an address.
    mock_send.assert_not_called()


def test_stage_change_skips_email_when_recipient_user_does_not_exist(db_session):
    tenant = _seed_tenant(db_session, "wiring-stage-missing-user")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=999_999,
        stage=PipelineStage.COUNSELING,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_application_stage_changed(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
            actor_user_id=1,
        )

    mock_send.assert_not_called()


def test_stage_change_skips_email_when_user_lookup_fails(db_session):
    """If the recipient-user DB lookup raises, email must be skipped silently."""
    tenant = _seed_tenant(db_session, "wiring-stage-lookup-error")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="stu@wiring.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        stage=PipelineStage.COUNSELING,
    )

    # Wrap the real session in a thin proxy whose ``.get`` raises the same
    # OperationalError the production code is built to swallow. The proxy
    # forwards every other attribute through to the real session so the
    # create_notification() insert (which runs first) still works against
    # the real DB.
    class _RaisingSession:
        def __init__(self, inner):
            self._inner = inner

        def get(self, *args, **kwargs):
            raise OperationalError("lookup", {}, Exception("simulated"))

        def __getattr__(self, name):
            return getattr(self._inner, name)

    raising_session = _RaisingSession(db_session)

    with patch("app.services.notifications.send_email") as mock_send:
        notify_application_stage_changed(
            raising_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
            actor_user_id=student.id,
        )

    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Document approval / rejection: student is the sole email recipient
# ---------------------------------------------------------------------------


def _seed_pending_doc(db_session, *, tenant, branch, student, filename: str = "t.pdf"):
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    document = StudentDocument(
        tenant_id=tenant.id, application_id=application.id, status=StudentDocumentStatus.PENDING,
        original_filename=filename, content_type="application/pdf", size_bytes=10,
        storage_path=f"t/{tenant.id}/{application.id}/{filename}",
        uploaded_by_user_id=student.id, uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document, application


def test_document_approval_dispatches_email_to_uploader(db_session):
    tenant = _seed_tenant(db_session, "wiring-doc-appr")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    document, application = _seed_pending_doc(
        db_session, tenant=tenant, branch=branch, student=student,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_document_approved(
            db_session,
            document=document,
            application=application,
            comment="looks good",
        )

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to"] == "stu@wiring.test"
    assert "approved" in mock_send.call_args.kwargs["subject"].lower()
    assert "looks good" in mock_send.call_args.kwargs["body_text"]


def test_document_approval_email_omits_comment_when_none(db_session):
    tenant = _seed_tenant(db_session, "wiring-doc-appr-nc")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    document, application = _seed_pending_doc(
        db_session, tenant=tenant, branch=branch, student=student,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_document_approved(
            db_session, document=document, application=application, comment=None,
        )

    mock_send.assert_called_once()
    assert "comment" not in mock_send.call_args.kwargs["body_text"].lower()


def test_document_rejection_dispatches_email_with_reason(db_session):
    tenant = _seed_tenant(db_session, "wiring-doc-rej")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    document, application = _seed_pending_doc(
        db_session, tenant=tenant, branch=branch, student=student,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_document_rejected(
            db_session,
            document=document,
            application=application,
            comment="blurry scan",
        )

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to"] == "stu@wiring.test"
    assert "blurry scan" in mock_send.call_args.kwargs["body_text"]


def test_document_email_swallows_delivery_error(db_session):
    tenant = _seed_tenant(db_session, "wiring-doc-smtp")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    document, application = _seed_pending_doc(
        db_session, tenant=tenant, branch=branch, student=student,
    )

    def _boom(**_kwargs):
        raise EmailDeliveryError("smtp down")

    with patch("app.services.notifications.send_email", side_effect=_boom):
        # Must not raise — in-app notification must still be persisted.
        notify_document_approved(
            db_session, document=document, application=application, comment=None,
        )

    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Meeting scheduled: student is the sole email recipient
# ---------------------------------------------------------------------------


def test_meeting_scheduled_dispatches_email_with_location(db_session):
    tenant = _seed_tenant(db_session, "wiring-meet")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR,
        tenant_id=tenant.id, branch_id=branch.id,
    )
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = _seed_meeting(
        db_session, tenant=tenant, student=student, counselor=counselor,
        application=application, location="Room 4",
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_meeting_scheduled(db_session, meeting=meeting)

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to"] == "stu@wiring.test"
    assert "Room 4" in mock_send.call_args.kwargs["body_text"]


def test_meeting_scheduled_dispatches_email_without_location(db_session):
    tenant = _seed_tenant(db_session, "wiring-meet-nl")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR,
        tenant_id=tenant.id, branch_id=branch.id,
    )
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = _seed_meeting(
        db_session, tenant=tenant, student=student, counselor=counselor,
        application=application, location=None,
    )

    with patch("app.services.notifications.send_email") as mock_send:
        notify_meeting_scheduled(db_session, meeting=meeting)

    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body_text"]
    assert "scheduled" in body.lower()
    # No "at <location>" segment when location is missing.
    assert " at " not in body


def test_meeting_scheduled_swallows_delivery_error(db_session):
    tenant = _seed_tenant(db_session, "wiring-meet-smtp")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session, Role.STUDENT,
        email="stu@wiring.test", tenant_id=tenant.id, branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session, Role.COUNSELOR,
        tenant_id=tenant.id, branch_id=branch.id,
    )
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    meeting = _seed_meeting(
        db_session, tenant=tenant, student=student, counselor=counselor,
        application=application, location=None,
    )

    def _boom(**_kwargs):
        raise EmailDeliveryError("connection refused")

    with patch("app.services.notifications.send_email", side_effect=_boom):
        notify_meeting_scheduled(db_session, meeting=meeting)

    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_meeting(
    db_session,
    *,
    tenant,
    student,
    counselor,
    application,
    location,
):
    """Seed a Meeting row for the meeting-scheduled wiring tests."""
    from app.models.meeting import Meeting

    now = datetime.now(timezone.utc)
    meeting = Meeting(
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=student.id,
        counselor_id=counselor.id,
        scheduled_at=now,
        duration_minutes=30,
        location=location,
        notes=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)
    return meeting
