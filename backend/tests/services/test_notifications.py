"""Unit tests for the E48 in-app notification creation service.

Traces to:

* Requirements §6 Notifications ("In-app + email for status changes,
  document verification results, meeting scheduling … architected to
  plug in SMS/WhatsApp providers later").
* Journey J41 ("User receives an in-app notification on a relevant
  event").
* Epic E48 ("In-App Notification Generation").
* Issue #231 ("Tests: notification generated on key events").

These tests cover the **service layer** defined in
``app.services.notifications``: the helpers that produce notification
rows for each key event the spec calls out (application creation,
stage advance, document approve, document reject, counselor
reassignment). Integration coverage of the hooks wired into the
``applications`` router lives in
``tests/applications/test_notification_hooks.py``; tests of the
read/mark-read API live in E50's sibling suite.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.application import Application
from app.models.notification import Notification
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.services.notifications import (
    EVENT_APPLICATION_CREATED,
    EVENT_APPLICATION_STAGE_ADVANCED,
    EVENT_COUNSELOR_ASSIGNED,
    EVENT_DOCUMENT_APPROVED,
    EVENT_DOCUMENT_REJECTED,
    create_notification,
    notify_application_created,
    notify_application_stage_advanced,
    notify_counselor_assigned,
    notify_document_review_outcome,
)
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_db_user


# ---------------------------------------------------------------------------
# Local fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def tenant(db_session) -> Tenant:
    tenant = Tenant(name="NotifyCo", slug="notifyco")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture()
def branch(db_session, tenant):
    return seed_branch(db_session, tenant_id=tenant.id)


@pytest.fixture()
def student(db_session, tenant, branch) -> User:
    return make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )


@pytest.fixture()
def counselor(db_session, tenant, branch) -> User:
    return make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )


@pytest.fixture()
def application(db_session, tenant, branch, student, counselor) -> Application:
    return seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=counselor.id,
        university_id=1,
        program_id=1,
        stage=PipelineStage.REGISTERED,
    )


def _pending_document(
    db_session,
    *,
    tenant_id: int,
    application_id: int,
    student_id: int,
    filename: str = "transcript.pdf",
) -> StudentDocument:
    document = StudentDocument(
        tenant_id=tenant_id,
        application_id=application_id,
        status=StudentDocumentStatus.PENDING,
        original_filename=filename,
        content_type="application/pdf",
        size_bytes=2048,
        storage_path=f"tenants/{tenant_id}/applications/{application_id}/{filename}",
        uploaded_by_user_id=student_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


# ---------------------------------------------------------------------------
# create_notification (low-level helper)
# ---------------------------------------------------------------------------


def test_create_notification_persists_row(db_session, tenant, student):
    """``create_notification`` inserts a row matching every input field."""
    notification = create_notification(
        db_session,
        tenant_id=tenant.id,
        user_id=student.id,
        event_type=EVENT_APPLICATION_CREATED,
        title="hi",
        message="hello",
        related_application_id=42,
    )
    db_session.commit()
    db_session.refresh(notification)

    assert notification.id is not None
    assert notification.tenant_id == tenant.id
    assert notification.user_id == student.id
    assert notification.event_type == EVENT_APPLICATION_CREATED
    assert notification.title == "hi"
    assert notification.message == "hello"
    assert notification.related_application_id == 42
    assert notification.related_document_id is None
    assert notification.related_stage_history_id is None
    assert notification.read_at is None
    assert notification.created_at is not None
    assert notification.updated_at is not None


def test_create_notification_allows_null_recipient(db_session, tenant):
    """The recipient is optional — ``user_id=None`` is permitted (system event)."""
    notification = create_notification(
        db_session,
        tenant_id=tenant.id,
        user_id=None,
        event_type="system.ping",
        title="ping",
        message="pong",
    )
    db_session.commit()

    rows = db_session.scalars(select(Notification)).all()
    assert len(rows) == 1
    assert rows[0].id == notification.id
    assert rows[0].user_id is None


def test_create_notification_rolls_back_with_caller_session(db_session, tenant):
    """Notifications live in the same transaction as the caller (no implicit commit)."""
    create_notification(
        db_session,
        tenant_id=tenant.id,
        user_id=None,
        event_type="x",
        title="t",
        message="m",
    )
    db_session.rollback()

    assert db_session.scalars(select(Notification)).all() == []


# ---------------------------------------------------------------------------
# notify_application_stage_advanced
# ---------------------------------------------------------------------------


def test_notify_application_stage_advanced_targets_student(
    db_session, application, student
):
    """Stage advance produces a notification for the application's student."""
    notification = notify_application_stage_advanced(
        db_session,
        application=application,
        to_stage=PipelineStage.COUNSELING,
        changed_by_user_id=None,
        stage_history_id=99,
    )
    db_session.commit()

    assert notification is not None
    assert notification.user_id == student.id
    assert notification.event_type == EVENT_APPLICATION_STAGE_ADVANCED
    assert notification.related_application_id == application.id
    assert notification.related_stage_history_id == 99
    assert PipelineStage.COUNSELING.value in notification.title


