"""Tests for the E31 re-upload / versioning support on the student-document
upload API (Journey J24; issue #187).

Covers the new ``supersedes_document_id`` form field on
``POST /applications/{application_id}/documents``. A re-upload against a
previously rejected document must:

* succeed with 201 and persist a new :class:`StudentDocument` row whose
  ``supersedes_id`` points at the rejected row (versioning audit
  trail — Requirements §8);
* the rejected row itself must remain untouched (its
  ``status='rejected'`` / ``rejection_reason`` / ``verified_by`` /
  ``verified_at`` must stay intact for the audit log);
* use a fresh storage key — the storage backend already guarantees
  this via UUID-prefixed keys (see ``app.storage.service``), but the
  test pins the contract end-to-end so a future refactor of
  ``build_storage_key`` cannot accidentally shadow the rejected
  document's bytes;
* reject non-rejected predecessors (approved / pending) with 422 so
  a student cannot silently shadow an approved file or create two
  competing pending rows for the same checklist slot;
* reject cross-tenant, cross-application, and unknown
  ``supersedes_document_id`` ids with 422 (bad request, not 404 — the
  same rationale as ``checklist_item_template_id``).

The existing :class:`InMemoryDocumentStorage` is injected via
:func:`app.storage.set_document_storage` so S3/MinIO is never reached
during the suite; the ``in_memory_storage`` fixture restores the
process-wide singleton on teardown.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pytest
from sqlalchemy import select

from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.storage import InMemoryDocumentStorage, set_document_storage
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.checklist.helpers import seed_checklist_template, seed_student_document
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def in_memory_storage():
    """Swap in the InMemoryDocumentStorage test double for the duration of the test.

    Yields the double so tests can assert on ``.stored``. After the test,
    the process-wide storage service is restored to its default
    (S3DocumentStorageService) so subsequent tests are isolated.
    """
    storage = InMemoryDocumentStorage()
    set_document_storage(storage)
    try:
        yield storage
    finally:
        set_document_storage(None)


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_owned_application(
    db_session,
    *,
    tenant_id: int,
    student_id: int,
    branch_id: int | None = 1,
    program_id: int = 1,
    university_id: int = 1,
) -> "object":
    return seed_application(
        db_session,
        tenant_id=tenant_id,
        branch_id=branch_id,
        student_id=student_id,
        university_id=university_id,
        program_id=program_id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )


def _auth_as(
    override_authenticated_user,
    role: Role,
    *,
    user_id: int,
    tenant_id: int | None,
    branch_id: int | None,
) -> None:
    override_authenticated_user(
        make_authenticated_user(
            role,
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
    )


def _seed_rejected_document(
    db_session,
    *,
    tenant_id: int,
    application_id: int,
    uploaded_by_user_id: int,
    checklist_item_template_id: int | None,
    original_filename: str = "passport.pdf",
    rejection_reason: str = "Image too blurry to read",
    verified_by_user_id: int | None = None,
) -> StudentDocument:
    """Persist a rejected StudentDocument row (the re-upload's predecessor)."""
    now = datetime.now(timezone.utc)
    if verified_by_user_id is None:
        # Lazily create a verifier user in the same tenant/branch.
        verifier = make_db_user(
            db_session,
            Role.DOCUMENT_VERIFIER,
            tenant_id=tenant_id,
            branch_id=None,
            email=f"verifier-{now.timestamp()}@example.test",
        )
        verified_by_user_id = verifier.id
    document = seed_student_document(
        db_session,
        tenant_id=tenant_id,
        application_id=application_id,
        checklist_item_template_id=checklist_item_template_id,
        status=StudentDocumentStatus.REJECTED,
        original_filename=original_filename,
        uploaded_by_user_id=uploaded_by_user_id,
        verified_by_user_id=verified_by_user_id,
        verified_at=now,
        rejection_reason=rejection_reason,
    )
    return document


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_reupload_against_rejected_document_persists_supersedes_link(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A re-upload against a rejected document persists a new pending row
    whose ``supersedes_id`` points at the rejected predecessor."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-happy@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
    )
    rejected = _seed_rejected_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        uploaded_by_user_id=student.id,
        checklist_item_template_id=None,
        original_filename="passport-v1.pdf",
        rejection_reason="Image too blurry",
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    payload = b"%PDF-1.4\n% clear v2 of the passport scan"
    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("passport-v2.pdf", BytesIO(payload), "application/pdf")},
        data={"supersedes_document_id": str(rejected.id)},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["supersedes_id"] == rejected.id
    assert body["status"] == StudentDocumentStatus.PENDING.value
    assert body["original_filename"] == "passport-v2.pdf"
    assert body["application_id"] == application.id
    assert body["checklist_item_template_id"] is None
    assert body["rejection_reason"] is None
    assert body["verified_at"] is None

    # The new row must NOT reuse the rejected row's storage key (rejected
    # bytes must stay on the storage backend for any future download /
    # audit-trail request, and the new row's bytes live under a fresh key).
    assert body["storage_path"] != rejected.storage_path


