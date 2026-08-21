"""Approve flow + permission checks for the E29 approve-document API (issue #183).

Complements the developer's #181 tests (`test_approve_document.py`) with the
acceptance-level coverage E29 calls for:

* permission checks — only DOCUMENT_VERIFIER (the sole holder of
  ``document:verify``) may approve; every other role, including the uploading
  STUDENT, is 403 and the document stays pending;
* the end-to-end approve flow — an approved document leaves the pending queue and
  its audit metadata (verifier id, verified_at, approval_comment) is persisted.
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


def _auth_as_verifier(override_authenticated_user, *, user_id: int, tenant_id: int | None) -> None:
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER, user_id=user_id, tenant_id=tenant_id, branch_id=None,
        )
    )


def _seed_verifier_and_doc(db_session, slug):
    tenant = _create_tenant(db_session, name=slug, slug=slug)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_document(db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id)
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    return tenant, document, verifier


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
def test_approve_denied_for_non_verifier_roles(client, db_session, override_authenticated_user, role):
    """Only DOCUMENT_VERIFIER holds ``document:verify``; every other role is 403,
    and the document is left pending."""
    tenant = _create_tenant(db_session, name=f"appr-authz-{role.value}", slug=f"appr-authz-{role.value}")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_document(db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id)

    caller_tenant = None if role == Role.SUPER_ADMIN else tenant.id
    caller_branch = None if role in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER) else branch.id
    override_authenticated_user(
        make_authenticated_user(role, user_id=student.id, tenant_id=caller_tenant, branch_id=caller_branch)
    )

    response = client.post(f"/verifier/documents/{document.id}/approve", json={"comment": "trying"})

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Insufficient permissions"

    db_session.expire_all()
    assert db_session.get(StudentDocument, document.id).status == StudentDocumentStatus.PENDING


def test_approve_allowed_for_document_verifier(client, db_session, override_authenticated_user):
    """The positive permission check: DOCUMENT_VERIFIER may approve."""
    tenant, document, verifier = _seed_verifier_and_doc(db_session, "appr-ok")
    _auth_as_verifier(override_authenticated_user, user_id=verifier.id, tenant_id=tenant.id)

    response = client.post(f"/verifier/documents/{document.id}/approve", json={"comment": "Looks good"})
    assert response.status_code == 200, response.text


def test_approved_document_leaves_the_pending_queue(client, db_session, override_authenticated_user):
    """End-to-end flow: after an approve, the document no longer appears in the
    verifier's pending queue and its audit metadata is persisted."""
    tenant, document, verifier = _seed_verifier_and_doc(db_session, "appr-flow")
    _auth_as_verifier(override_authenticated_user, user_id=verifier.id, tenant_id=tenant.id)

    before = client.get("/verifier/documents/pending").json()
    assert any(item["id"] == document.id for item in before["items"])

    approve = client.post(f"/verifier/documents/{document.id}/approve", json={"comment": "All clear"})
    assert approve.status_code == 200, approve.text

    after = client.get("/verifier/documents/pending").json()
    assert all(item["id"] != document.id for item in after["items"])
    assert after["total"] == before["total"] - 1

    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.APPROVED
    assert persisted.verified_by_user_id == verifier.id
    assert persisted.verified_at is not None
    assert persisted.approval_comment == "All clear"


def test_approve_comment_is_optional(client, db_session, override_authenticated_user):
    """Approval needs no comment (unlike reject)."""
    tenant, document, verifier = _seed_verifier_and_doc(db_session, "appr-nocomment")
    _auth_as_verifier(override_authenticated_user, user_id=verifier.id, tenant_id=tenant.id)

    response = client.post(f"/verifier/documents/{document.id}/approve", json={})
    assert response.status_code == 200, response.text
    assert response.json()["approval_comment"] is None
