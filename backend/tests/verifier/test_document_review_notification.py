"""Document review outcome fires the right in-app notification (E32; Journey J25; issue #189).

End-to-end coverage of the wiring that calls
:func:`app.services.notifications.notify_document_approved` /
:func:`notify_document_rejected` from the E29 / E30 verifier endpoints
(E32 — "Document Review Outcome Notification"). Sibling ticket #190
owns additional black-box coverage; this file is the developer-side
acceptance that the verifier router actually invokes the notification
helpers and produces the documented notification rows.

Specifically, on the approve/reject happy paths we assert:

* the student who uploaded the document receives exactly one
  in-app :class:`Notification` (no self-notify of the verifier; no
  double-insert);
* the notification's ``title`` is the documented short heading
  (``"Document approved"`` / ``"Document rejected"``);
* the notification's ``message`` carries the verifier's comment /
  rejection reason so the student sees the reviewer's feedback
  alongside the verdict;
* the notification is tenant-scoped to the document's tenant
  (no cross-tenant leak).

We exercise the hooks via the real ``POST /verifier/documents/{id}/approve``
and ``POST /verifier/documents/{id}/reject`` endpoints (not by calling
the service module directly) so that if the wiring is ever removed from
the router, these tests fail -- which is the whole point of an
integration test for an end-to-end wiring ticket.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.notification import Notification
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_pending_document(
    db_session,
    *,
    tenant_id: int,
    branch_id: int,
    student_id: int,
    filename: str = "transcript.pdf",
) -> StudentDocument:
    """Seed an application + a pending StudentDocument row."""
    application = seed_application(
        db_session,
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        university_id=11,
        program_id=21,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    document = StudentDocument(
        tenant_id=tenant_id,
        application_id=application.id,
        status=StudentDocumentStatus.PENDING,
        original_filename=filename,
        content_type="application/pdf",
        size_bytes=2048,
        storage_path=(
            f"tenants/{tenant_id}/applications/{application.id}/{filename}"
        ),
        uploaded_by_user_id=student_id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _auth_as_verifier(
    override_authenticated_user,
    *,
    user_id: int,
    tenant_id: int,
) -> None:
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=None,
        )
    )


def _seed_verifier_student_doc(
    db_session, *, slug: str, filename: str = "doc.pdf"
):
    """Seed a tenant + branch + student + pending document + verifier."""
    tenant = _create_tenant(db_session, name=slug, slug=slug)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    document = _seed_pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        filename=filename,
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    return tenant, student, verifier, document


def _notifications_for(db_session, user_id: int) -> list[Notification]:
    return (
        db_session.query(Notification)
        .filter(Notification.user_id == user_id)
        .all()
    )


# ---------------------------------------------------------------------------
# Approve path: notification content (E32 / J25 / #189)
# ---------------------------------------------------------------------------


def test_approve_creates_notification_with_expected_title_and_message(
    client, db_session, override_authenticated_user
):
    """The verifier approve endpoint creates one in-app notification for the
    uploading student with the documented title and a message that
    embeds the verifier's optional comment."""
    tenant, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="appr-notif-content"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "All good"},
    )

    assert response.status_code == 200, response.text

    rows = _notifications_for(db_session, student.id)
    assert len(rows) == 1
    notification = rows[0]
    assert notification.title == "Document approved"
    assert "approved" in notification.message.lower()
    assert "All good" in notification.message
    # Tenant scope matches the document's tenant (no cross-tenant leak).
    assert notification.tenant_id == tenant.id
    assert notification.read_at is None


def test_approve_creates_notification_without_comment_suffix_when_no_comment(
    client, db_session, override_authenticated_user
):
    """An approve without a comment produces the documented notification
    whose message has no "Comment:" suffix (mirrors the service helper)."""
    tenant, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="appr-notif-nocomment"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": None},
    )

    assert response.status_code == 200, response.text

    rows = _notifications_for(db_session, student.id)
    assert len(rows) == 1
    notification = rows[0]
    assert notification.title == "Document approved"
    # No comment => no "Comment:" suffix in the message body.
    assert "Comment:" not in notification.message
    assert notification.tenant_id == tenant.id


def test_approve_does_not_notify_the_verifier(
    client, db_session, override_authenticated_user
):
    """The verifier is the actor; they must not be self-notified about
    their own approval action."""
    tenant, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="appr-notif-self"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "ok"},
    )

    assert response.status_code == 200, response.text
    assert _notifications_for(db_session, verifier.id) == []


# ---------------------------------------------------------------------------
# Reject path: notification content (E32 / J25 / #189)
# ---------------------------------------------------------------------------


