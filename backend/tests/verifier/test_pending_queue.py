"""Tests for the E28 document verifier pending queue (Journey J21)."""

from datetime import datetime, timezone

from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


def _seed_document(db_session, *, tenant_id, branch_id, student_id, status_value, filename):
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
        status=status_value,
        original_filename=filename,
        content_type="application/pdf",
        size_bytes=10,
        storage_path=f"tenants/{tenant_id}/applications/{application.id}/{filename}",
        uploaded_by_user_id=student_id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return application, document


def test_pending_queue_returns_only_pending_documents_in_tenant(
    client, db_session, override_authenticated_user
):
    tenant = Tenant(name="Queue Tenant", slug="queue-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    _, pending = _seed_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        status_value=StudentDocumentStatus.PENDING,
        filename="pending.pdf",
    )
    _seed_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        status_value=StudentDocumentStatus.APPROVED,
        filename="approved.pdf",
    )
    other = Tenant(name="Other Tenant", slug="other-tenant")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    other_branch = seed_branch(db_session, tenant_id=other.id)
    other_student = make_db_user(db_session, Role.STUDENT, tenant_id=other.id, branch_id=other_branch.id)
    _seed_document(
        db_session,
        tenant_id=other.id,
        branch_id=other_branch.id,
        student_id=other_student.id,
        status_value=StudentDocumentStatus.PENDING,
        filename="foreign.pdf",
    )
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=verifier.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    response = client.get("/verifier/documents/pending")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == pending.id
    assert body["items"][0]["application_stage"] == PipelineStage.DOCUMENT_VERIFICATION.value
    assert body["items"][0]["student_id"] == student.id
    assert "approved" not in response.text
    assert "foreign" not in response.text


def test_pending_queue_is_stable_and_paginatable(client, db_session, override_authenticated_user):
    tenant = Tenant(name="Paged Tenant", slug="paged-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id)
    first_application, first = _seed_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        status_value=StudentDocumentStatus.PENDING,
        filename="first.pdf",
    )
    second_application, second = _seed_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        status_value=StudentDocumentStatus.PENDING,
        filename="second.pdf",
    )
    verifier = make_db_user(db_session, Role.DOCUMENT_VERIFIER, tenant_id=tenant.id)
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=verifier.id,
            tenant_id=tenant.id,
            branch_id=None,
        )
    )

    response = client.get("/verifier/documents/pending?limit=1&offset=0")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [first.id]
    assert body["items"][0]["application_id"] == first_application.id
    second_response = client.get("/verifier/documents/pending?limit=1&offset=1")
    assert second_response.status_code == 200
    assert [item["id"] for item in second_response.json()["items"]] == [second.id]
    assert second_response.json()["items"][0]["application_id"] == second_application.id


def test_pending_queue_requires_document_read_permission(client, db_session, override_authenticated_user):
    student = make_db_user(db_session, Role.STUDENT, tenant_id=1)
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=student.tenant_id,
            branch_id=None,
        )
    )

    response = client.get("/verifier/documents/pending")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_pending_queue_rejects_verifier_without_tenant_scope(client, override_authenticated_user):
    verifier = make_authenticated_user(
        Role.DOCUMENT_VERIFIER,
        user_id=1,
        tenant_id=None,
        branch_id=None,
    )
    override_authenticated_user(verifier)

    response = client.get("/verifier/documents/pending")

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no tenant scope"


def test_pending_queue_rejects_invalid_pagination(client, override_authenticated_user):
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=1,
            tenant_id=1,
            branch_id=None,
        )
    )

    assert client.get("/verifier/documents/pending?limit=0").status_code == 422
    assert client.get("/verifier/documents/pending?limit=101").status_code == 422
    assert client.get("/verifier/documents/pending?offset=-1").status_code == 422
