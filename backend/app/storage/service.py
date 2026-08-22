"""S3-compatible storage services (E27 documents + E10 logos).

The upload routers (:mod:`app.routers.student_documents` and
:mod:`app.routers.tenants`) never talk to S3 directly. They go
through :class:`DocumentStorageService` / :class:`LogoStorageService`,
two small interfaces that share a single boto3 client. Production
implementations (:class:`S3DocumentStorageService` /
:class:`S3LogoStorageService`) honour the configuration in
:mod:`app.storage.config`; tests swap in
:class:`InMemoryDocumentStorage` / :class:`InMemoryLogoStorage` so
the suite never touches the network.

Design notes
------------

* The document service is intentionally narrow — ``store(tenant_id,
  application_id, original_filename, content, content_type)`` returns
  the object key the caller persists on the :class:`StudentDocument`
  row's ``storage_path`` column. We deliberately do not return a
  presigned URL or a public URL: the E27 task ships *upload only*;
  the download / serve endpoint lands in a later ticket.
* The logo service is the E10 sibling — ``store_logo(tenant_id,
  original_filename, content, content_type)`` returns the storage
  path; the E10 PATCH endpoint is what eventually writes it to
  ``tenants.logo_url`` (or the logo-upload endpoint itself does so
  atomically — see :mod:`app.routers.tenants`).
* Failures surface as :class:`DocumentStorageError` (or
  :class:`LogoStorageError`) so the router can translate them into a
  stable ``503`` response regardless of which underlying SDK raised.
* The module-level :func:`get_document_storage` / :func:`set_document_storage`
  / :func:`get_logo_storage` / :func:`set_logo_storage` pair gives
  tests a single seam to replace each global service without
  monkey-patching module-level state.
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


class LogoStorageError(Exception):
    """Raised when an upload to the logo store fails.

    The router translates this into HTTP 503 for the same reason as
    :class:`DocumentStorageError` — we never echo underlying
    boto3 / network error strings back to the client.
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


