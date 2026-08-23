"""E49 mocked-SMTP integration tests — Issue #235.

These are the end-to-end coverage for the E49 / J42 "Email
Notifications" epic at the HTTP boundary. Issue #234's developer
tests (:mod:`tests.notifications.test_email_wiring`) exercise the
service-layer notification hooks directly; the tests here drive the
real router endpoints (``POST /applications/{id}/stage``,
``POST /applications/{id}/mark-enrolled``, ``mark-rejected``,
``mark-withdrawn``, ``POST /verifier/documents/{id}/approve``,
``POST /verifier/documents/{id}/reject``, and ``POST /meetings``)
through the FastAPI ``TestClient`` and assert that, after the
originating 2xx response, ``send_email`` is invoked with the right
``to`` / ``subject`` / ``body_text`` for each event.

The SMTP network layer is fully mocked: every test patches
``app.services.notifications.send_email`` at the caller's import
site (the contract pinned by :mod:`tests.email.test_e49_abstraction`)
so no real socket is opened. The end-to-end shape is:

    HTTP request -> router -> notify_* -> _send_notification_email ->
    send_email (patched) -> captured call args

We additionally exercise the failure-shapes contract from #234:

* A recipient user with no email address must not crash the wiring
  (mock must not be called).
* A recipient user that doesn't exist in the DB at all must not
  crash the wiring (mock must not be called).
* An :class:`EmailDeliveryError` raised by ``send_email`` must be
  swallowed so the originating HTTP request still returns 2xx (and
  the in-app notification row is still persisted).

These tests intentionally live under ``tests/email/`` (not
``tests/notifications/``) because they cover the E49 epic and
use the same mock-friendly conventions as the rest of
``tests/email/``. They never read the implementation files; the
patch target (``app.services.notifications.send_email``) is the
public seam pinned by the E49 abstraction contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.email.service import EmailDeliveryError
from app.models.meeting import Meeting
from app.models.notification import Notification
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.default_transitions import seed_default_stage_transitions
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_tenant(db_session: Session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _auth_for(user) -> object:
    return make_authenticated_user(
        user.role,
        user_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


def _stage_rules(db_session: Session) -> None:
    seed_default_stage_transitions(db_session)


def _emails_to(mock_send) -> list[str]:
    """Return the list of recipients from a ``send_email`` call list, in order."""
    return [call.kwargs["to"] for call in mock_send.call_args_list]


def _emails_for(mock_send, *, to: str) -> list:
    """Return every ``send_email`` call whose recipient is ``to``."""
    return [call for call in mock_send.call_args_list if call.kwargs["to"] == to]


# ---------------------------------------------------------------------------
# Stage change (POST /applications/{id}/stage) — student + counselor
# ---------------------------------------------------------------------------


def test_advance_stage_endpoint_dispatches_emails_to_student_and_counselor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Hitting the advance-stage endpoint must send email to the student and
    the assigned counselor (when the counselor is not the actor)."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int Stage", slug="int-stage")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-stage-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-stage-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="int-stage-manager@example.test",
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
    override_authenticated_user(_auth_for(manager))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": PipelineStage.COUNSELING.value},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200, response.text

    # Two emails dispatched: one to the student, one to the assigned counselor.
    recipients = _emails_to(mock_send)
    assert sorted(recipients) == [
        "int-stage-counselor@example.test",
        "int-stage-student@example.test",
    ]

    # The student's email subject/body matches the template for stage change.
    student_calls = _emails_for(mock_send, to="int-stage-student@example.test")
    assert len(student_calls) == 1
    assert "counseling" in student_calls[0].kwargs["subject"].lower()
    assert "registered" in student_calls[0].kwargs["body_text"]
    assert "counseling" in student_calls[0].kwargs["body_text"]

    # The counselor's email body mentions the new stage (assigned-application copy).
    counselor_calls = _emails_for(
        mock_send, to="int-stage-counselor@example.test"
    )
    assert len(counselor_calls) == 1
    assert "assigned" in counselor_calls[0].kwargs["body_text"].lower()


def test_advance_stage_endpoint_skips_counselor_email_when_counselor_is_actor(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """If the assigned counselor is the actor, only the student gets an email."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int Self", slug="int-self")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-self-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-self-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_auth_for(counselor))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": PipelineStage.UNIVERSITY_SHORTLISTING.value},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200, response.text
    assert _emails_to(mock_send) == ["int-self-student@example.test"]