def test_reupload_leaves_rejected_row_unchanged(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """The rejected predecessor is never mutated by the re-upload path —
    its status / rejection_reason / verifier / verified_at stay intact."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-audit@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    rejected = _seed_rejected_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        uploaded_by_user_id=student.id,
        checklist_item_template_id=None,
        rejection_reason="Original rejection reason",
    )
    snapshot_status = rejected.status
    snapshot_reason = rejected.rejection_reason
    snapshot_verified_by = rejected.verified_by_user_id
    snapshot_verified_at = rejected.verified_at
    snapshot_storage_path = rejected.storage_path

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2 bytes"), "application/pdf")},
        data={"supersedes_document_id": str(rejected.id)},
    )

    assert response.status_code == 201, response.text

    # Re-fetch from the DB so we observe the post-commit state, not the
    # stale in-memory snapshot.
    refreshed = db_session.get(StudentDocument, rejected.id)
    assert refreshed.status == snapshot_status
    assert refreshed.rejection_reason == snapshot_reason
    assert refreshed.verified_by_user_id == snapshot_verified_by
    assert refreshed.verified_at == snapshot_verified_at
    assert refreshed.storage_path == snapshot_storage_path


def test_reupload_generates_fresh_storage_key(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """The re-upload's bytes are written to the storage backend under a
    distinct key, not over the rejected row's bytes.

    The rejected row itself was inserted directly via the model helper
    (bypassing the upload endpoint), so it does not appear in the
    in-memory storage record — only the re-upload does. The contract we
    pin here is that the new key is a *fresh* UUID-prefixed key
    (different from the rejected row's manually-set placeholder key),
    so a future refactor of ``build_storage_key`` cannot accidentally
    shadow the rejected document's bytes on the storage backend.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-storage@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    rejected = _seed_rejected_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        uploaded_by_user_id=student.id,
        checklist_item_template_id=None,
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"new"), "application/pdf")},
        data={"supersedes_document_id": str(rejected.id)},
    )

    assert response.status_code == 201, response.text
    new_path = response.json()["storage_path"]

    # The InMemoryDocumentStorage double records the re-upload under a
    # brand-new key; it must not collide with the rejected row's key.
    assert len(in_memory_storage.stored) == 1
    assert in_memory_storage.stored[0].key == new_path
    assert new_path != rejected.storage_path
    # The new key follows the tenant/application/UUID-prefix shape that
    # the storage layer guarantees for every upload (rejected or not).
    assert new_path.startswith(
        f"tenants/{tenant.id}/applications/{application.id}/"
    )


