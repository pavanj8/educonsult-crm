"""Tests for the E29 approve-document API (Journey J22; issue #181).

Covers ``POST /verifier/documents/{document_id}/approve``:

* authorizes the caller (RBAC: DOCUMENT_VERIFIER with
  ``document:verify``, active, has a tenant scope);
* enforces tenant scoping (cross-tenant -> 404, never 403);
* flips the document from ``pending`` to ``approved`` and persists the
  verifier's id, the current UTC ``verified_at``, and the optional
  ``approval_comment``;
* rejects approving already-approved / already-rejected documents
  with 422 (keeps the audit trail stable: the first verifier to act
  wins, and a verifier cannot silently flip a previously-rejected
  upload -- the student must re-upload per Journey J24 / E31).

These are the developer's tests for the #181 acceptance criteria.
Sibling ticket #183 owns additional black-box tests derived only from
``docs/requirements.md`` / ``docs/journeys.md`` / ``docs/epics.md`` /
the issue body.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

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
    """Override ``get_current_user`` with a DOCUMENT_VERIFIER principal."""
    override_authenticated_user(
        make_authenticated_user(
            Role.DOCUMENT_VERIFIER,
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=None,
        )
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_approve_pending_document_sets_status_and_verifier_metadata(
    client, db_session, override_authenticated_user
):
    """A pending document is flipped to ``approved`` and the verifier's id,
    ``verified_at`` (current UTC), and ``approval_comment`` are persisted.
    """
    tenant = _create_tenant(db_session, name="Approve Tenant", slug="approve-tenant")
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
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    before = datetime.now(timezone.utc)
    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "Looks good"},
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == document.id
    assert body["tenant_id"] == tenant.id
    assert body["application_id"] == document.application_id
    assert body["status"] == StudentDocumentStatus.APPROVED.value
    assert body["verified_by_user_id"] == verifier.id
    assert body["approval_comment"] == "Looks good"
    assert body["rejection_reason"] is None

    verified_at = datetime.fromisoformat(body["verified_at"])
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    assert before <= verified_at <= after

    # Persisted row matches the response.
    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.APPROVED
    assert persisted.verified_by_user_id == verifier.id
    assert persisted.verified_at is not None
    assert persisted.approval_comment == "Looks good"
    assert persisted.rejection_reason is None


def test_approve_without_comment_persists_null_approval_comment(
    client, db_session, override_authenticated_user
):
    """Omitting the body (or sending ``comment=null``) stores NULL in
    ``approval_comment`` -- "no comment" is a valid state.
    """
    tenant = _create_tenant(db_session, name="No Comment", slug="no-comment")
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
        filename="no-comment.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
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
    assert response.json()["status"] == StudentDocumentStatus.APPROVED.value
    assert response.json()["approval_comment"] is None
    assert response.json()["verified_by_user_id"] == verifier.id


def test_approve_with_no_body_persists_null_approval_comment(
    client, db_session, override_authenticated_user
):
    """A request with no JSON body at all is treated the same as
    ``comment=None`` -- FastAPI delivers ``None`` for the optional
    body parameter and the handler normalises to ``comment=None``.
    """
    tenant = _create_tenant(db_session, name="No Body", slug="no-body")
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
        filename="no-body.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(f"/verifier/documents/{document.id}/approve")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == StudentDocumentStatus.APPROVED.value
    assert response.json()["approval_comment"] is None


def test_approve_removes_document_from_pending_queue(
    client, db_session, override_authenticated_user
):
    """An approved document disappears from ``GET /verifier/documents/pending``
    (the queue is filtered to ``status == pending`` per E28). The
    approve endpoint therefore works hand-in-hand with the existing
    verifier queue: approve, then re-render the queue without a
    second round-trip.
    """
    tenant = _create_tenant(db_session, name="Queue Drop", slug="queue-drop")
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
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    approve_response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "Looks good"},
    )
    assert approve_response.status_code == 200, approve_response.text

    queue_response = client.get("/verifier/documents/pending")
    assert queue_response.status_code == 200
    body = queue_response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_approve_response_includes_persisted_metadata(
    client, db_session, override_authenticated_user
):
    """The response carries every persisted column the frontend needs to
    re-render the row (Journey J19 + J21).
    """
    tenant = _create_tenant(db_session, name="Response Shape", slug="response-shape")
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
        filename="meta.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "All clear"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    expected_fields = {
        "id",
        "tenant_id",
        "application_id",
        "checklist_item_template_id",
        "status",
        "original_filename",
        "content_type",
        "size_bytes",
        "uploaded_by_user_id",
        "uploaded_at",
        "verified_by_user_id",
        "verified_at",
        "rejection_reason",
        "approval_comment",
        "created_at",
        "updated_at",
    }
    assert expected_fields.issubset(set(body.keys()))
    assert body["original_filename"] == "meta.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == 2048
    assert body["uploaded_by_user_id"] == student.id


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


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
def test_approve_rejects_non_verifier_roles(
    client, db_session, override_authenticated_user, role
):
    """Only DOCUMENT_VERIFIER has ``document:verify``. Every other role,
    including STUDENT (who can upload), is rejected with 403.
    """
    tenant = _create_tenant(db_session, name=f"Authz {role.value}", slug=f"authz-{role.value}")
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

    if role == Role.SUPER_ADMIN:
        caller = make_db_user(db_session, Role.SUPER_ADMIN)
        caller_tenant = None
    elif role == Role.CONSULTANCY_OWNER:
        caller = make_db_user(
            db_session,
            Role.CONSULTANCY_OWNER,
            tenant_id=tenant.id,
            branch_id=None,
        )
        caller_tenant = tenant.id
    elif role == Role.STUDENT:
        # The "uploader" is the natural attacker: they own the upload but
        # do not have ``document:verify``.
        caller = student
        caller_tenant = tenant.id
    else:
        caller = make_db_user(
            db_session,
            role,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
        caller_tenant = tenant.id

    override_authenticated_user(
        make_authenticated_user(
            role,
            user_id=caller.id,
            tenant_id=caller_tenant,
            branch_id=None if role in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER) else branch.id,
        )
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "trying"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"

    # Document is still pending.
    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.PENDING
    assert persisted.verified_by_user_id is None
    assert persisted.verified_at is None
    assert persisted.approval_comment is None


def test_approve_rejects_verifier_without_tenant_scope(
    client, override_authenticated_user
):
    """A DOCUMENT_VERIFIER with ``tenant_id=None`` is rejected with 403,
    matching the convention used by the pending-queue endpoint.
    """
    verifier = make_authenticated_user(
        Role.DOCUMENT_VERIFIER,
        user_id=1,
        tenant_id=None,
        branch_id=None,
    )
    override_authenticated_user(verifier)

    response = client.post(
        "/verifier/documents/1/approve",
        json={"comment": "trying"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no tenant scope"


def test_approve_requires_authentication(client, db_session):
    """Unauthenticated callers are rejected with 401."""
    tenant = _create_tenant(db_session, name="Anon Approve", slug="anon-approve")
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

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "trying"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.PENDING


def test_approve_rejects_invalid_access_token(client):
    response = client.post(
        "/verifier/documents/1/approve",
        json={"comment": "trying"},
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


# ---------------------------------------------------------------------------
# Tenant scoping
# ---------------------------------------------------------------------------


def test_approve_returns_404_for_other_tenant_document(
    client, db_session, override_authenticated_user
):
    """A verifier in tenant A cannot approve a document owned by tenant B;
    surfaces as 404 (not 403) to prevent tenant / id enumeration.
    """
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="approve-tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="approve-tenant-b")
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
    assert response.json()["detail"] == "Document not found"

    # Foreign document remains pending and untouched.
    db_session.expire_all()
    persisted = db_session.get(StudentDocument, foreign_document.id)
    assert persisted.status == StudentDocumentStatus.PENDING
    assert persisted.verified_by_user_id is None
    assert persisted.approval_comment is None


def test_approve_returns_404_for_nonexistent_document(
    client, db_session, override_authenticated_user
):
    """A non-existent document id surfaces as 404."""
    tenant = _create_tenant(db_session, name="Missing", slug="missing-doc")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post("/verifier/documents/999999/approve", json={"comment": "x"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


# ---------------------------------------------------------------------------
# State-transition guardrails
# ---------------------------------------------------------------------------


def test_approve_rejects_already_approved_document(
    client, db_session, override_authenticated_user
):
    """Re-approving an already-approved document is 422 -- the first verifier
    wins, the audit trail stays stable.
    """
    tenant = _create_tenant(db_session, name="Already Approved", slug="already-approved")
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
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    first = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "first verifier"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "second verifier"},
    )
    assert second.status_code == 422
    assert second.json()["detail"] == (
        f"Only pending documents can be approved "
        f"(current status: '{StudentDocumentStatus.APPROVED.value}')"
    )

    # First verifier's comment and id are still the persisted ones.
    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.APPROVED
    assert persisted.verified_by_user_id == verifier.id
    assert persisted.approval_comment == "first verifier"


def test_approve_rejects_already_rejected_document(
    client, db_session, override_authenticated_user
):
    """A previously-rejected document cannot be flipped to approved by a
    later verifier -- the student must re-upload per Journey J24 (E31).
    """
    tenant = _create_tenant(db_session, name="Rejected Then Approve", slug="rejected-then-approve")
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
    # Manually flip to rejected to simulate a prior rejection
    # (the actual reject endpoint lands in #30 / sibling ticket).
    document.status = StudentDocumentStatus.REJECTED
    document.verified_by_user_id = student.id
    document.verified_at = datetime.now(timezone.utc)
    document.rejection_reason = "Image too blurry"
    db_session.commit()
    db_session.refresh(document)

    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "trying anyway"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        f"Only pending documents can be approved "
        f"(current status: '{StudentDocumentStatus.REJECTED.value}')"
    )

    # Rejected state preserved; approval_comment not written.
    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.REJECTED
    assert persisted.rejection_reason == "Image too blurry"
    assert persisted.approval_comment is None


def test_approve_does_not_touch_rejection_reason(
    client, db_session, override_authenticated_user
):
    """An approve never writes ``rejection_reason``. (Today ``rejection_reason``
    is NULL on a pending row so this is a no-op, but the contract must
    hold even if a future call site pre-fills it.)
    """
    tenant = _create_tenant(db_session, name="No Reject Touch", slug="no-reject-touch")
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
    # Pre-populate rejection_reason directly to prove approve leaves it alone.
    document.rejection_reason = "leftover"
    db_session.commit()
    db_session.refresh(document)

    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "approved anyway"},
    )

    assert response.status_code == 200
    assert response.json()["rejection_reason"] == "leftover"
    assert response.json()["approval_comment"] == "approved anyway"


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def test_approve_rejects_oversized_comment(
    client, db_session, override_authenticated_user
):
    """``comment`` is capped at 2000 chars (mirrors the rejection comment
    constraint). A longer value is rejected with 422.
    """
    tenant = _create_tenant(db_session, name="Long Comment", slug="long-comment")
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
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "x" * 2001},
    )

    assert response.status_code == 422

    db_session.expire_all()
    persisted = db_session.get(StudentDocument, document.id)
    assert persisted.status == StudentDocumentStatus.PENDING


def test_approve_accepts_comment_at_max_length(
    client, db_session, override_authenticated_user
):
    """A comment of exactly 2000 chars is accepted."""
    tenant = _create_tenant(db_session, name="Max Comment", slug="max-comment")
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
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "x" * 2000},
    )

    assert response.status_code == 200
    assert response.json()["approval_comment"] == "x" * 2000


# ---------------------------------------------------------------------------
# Database availability
# ---------------------------------------------------------------------------


class _FakeSessionForApprove503:
    """Minimal fake session whose ``get`` always raises OperationalError."""

    def get(self, *args, **kwargs):
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def add(self, *_args, **_kwargs):
        return None

    def commit(self):
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def rollback(self):
        return None

    def refresh(self, *_args, **_kwargs):
        return None

    def close(self):
        pass


def test_approve_returns_503_when_database_unavailable_loading_document(
    client, db_session, override_authenticated_user
):
    """An ``OperationalError`` while loading the document surfaces as 503."""
    # Import the exact ``get_db`` the router captured at import time so
    # tests/database/ reloading ``app.db.database`` cannot break us.
    from app.routers.verifier import get_db as router_get_db

    tenant = _create_tenant(db_session, name="DB Down Approve", slug="db-down-approve")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    _seed_pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    fake_session = _FakeSessionForApprove503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[router_get_db] = _override_get_db
    try:
        response = client.post(
            "/verifier/documents/1/approve",
            json={"comment": "trying"},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Document service is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(router_get_db, None)


# ---------------------------------------------------------------------------
# Real-JWT smoke
# ---------------------------------------------------------------------------


def test_approve_success_with_real_jwt(client, db_session):
    """The endpoint works end-to-end through a real JWT (no auth override)."""
    tenant = _create_tenant(db_session, name="JWT Smoke Approve", slug="jwt-smoke-approve")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="approve-smoke-student@example.test",
        password="student-password",
    )
    document = _seed_pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        filename="jwt-smoke.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
        email="approve-smoke-verifier@example.test",
        password="verifier-password",
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "approve-smoke-verifier@example.test",
            "password": "verifier-password",
        },
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]

    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "JWT smoke"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == StudentDocumentStatus.APPROVED.value
    assert body["verified_by_user_id"] == verifier.id
    assert body["approval_comment"] == "JWT smoke"


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_approve_sets_verified_at_to_current_utc_within_window(
    client, db_session, override_authenticated_user
):
    """The persisted ``verified_at`` is the current UTC timestamp (the
    window is opened *before* the request and closed *after*, so any
    clock drift from the server is reflected in the assertion).
    """
    tenant = _create_tenant(db_session, name="Audit Window", slug="audit-window")
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
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    before = datetime.now(timezone.utc)
    response = client.post(
        f"/verifier/documents/{document.id}/approve",
        json={"comment": "audit"},
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 200
    verified_at = datetime.fromisoformat(response.json()["verified_at"])
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    assert before <= verified_at <= after


def test_approve_only_affects_target_document(
    client, db_session, override_authenticated_user
):
    """Approving one document does not touch other pending documents in
    the same tenant (defends against a missing WHERE clause or a
    cross-row write bug).
    """
    tenant = _create_tenant(db_session, name="Isolation", slug="isolation")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    target = _seed_pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        filename="target.pdf",
    )
    sibling = _seed_pending_document(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        filename="sibling.pdf",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
    )
    _auth_as_verifier(
        override_authenticated_user,
        user_id=verifier.id,
        tenant_id=tenant.id,
    )

    response = client.post(
        f"/verifier/documents/{target.id}/approve",
        json={"comment": "just target"},
    )
    assert response.status_code == 200

    # The endpoint commits on its own session; expire our session's
    # identity map so we re-read the committed state instead of the
    # stale pre-call snapshot. Scope the query to the tenant (not just
    # the target's application, since sibling lives on a separate
    # application) so we can verify sibling was not touched.
    db_session.expire_all()
    rows = list(
        db_session.scalars(
            select(StudentDocument).where(
                StudentDocument.tenant_id == tenant.id
            )
        ).all()
    )
    by_id = {row.id: row for row in rows}
    assert by_id[target.id].status == StudentDocumentStatus.APPROVED
    assert by_id[target.id].approval_comment == "just target"
    assert by_id[sibling.id].status == StudentDocumentStatus.PENDING
    assert by_id[sibling.id].approval_comment is None
    assert by_id[sibling.id].verified_by_user_id is None
    assert by_id[sibling.id].verified_at is None