def test_advance_stage_endpoint_swallows_email_delivery_error(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An ``EmailDeliveryError`` from SMTP must NOT fail the originating request."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int Smtp", slug="int-smtp")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-smtp-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="int-smtp-manager@example.test",
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
    override_authenticated_user(_auth_for(manager))

    def _boom(**_kwargs) -> None:
        raise EmailDeliveryError("connection refused")

    with patch("app.services.notifications.send_email", side_effect=_boom):
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": PipelineStage.UNIVERSITY_SHORTLISTING.value},
            headers={"Authorization": "Bearer test-token"},
        )

    # The originating HTTP request still succeeds; the email failure is swallowed.
    assert response.status_code == 200, response.text

    # The in-app notification row was persisted even though SMTP failed.
    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert len(rows) == 1


def test_advance_stage_endpoint_skips_email_when_student_has_no_email(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A student with no email address must not crash the wiring nor send a blank email."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int NoEmail", slug="int-noemail")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    student.email = ""  # type: ignore[assignment]
    db_session.commit()
    db_session.refresh(student)
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="int-noemail-mgr@example.test",
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
    override_authenticated_user(_auth_for(manager))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": PipelineStage.UNIVERSITY_SHORTLISTING.value},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200, response.text
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Mark enrolled / rejected / withdrawn — student + counselor emails
# ---------------------------------------------------------------------------


