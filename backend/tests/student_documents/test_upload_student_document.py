"""Tests for the E27 student-document upload API (Journey J20; issue #175).

Covers the ``POST /applications/{application_id}/documents`` endpoint that:

* authorizes the caller (RBAC: STUDENT with ``document:upload``,
  active student, owns the application, cross-tenant → 404);
* reads the multipart upload into memory with a hard size cap;
* calls :class:`DocumentStorageService.store` (S3-compatible storage);
* persists a :class:`StudentDocument` row in ``pending`` state.

The router does **not** enforce the 10 MB / PDF/JPG/PNG/DOCX
constraints (those land in sibling ticket #176); this test file
covers only what the #175 acceptance criteria describe:
**file upload API to S3-compatible storage**.

S3 / MinIO is never reached in tests — the test-suite
:class:`InMemoryDocumentStorage` is injected via
:func:`app.storage.set_document_storage` and reset between tests
via the ``in_memory_storage`` fixture (which monkey-patches the
process-wide singleton at setup and restores the default afterwards).
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models.student_document import StudentDocument, StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.storage import InMemoryDocumentStorage, set_document_storage
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.checklist.helpers import seed_checklist_template
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
    """Create an application owned by ``student_id`` in ``tenant_id``.

    Thin convenience wrapper around ``seed_application`` that mirrors the
    helpers used by the checklist endpoint tests.
    """
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


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_upload_persists_document_and_returns_201(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A successful upload returns 201, persists a pending StudentDocument row,
    and forwards the bytes to the storage service."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="student-upload@example.test",
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

    payload = b"%PDF-1.4\n% fake pdf bytes for tests"
    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("transcripts.pdf", BytesIO(payload), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["application_id"] == application.id
    assert body["tenant_id"] == tenant.id
    assert body["status"] == StudentDocumentStatus.PENDING.value
    assert body["original_filename"] == "transcripts.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(payload)
    assert body["uploaded_by_user_id"] == student.id
    assert body["verified_at"] is None
    assert body["rejection_reason"] is None

    # Storage service saw exactly one upload with the same payload and content type.
    assert len(in_memory_storage.stored) == 1
    stored = in_memory_storage.stored[0]
    assert stored.tenant_id == tenant.id
    assert stored.application_id == application.id
    assert stored.original_filename == "transcripts.pdf"
    assert stored.content == payload
    assert stored.content_type == "application/pdf"

    # Persisted StudentDocument row's storage_path matches the service's returned key.
    assert body["storage_path"] == stored.key
    assert stored.key.startswith(
        f"tenants/{tenant.id}/applications/{application.id}/"
    )
    assert stored.key.endswith("-transcripts.pdf")

    # And there is exactly one StudentDocument row with the right shape.
    rows = list(
        db_session.scalars(
            select(StudentDocument).where(StudentDocument.application_id == application.id)
        ).all()
    )
    assert len(rows) == 1
    persisted = rows[0]
    assert persisted.status == StudentDocumentStatus.PENDING
    assert persisted.storage_path == stored.key
    assert persisted.uploaded_by_user_id == student.id
    assert persisted.verified_by_user_id is None
    assert persisted.rejection_reason is None


def test_upload_without_checklist_template_persists_null_fk(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An ad-hoc upload (no ``checklist_item_template_id`` form field) is
    persisted with ``checklist_item_template_id`` set to NULL.
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="ad-hoc@example.test",
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
        files={"file": ("extra.pdf", BytesIO(b"extra"), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["checklist_item_template_id"] is None


def test_upload_with_checklist_template_persists_fk(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A targeted upload sets ``checklist_item_template_id`` on the row."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="targeted@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
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
        files={"file": ("passport.pdf", BytesIO(b"pdf"), "application/pdf")},
        data={"checklist_item_template_id": str(template.id)},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["checklist_item_template_id"] == template.id


def test_upload_generates_unique_storage_keys_per_upload(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """Two uploads of the same filename generate distinct storage keys
    (no silent shadowing on the storage backend).
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="twice@example.test",
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

    first = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("same-name.pdf", BytesIO(b"first"), "application/pdf")},
    )
    second = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("same-name.pdf", BytesIO(b"second"), "application/pdf")},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["storage_path"] != second.json()["storage_path"]
    assert len(in_memory_storage.stored) == 2
    assert in_memory_storage.stored[0].key != in_memory_storage.stored[1].key


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def test_upload_requires_authentication(client, db_session, in_memory_storage):
    """Unauthenticated callers are rejected with 401."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="anon-upload@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_upload_rejects_invalid_access_token(client, in_memory_storage):
    response = client.post(
        "/applications/1/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


@pytest.mark.parametrize(
    "role",
    [
        Role.SUPER_ADMIN,
        Role.CONSULTANCY_OWNER,
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
    ],
)
def test_upload_rejects_non_student_roles(
    client, db_session, override_authenticated_user, in_memory_storage, role
):
    """Only STUDENT is granted ``document:upload``; every other role is 403."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email=f"target-{role.value}@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )
    staff = make_db_user(
        db_session,
        role,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email=f"{role.value}@example.test",
    )
    _auth_as(
        override_authenticated_user,
        role,
        user_id=staff.id,
        tenant_id=tenant.id if role != Role.SUPER_ADMIN else None,
        branch_id=None if role == Role.CONSULTANCY_OWNER else branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_upload_student_cannot_upload_to_other_students_application(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A STUDENT can only upload to their own application."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    other_student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="other-student@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=other_student.id,
    )

    attacker = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="attacker-student@example.test",
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
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot upload documents to another student's application"


def test_upload_returns_404_for_other_tenant_application(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """Cross-tenant application access surfaces as 404, never 403 (no enumeration)."""
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    branch_b = seed_branch(db_session, tenant_id=tenant_b.id)

    student_b = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        email="tenant-b-student@example.test",
    )
    application_b = _seed_owned_application(
        db_session,
        tenant_id=tenant_b.id,
        branch_id=branch_b.id,
        student_id=student_b.id,
    )

    student_a = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        email="tenant-a-prober@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student_a.id,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
    )

    response = client.post(
        f"/applications/{application_b.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_upload_returns_404_for_nonexistent_application(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A non-existent application id surfaces as 404."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="no-app@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        "/applications/999999/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


# ---------------------------------------------------------------------------
# Student account state
# ---------------------------------------------------------------------------


def test_upload_rejects_deactivated_student(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A deactivated student cannot upload (403, no DB write)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="deactivated-upload@example.test",
        is_active=False,
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
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is deactivated"
    # Storage was not touched.
    assert in_memory_storage.stored == []


def test_upload_rejects_student_missing_tenant_scope(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A student with ``tenant_id=None`` cannot upload (403)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=None,
        branch_id=branch.id,
        email="missing-tenant-upload@example.test",
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
        tenant_id=None,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Student account is missing tenant scope"
    assert in_memory_storage.stored == []


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def test_upload_rejects_missing_file_form_field(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A request without the ``file`` form field is a 400."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="no-file@example.test",
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

    # Send a multipart request with no ``file`` part.
    response = client.post(
        f"/applications/{application.id}/documents",
        data={"checklist_item_template_id": "1"},
    )

    # FastAPI's multipart parser surfaces a missing required file as 422.
    assert response.status_code in (400, 422)
    assert in_memory_storage.stored == []


def test_upload_rejects_empty_file(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A zero-byte upload is rejected with 400 and never reaches storage."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="empty-file@example.test",
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
        files={"file": ("empty.pdf", BytesIO(b""), "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is empty"
    assert in_memory_storage.stored == []


def test_upload_rejects_invalid_checklist_template(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A ``checklist_item_template_id`` that does not exist is a 422."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="bad-template@example.test",
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
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
        data={"checklist_item_template_id": "999999"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid checklist_item_template_id"
    assert in_memory_storage.stored == []


def test_upload_rejects_checklist_template_from_other_tenant(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A ``checklist_item_template_id`` from a different tenant is 422 (not 404 —
    it's a bad request, not a tenant-existence leak).
    """
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    branch_a = seed_branch(db_session, tenant_id=tenant_a.id)
    seed_branch(db_session, tenant_id=tenant_b.id)

    foreign_template = seed_checklist_template(
        db_session,
        tenant_id=tenant_b.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
        program_id=None,
        name="Tenant B template",
    )

    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        email="cross-tenant-template@example.test",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
        student_id=student.id,
    )
    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant_a.id,
        branch_id=branch_a.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
        data={"checklist_item_template_id": str(foreign_template.id)},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid checklist_item_template_id"
    assert in_memory_storage.stored == []


# ---------------------------------------------------------------------------
# Storage backend failures
# ---------------------------------------------------------------------------


def test_upload_returns_503_when_storage_backend_fails(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A :class:`DocumentStorageError` from the storage backend surfaces as 503."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="storage-failure@example.test",
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
    in_memory_storage.fail_next_store()

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Document storage is temporarily unavailable"


def test_upload_does_not_persist_row_when_storage_fails(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """If the storage backend fails, no StudentDocument row is persisted."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="no-row@example.test",
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
    in_memory_storage.fail_next_store()

    client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    rows = list(
        db_session.scalars(
            select(StudentDocument).where(StudentDocument.application_id == application.id)
        ).all()
    )
    assert rows == []


# ---------------------------------------------------------------------------
# Storage key construction
# ---------------------------------------------------------------------------


def test_upload_storage_key_is_tenant_and_application_scoped(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """The generated storage key embeds the tenant and application ids so
    storage objects can be cleaned up by tenant (and so cross-tenant
    objects can never collide).
    """
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="key-shape@example.test",
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
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 201
    key = response.json()["storage_path"]
    assert key.startswith(f"tenants/{tenant.id}/applications/{application.id}/")
    # Filename appears at the end of the key (sanitized).
    assert key.endswith("-x.pdf")


def test_upload_sanitizes_dangerous_filename(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """Path-traversal-ish characters in the original filename are sanitized."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="evil-name@example.test",
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
        files={"file": ("../../etc/passwd.pdf", BytesIO(b"x"), "application/pdf")},
    )

    assert response.status_code == 201
    key = response.json()["storage_path"]
    # No path traversal: the key stays inside the tenant/application prefix.
    assert key.startswith(f"tenants/{tenant.id}/applications/{application.id}/")
    assert ".." not in key
    assert "/etc/" not in key


# ---------------------------------------------------------------------------
# Database availability
# ---------------------------------------------------------------------------


class _FakeSessionForUploadStorage503:
    """Minimal fake session whose ``get`` always raises OperationalError."""

    def get(self, *args, **kwargs):
        raise OperationalError("statement", {}, ConnectionError("lost connection"))

    def scalars(self, *args, **kwargs):
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


def test_upload_returns_503_when_database_unavailable_loading_student(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An OperationalError loading the student surfaces as 503."""
    # Import the exact ``get_db`` function the router captures at import
    # time (``Depends(get_db)`` freezes the reference). Importing from
    # ``app.routers.student_documents`` (rather than ``app.db.database``
    # directly) keeps us in sync with the router, even after sibling
    # tests in ``tests/database/`` reload ``app.db.database`` via
    # ``importlib.reload``.
    from app.routers.student_documents import get_db as router_get_db

    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="db-down-upload@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.STUDENT,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    fake_session = _FakeSessionForUploadStorage503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[router_get_db] = _override_get_db
    try:
        response = client.post(
            "/applications/1/documents",
            files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Document service is unavailable"
    finally:
        client.app.dependency_overrides.pop(router_get_db, None)


# ---------------------------------------------------------------------------
# Real-JWT smoke
# ---------------------------------------------------------------------------


def test_upload_success_with_real_jwt(client, db_session, in_memory_storage):
    """The endpoint works end-to-end through a real JWT (no auth-override)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="jwt-smoke-upload@example.test",
        password="student-password",
    )
    application = _seed_owned_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
    )

    login_response = client.post(
        "/auth/login",
        json={"email": "jwt-smoke-upload@example.test", "password": "student-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("passport.pdf", BytesIO(b"pdf-bytes"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == StudentDocumentStatus.PENDING.value
    assert body["original_filename"] == "passport.pdf"
    assert len(in_memory_storage.stored) == 1


# ---------------------------------------------------------------------------
# Audit / metadata fields
# ---------------------------------------------------------------------------


def test_upload_records_uploaded_at_as_current_utc(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """The persisted row's ``uploaded_at`` is the current UTC timestamp."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="timestamp@example.test",
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

    before = datetime.now(timezone.utc)
    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("x.pdf", BytesIO(b"x"), "application/pdf")},
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 201
    body = response.json()
    uploaded_at = datetime.fromisoformat(body["uploaded_at"])
    # SQLite drops tzinfo on round-trip; coerce to UTC for comparison.
    if uploaded_at.tzinfo is None:
        uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
    assert before <= uploaded_at <= after