def test_reject_creates_notification_with_expected_title_and_message(
    client, db_session, override_authenticated_user
):
    """The verifier reject endpoint creates one in-app notification for the
    uploading student with the documented title and a message that
    embeds the mandatory rejection reason."""
    tenant, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="rej-notif-content"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/reject",
        json={"comment": "Image too blurry"},
    )

    assert response.status_code == 200, response.text

    rows = _notifications_for(db_session, student.id)
    assert len(rows) == 1
    notification = rows[0]
    assert notification.title == "Document rejected"
    assert "rejected" in notification.message.lower()
    assert "Image too blurry" in notification.message
    assert notification.tenant_id == tenant.id
    assert notification.read_at is None


def test_reject_does_not_notify_the_verifier(
    client, db_session, override_authenticated_user
):
    """The verifier is the actor on the reject path too; they must not be
    self-notified about their own rejection."""
    tenant, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="rej-notif-self"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/reject",
        json={"comment": "Wrong document"},
    )

    assert response.status_code == 200, response.text
    assert _notifications_for(db_session, verifier.id) == []


# ---------------------------------------------------------------------------
# Tenant isolation (cross-tenant verifier cannot trigger a notification
# for the foreign document's student -- the request is 404, so no row
# is written at all).
# ---------------------------------------------------------------------------


def test_cross_tenant_approve_does_not_create_notification(
    client, db_session, override_authenticated_user
):
    """A verifier in tenant A cannot approve tenant B's document; the
    request is 404 and no notification is written for tenant B's student
    (no cross-tenant notification leak via the wiring)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="appr-xtenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="appr-xtenant-b")
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
    )
    foreign_document = _seed_pending_document(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        filename="foreign.pdf",
    )
    verifier_a = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant_a.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier_a.id,
        tenant_id=tenant_a.id,
    )

    response = client.post(
        f"/verifier/documents/{foreign_document.id}/approve",
        json={"comment": "trying"},
    )

    assert response.status_code == 404
    # No notification for the foreign student -- the wiring never ran
    # because the endpoint returned 404 before reaching the hook call.
    assert _notifications_for(db_session, student_b.id) == []


def test_cross_tenant_reject_does_not_create_notification(
    client, db_session, override_authenticated_user
):
    """Same isolation contract for reject: cross-tenant request is 404,
    no notification for the foreign student."""
    tenant_a = _create_tenant(db_session, name="Tenant A Reject", slug="rej-xtenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B Reject", slug="rej-xtenant-b")
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)
    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
    )
    foreign_document = _seed_pending_document(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
        filename="foreign.pdf",
    )
    verifier_a = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant_a.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier_a.id,
        tenant_id=tenant_a.id,
    )

    response = client.post(
        f"/verifier/documents/{foreign_document.id}/reject",
        json={"comment": "trying"},
    )

    assert response.status_code == 404
    assert _notifications_for(db_session, student_b.id) == []


# ---------------------------------------------------------------------------
# Negative path: a 403 / 422 must NOT create a notification.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [Role.STUDENT, Role.CONSULTANCY_OWNER, Role.COUNSELOR],
)
def test_non_verifier_approve_attempt_does_not_create_notification(
    client, db_session, override_authenticated_user, role
):
    """A non-verifier role attempting to approve is 403 (or 422 once
    permission-check ordering is in scope); in every case the wiring
    must not fire -- no spurious notifications are produced for the
    student when the action is rejected."""
    tenant = _create_tenant(
        db_session,
        name=f"Authz {role.value}",
        slug=f"appr-notif-{role.value}",
    )
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    document = _seed_pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )

    if role == Role.CONSULTANCY_OWNER:
        caller = make_db_user(
            db_session,
            Role.CONSULTANCY_OWNER,
            tenant_id=tenant.id,
            branch_id=None,
        )
    else:
        caller = make_db_user(
            db_session,
            role,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

    override_authenticated_user(
        make_authenticated_user(
            role,
            user_id=caller.id,
            tenant_id=tenant.id,
            branch_id=None if role == Role.CONSULTANCY_OWNER else branch.id,
        )
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "trying"},
    )

    # The exact status code varies by role (403 for STUDENT/COUNSELOR,
    # 403 for CONSULTANCY_OWNER as well -- no role other than
    # DOCUMENT_VERIFIER holds ``document:verify``), but no role in
    # this parametrize set is allowed through, and no notification
    # must have been written for the student.
    assert response.status_code in (403, 422)
    assert _notifications_for(db_session, student.id) == []
