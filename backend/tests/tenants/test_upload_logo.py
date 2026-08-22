"""Tests for the E10 tenant-logo upload endpoint (issue #111).

Covers ``POST /tenants/{tenant_id}/logo`` end-to-end:

* **Happy path** — Consultancy Owner / Super Admin uploads a valid
  PNG / JPG / WebP logo; the row's ``logo_url`` is updated and the
  in-memory storage records the upload.
* **RBAC gate** — only roles granted ``tenant:update`` may upload;
  every other role is 403.
* **Cross-tenant guard** — an owner from a *different* tenant gets
  404 (not 403) so tenant-id existence is not leaked.
* **Validation** — 400 for missing / empty ``file`` form field,
  400 for empty body, 413 for oversized uploads (>2 MB), 415 for
  disallowed extensions / content types, 400 for a missing
  ``Content-Type`` header (so the frontend can surface a clearer
  error than "only PNG/JPG/WebP accepted").
* **Storage backend failures** — 503 when :class:`LogoStorageError`
  is raised, 503 when the DB raises :class:`OperationalError`.
* **Replacement** — a second upload replaces ``logo_url`` (with a
  fresh storage key), and never silently shadows the previous key.

S3 / MinIO is never reached in tests — :class:`InMemoryLogoStorage`
is injected via :func:`app.storage.set_logo_storage` and reset
between tests via the ``in_memory_logo_storage`` fixture (which
monkey-patches the process-wide singleton at setup and restores the
default afterwards).

Traceability
------------
* Requirements §1 (White-labeling: each tenant can upload a logo).
* Journey J3 (Consultancy Owner completes tenant profile).
* Epic E10 (Tenant Branding & Profile); sibling ticket #109 owns
  the ``Tenant.logo_url`` column, #110 owns ``PATCH
  /tenants/{id}/branding``, #112 / #113 own the frontend settings
  page and brand-color theming. This file covers the upload half of
  #111.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models.tenant import Tenant
from app.rbac.roles import Role
from app.storage import (
    ALLOWED_LOGO_CONTENT_TYPES,
    ALLOWED_LOGO_EXTENSIONS,
    LOGO_FILE_TOO_LARGE_DETAIL,
    LOGO_FILE_TYPE_NOT_ALLOWED_DETAIL,
    LOGO_MAX_FILE_BYTES,
    InMemoryLogoStorage,
    set_logo_storage,
)
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def in_memory_logo_storage():
    """Swap in the :class:`InMemoryLogoStorage` test double for the
    duration of the test. Yields the double so tests can assert on
    ``.stored``. After the test, the process-wide logo storage
    service is restored to its default (``S3LogoStorageService``) so
    subsequent tests are isolated.
    """
    storage = InMemoryLogoStorage()
    set_logo_storage(storage)
    try:
        yield storage
    finally:
        set_logo_storage(None)


def _create_tenant(db_session, *, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


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


def _seed_owner_with_tenant(db_session, *, tenant_id: int, email: str = "owner@example.test"):
    """Create the Consultancy Owner User row for a tenant."""
    return make_db_user(
        db_session,
        Role.CONSULTANCY_OWNER,
        tenant_id=tenant_id,
        branch_id=None,
        email=email,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("brand.png", "image/png"),
        ("brand.jpg", "image/jpeg"),
        ("brand.jpeg", "image/jpeg"),
        ("brand.webp", "image/webp"),
    ],
)
def test_owner_can_upload_logo(
    client,
    db_session,
    override_authenticated_user,
    in_memory_logo_storage,
    filename,
    content_type,
):
    """A Consultancy Owner can upload a valid logo for their own tenant."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    payload = b"fake-logo-bytes"
    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": (filename, BytesIO(payload), content_type)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == tenant.id
    assert body["logo_url"] is not None
    assert body["logo_url"].startswith(f"tenants/{tenant.id}/logo/")
    assert body["logo_url"].endswith(f"-{filename.lower()}")

    # Storage service saw exactly one upload.
    assert len(in_memory_logo_storage.stored) == 1
    recorded = in_memory_logo_storage.stored[0]
    assert recorded.tenant_id == tenant.id
    assert recorded.content == payload
    assert recorded.content_type == content_type

    # Persisted row's logo_url matches the storage key.
    db_session.expire_all()
    persisted = db_session.get(Tenant, tenant.id)
    assert persisted.logo_url == recorded.key
    assert persisted.logo_url == body["logo_url"]


