"""Notifications are generated on key events (E48; Journey J41; issue #231).

End-to-end coverage that hitting the real endpoints creates in-app Notification
rows for the right recipients:
- an application stage transition (mark-enrolled/rejected/withdrawn, advance)
  notifies the student, and the assigned counselor when they are not the actor;
- approving / rejecting a document notifies the uploading student.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.notification import Notification
from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.default_transitions import seed_default_stage_transitions
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


def _tenant(db_session, slug) -> Tenant:
    tenant = Tenant(name=slug, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _notifications_for(db_session, user_id: int) -> list[Notification]:
    return db_session.query(Notification).filter(Notification.user_id == user_id).all()


def test_stage_transition_notifies_student_and_counselor(client, db_session, override_authenticated_user):
    seed_default_stage_transitions(db_session)
    tenant = _tenant(db_session, "notif-stage")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    manager = make_db_user(db_session, Role.BRANCH_MANAGER, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        assigned_counselor_id=counselor.id, stage=PipelineStage.VISA_PROCESSING,
    )
    # A branch manager (not the assigned counselor) performs the action.
    override_authenticated_user(
        make_authenticated_user(Role.BRANCH_MANAGER, user_id=manager.id, tenant_id=tenant.id, branch_id=branch.id)
    )

    resp = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "done"}, headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200, resp.text

    assert len(_notifications_for(db_session, student.id)) == 1
    assert len(_notifications_for(db_session, counselor.id)) == 1
    # The actor (manager) is not notified about their own action.
    assert _notifications_for(db_session, manager.id) == []


def test_counselor_self_action_does_not_self_notify(client, db_session, override_authenticated_user):
    seed_default_stage_transitions(db_session)
    tenant = _tenant(db_session, "notif-self")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        assigned_counselor_id=counselor.id, stage=PipelineStage.VISA_PROCESSING,
    )
    override_authenticated_user(
        make_authenticated_user(Role.COUNSELOR, user_id=counselor.id, tenant_id=tenant.id, branch_id=branch.id)
    )

    resp = client.post(
        f"/applications/{application.id}/mark-rejected",
        json={"reason": "incomplete"}, headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200, resp.text

    # Student notified; the acting counselor is not self-notified.
    assert len(_notifications_for(db_session, student.id)) == 1
    assert _notifications_for(db_session, counselor.id) == []


def _seed_pending_doc(db_session, *, tenant, branch, student):
    application = seed_application(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    document = StudentDocument(
        tenant_id=tenant.id, application_id=application.id, status=StudentDocumentStatus.PENDING,
        original_filename="t.pdf", content_type="application/pdf", size_bytes=10,
        storage_path=f"t/{tenant.id}/{application.id}/t.pdf",
        uploaded_by_user_id=student.id, uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_document_approval_notifies_uploader(client, db_session, override_authenticated_user):
    tenant = _tenant(db_session, "notif-appr")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_doc(db_session, tenant=tenant, branch=branch, student=student)
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    override_authenticated_user(
        make_authenticated_user(Role.DOCUMENT_VERIFIER, user_id=verifier.id, tenant_id=tenant.id, branch_id=None)
    )

    resp = client.post(f"/verifier/documents/{document.id}/approve", json={"comment": "ok"})
    assert resp.status_code == 200, resp.text
    assert len(_notifications_for(db_session, student.id)) == 1


def test_document_rejection_notifies_uploader(client, db_session, override_authenticated_user):
    tenant = _tenant(db_session, "notif-rej")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_doc(db_session, tenant=tenant, branch=branch, student=student)
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    override_authenticated_user(
        make_authenticated_user(Role.DOCUMENT_VERIFIER, user_id=verifier.id, tenant_id=tenant.id, branch_id=None)
    )

    resp = client.post(f"/verifier/documents/{document.id}/reject", json={"comment": "blurry"})
    assert resp.status_code == 200, resp.text
    assert len(_notifications_for(db_session, student.id)) == 1
