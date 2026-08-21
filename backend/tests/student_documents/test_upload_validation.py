"""Tests for the E27 file-size + file-type validation layer (issue #176).

The validation primitives live in :mod:`app.storage.validation` and
are wired into ``POST /applications/{application_id}/documents`` by
the upload router (:mod:`app.routers.student_documents`). This test
file covers both surfaces**, so the contract is enforced end-to-end:

* **Helper-level** — :func:`validate_file_size` and
  :func:`validate_file_type` are exercised directly so a regression
  in the validation module cannot hide behind a passing router
  integration test.
* **Router-level** — the public endpoint returns 413 (Request Entity
  Too Large) for oversized uploads and 415 (Unsupported Media Type)
  for extensions / content-types outside the allow-list, with the
  message constant from the validation module (so the frontend can
  surface them verbatim).

Traceability
------------
* Requirements §5 (Documents ... default limits 10MB, PDF/JPG/PNG/DOCX).
* Journey J20 (Student uploads a document against a checklist item).
* Epic E27 (Student Document Upload); sibling tickets own the model
  (#174), the upload endpoint (#175), and the upload UI (#177). The
  end-to-end "upload validation and checklist completeness calculation"
  test suite lands in #178.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from app.storage import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    FILE_TOO_LARGE_DETAIL,
    FILE_TYPE_NOT_ALLOWED_DETAIL,
    MAX_FILE_BYTES,
    MAX_FILE_SIZE_MB,
    validate_file_size,
    validate_file_type,
)
from app.storage.validation import (
    _check_extension,
    _extension_of,
)

from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role


# ---------------------------------------------------------------------------
# Helper-level: validate_file_size
# ---------------------------------------------------------------------------


def test_validate_file_size_accepts_zero_bytes():
    """Zero-byte uploads pass the size check (the router rejects them
    earlier with HTTP 400, so this never reaches the validator in
    practice — but the helper itself is permissive)."""
    validate_file_size(0)


@pytest.mark.parametrize("size_bytes", [1, 1024, 1024 * 1024, MAX_FILE_BYTES])
def test_validate_file_size_accepts_up_to_cap(size_bytes):
    """A file at or below the cap is accepted (the cap is strict ``>``)."""
    validate_file_size(size_bytes)


def test_validate_file_size_accepts_exactly_cap():
    """An upload of exactly ``MAX_FILE_BYTES`` is accepted."""
    assert MAX_FILE_BYTES == 10 * 1024 * 1024  # the rule we test against
    validate_file_size(MAX_FILE_BYTES)


def test_validate_file_size_rejects_one_byte_over_cap():
    """One byte past the cap is rejected with HTTP 413."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_size(MAX_FILE_BYTES + 1)

    assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert exc_info.value.detail == FILE_TOO_LARGE_DETAIL
    # The detail must reference the size in MB so the frontend can
    # surface a user-friendly message.
    assert str(MAX_FILE_SIZE_MB) in FILE_TOO_LARGE_DETAIL


def test_validate_file_size_rejects_far_over_cap():
    """An obviously-oversized payload (e.g. 1 GB) is rejected with 413."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_size(1024 * 1024 * 1024)

    assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


# ---------------------------------------------------------------------------
# Helper-level: _extension_of
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("transcript.pdf", ".pdf"),
        ("photo.JPG", ".jpg"),
        ("photo.JPEG", ".jpeg"),
        ("image.PNG", ".png"),
        ("letter.docx", ".docx"),
        ("no-extension", ""),
        ("", ""),
        (None, ""),
        ("path/with/slashes.pdf", ".pdf"),
        ("../traversal.pdf", ".pdf"),
    ],
)
def test_extension_of_is_lowercase_and_handles_edges(filename, expected):
    """``_extension_of`` lowercases extensions, strips paths, and is
    robust to ``None``/empty input."""
    assert _extension_of(filename) == expected


# ---------------------------------------------------------------------------
# Helper-level: _check_extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extension",
    sorted(ALLOWED_EXTENSIONS),
)
def test_check_extension_accepts_each_allowed_extension(extension):
    """Every extension in :data:`ALLOWED_EXTENSIONS` is accepted."""
    assert _check_extension(f"file{extension}") == extension


@pytest.mark.parametrize(
    "filename",
    [
        "evil.txt",
        "evil.exe",
        "evil.zip",
        "evil.tar",
        "evil",
        "evil.pdf.exe",
        "evil.",
        "evil.PDF.exe",  # last extension wins — ".exe"
    ],
)
def test_check_extension_rejects_disallowed(filename):
    """Anything outside :data:`ALLOWED_EXTENSIONS` raises HTTP 415."""
    with pytest.raises(HTTPException) as exc_info:
        _check_extension(filename)

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert exc_info.value.detail == FILE_TYPE_NOT_ALLOWED_DETAIL


# ---------------------------------------------------------------------------
# Helper-level: validate_file_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("transcript.pdf", "application/pdf"),
        ("photo.jpg", "image/jpeg"),
        ("photo.jpeg", "image/jpeg"),
        ("image.png", "image/png"),
        ("letter.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ],
)
def test_validate_file_type_accepts_allowed_pairs(filename, content_type):
    """Each allow-listed (extension, content-type) pair is accepted."""
    extension = validate_file_type(filename=filename, content_type=content_type)
    assert extension in ALLOWED_EXTENSIONS


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("transcript.PDF", "application/pdf"),
        ("photo.Jpg", "image/jpeg"),
        ("photo.JPEG", "image/jpeg"),
        ("image.PNG", "image/png"),
        ("letter.DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ],
)
def test_validate_file_type_accepts_uppercase_extensions(filename, content_type):
    """Extensions are matched case-insensitively."""
    extension = validate_file_type(filename=filename, content_type=content_type)
    assert extension.startswith(".")


def test_validate_file_type_rejects_disallowed_extension():
    """A disallowed extension raises 415 with the standard detail."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename="evil.exe", content_type="application/octet-stream")

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert exc_info.value.detail == FILE_TYPE_NOT_ALLOWED_DETAIL