def test_owner_can_upload_logo_uppercase_extension(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """An uppercase extension is accepted (the validator lowercases for
    matching). The generated storage key preserves the original-case
    filename — it is not lowercased."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.PNG", BytesIO(b"png"), "image/png")},
    )

    assert response.status_code == 200, response.text
    # Storage key preserves the original-case filename.
    assert response.json()["logo_url"].endswith("-brand.PNG")


def test_super_admin_can_upload_logo_to_any_tenant(
    client,
    db_session,
    override_authenticated_user,
    in_memory_logo_storage,
):
    """Super Admin (no tenant_id on JWT) can upload a logo to any tenant."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    super_admin = make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        tenant_id=None,
        branch_id=None,
        email="superadmin@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.SUPER_ADMIN,
        user_id=super_admin.id,
        tenant_id=None,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["logo_url"].startswith(f"tenants/{tenant.id}/logo/")
    assert len(in_memory_logo_storage.stored) == 1


def test_upload_replaces_existing_logo_url(
    client,
    db_session,
    override_authenticated_user,
    in_memory_logo_storage,
):
    """A second upload replaces the tenant's ``logo_url`` with a fresh
    storage key (the older key remains orphaned on the storage backend
    but is no longer referenced by the row)."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    first = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("first.png", BytesIO(b"first"), "image/png")},
    )
    second = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("second.png", BytesIO(b"second"), "image/png")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["logo_url"] != second.json()["logo_url"]
    # The most recent response reflects the latest key.
    db_session.expire_all()
    persisted = db_session.get(Tenant, tenant.id)
    assert persisted.logo_url == second.json()["logo_url"]
    assert persisted.logo_url != first.json()["logo_url"]
    # Both uploads reached storage.
    assert len(in_memory_logo_storage.stored) == 2


def test_upload_persists_logo_url_visible_via_get_tenant(
    client,
    db_session,
    override_authenticated_user,
    in_memory_logo_storage,
):
    """A subsequent ``GET /tenants/{id}`` (super admin only) reflects the
    just-uploaded logo URL — the row's ``logo_url`` was committed."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    upload_response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )
    assert upload_response.status_code == 200
    expected_key = upload_response.json()["logo_url"]

    # Switch to a super admin to call the list/detail endpoints
    # (consultancy owners don't have TENANT_READ; the cross-tenant
    # guard would surface a 404 otherwise).
    super_admin = make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        tenant_id=None,
        branch_id=None,
        email="super-admin-read@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.SUPER_ADMIN,
        user_id=super_admin.id,
        tenant_id=None,
        branch_id=None,
    )

    detail_response = client.get(f"/tenants/{tenant.id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["logo_url"] == expected_key


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def test_upload_requires_authentication(client, db_session, in_memory_logo_storage):
    """Unauthenticated callers are rejected with 401."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )

    assert response.status_code == 401
    assert in_memory_logo_storage.stored == []


def test_upload_rejects_invalid_access_token(client, in_memory_logo_storage):
    response = client.post(
        "/tenants/1/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert in_memory_logo_storage.stored == []


@pytest.mark.parametrize(
    "role",
    [
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
        Role.STUDENT,
    ],
)
def test_upload_rejects_roles_without_tenant_update(
    client,
    db_session,
    override_authenticated_user,
    in_memory_logo_storage,
    role,
):
    """Only SUPER_ADMIN and CONSULTANCY_OWNER have ``tenant:update``; every
    other role is 403 (even staff who otherwise have tenant-scoped power,
    e.g. branch manager — uploading a logo is a tenant-level act, not a
    branch-level one)."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    # Create a staff user with the role under test, scoped to the tenant.
    staff = make_db_user(
        db_session,
        role,
        tenant_id=tenant.id,
        branch_id=None,
        email=f"staff-{role.value}@example.test",
    )
    _auth_as(
        override_authenticated_user,
        role,
        user_id=staff.id,
        tenant_id=tenant.id,
        branch_id=staff.branch_id,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
    assert in_memory_logo_storage.stored == []
    # And no DB write occurred.
    db_session.expire_all()
    persisted = db_session.get(Tenant, tenant.id)
    assert persisted.logo_url is None


def test_owner_can_upload_to_own_tenant(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A Consultancy Owner uploading to their **own** tenant succeeds (200)."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )

    assert response.status_code == 200, response.text


def test_owner_cannot_upload_to_other_tenant_returns_404(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A Consultancy Owner uploading to a **different** tenant gets 404
    (not 403) so tenant-id existence is not leaked. Per the endpoint
    contract, this is the cross-tenant guard at work, not an authorization
    failure.
    """
    apex = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    other = _create_tenant(db_session, name="Global Reach", slug="global-reach")

    apex_owner = _seed_owner_with_tenant(
        db_session, tenant_id=apex.id, email="apex-owner@example.test"
    )
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=apex_owner.id,
        tenant_id=apex.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{other.id}/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"
    assert in_memory_logo_storage.stored == []
    # And the other tenant's row is untouched.
    db_session.expire_all()
    other_row = db_session.get(Tenant, other.id)
    assert other_row.logo_url is None


def test_upload_returns_404_for_nonexistent_tenant(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A 404 is returned for a tenant id that does not exist."""
    super_admin = make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        tenant_id=None,
        branch_id=None,
        email="ghost-admin@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.SUPER_ADMIN,
        user_id=super_admin.id,
        tenant_id=None,
        branch_id=None,
    )

    response = client.post(
        "/tenants/999999/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"
    assert in_memory_logo_storage.stored == []


# ---------------------------------------------------------------------------
# Validation: file form field
# ---------------------------------------------------------------------------


def test_upload_rejects_missing_file_form_field(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A request without the ``file`` form field is rejected with 400."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    # Send a multipart request with no ``file`` part. The fastapi
    # multipart parser surfaces a missing required File dependency as
    # 422, which is the closest analogue for the route's contract — the
    # endpoint never receives a file-shaped argument.
    response = client.post(f"/tenants/{tenant.id}/logo", data={"unrelated": "value"})

    assert response.status_code in (400, 422)
    assert in_memory_logo_storage.stored == []


def test_upload_rejects_empty_file_body(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A zero-byte upload is rejected with 400 and never reaches storage."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("empty.png", BytesIO(b""), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded logo is empty"
    assert in_memory_logo_storage.stored == []
    db_session.expire_all()
    persisted = db_session.get(Tenant, tenant.id)
    assert persisted.logo_url is None


def test_upload_rejects_empty_filename(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A file with an empty filename surfaces a 400 with the distinct
    "File is missing a filename" detail — distinct from the "missing form
    field" 400 so the frontend can surface a clearer message.

    Starlette's multipart parser rejects a literally-empty filename at
    the form-parsing layer with 422 (the request never reaches the
    route handler), so the most realistic way to trip our
    :func:`_validate_filename` branch is a file part whose
    ``content_type`` header is missing — which we cover separately in
    :func:`test_upload_rejects_missing_content_type_header`. The
    contract for the empty-filename path is therefore pinned on the
    helper-level unit tests in :mod:`tests.storage.test_logo_storage`
    via :func:`build_logo_storage_key` with ``original_filename=""``;
    here we just assert the starlette-level 422 contract so a future
    refactor that bypasses our handler is caught.
    """
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("", BytesIO(b"x"), "image/png")},
    )

    # Either our handler rejects it (400) or starlette's parser does
    # (422) — both are acceptable; the contract that matters is that
    # the request never reaches storage.
    assert response.status_code in (400, 422), response.text
    assert in_memory_logo_storage.stored == []


# ---------------------------------------------------------------------------
# Validation: file size
# ---------------------------------------------------------------------------


def test_upload_accepts_exactly_two_megabytes(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """An upload of exactly the 2 MB cap is accepted (the cap is strict ``>``)."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    payload = b"x" * LOGO_MAX_FILE_BYTES
    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(payload), "image/png")},
    )

    assert response.status_code == 200, response.text
    assert len(in_memory_logo_storage.stored) == 1


def test_upload_rejects_oversized(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """An upload exceeding the 2 MB cap is rejected with 413 and never reaches
    storage."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    payload = b"x" * (LOGO_MAX_FILE_BYTES + 1)
    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("too-big.png", BytesIO(payload), "image/png")},
    )

    assert response.status_code == 413, response.text
    assert response.json()["detail"] == LOGO_FILE_TOO_LARGE_DETAIL
    assert in_memory_logo_storage.stored == []
    db_session.expire_all()
    persisted = db_session.get(Tenant, tenant.id)
    assert persisted.logo_url is None


# ---------------------------------------------------------------------------
# Validation: file type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("evil.svg", "image/svg+xml"),
        ("evil.gif", "image/gif"),
        ("evil.bmp", "image/bmp"),
        ("evil.tiff", "image/tiff"),
        ("evil.txt", "text/plain"),
        ("evil", "image/png"),  # no extension
        ("brand.png.exe", "image/png"),  # wrong extension
    ],
)
def test_upload_rejects_disallowed_extension(
    client,
    db_session,
    override_authenticated_user,
    in_memory_logo_storage,
    filename,
    content_type,
):
    """Extensions outside :data:`ALLOWED_LOGO_EXTENSIONS` (PNG / JPG /
    JPEG / WebP) are rejected with 415. SVG is explicitly excluded (it
    can carry scripts)."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": (filename, BytesIO(b"x"), content_type)},
    )

    assert response.status_code == 415, response.text
    assert response.json()["detail"] == LOGO_FILE_TYPE_NOT_ALLOWED_DETAIL
    assert in_memory_logo_storage.stored == []


def test_upload_rejects_mismatched_content_type_for_allowed_extension(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """An allowed extension with a non-matching content type is rejected
    (the cross-check catches "rename-and-relabel" attacks)."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("renamed.png", BytesIO(b"x"), "application/octet-stream")},
    )

    assert response.status_code == 415, response.text
    assert response.json()["detail"] == LOGO_FILE_TYPE_NOT_ALLOWED_DETAIL
    assert in_memory_logo_storage.stored == []


def test_upload_rejects_missing_content_type_header(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A multipart upload whose ``Content-Type`` header is empty is rejected
    with 400 (and the error names the missing header) so the frontend can
    surface a clearer message than the type-allow-list 415 — see the UX
    Architect finding for the rationale.

    Note: TestClient / Starlette's multipart parser fills a literal
    ``None`` content type with the default ``"image/png"``, so to
    actually trip our missing-content-type branch we pass an empty
    string ``""`` (which Starlette preserves as-is and our handler
    treats as missing).
    """
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"x"), "")},
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "File is missing a Content-Type header"
    assert in_memory_logo_storage.stored == []


def test_allowed_logo_extensions_matches_requirements():
    """Pinned to the E10 / Journey J3 contract: PNG, JPG/JPEG, WebP only.

    Guard against accidental edits that drop or extend the allow-list
    silently. SVG is intentionally excluded.
    """
    assert ALLOWED_LOGO_EXTENSIONS == frozenset({".png", ".jpg", ".jpeg", ".webp"})
    assert ".svg" not in ALLOWED_LOGO_EXTENSIONS


def test_allowed_logo_content_types_keys_match_extensions():
    """The :data:`ALLOWED_LOGO_CONTENT_TYPES` map must cover every extension
    in :data:`ALLOWED_LOGO_EXTENSIONS` and no others (otherwise a typo in
    the map would silently regress the validator)."""
    assert set(ALLOWED_LOGO_CONTENT_TYPES.keys()) == set(ALLOWED_LOGO_EXTENSIONS)


# ---------------------------------------------------------------------------
# Storage backend failures
# ---------------------------------------------------------------------------


def test_upload_returns_503_when_storage_backend_fails(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """A :class:`LogoStorageError` from the storage backend surfaces as 503."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )
    in_memory_logo_storage.fail_next_store()

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"x"), "image/png")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Logo storage is temporarily unavailable"


def test_upload_does_not_persist_row_when_storage_fails(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """If the storage backend fails, ``logo_url`` is not committed."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )
    in_memory_logo_storage.fail_next_store()

    client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"x"), "image/png")},
    )

    db_session.expire_all()
    persisted = db_session.get(Tenant, tenant.id)
    assert persisted.logo_url is None


