"""Tests for the E30 reject-document API (Journey J23; issue #184).

Covers ``POST /verifier/documents/{document_id}/reject``:

* authorizes the caller (RBAC: DOCUMENT_VERIFIER with ``document:verify``,
  active, has a tenant scope);
* enforces tenant scoping (cross-tenant -> 404, never 403);
* REQUIRES a rejection comment (empty / whitespace-only / missing -> 422,
  over 2000 chars -> 422); trims the stored value;
* flips the document from ``pending`` to ``rejected`` and persists the
  verifier's id, the current UTC ``verified_at``, and ``rejection_reason``;
* rejects rejecting a non-pending document with 422.
"""

from __future__ import annotations

from datetime import datetime, timezone

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


def _seed_pending_document(
    db_session, *, tenant_id: int, branch_id: int, student_id: int,
    filename: str = "transcript.pdf",
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
    document = StudentDocument(
        tenant_id=tenant_id,
        application_id=application.id,
        status=StudentDocumentStatus.PENDING,
        original_filename=filename,
        content_type="application/pdf",
        size_bytes=2048,
        storage_path=f"tenants/{tenant_id}/applications/{application.id}/{filename}",
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


def _seed_verifier_and_doc(db_session):
    tenant = _create_tenant(db_session, name="Reject Tenant", slug="reject-tenant")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    document = _seed_pending_document(
        db_session, tenant_id=tenant.id, branch_id=branch.id, student_id=student.id,
    )
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    return tenant, document, verifier


def test_reject_pending_document_sets_status_reason_and_metadata(
    client, db_session, override_authenticated_user
):
    tenant, document, verifier = _seed_verifier_and_doc(db_session)
    _auth_as_verifier(override_authenticated_user, user_id=verifier.id, tenant_id=tenant.id)

    response = client.post(
        f"/verifier/documents/{document.id}/reject",
        json={"comment": "  Passport photo is not legible  "},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == document.id
    assert body["status"] == StudentDocumentStatus.REJECTED.value
    assert body["verified_by_user_id"] == verifier.id
    assert body["rejection_reason"] == "Passport photo is not legible"  # trimmed
    assert body["approval_comment"] is None
    assert body["verified_at"] is not None


def test_reject_requires_a_comment(client, db_session, override_authenticated_user):
    tenant, document, verifier = _seed_verifier_and_doc(db_session)
    _auth_as_verifier(override_authenticated_user, user_id=verifier.id, tenant_id=tenant.id)

    assert client.post(f"/verifier/documents/{document.id}/reject", json={}).status_code == 422
    assert client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "   "}
    ).status_code == 422
    assert client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "x" * 2001}
    ).status_code == 422


def test_reject_non_pending_document_is_422(client, db_session, override_authenticated_user):
    tenant, document, verifier = _seed_verifier_and_doc(db_session)
    document.status = StudentDocumentStatus.APPROVED
    db_session.commit()
    _auth_as_verifier(override_authenticated_user, user_id=verifier.id, tenant_id=tenant.id)

    response = client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "too late"}
    )
    assert response.status_code == 422, response.text


def test_reject_cross_tenant_document_is_404(client, db_session, override_authenticated_user):
    tenant, document, _ = _seed_verifier_and_doc(db_session)
    other = _create_tenant(db_session, name="Other Tenant", slug="other-tenant")
    other_verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=other.id)
    _auth_as_verifier(override_authenticated_user, user_id=other_verifier.id, tenant_id=other.id)

    response = client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "not mine"}
    )
    assert response.status_code == 404, response.text


def test_reject_without_tenant_scope_is_403(client, db_session, override_authenticated_user):
    tenant, document, verifier = _seed_verifier_and_doc(db_session)
    _auth_as_verifier(override_authenticated_user, user_id=verifier.id, tenant_id=None)

    response = client.post(
        f"/verifier/documents/{document.id}/reject", json={"comment": "no scope"}
    )
    assert response.status_code == 403, response.text