def test_validate_file_type_rejects_missing_extension():
    """A filename with no extension is rejected with 415."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename="just-a-name", content_type="application/pdf")

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_validate_file_type_rejects_none_filename():
    """A ``None`` filename is rejected with 415."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename=None, content_type="application/pdf")

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_validate_file_type_rejects_empty_filename():
    """An empty-string filename is rejected with 415."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename="", content_type="application/pdf")

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_validate_file_type_rejects_mismatched_content_type():
    """An allowed extension with an unrelated content type is rejected (415).

    This is the realistic "rename ``evil.exe`` to ``evil.pdf`` and submit
    with ``Content-Type: application/octet-stream``" attack — the
    extension alone is not enough.
    """
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(
            filename="renamed.pdf", content_type="application/octet-stream"
        )

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert exc_info.value.detail == FILE_TYPE_NOT_ALLOWED_DETAIL


def test_validate_file_type_rejects_missing_content_type():
    """A missing ``content_type`` is rejected for an allowed extension
    (the multipart parser almost always populates the field)."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename="transcript.pdf", content_type=None)

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_validate_file_type_rejects_empty_content_type():
    """An empty ``content_type`` is rejected."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename="transcript.pdf", content_type="")

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_validate_file_type_accepts_jpeg_as_jpg_or_jpeg():
    """``.jpg`` and ``.jpeg`` are both valid; both require ``image/jpeg``."""
    # .jpg
    validate_file_type(filename="photo.jpg", content_type="image/jpeg")
    # .jpeg
    validate_file_type(filename="photo.jpeg", content_type="image/jpeg")


def test_validate_file_type_jpeg_with_wrong_type_rejected():
    """``.jpg`` with ``image/png`` is rejected — extension and content-type
    must agree."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename="photo.jpg", content_type="image/png")

    assert exc_info.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_allowed_content_types_keys_match_allowed_extensions():
    """The :data:`ALLOWED_CONTENT_TYPES` map must cover every extension in
    :data:`ALLOWED_EXTENSIONS` and no others (otherwise a typo in the
    map would silently regress the validator)."""
    assert set(ALLOWED_CONTENT_TYPES.keys()) == set(ALLOWED_EXTENSIONS)


def test_allowed_extensions_is_complete_for_requirements():
    """Requirements §5 names PDF/JPG/PNG/DOCX — guard against accidental
    edits that drop or extend the allow-list silently."""
    assert ALLOWED_EXTENSIONS == frozenset({".pdf", ".jpg", ".jpeg", ".png", ".docx"})


# ---------------------------------------------------------------------------
# Router-level: end-to-end via the upload endpoint
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex"):
    from app.models.tenant import Tenant

    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _auth_as_student(override_authenticated_user, *, user_id, tenant_id, branch_id):
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
    )


def _seed_student_with_application(db_session):
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="validator@example.test",
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    return tenant, branch, student, application


@pytest.fixture()
def in_memory_storage():
    from app.storage import InMemoryDocumentStorage, set_document_storage

    storage = InMemoryDocumentStorage()
    set_document_storage(storage)
    try:
        yield storage
    finally:
        set_document_storage(None)


def test_router_accepts_exactly_ten_megabytes(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An upload of exactly 10 MB is accepted (the cap is strict ``>``)."""
    tenant, branch, student, application = _seed_student_with_application(db_session)
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    payload = b"x" * MAX_FILE_BYTES
    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("edge.pdf", payload, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert len(in_memory_storage.stored) == 1


def test_router_rejects_one_byte_over_ten_megabytes(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An upload of 10 MB + 1 byte is rejected with 413 (the streaming cap
    triggers first because we detect during read; either way the contract
    is 413 + the standard detail)."""
    tenant, branch, student, application = _seed_student_with_application(db_session)
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    payload = b"x" * (MAX_FILE_BYTES + 1)
    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("too-big.pdf", payload, "application/pdf")},
    )

    assert response.status_code == 413, response.text
    assert response.json()["detail"] == FILE_TOO_LARGE_DETAIL
    assert in_memory_storage.stored == []


