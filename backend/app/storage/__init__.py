"""S3-compatible document storage layer (E27; Journey J20; Requirements §2).

The CRM persists student-uploaded documents in an S3-compatible object
store — AWS S3 in the SaaS deployment, MinIO in the on-prem / Docker
Compose local-dev deployment (Requirements §2 "Tech Stack"). This
package isolates that I/O behind a small service so the router code
stays focused on request validation and DB persistence, and so tests
can patch the service out with a fake (the real S3 client never reaches
the network during CI).

The default export is :func:`get_document_storage`, a process-wide
singleton used by the upload router. Replacement happens in tests via
:func:`set_document_storage`.
"""

from app.storage.config import (
    document_storage_bucket,
    document_storage_endpoint_url,
    document_storage_key_prefix,
    document_storage_region,
)
from app.storage.service import (
    DocumentStorageError,
    DocumentStorageService,
    InMemoryDocumentStorage,
    S3DocumentStorageService,
    get_document_storage,
    set_document_storage,
)

__all__ = [
    "DocumentStorageError",
    "DocumentStorageService",
    "InMemoryDocumentStorage",
    "S3DocumentStorageService",
    "document_storage_bucket",
    "document_storage_endpoint_url",
    "document_storage_key_prefix",
    "document_storage_region",
    "get_document_storage",
    "set_document_storage",
]