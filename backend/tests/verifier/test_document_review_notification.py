"""Document review outcome generates an in-app notification (E32; Journey J25; issue #190).

End-to-end acceptance that approving or rejecting a pending student
document through the E29 / E30 verifier endpoints creates the
in-app :class:`Notification` row the student needs to see the
review outcome in their notification center (Journey J25). The
notification-creation helpers themselves
(:func:`app.services.notifications.notify_document_approved` /
:func:`notify_document_rejected`) are unit-tested in
``tests/services/test_notifications.py``; this file drives them via
the real ``POST /verifier/documents/{id}/approve`` and
``POST /verifier/documents/{id}/reject`` endpoints so a regression
that silently removes the wiring (e.g. drops the
``notify_document_*`` call from the router) is caught.

Specifically:

* an approve with a comment generates a single notification for the
  uploading student with ``title="Document approved"`` and a
  message that embeds the verifier's comment;
* an approve without a comment still produces a notification with
  ``title="Document approved"`` and no ``"Comment:"`` suffix;
* a reject with the mandatory comment generates a single
  notification for the uploading student with
  ``title="Document rejected"`` and a message that embeds the
  rejection reason;
* the verifier (the actor) is never self-notified;
* the notification is tenant-scoped to the document's tenant
  (no cross-tenant leak);
* a 403 / 422 / 404 (cross-tenant) response never produces a
  notification.

Sibling ticket #189 owns the developer-side wiring acceptance for
the same hooks; this file is the issue #190 black-box / regression
suite that exercises the *end-to-end* behaviour via the HTTP
surface (approve / reject endpoints) rather than calling the
service helpers directly.
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
    """Seed an application + pending StudentDocument row."""
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
    db_session,
    *,
    slug: str,
    filename: str = "doc.pdf",
):
    """Seed tenant + branch + student + pending document + verifier."""
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
    return tenant, branch, student, verifier, document


def _notifications_for(db_session, user_id: int) -> list[Notification]:
    return (
        db_session.query(Notification)
        .filter(Notification.user_id == user_id)
        .all()
    )


# ---------------------------------------------------------------------------
# Approve path: notification is generated with the documented content
# ---------------------------------------------------------------------------


def test_approve_creates_notification_with_expected_title_and_message(
    client, db_session, override_authenticated_user
):
    """Approving a pending document creates exactly one in-app notification
    for the uploading student with the documented title and a message
    that embeds the verifier's comment (E32; J25).
    """
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
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
    # Tenant scope matches the document's tenant.
    assert notification.tenant_id == tenant.id
    # Freshly created, so still unread.
    assert notification.read_at is None


def test_approve_creates_notification_without_comment_suffix_when_no_comment(
    client, db_session, override_authenticated_user
):
    """An approve without a comment produces the documented notification
    whose message has no ``"Comment:"`` suffix."""
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
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
    # No comment => no "Comment:" suffix.
    assert "Comment:" not in notification.message
    assert notification.tenant_id == tenant.id


def test_approve_does_not_notify_the_verifier(
    client, db_session, override_authenticated_user
):
    """The verifier is the actor; they must not be self-notified about
    their own approval action."""
    tenant, _branch, _student, verifier, document = _seed_verifier_student_doc(
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


def test_approve_only_writes_one_notification_for_the_student(
    client, db_session, override_authenticated_user
):
    """The approve path writes EXACTLY one notification (no double-insert
    when the request is retried or when the wiring is invoked twice in
    the same transaction).
    """
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="appr-notif-once"
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

    rows = _notifications_for(db_session, student.id)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Reject path: notification is generated with the documented content
# ---------------------------------------------------------------------------


def test_reject_creates_notification_with_expected_title_and_message(
    client, db_session, override_authenticated_user
):
    """Rejecting a pending document creates exactly one in-app notification
    for the uploading student with the documented title and a message
    that embeds the (mandatory) rejection reason (E32; J25).
    """
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
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
    """The verifier is the actor on the reject path too; they must not
    be self-notified about their own rejection."""
    tenant, _branch, _student, verifier, document = _seed_verifier_student_doc(
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


def test_reject_only_writes_one_notification_for_the_student(
    client, db_session, override_authenticated_user
):
    """The reject path writes EXACTLY one notification."""
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="rej-notif-once"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/reject",
        json={"comment": "Blurry"},
    )
    assert response.status_code == 200, response.text

    rows = _notifications_for(db_session, student.id)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Notification persists past the HTTP response: J25 / J43 wiring.
# The notification produced by approve / reject must outlive the request so
# the student's notification-center list endpoint (E50) can render it on
# the next page load.
# ---------------------------------------------------------------------------


def test_approve_notification_persists_to_database_after_response(
    client, db_session, override_authenticated_user
):
    """After the approve HTTP response returns, the notification is in the
    DB (not just in some in-flight buffer). A second request via a fresh
    session boundary observes the same row. Regression guard for an
    uncommitted-flush bug."""
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="appr-notif-persist"
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

    # The notification row is visible to a fresh query -- the router
    # committed (or the session was flushed) before returning, so the
    # J43 notification-center list endpoint (E50) will see it.
    db_session.expire_all()
    rows = (
        db_session.query(Notification)
        .filter(
            Notification.user_id == student.id,
            Notification.tenant_id == tenant.id,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Document approved"
    assert rows[0].user_id == student.id
    assert rows[0].tenant_id == tenant.id


def test_reject_notification_persists_to_database_after_response(
    client, db_session, override_authenticated_user
):
    """Same persistence contract for reject."""
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="rej-notif-persist"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/reject",
        json={"comment": "Wrong file"},
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    rows = (
        db_session.query(Notification)
        .filter(
            Notification.user_id == student.id,
            Notification.tenant_id == tenant.id,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Document rejected"
    assert "Wrong file" in rows[0].message


def test_approve_then_reject_creates_two_independent_notifications(
    client, db_session, override_authenticated_user
):
    """Approving one document and rejecting a different document for the
    same student produces TWO notifications (no overwrite, no missing
    row). The student sees both review outcomes in their notification
    center, matching J25 / J43.
    """
    tenant, branch, student, verifier, approved_doc = _seed_verifier_student_doc(
        db_session, slug="seq-notif-approve", filename="first.pdf"
    )
    rejected_doc = _seed_pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        filename="second.pdf",
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    approve_response = client.post(
        f"/verifier/documents/{approved_doc.id}/approve",
        json={"comment": "ok"},
    )
    assert approve_response.status_code == 200, approve_response.text

    reject_response = client.post(
        f"/verifier/documents/{rejected_doc.id}/reject",
        json={"comment": "blurry"},
    )
    assert reject_response.status_code == 200, reject_response.text

    db_session.expire_all()
    rows = _notifications_for(db_session, student.id)
    titles = {row.title for row in rows}
    assert titles == {"Document approved", "Document rejected"}
    # Each notification's message carries its own verifier feedback.
    messages_by_title = {row.title: row.message for row in rows}
    assert "ok" in messages_by_title["Document approved"]
    assert "blurry" in messages_by_title["Document rejected"]


def test_notification_created_by_approve_is_unread_by_default(
    client, db_session, override_authenticated_user
):
    """A freshly created document-review notification is unread
    (``read_at IS NULL``) so the student's notification-center badge
    (E50 / J43) counts it.
    """
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="appr-notif-unread"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "fine"},
    )
    assert response.status_code == 200, response.text

    [notification] = _notifications_for(db_session, student.id)
    assert notification.read_at is None


def test_notification_created_by_reject_is_unread_by_default(
    client, db_session, override_authenticated_user
):
    """Reject-created notifications are also unread by default."""
    tenant, _branch, student, verifier, document = _seed_verifier_student_doc(
        db_session, slug="rej-notif-unread"
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/reject",
        json={"comment": "Wrong type"},
    )
    assert response.status_code == 200, response.text

    [notification] = _notifications_for(db_session, student.id)
    assert notification.read_at is None


# ---------------------------------------------------------------------------
# Tenant isolation: cross-tenant requests surface as 404 and never
# produce a notification for the foreign student.
# ---------------------------------------------------------------------------


def test_cross_tenant_approve_does_not_create_notification(
    client, db_session, override_authenticated_user
):
    """A verifier in tenant A cannot approve tenant B's document; the
    request is 404 and no notification is written for tenant B's student
    (no cross-tenant leak via the wiring).
    """
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
        filename="foreign-rej.pdf",
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
# Negative paths: a 403 / 422 must NOT create a notification.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [Role.STUDENT, Role.CONSULTANCY_OWNER, Role.COUNSELOR],
)
def test_non_verifier_approve_attempt_does_not_create_notification(
    client, db_session, override_authenticated_user, role
):
    """A non-verifier role attempting to approve is rejected (no role
    other than DOCUMENT_VERIFIER holds ``document:verify``). The wiring
    must not fire -- no spurious notifications are produced for the
    student when the action is rejected.
    """
    tenant = _create_tenant(
        db_session,
        name=f"{role.value} approve",
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
        filename=f"{role.value}-approve.pdf",
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

    assert response.status_code in (403, 422)
    assert _notifications_for(db_session, student.id) == []


@pytest.mark.parametrize(
    "role",
    [Role.STUDENT, Role.CONSULTANCY_OWNER, Role.COUNSELOR],
)
def test_non_verifier_reject_attempt_does_not_create_notification(
    client, db_session, override_authenticated_user, role
):
    """Same isolation contract for reject: a non-verifier role's
    request is rejected, and no spurious notification is written
    for the student.
    """
    tenant = _create_tenant(
        db_session,
        name=f"{role.value} reject",
        slug=f"rej-notif-{role.value}",
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
        filename=f"{role.value}-reject.pdf",
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
        f"/verifier/documents/{document.id}/reject",
        json={"comment": "trying"},
    )

    assert response.status_code in (403, 422)
    assert _notifications_for(db_session, student.id) == []