def test_router_rejects_far_oversized_upload(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An obviously oversized upload (e.g. 12 MB) is rejected with 413 and
    never reaches storage or DB."""
    tenant, branch, student, application = _seed_student_with_application(db_session)
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    payload = b"x" * (12 * 1024 * 1024)
    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("big.pdf", payload, "application/pdf")},
    )

    assert response.status_code == 413, response.text
    assert response.json()["detail"] == FILE_TOO_LARGE_DETAIL
    assert in_memory_storage.stored == []


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("transcript.pdf", "application/pdf"),
        ("photo.jpg", "image/jpeg"),
        ("photo.jpeg", "image/jpeg"),
        ("image.png", "image/png"),
        ("letter.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("transcript.PDF", "application/pdf"),  # uppercase extension
        ("photo.JPG", "image/jpeg"),
    ],
)
def test_router_accepts_each_allowed_type(
    client,
    db_session,
    override_authenticated_user,
    in_memory_storage,
    filename,
    content_type,
):
    """All allowed (extension, content-type) pairs are accepted by the
    endpoint."""
    tenant, branch, student, application = _seed_student_with_application(db_session)
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": (filename, b"x-bytes", content_type)},
    )

    assert response.status_code == 201, response.text
    assert len(in_memory_storage.stored) == 1


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("evil.exe", "application/octet-stream"),
        ("evil.zip", "application/zip"),
        ("evil.txt", "text/plain"),
        ("evil.csv", "text/csv"),
        ("evil.tar", "application/x-tar"),
        ("evil", "application/octet-stream"),  # no extension
    ],
)
def test_router_rejects_disallowed_extensions(
    client,
    db_session,
    override_authenticated_user,
    in_memory_storage,
    filename,
    content_type,
):
    """Disallowed extensions are rejected with 415."""
    tenant, branch, student, application = _seed_student_with_application(db_session)
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": (filename, b"x-bytes", content_type)},
    )

    assert response.status_code == 415, response.text
    assert response.json()["detail"] == FILE_TYPE_NOT_ALLOWED_DETAIL
    assert in_memory_storage.stored == []


def test_router_rejects_mismatched_content_type_for_allowed_extension(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An allowed extension with a non-matching content type is rejected
    (the cross-check catches "rename-and-relabel" attacks)."""
    tenant, branch, student, application = _seed_student_with_application(db_session)
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("renamed.pdf", b"x-bytes", "application/octet-stream")},
    )

    assert response.status_code == 415, response.text
    assert response.json()["detail"] == FILE_TYPE_NOT_ALLOWED_DETAIL
    assert in_memory_storage.stored == []


def test_router_validation_runs_after_authentication(
    client, db_session, in_memory_storage
):
    """An unauthenticated oversized upload is rejected with 401, not 413 —
    authorization wins over validation (no point leaking the size rule to
    anonymous probers)."""
    # Need an application to point at — auth fails before we reach
    # validation, but the route still needs a syntactically valid path.
    response = client.post(
        "/applications/1/documents",
        files={"file": ("big.pdf", b"x" * (MAX_FILE_BYTES + 1), "application/pdf")},
    )
    assert response.status_code == 401
    assert in_memory_storage.stored == []


def test_router_validation_runs_after_authorization(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """An oversized upload from a non-owner is rejected with 403, not 413."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    # Create an application owned by someone else.
    other_student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="other-owner@example.test",
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=other_student.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )

    # Attacker is a different student in the same tenant.
    attacker = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="attacker@example.test",
    )
    _auth_as_student(
        override_authenticated_user,
        user_id=attacker.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("big.pdf", b"x" * (MAX_FILE_BYTES + 1), "application/pdf")},
    )

    assert response.status_code == 403
    assert in_memory_storage.stored == []


def test_router_type_validation_runs_after_authentication(
    client, db_session, in_memory_storage
):
    """Symmetric to :func:`test_router_validation_runs_after_authentication`
    but for the type path: an unauthenticated wrong-type upload is rejected
    with 401, not 415. Pins the auth-before-validation invariant for both
    rejection branches."""
    response = client.post(
        "/applications/1/documents",
        files={"file": ("evil.exe", b"x-bytes", "application/octet-stream")},
    )
    assert response.status_code == 401
    assert in_memory_storage.stored == []


def test_router_type_validation_runs_after_authorization(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """Symmetric to :func:`test_router_validation_runs_after_authorization`
    but for the type path: a wrong-type upload from a non-owner is rejected
    with 403, not 415."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    other_student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="other-owner-type@example.test",
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=other_student.id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )

    attacker = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="attacker-type@example.test",
    )
    _auth_as_student(
        override_authenticated_user,
        user_id=attacker.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("evil.exe", b"x-bytes", "application/octet-stream")},
    )

    assert response.status_code == 403
    assert in_memory_storage.stored == []


def test_router_validation_runs_before_storage(
    client, db_session, override_authenticated_user, in_memory_storage
):
    """A wrong-type upload never reaches the storage backend."""
    tenant, branch, student, application = _seed_student_with_application(db_session)
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.post(
        f"/applications/{application.id}/documents",
        files={"file": ("evil.exe", b"x-bytes", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert in_memory_storage.stored == []