# ---------------------------------------------------------------------------
# Database availability
# ---------------------------------------------------------------------------


class _FakeSessionForLogo503:
    """Minimal fake session whose ``get`` always raises ``OperationalError``."""

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


def test_upload_returns_503_when_database_unavailable(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """An :class:`OperationalError` loading the tenant surfaces as 503.

    We swap in a fake session whose ``get`` raises; the router catches
    and translates to a stable 503 + "Tenant service is temporarily
    unavailable" detail. The exact dependency that the router captured
    at import time must be the one we override (mirrors the same
    pattern in the E27 test suite — see
    :func:`test_upload_returns_503_when_database_unavailable_loading_student`).
    """
    from app.routers.tenants import get_db as router_get_db

    super_admin = make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        tenant_id=None,
        branch_id=None,
        email="db-down-logo@example.test",
    )
    _auth_as(
        override_authenticated_user,
        Role.SUPER_ADMIN,
        user_id=super_admin.id,
        tenant_id=None,
        branch_id=None,
    )

    fake_session = _FakeSessionForLogo503()

    def _override_get_db():
        yield fake_session

    client.app.dependency_overrides[router_get_db] = _override_get_db
    try:
        response = client.post(
            "/tenants/1/logo",
            files={"file": ("brand.png", BytesIO(b"x"), "image/png")},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Tenant service is temporarily unavailable"
    finally:
        client.app.dependency_overrides.pop(router_get_db, None)
    # And storage was not touched (the DB error trips before storage).
    assert in_memory_logo_storage.stored == []


# ---------------------------------------------------------------------------
# Row write — guards against regressions on the logo_url column name
# ---------------------------------------------------------------------------


def test_upload_writes_to_logo_url_column(
    client, db_session, override_authenticated_user, in_memory_logo_storage
):
    """Pin that the row's ``logo_url`` column (not some new ``logo_path``
    column) is the one that gets written — guards against a refactor
    silently renaming the column without a migration."""
    tenant = _create_tenant(db_session, name="Apex EduConsult", slug="apex")
    owner = _seed_owner_with_tenant(db_session, tenant_id=tenant.id)
    _auth_as(
        override_authenticated_user,
        Role.CONSULTANCY_OWNER,
        user_id=owner.id,
        tenant_id=tenant.id,
        branch_id=None,
    )

    response = client.post(
        f"/tenants/{tenant.id}/logo",
        files={"file": ("brand.png", BytesIO(b"png"), "image/png")},
    )
    assert response.status_code == 200

    # Read the column directly via a query so the assertion is on the
    # physical column, not just the API response.
    db_session.expire_all()
    persisted = db_session.scalars(
        select(Tenant).where(Tenant.id == tenant.id)
    ).one()
    assert persisted.logo_url is not None
    assert persisted.logo_url.startswith(f"tenants/{tenant.id}/logo/")