def test_initial_upload_without_supersedes_persists_null(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An upload that omits ``supersedes_document_id`` persists
    ``supersedes_id`` as NULL (initial-upload path unchanged)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="initial-upload@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("first.pdf", BytesIO(b"first"), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["supersedes_id"] is None


# ---------------------------------------------------------------------------
# Validation: superseded document state
# ---------------------------------------------------------------------------


def test_reupload_against_approved_document_is_rejected(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A re-upload targeting an *approved* document is rejected (422).

    Rationale: re-uploading against an approved file would silently
    shadow a verified upload, breaking the audit trail (Requirements §8)
    and confusing the verifier who already approved the original.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-approved@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="verifier-approved@example.test",
    )
    approved = seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=None,
        status=StudentDocumentStatus.APPROVED,
        uploaded_by_user_id=student.id,
        verified_by_user_id=verifier.id,
        verified_at=datetime.now(timezone.utc),
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2"), "application/pdf")},
        data={"supersedes_document_id": str(approved.id)},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "rejected document" in detail
    assert "approved" in detail


def test_reupload_against_pending_document_is_rejected(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A re-upload targeting a *pending* document is rejected (422).

    Rationale: re-uploading against a still-pending row would create two
    competing pending uploads for the same checklist slot. The student
    should wait for the verifier to act on the first upload.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-pending@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    pending = seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=None,
        status=StudentDocumentStatus.PENDING,
        uploaded_by_user_id=student.id,
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2"), "application/pdf")},
        data={"supersedes_document_id": str(pending.id)},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "rejected document" in detail
    assert "pending" in detail


def test_reupload_with_unknown_supersedes_id_is_rejected(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A ``supersedes_document_id`` that does not exist is a 422 (bad
    request, not 404 — the same rationale as ``checklist_item_template_id``).
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-unknown@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2"), "application/pdf")},
        data={"supersedes_document_id": "999999"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid supersedes_document_id"
    # Storage must not be touched on a validation failure.
    assert in_memory_storage.stored == []


def test_reupload_with_cross_tenant_supersedes_id_is_rejected(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A ``supersedes_document_id`` from a different tenant is 422 (not 404 —
    the same rationale as ``checklist_item_template_id``).
    """
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    seed_branch(db_session, tenant_id=tenant_b.id)

    # A rejected document in tenant B.
    foreign_student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_b.id,
        branch_id=None,
        email="tenant-b-student@example.test",
    )
    foreign_application = _seed_owned_application(
        db_session,
        tenant_id=tenant_b.id,
        student_id=foreign_student.id,
        branch_id=None,
    )
    foreign_rejected = _seed_rejected_document(
        db_session,
        tenant_id=tenant_b.id,
        application_id=foreign_application.id,
        uploaded_by_user_id=foreign_student.id,
        checklist_item_template_id=None,
    )

    # The student in tenant A trying to reference tenant B's document.
    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        email="tenant-a-attacker@example.test",
    )
    application_a = _seed_owned_application(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        student_id=student_a.id,
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student_a.id,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
    )

    response = client.post(
        f"/applications/{application_a.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2"), "application/pdf")},
        data={"supersedes_document_id": str(foreign_rejected.id)},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid supersedes_document_id"
    assert in_memory_storage.stored == []


def test_reupload_with_cross_application_supersedes_id_is_rejected(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A ``supersedes_document_id`` from a *different application* in the
    same tenant is 422 — re-uploads replace their own predecessor only.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="cross-app-student-a@example.test",
    )
    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="cross-app-student-b@example.test",
    )
    application_a = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_a.id,
    )
    application_b = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student_b.id,
    )
    foreign_rejected = _seed_rejected_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application_b.id,
        uploaded_by_user_id=student_b.id,
        checklist_item_template_id=None,
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student_a.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application_a.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2"), "application/pdf")},
        data={"supersedes_document_id": str(foreign_rejected.id)},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "this application" in detail
    assert in_memory_storage.stored == []


# ---------------------------------------------------------------------------
# Validation: re-upload must still pass standard upload checks
# ---------------------------------------------------------------------------


def test_reupload_still_requires_ownership(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """Re-uploading against another student's rejected document is blocked
    by the standard owner check before ``_resolve_superseded_document``
    runs.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    other_student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="other-reupload-student@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=other_student.id,
    )
    rejected = _seed_rejected_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        uploaded_by_user_id=other_student.id,
        checklist_item_template_id=None,
    )

    attacker = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-attacker@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=attacker.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2"), "application/pdf")},
        data={"supersedes_document_id": str(rejected.id)},
    )

    # The owner check fires before the supersedes-resolution helper.
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Cannot upload documents to another student's application"
    )
    assert in_memory_storage.stored == []


def test_reupload_does_not_persist_row_when_storage_fails(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """If storage fails on the re-upload path, no StudentDocument row is
    persisted — same atomicity guarantee as the initial-upload path."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="reupload-storage-failure@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    rejected = _seed_rejected_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        uploaded_by_user_id=student.id,
        checklist_item_template_id=None,
    )

    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    in_memory_storage.fail_next_store()

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("v2.pdf", BytesIO(b"v2"), "application/pdf")},
        data={"supersedes_document_id": str(rejected.id)},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Document storage is temporarily unavailable"

    # Only the original rejected row exists; the failed re-upload left
    # no partial write behind.
    rows = list(
        db_session.scalars(
            select(StudentDocument).where(StudentDocument.application_id == application.id)
        ).all()
    )
    assert [row.id for row in rows] == [rejected.id]