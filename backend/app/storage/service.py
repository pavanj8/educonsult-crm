"""Document-storage service abstraction (E27; Journey J20).

The upload router (:mod:`app.routers.student_documents`) never talks to
S3 directly. It goes through :class:`DocumentStorageService`, which is
a small interface with a single ``store`` operation. The production
implementation (:class:`S3DocumentStorageService`) uses ``boto3`` and
honours the configuration in :mod:`app.storage.config`; tests swap in
:class:`InMemoryDocumentStorage` so the suite never touches the
network.

Design notes
------------

* The service is intentionally narrow — ``store(tenant_id, application_id,
     original_filename, content, content_type)`` returns the object key
     the caller persists on the :class:`StudentDocument` row's
     ``storage_path`` column. We deliberately do not return a presigned
     URL or a public URL: the E27 task ships *upload only*; the
     download / serve endpoint lands in a later ticket.
* Failures surface as :class:`DocumentStorageError` so the router can
  translate them into a stable ``503`` response regardless of which
  underlying SDK raised.
* The module-level :func:`get_document_storage` / :func:`set_document_storage`
  pair gives tests a single seam to replace the global service (the
  upload router reads the default service once per request via
  :func:`get_document_storage`, so a test can swap in a fake without
  monkey-patching module-level state).
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.storage.config import (
    document_storage_bucket,
    document_storage_endpoint_url,
    document_storage_key_prefix,
    document_storage_region,
)


class DocumentStorageError(Exception):
    """Raised when an upload to the document store fails.

    The router translates this into HTTP 503. We do not expose the
    underlying boto3 / network error to clients (it may carry
    credentials, internal hostnames, or vendor-specific payloads).
    """


class DocumentStorageService(Protocol):
    """Minimal document-storage interface used by the upload router."""

    def store(
        self,
        *,
        tenant_id: int,
        application_id: int,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """Persist ``content`` and return the storage path to record on the row."""
        ...


@dataclass(frozen=True)
class S3DocumentStorageService:
    """Production S3-compatible storage service backed by ``boto3``.

    A new instance is constructed on each access via
    :func:`get_default_storage_service` (the configuration is
    env-driven and may change between processes, so we don't cache it
    across boots). The boto3 client itself is lazy — only constructed
    the first time :meth:`store` is called — so importing this module
    never triggers AWS network calls.
    """

    bucket: str = field(default_factory=document_storage_bucket)
    region: str = field(default_factory=document_storage_region)
    endpoint_url: str | None = field(default_factory=document_storage_endpoint_url)
    key_prefix: str = field(default_factory=document_storage_key_prefix)

    def _client(self):
        # Imported lazily so the module is usable in tests that mock
        # out ``boto3.client`` without ever needing the real package
        # to import cleanly (and so test failures don't surface as
        # boto3 import errors).
        import boto3
        from botocore.client import Config as BotoConfig

        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
            config=BotoConfig(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                ),
        )

    def store(
        self,
        *,
        tenant_id: int,
        application_id: int,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        key = build_storage_key(
            key_prefix=self.key_prefix,
            tenant_id=tenant_id,
            application_id=application_id,
            original_filename=original_filename,
        )
        try:
            self._client().put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except Exception as exc:  # noqa: BLE001 — translated intentionally
            raise DocumentStorageError("Failed to upload document to storage") from exc
        return key


class InMemoryDocumentStorage:
    """Test double that records uploads without touching the network.

    Each call appends a :class:`StoredDocument` to ``.stored`` so tests
    can assert on what was uploaded, what key was generated, and what
    bytes were stored. ``fail_on_next_store`` is a one-shot fault
    injector for the negative-path tests (storage outage).
    """

    def __init__(self) -> None:
        self.stored: list[StoredDocument] = []
        self._fail_on_next_store = False

    def fail_next_store(self) -> None:
        """Cause the next call to ``store`` to raise :class:`DocumentStorageError`."""
        self._fail_on_next_store = True

    def store(
        self,
        *,
        tenant_id: int,
        application_id: int,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        if self._fail_on_next_store:
            self._fail_on_next_store = False
            raise DocumentStorageError("simulated outage")
        key = build_storage_key(
            key_prefix="tenants",
            tenant_id=tenant_id,
            application_id=application_id,
            original_filename=original_filename,
        )
        self.stored.append(
            StoredDocument(
                key=key,
                tenant_id=tenant_id,
                application_id=application_id,
                original_filename=original_filename,
                content=content,
                content_type=content_type,
            )
        )
        return key


@dataclass(frozen=True)
class StoredDocument:
    """A single recorded upload, captured by :class:`InMemoryDocumentStorage`."""

    key: str
    tenant_id: int
    application_id: int
    original_filename: str
    content: bytes
    content_type: str


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename_component(filename: str) -> str:
    """Return a path-safe filename component.

    The original filename is user-supplied and untrusted (Journey J20).
    We only use it as a *suffix* on the storage key (which is itself
    prefixed with a UUID), so the goal is purely defensive — never to
    let a crafted filename traverse the storage path.
    """
    name = os.path.basename(filename or "").strip()
    if not name:
        name = "upload"
    sanitized = _SAFE_FILENAME_RE.sub("_", name)
    # Trim leading/trailing dots/dashes that some filesystems reject.
    return sanitized.strip("._") or "upload"


def build_storage_key(
    *,
    key_prefix: str,
    tenant_id: int,
    application_id: int,
    original_filename: str,
) -> str:
    """Build the deterministic-but-unique object key for an upload.

    Shape: ``{prefix}/{tenant_id}/applications/{application_id}/{uuid}-{sanitized}``

    The UUID makes every upload unique even when the student uploads
    the same file twice (E31 re-upload flow), so we never silently
    shadow a previous version on the storage backend.
    """
    sanitized = _sanitize_filename_component(original_filename)
    object_id = uuid.uuid4().hex
    prefix = key_prefix.strip().strip("/") or "tenants"
    return f"{prefix}/{tenant_id}/applications/{application_id}/{object_id}-{sanitized}"


_storage_service: DocumentStorageService | None = None


def get_document_storage() -> DocumentStorageService:
    """Return the process-wide storage service, constructing it on first use."""
    global _storage_service
    if _storage_service is None:
        _storage_service = S3DocumentStorageService()
    return _storage_service


def set_document_storage(service: DocumentStorageService | None) -> None:
    """Replace (or clear) the process-wide storage service.

    Pass ``None`` to revert to the default :class:`S3DocumentStorageService`
    on the next :func:`get_document_storage` call. Tests use this to
    inject :class:`InMemoryDocumentStorage` so the suite never reaches
    the network.
    """
    global _storage_service
    _storage_service = service


def reset_document_storage() -> None:
    """Clear the cached storage service so the next get returns the default."""
    set_document_storage(None)


__all__ = [
    "DocumentStorageError",
    "DocumentStorageService",
    "InMemoryDocumentStorage",
    "S3DocumentStorageService",
    "StoredDocument",
    "build_storage_key",
    "get_document_storage",
    "reset_document_storage",
    "set_document_storage",
]