def test_mark_enrolled_endpoint_dispatches_emails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """POST /applications/{id}/mark-enrolled sends student + counselor emails."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int Enroll", slug="int-enroll")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-enroll-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-enroll-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="int-enroll-manager@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.VISA_PROCESSING,
    )
    override_authenticated_user(_auth_for(manager))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/applications/{application.id}/mark-enrolled",
            json={"details": "Visa stamped"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200, response.text
    recipients = _emails_to(mock_send)
    assert sorted(recipients) == [
        "int-enroll-counselor@example.test",
        "int-enroll-student@example.test",
    ]
    student_call = _emails_for(
        mock_send, to="int-enroll-student@example.test"
    )[0]
    assert "enrolled" in student_call.kwargs["subject"].lower()


def test_mark_rejected_endpoint_dispatches_emails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """POST /applications/{id}/mark-rejected sends student + counselor emails."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int Reject", slug="int-reject")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-reject-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-reject-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="int-reject-manager@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_auth_for(manager))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/applications/{application.id}/mark-rejected",
            json={"reason": "Incomplete application"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200, response.text
    recipients = _emails_to(mock_send)
    assert sorted(recipients) == [
        "int-reject-counselor@example.test",
        "int-reject-student@example.test",
    ]
    student_call = _emails_for(
        mock_send, to="int-reject-student@example.test"
    )[0]
    assert "rejected" in student_call.kwargs["subject"].lower()
    # The stage-change email body includes from/to stages (per the
    # E49 stage-change template pinned by issue #233) but does NOT
    # carry the rejection reason -- reasons are surfaced via the
    # in-app notification row only.
    assert "rejected" in student_call.kwargs["body_text"]
    assert "counseling" in student_call.kwargs["body_text"]


def test_mark_withdrawn_endpoint_dispatches_emails(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """POST /applications/{id}/mark-withdrawn sends student + counselor emails."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int Withdraw", slug="int-withdraw")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-withdraw-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-withdraw-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="int-withdraw-manager@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        stage=PipelineStage.VISA_PROCESSING,
    )
    override_authenticated_user(_auth_for(manager))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/applications/{application.id}/mark-withdrawn",
            json={"reason": "Student changed mind"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200, response.text
    recipients = _emails_to(mock_send)
    assert sorted(recipients) == [
        "int-withdraw-counselor@example.test",
        "int-withdraw-student@example.test",
    ]
    student_call = _emails_for(
        mock_send, to="int-withdraw-student@example.test"
    )[0]
    assert "withdrawn" in student_call.kwargs["subject"].lower()
    # The stage-change email body includes from/to stages (per the
    # E49 stage-change template pinned by issue #233) but does NOT
    # carry the withdrawal reason -- reasons are surfaced via the
    # in-app notification row only.
    assert "withdrawn" in student_call.kwargs["body_text"]
    assert "visa_processing" in student_call.kwargs["body_text"]


# ---------------------------------------------------------------------------
# Document approve / reject — student email only
# ---------------------------------------------------------------------------


def _seed_pending_document(
    db_session: Session,
    *,
    tenant: Tenant,
    branch,
    student,
    filename: str = "t.pdf",
) -> StudentDocument:
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    document = StudentDocument(
        tenant_id=tenant.id,
        application_id=application.id,
        status=StudentDocumentStatus.PENDING,
        original_filename=filename,
        content_type="application/pdf",
        size_bytes=10,
        storage_path=f"t/{tenant.id}/{application.id}/{filename}",
        uploaded_by_user_id=student.id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_approve_document_endpoint_dispatches_student_email(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """POST /verifier/documents/{id}/approve sends an approval email to the student."""
    tenant = _seed_tenant(db_session, name="Int Doc Approve", slug="int-doc-approve")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-doc-approve-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    document = _seed_pending_document(
        db_session, tenant=tenant, branch=branch, student=student,
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        email="int-doc-approve-verifier@example.test",
        tenant_id=tenant.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=verifier.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/verifier/documents/{document.id}/approve",
            json={"comment": "Looks good"},
        )

    assert response.status_code == 200, response.text

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "int-doc-approve-student@example.test"
    assert "approved" in kwargs["subject"].lower()
    assert "Looks good" in kwargs["body_text"]


def test_approve_document_endpoint_skips_email_when_no_comment(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """Approve with ``comment=null`` still sends an email; the body has no comment marker."""
    tenant = _seed_tenant(db_session, name="Int Doc Approve NC", slug="int-doc-approve-nc")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-doc-approve-nc-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    document = _seed_pending_document(
        db_session,
        tenant=tenant,
        branch=branch,
        student=student,
        filename="nc.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        email="int-doc-approve-nc-verifier@example.test",
        tenant_id=tenant.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=verifier.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/verifier/documents/{document.id}/approve",
            json={"comment": None},
        )

    assert response.status_code == 200, response.text
    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body_text"]
    assert "comment" not in body.lower()


def test_reject_document_endpoint_dispatches_student_email_with_reason(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """POST /verifier/documents/{id}/reject sends a rejection email to the student."""
    tenant = _seed_tenant(db_session, name="Int Doc Reject", slug="int-doc-reject")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-doc-reject-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    document = _seed_pending_document(
        db_session,
        tenant=tenant,
        branch=branch,
        student=student,
        filename="reject.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        email="int-doc-reject-verifier@example.test",
        tenant_id=tenant.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=verifier.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/verifier/documents/{document.id}/reject",
            json={"comment": "Image too blurry"},
        )

    assert response.status_code == 200, response.text
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "int-doc-reject-student@example.test"
    assert "rejected" in kwargs["subject"].lower()
    assert "Image too blurry" in kwargs["body_text"]


def test_reject_document_endpoint_swallows_email_delivery_error(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An SMTP failure on the reject endpoint must not break the response."""
    tenant = _seed_tenant(db_session, name="Int Doc Reject Smtp", slug="int-doc-reject-smtp")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-doc-reject-smtp-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    document = _seed_pending_document(
        db_session,
        tenant=tenant,
        branch=branch,
        student=student,
        filename="reject-smtp.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        email="int-doc-reject-smtp-verifier@example.test",
        tenant_id=tenant.id,
    )
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=verifier.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    def _boom(**_kwargs) -> None:
        raise EmailDeliveryError("smtp down")

    with patch("app.services.notifications.send_email", side_effect=_boom):
        response = client.post(
            f"/verifier/documents/{document.id}/reject",
            json={"comment": "Image too blurry"},
        )

    assert response.status_code == 200, response.text

    # In-app notification was persisted even though SMTP failed.
    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Meeting scheduled — student email only
# ---------------------------------------------------------------------------


def _schedule_payload(
    *,
    application_id: int,
    student_id: int,
    counselor_id: int,
    location: str | None = "Room 1",
) -> dict:
    return {
        "application_id": application_id,
        "student_id": student_id,
        "counselor_id": counselor_id,
        "scheduled_at": (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat(),
        "duration_minutes": 30,
        "location": location,
    }


def test_schedule_meeting_endpoint_dispatches_student_email_with_location(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """POST /meetings sends a meeting-scheduled email to the student."""
    tenant = _seed_tenant(db_session, name="Int Meet", slug="int-meet")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-meet-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-meet-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            "/meetings",
            json=_schedule_payload(
                application_id=application.id,
                student_id=student.id,
                counselor_id=counselor.id,
                location="Room 4",
            ),
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 201, response.text

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "int-meet-student@example.test"
    assert "scheduled" in kwargs["subject"].lower()
    assert "Room 4" in kwargs["body_text"]


def test_schedule_meeting_endpoint_dispatches_student_email_without_location(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """A meeting scheduled with no location still produces an email; no ``at <loc>`` segment."""
    tenant = _seed_tenant(db_session, name="Int Meet NL", slug="int-meet-nl")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-meet-nl-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-meet-nl-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            "/meetings",
            json=_schedule_payload(
                application_id=application.id,
                student_id=student.id,
                counselor_id=counselor.id,
                location=None,
            ),
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 201, response.text
    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body_text"]
    assert "scheduled" in body.lower()
    assert " at " not in body


def test_schedule_meeting_endpoint_swallows_email_delivery_error(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An SMTP failure on meeting scheduling must not break the response."""
    tenant = _seed_tenant(db_session, name="Int Meet Smtp", slug="int-meet-smtp")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        email="int-meet-smtp-student@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="int-meet-smtp-counselor@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
    )
    override_authenticated_user(_auth_for(counselor))

    def _boom(**_kwargs) -> None:
        raise EmailDeliveryError("connection refused")

    with patch("app.services.notifications.send_email", side_effect=_boom):
        response = client.post(
            "/meetings",
            json=_schedule_payload(
                application_id=application.id,
                student_id=student.id,
                counselor_id=counselor.id,
            ),
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 201, response.text

    # The meeting row is committed (first commit), and the in-app
    # notification row was persisted even though SMTP failed (the
    # notification helper's EmailDeliveryError swallow is independent
    # of the email-send call itself).
    assert (
        db_session.query(Meeting)
        .filter(Meeting.application_id == application.id)
        .count()
        == 1
    )
    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# No-recipient fallbacks — end-to-end via the router
# ---------------------------------------------------------------------------


def test_advance_stage_endpoint_skips_email_when_student_user_missing(
    client: TestClient,
    db_session: Session,
    override_authenticated_user,
) -> None:
    """An application whose student_id points at a missing user must not crash the wiring."""
    _stage_rules(db_session)
    tenant = _seed_tenant(db_session, name="Int Missing St", slug="int-missing-st")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    manager = make_db_user(
        db_session,
        Role.BRANCH_MANAGER,
        email="int-missing-st-mgr@example.test",
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=999_999,
        stage=PipelineStage.COUNSELING,
    )
    override_authenticated_user(_auth_for(manager))

    with patch("app.services.notifications.send_email") as mock_send:
        response = client.post(
            f"/applications/{application.id}/stage",
            json={"to_stage": PipelineStage.UNIVERSITY_SHORTLISTING.value},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200, response.text
    mock_send.assert_not_called()