class LogoStorageService(Protocol):
    """Minimal logo-storage interface used by the tenant logo upload router.

    The logo is keyed on ``tenant_id`` only — each tenant has at most
    one logo, so the storage key shape (see :func:`build_logo_storage_key`)
    is simpler than the document key and never carries an
    application id.
    """

    def store_logo(
        self,
        *,
        tenant_id: int,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """Persist ``content`` and return the storage path to record on the tenant row."""
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


@dataclass(frozen=True)
class S3LogoStorageService:
    """Production S3-compatible storage service for tenant logos (E10; Journey J3).

    A new instance is constructed on each access via
    :func:`get_logo_storage` (the configuration is env-driven and may
    change between processes, so we don't cache it across boots). The
    boto3 client itself is lazy — only constructed the first time
    :meth:`store_logo` is called — so importing this module never
    triggers AWS network calls.

    The service uses the same bucket/region/endpoint configuration as
    the document service because Requirements §2 ships one
    S3-compatible store per deployment; the ``key_prefix`` differs
    because tenant logos live at a different key prefix than student
    documents (so cleanup / IAM policies can target them separately).
    """

    bucket: str = field(default_factory=document_storage_bucket)
    region: str = field(default_factory=document_storage_region)
    endpoint_url: str | None = field(default_factory=document_storage_endpoint_url)
    key_prefix: str = field(default_factory=document_storage_key_prefix)

    def _client(self):
        # Imported lazily for the same reason as
        # :meth:`S3DocumentStorageService._client`.
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

    def store_logo(
        self,
        *,
        tenant_id: int,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        key = build_logo_storage_key(
            key_prefix=self.key_prefix,
            tenant_id=tenant_id,
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
            raise LogoStorageError("Failed to upload logo to storage") from exc
        return key


class InMemoryLogoStorage:
    """Test double for :class:`LogoStorageService` that records uploads without
    touching the network.

    Each call appends a :class:`StoredLogo` to ``.stored`` so tests can
    assert on what was uploaded, what key was generated, and what bytes
    were stored. ``fail_on_next_store`` is a one-shot fault injector
    for the negative-path tests (storage outage).
    """

    def __init__(self) -> None:
        self.stored: list[StoredLogo] = []
        self._fail_on_next_store = False

    def fail_next_store(self) -> None:
        """Cause the next call to ``store_logo`` to raise :class:`LogoStorageError`."""
        self._fail_on_next_store = True

    def store_logo(
        self,
        *,
        tenant_id: int,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        if self._fail_on_next_store:
            self._fail_on_next_store = False
            raise LogoStorageError("simulated outage")
        key = build_logo_storage_key(
            key_prefix="tenants",
            tenant_id=tenant_id,
            original_filename=original_filename,
        )
        self.stored.append(
            StoredLogo(
                key=key,
                tenant_id=tenant_id,
                original_filename=original_filename,
                content=content,
                content_type=content_type,
            )
        )
        return key


@dataclass(frozen=True)
class StoredLogo:
    """A single recorded logo upload, captured by :class:`InMemoryLogoStorage`."""

    key: str
    tenant_id: int
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


def build_logo_storage_key(
    *,
    key_prefix: str,
    tenant_id: int,
    original_filename: str,
) -> str:
    """Build the storage key for a tenant logo upload (E10; Journey J3).

    Shape: ``{prefix}/{tenant_id}/logo/{uuid}-{sanitized}``

    The key lives under ``{tenant_id}/logo/`` (not ``applications/``)
    so the logo namespace is clearly separate from the document
    namespace, and so per-tenant cleanup / IAM policies can target
    logos by key prefix without touching student documents. The UUID
    keeps every upload distinct even when a tenant re-uploads a logo
    of the same filename — older keys remain on the storage backend
    but are orphaned (the tenant row's ``logo_url`` always points at
    the latest upload's key).
    """
    sanitized = _sanitize_filename_component(original_filename)
    object_id = uuid.uuid4().hex
    prefix = key_prefix.strip().strip("/") or "tenants"
    return f"{prefix}/{tenant_id}/logo/{object_id}-{sanitized}"


_storage_service: DocumentStorageService | None = None


def get_document_storage() -> DocumentStorageService:
    """Return the process-wide storage service, constructing it on first use.

    Honors ``DOCUMENT_STORAGE=memory`` to select the in-memory backend, so the app
    can be booted for black-box testing (e.g. the Test agent) without S3/MinIO —
    mirroring how ``DATABASE_OVERRIDE=sqlite`` gives a self-contained database.
    Unset (or any other value) keeps the production S3 backend, so this is a no-op
    in real deployments.
    """
    global _storage_service
    if _storage_service is None:
        if os.environ.get("DOCUMENT_STORAGE", "").strip().lower() in {"memory", "in-memory", "inmemory"}:
            _storage_service = InMemoryDocumentStorage()
        else:
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


_logo_storage_service: LogoStorageService | None = None


def get_logo_storage() -> LogoStorageService:
    """Return the process-wide logo storage service, constructing it on first use.

    Honors ``LOGO_STORAGE=memory`` to select the in-memory backend, so
    the app can be booted for black-box testing (e.g. the Test agent)
    without S3/MinIO — mirroring how ``DOCUMENT_STORAGE=memory`` gives
    a self-contained document store. Unset (or any other value) keeps
    the production S3 backend, so this is a no-op in real deployments.
    """
    global _logo_storage_service
    if _logo_storage_service is None:
        if os.environ.get("LOGO_STORAGE", "").strip().lower() in {"memory", "in-memory", "inmemory"}:
            _logo_storage_service = InMemoryLogoStorage()
        else:
            _logo_storage_service = S3LogoStorageService()
    return _logo_storage_service


def set_logo_storage(service: LogoStorageService | None) -> None:
    """Replace (or clear) the process-wide logo storage service.

    Pass ``None`` to revert to the default :class:`S3LogoStorageService`
    on the next :func:`get_logo_storage` call. Tests use this to inject
    :class:`InMemoryLogoStorage` so the suite never reaches the network.
    """
    global _logo_storage_service
    _logo_storage_service = service


def reset_logo_storage() -> None:
    """Clear the cached logo storage service so the next get returns the default."""
    set_logo_storage(None)


__all__ = [
    "DocumentStorageError",
    "DocumentStorageService",
    "InMemoryDocumentStorage",
    "InMemoryLogoStorage",
    "LogoStorageError",
    "LogoStorageService",
    "S3DocumentStorageService",
    "S3LogoStorageService",
    "StoredDocument",
    "StoredLogo",
    "build_logo_storage_key",
    "build_storage_key",
    "get_document_storage",
    "get_logo_storage",
    "reset_document_storage",
    "reset_logo_storage",
    "set_document_storage",
    "set_logo_storage",
]