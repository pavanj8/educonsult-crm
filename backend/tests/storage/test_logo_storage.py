"""Tests for the E10 logo storage service layer (issue #111).

Covers the helpers and seams in :mod:`app.storage.service` that the
logo upload router depends on:

* :class:`InMemoryLogoStorage` — the test double injected into the
  router under ``LOGO_STORAGE=memory``.
* :func:`build_logo_storage_key` — deterministic-but-unique key
  generation, including the path-traversal sanitization rule on
  ``original_filename``.
* :func:`get_logo_storage` / :func:`set_logo_storage` /
  :func:`reset_logo_storage` — the singleton seam that lets the
  Test Agent inject the in-memory backend.
* The :data:`LOGO_STORAGE` env switch (mirror of
  :data:`DOCUMENT_STORAGE` for the document service — already covered
  by ``tests/student_documents/test_upload_student_document.py`` for
  the document side).

The router-level contract (validation, authorization, persistence,
status codes) is exercised in :mod:`tests.tenants.test_upload_logo`
— this file stays focused on the storage layer.

Traceability
------------
* Requirements §1 (White-labeling: each tenant can upload a logo).
* Journey J3 (Consultancy Owner completes tenant profile).
* Epic E10 (Tenant Branding & Profile); sibling ticket #109 owns
  the ``Tenant.logo_url`` column, #110 owns ``PATCH
  /tenants/{id}/branding``, #112 / #113 own the frontend settings
  page and brand-color theming. This file covers the storage half
  of #111.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage import (
    InMemoryLogoStorage,
    LogoStorageError,
    S3LogoStorageService,
    build_logo_storage_key,
    get_logo_storage,
    reset_logo_storage,
    set_logo_storage,
)
from app.storage.service import _sanitize_filename_component


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_build_logo_storage_key_has_expected_shape():
    """The generated key embeds the tenant id and lives under ``logo/``."""
    key = build_logo_storage_key(
        key_prefix="tenants", tenant_id=42, original_filename="brand.png"
    )
    assert key.startswith("tenants/42/logo/")
    assert key.endswith("-brand.png")


def test_build_logo_storage_key_is_unique_per_call():
    """Two calls with the same tenant/filename generate distinct keys.

    Without the UUID prefix, two uploads of ``brand.png`` from tenant 1
    would silently shadow each other on the storage backend — the
    UUID guard is what stops that. The UUID is also a defense-in-depth
    against key-prediction attacks (an attacker guessing the storage
    key for a target tenant's logo).
    """
    first = build_logo_storage_key(
        key_prefix="tenants", tenant_id=1, original_filename="brand.png"
    )
    second = build_logo_storage_key(
        key_prefix="tenants", tenant_id=1, original_filename="brand.png"
    )
    assert first != second
    # The UUID is a 32-char hex prefix at the start of the basename.
    assert first.split("/")[-1].split("-", 1)[0] != second.split("/")[-1].split("-", 1)[0]
    # Sanity-check that the UUIDs are well-formed.
    uuid.UUID(first.split("/")[-1].split("-", 1)[0])
    uuid.UUID(second.split("/")[-1].split("-", 1)[0])


def test_build_logo_storage_key_strips_prefix_slashes():
    """A leading ``/`` or trailing ``/`` on the prefix does not produce
    a doubled slash in the key."""
    key = build_logo_storage_key(
        key_prefix="/tenants/", tenant_id=7, original_filename="logo.png"
    )
    assert "//" not in key
    assert key.startswith("tenants/7/logo/")


def test_build_logo_storage_key_defaults_prefix_when_blank():
    """A blank prefix (or whitespace-only) falls back to ``tenants``
    rather than producing a relative path like ``/1/logo/...``."""
    key_blank = build_logo_storage_key(
        key_prefix="", tenant_id=1, original_filename="logo.png"
    )
    key_whitespace = build_logo_storage_key(
        key_prefix="   ", tenant_id=1, original_filename="logo.png"
    )
    assert key_blank.startswith("tenants/1/logo/")
    assert key_whitespace.startswith("tenants/1/logo/")


def test_build_logo_storage_key_handles_path_traversal_in_filename():
    """A ``original_filename`` crafted with ``..`` segments never lets the
    storage key escape the tenant's ``logo/`` namespace."""
    key = build_logo_storage_key(
        key_prefix="tenants",
        tenant_id=42,
        original_filename="../../etc/passwd.png",
    )
    # Key remains inside the tenant's logo directory.
    assert key.startswith("tenants/42/logo/")
    assert ".." not in key
    assert "/etc/" not in key
    # The trailing ``-`` + sanitized-name suffix has been collapsed to a
    # safe form (the literal substring ``passwd`` survives because the
    # sanitiser only collapses characters outside ``[A-Za-z0-9._-]``).
    assert key.endswith("-passwd.png")


def test_build_logo_storage_key_sanitizes_special_characters():
    """Characters outside the ``[A-Za-z0-9._-]`` set are collapsed to ``_``."""
    key = build_logo_storage_key(
        key_prefix="tenants",
        tenant_id=1,
        original_filename="evil name with / slashes & symbols!.png",
    )
    # No spaces, no slashes, no ampersands in the final basename.
    basename = key.rsplit("/", 1)[-1]
    assert " " not in basename
    assert "/" not in basename
    assert "&" not in basename
    assert "!" not in basename


def test_build_logo_storage_key_handles_empty_or_none_filename():
    """An empty / whitespace / ``None`` filename falls back to ``upload``."""
    key_empty = build_logo_storage_key(
        key_prefix="tenants", tenant_id=1, original_filename=""
    )
    key_none = build_logo_storage_key(
        key_prefix="tenants", tenant_id=1, original_filename=None  # type: ignore[arg-type]
    )
    key_whitespace = build_logo_storage_key(
        key_prefix="tenants", tenant_id=1, original_filename="   "
    )
    assert key_empty.endswith("-upload")
    assert key_none.endswith("-upload")
    assert key_whitespace.endswith("-upload")


def test_sanitize_filename_component_falls_back_to_upload_for_empty_input():
    """An empty / whitespace-only input is replaced with ``upload`` — a
    filesystem-safe fallback so the storage key never has a trailing
    ``-`` with nothing after it."""
    assert _sanitize_filename_component("") == "upload"
    assert _sanitize_filename_component("   ") == "upload"


def test_sanitize_filename_component_strips_leading_dots_and_underscores():
    """Leading/trailing dots and underscores are stripped; if nothing is
    left, the function falls back to ``upload``. Dashes are *not*
    stripped — they survive in the basename (``--`` is not treated as
    a "dotted" sentinel the way ``..`` is)."""
    assert _sanitize_filename_component("..") == "upload"
    assert _sanitize_filename_component("...") == "upload"
    assert _sanitize_filename_component("___") == "upload"
    # Dashes survive (they are a safe filename character on every
    # filesystem we target).
    assert _sanitize_filename_component("---") == "---"


# ---------------------------------------------------------------------------
# InMemoryLogoStorage
# ---------------------------------------------------------------------------


def test_in_memory_logo_storage_records_upload():
    """A successful ``store_logo`` call appends a :class:`StoredLogo`
    carrying the key, tenant id, filename, content, and content type."""
    storage = InMemoryLogoStorage()
    payload = b"\x89PNG\r\n\x1a\n" + b"fake-bytes"

    key = storage.store_logo(
        tenant_id=42,
        original_filename="brand.png",
        content=payload,
        content_type="image/png",
    )

    assert len(storage.stored) == 1
    recorded = storage.stored[0]
    assert recorded.key == key
    assert recorded.tenant_id == 42
    assert recorded.original_filename == "brand.png"
    assert recorded.content == payload
    assert recorded.content_type == "image/png"


def test_in_memory_logo_storage_fail_next_store_raises_then_resets():
    """``fail_next_store`` is a one-shot fault injector: the next
    ``store_logo`` raises :class:`LogoStorageError` and the latch
    resets so subsequent calls succeed."""
    storage = InMemoryLogoStorage()
    storage.fail_next_store()

    with pytest.raises(LogoStorageError):
        storage.store_logo(
            tenant_id=1,
            original_filename="logo.png",
            content=b"x",
            content_type="image/png",
        )

    # Latch has cleared — subsequent call succeeds.
    key = storage.store_logo(
        tenant_id=1,
        original_filename="logo.png",
        content=b"x",
        content_type="image/png",
    )
    assert key.startswith("tenants/1/logo/")
    assert len(storage.stored) == 1


def test_in_memory_logo_storage_does_not_record_on_failure():
    """A faulted call does not partially-populate ``.stored``."""
    storage = InMemoryLogoStorage()
    storage.fail_next_store()

    with pytest.raises(LogoStorageError):
        storage.store_logo(
            tenant_id=1,
            original_filename="logo.png",
            content=b"x",
            content_type="image/png",
        )

    assert storage.stored == []


def test_in_memory_logo_storage_keys_are_distinct_per_call():
    """Even with the same tenant id and filename, each ``store_logo`` call
    generates a fresh UUID suffix — no silent shadowing on the backend."""
    storage = InMemoryLogoStorage()
    first = storage.store_logo(
        tenant_id=1,
        original_filename="logo.png",
        content=b"first",
        content_type="image/png",
    )
    second = storage.store_logo(
        tenant_id=1,
        original_filename="logo.png",
        content=b"second",
        content_type="image/png",
    )
    assert first != second
    assert len(storage.stored) == 2


# ---------------------------------------------------------------------------
# Singleton seam: get_logo_storage / set_logo_storage / reset_logo_storage
# ---------------------------------------------------------------------------


def test_set_logo_storage_swaps_the_singleton():
    """``set_logo_storage`` replaces the process-wide service returned by
    ``get_logo_storage``. The replacement is observable on the very next
    ``get_logo_storage`` call (no caching across swaps)."""
    replacement = InMemoryLogoStorage()
    try:
        set_logo_storage(replacement)
        assert get_logo_storage() is replacement
    finally:
        reset_logo_storage()


def test_set_logo_storage_none_reverts_to_default():
    """``set_logo_storage(None)`` clears the override so the next
    ``get_logo_storage`` returns the default :class:`S3LogoStorageService`."""
    replacement = InMemoryLogoStorage()
    set_logo_storage(replacement)
    assert get_logo_storage() is replacement

    set_logo_storage(None)
    default = get_logo_storage()
    assert isinstance(default, S3LogoStorageService)
    # And a second get returns the same default (cached).
    assert get_logo_storage() is default


def test_reset_logo_storage_clears_override():
    """``reset_logo_storage`` is a thin alias for ``set_logo_storage(None)``
    — kept for symmetry with the document side (``reset_document_storage``)."""
    replacement = InMemoryLogoStorage()
    set_logo_storage(replacement)
    assert get_logo_storage() is replacement

    reset_logo_storage()
    assert isinstance(get_logo_storage(), S3LogoStorageService)


def test_get_logo_storage_uses_in_memory_backend_when_env_var_is_set(monkeypatch):
    """The :data:`LOGO_STORAGE` env switch selects the in-memory backend,
    mirroring :data:`DOCUMENT_STORAGE` for the document side. Unset (or
    any other value) falls back to :class:`S3LogoStorageService`."""
    monkeypatch.setenv("LOGO_STORAGE", "memory")
    reset_logo_storage()
    assert isinstance(get_logo_storage(), InMemoryLogoStorage)

    # Common alternate spellings also select the in-memory backend so
    # typos in the harness bootstrap don't silently fall back to S3.
    for value in ("MEMORY", "in-memory", "InMemory"):
        monkeypatch.setenv("LOGO_STORAGE", value)
        reset_logo_storage()
        assert isinstance(get_logo_storage(), InMemoryLogoStorage), value


def test_get_logo_storage_defaults_to_s3_when_env_var_unset(monkeypatch):
    """When :data:`LOGO_STORAGE` is unset (or any non-memory value), the
    production :class:`S3LogoStorageService` is selected."""
    monkeypatch.delenv("LOGO_STORAGE", raising=False)
    reset_logo_storage()
    assert isinstance(get_logo_storage(), S3LogoStorageService)

    monkeypatch.setenv("LOGO_STORAGE", "s3")
    reset_logo_storage()
    assert isinstance(get_logo_storage(), S3LogoStorageService)