"""Reject flow + permission checks for the E30 reject-document API (issue #186).

Complements the developer's #184 tests (`test_reject_document.py`) with the
acceptance-level coverage E30 calls for:

* permission checks — only DOCUMENT_VERIFIER (the sole holder of
  ``document:verify``) may reject; every other role, including the uploading
  STUDENT, is 403 and the document stays pending;
* the end-to-end reject flow — a rejected document leaves the pending queue and
  its audit metadata (verifier id, verified_at, rejection_reason) is persisted.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_pending_document(db_session, *, tenant_id, branch_id, student_id) -> StudentDocument:
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
        original_filename="transcript.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        storage_path=f"tenants/{tenant_id}/applications/{application.id}/transcript.pdf",
        uploaded_by_user_id=student_id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.mark.parametrize(
    "role",
    [
        Role.SUPER_ADMIN,
        Role.CONSULTANCY_OWNER,
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.STUDENT,
    ],
)
def test_reject_denied_for_non_verifier_roles(
    client, db_session, override_authenticated_user, role
):
    """Only DOCUMENT_VERIFIER holds ``document:verify``; every other role is 403,
    and the document is left pending."""
    tenant = _create_tenant(db_session, name=f"Authz {role.value}", slug=f"reject-authz-{role.value}")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_document(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
    )

    caller_tenant = None if role == Role.SUPER_ADMIN else tenant.id
    caller_branch = None if role in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER) else branch.id
    override_authenticated_user(
        make_authenticated_user(role, user_id=student.id, tenant_id=caller_tenant, branch_id=caller_branch)
    )

    response = client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "trying to reject"}
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Insufficient permissions"

    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.PENDING


def test_reject_allowed_for_document_verifier(client, db_session, override_authenticated_user):
    """The positive permission check: DOCUMENT_VERIFIER may reject."""
    tenant = _create_tenant(db_session, name="Verifier OK", slug="reject-verifier-ok")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_document(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
    )
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    override_authenticated_user(
        make_authenticated_user(Role.DOCUMENT_VERIFIER, user_id=verifier.id, tenant_id=tenant.id, branch_id=None)
    )

    response = client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "Illegible scan"}
    )
    assert response.status_code == 200, response.text


def test_rejected_document_leaves_the_pending_queue(
    client, db_session, override_authenticated_user
):
    """End-to-end flow: after a reject, the document no longer appears in the
    verifier's pending queue and its audit metadata is persisted."""
    tenant = _create_tenant(db_session, name="Flow", slug="reject-flow")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_document(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
    )
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    override_authenticated_user(
        make_authenticated_user(Role.DOCUMENT_VERIFIER, user_id=verifier.id, tenant_id=tenant.id, branch_id=None)
    )

    # Present in the queue before rejection.
    before = client.get("/verifier/documents/pending").json()
    assert any(item["id"] == document.id for item in before["items"])

    reject = client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "Wrong document uploaded"}
    )
    assert reject.status_code == 200, reject.text

    # Gone from the queue afterward.
    after = client.get("/verifier/documents/pending").json()
    assert all(item["id"] != document.id for item in after["items"])
    assert after["total"] == before["total"] - 1

    # Audit metadata persisted.
    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.REJECTED
    assert persisted.verified_by_user_id == verifier.id
    assert persisted.verified_at is not None
    assert persisted.rejection_reason == "Wrong document uploaded"