def test_notify_application_stage_advanced_returns_none_without_student(
    db_session, tenant, branch, counselor
):
    """No recipient -> no row (no orphaned notifications)."""
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=None,
        assigned_counselor_id=counselor.id,
    )

    assert (
        notify_application_stage_advanced(
            db_session,
            application=application,
            to_stage=PipelineStage.COUNSELING,
            changed_by_user_id=None,
        )
        is None
    )
    assert db_session.scalars(select(Notification)).all() == []


# ---------------------------------------------------------------------------
# notify_document_review_outcome
# ---------------------------------------------------------------------------


def test_notify_document_review_outcome_approved(db_session, application, student):
    document = _pending_document(
        db_session,
        tenant_id=application.tenant_id,
        application_id=application.id,
        student_id=student.id,
        filename="marksheet.pdf",
    )

    notification = notify_document_review_outcome(
        db_session,
        document=document,
        outcome="approved",
        comment="looks good",
    )
    db_session.commit()

    assert notification is not None
    assert notification.event_type == EVENT_DOCUMENT_APPROVED
    assert notification.title == "Document approved"
    assert "marksheet.pdf" in notification.message
    assert "approved" in notification.message
    assert "looks good" in notification.message
    assert notification.user_id == student.id
    assert notification.related_application_id == application.id
    assert notification.related_document_id == document.id


def test_notify_document_review_outcome_rejected(db_session, application, student):
    document = _pending_document(
        db_session,
        tenant_id=application.tenant_id,
        application_id=application.id,
        student_id=student.id,
        filename="id-card.pdf",
    )

    notification = notify_document_review_outcome(
        db_session,
        document=document,
        outcome="rejected",
        comment="blurry scan",
    )
    db_session.commit()

    assert notification is not None
    assert notification.event_type == EVENT_DOCUMENT_REJECTED
    assert notification.title == "Document rejected"
    assert "id-card.pdf" in notification.message
    assert "rejected" in notification.message
    assert "blurry scan" in notification.message


def test_notify_document_review_outcome_no_comment_omits_note(
    db_session, application, student
):
    """An approve/reject without a comment must not produce a trailing 'Note: …'."""
    document = _pending_document(
        db_session,
        tenant_id=application.tenant_id,
        application_id=application.id,
        student_id=student.id,
    )

    notification = notify_document_review_outcome(
        db_session,
        document=document,
        outcome="approved",
    )
    db_session.commit()

    assert notification is not None
    assert "Note:" not in notification.message


def test_notify_document_review_outcome_rejects_unknown_value(
    db_session, application, student
):
    document = _pending_document(
        db_session,
        tenant_id=application.tenant_id,
        application_id=application.id,
        student_id=student.id,
    )

    with pytest.raises(ValueError):
        notify_document_review_outcome(
            db_session,
            document=document,
            outcome="mysteriously-vanished",
        )


def test_notify_document_review_outcome_returns_none_without_uploader(
    db_session, tenant, branch
):
    """A document with no recorded uploader produces no notification row."""
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=None,
    )
    document = _pending_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        student_id=None,
    )

    assert (
        notify_document_review_outcome(
            db_session,
            document=document,
            outcome="approved",
        )
        is None
    )


# ---------------------------------------------------------------------------
# notify_application_created
# ---------------------------------------------------------------------------


def test_notify_application_created_targets_counselor(
    db_session, application, counselor
):
    notification = notify_application_created(db_session, application=application)
    db_session.commit()

    assert notification is not None
    assert notification.user_id == counselor.id
    assert notification.event_type == EVENT_APPLICATION_CREATED
    assert notification.related_application_id == application.id


def test_notify_application_created_skips_when_no_counselor(
    db_session, tenant, branch, student
):
    """No assigned counselor -> no notification row (per E19 design)."""
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        assigned_counselor_id=None,
    )

    assert (
        notify_application_created(db_session, application=application) is None
    )
    assert db_session.scalars(select(Notification)).all() == []


# ---------------------------------------------------------------------------
# notify_counselor_assigned
# ---------------------------------------------------------------------------


def test_notify_counselor_assigned_targets_new_counselor(
    db_session, application, counselor
):
    notification = notify_counselor_assigned(
        db_session,
        application=application,
        new_counselor_user_id=counselor.id,
    )
    db_session.commit()

    assert notification is not None
    assert notification.user_id == counselor.id
    assert notification.event_type == EVENT_COUNSELOR_ASSIGNED
    assert notification.related_application_id == application.id


def test_notify_counselor_assigned_skips_when_none(db_session, application):
    """Unsetting a counselor (``None``) must not produce a notification row."""
    assert (
        notify_counselor_assigned(
            db_session,
            application=application,
            new_counselor_user_id=None,
        )
        is None
    )
    assert db_session.scalars(select(Notification)).all() == []
