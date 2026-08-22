"""S3-compatible document + logo storage layer.

The CRM persists student-uploaded documents and tenant logos in an
S3-compatible object store — AWS S3 in the SaaS deployment, MinIO in
the on-prem / Docker Compose local-dev deployment (Requirements §2
"Tech Stack"). This package isolates that I/O behind small services
so router code stays focused on request validation and DB
persistence, and so tests can patch the services out with fakes (the
real S3 client never reaches the network during CI).

The default exports are :func:`get_document_storage` and
:func:`get_logo_storage`, two process-wide singletons used by the
upload routers. Replacement happens in tests via
:func:`set_document_storage` and :func:`set_logo_storage`.
"""

from app.storage.checklist_completeness import (
    ChecklistCompletenessItem,
    ChecklistCompletenessSummary,
    ChecklistCompletenessUpload,
    compute_checklist_completeness,
)
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
    InMemoryLogoStorage,
    LogoStorageError,
    LogoStorageService,
    S3DocumentStorageService,
    S3LogoStorageService,
    StoredDocument,
    StoredLogo,
    build_logo_storage_key,
    build_storage_key,
    get_document_storage,
    get_logo_storage,
    reset_document_storage,
    reset_logo_storage,
    set_document_storage,
    set_logo_storage,
)
from app.storage.validation import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    FILE_TOO_LARGE_DETAIL,
    FILE_TYPE_NOT_ALLOWED_DETAIL,
    LOGO_FILE_TOO_LARGE_DETAIL,
    LOGO_FILE_TYPE_NOT_ALLOWED_DETAIL,
    LOGO_MAX_FILE_BYTES,
    LOGO_MAX_FILE_SIZE_MB,
    MAX_FILE_BYTES,
    MAX_FILE_SIZE_MB,
    validate_file_size,
    validate_file_type,
    validate_logo_file_size,
    validate_logo_file_type,
)

__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "ALLOWED_EXTENSIONS",
    "ChecklistCompletenessItem",
    "ChecklistCompletenessSummary",
    "ChecklistCompletenessUpload",
    "DocumentStorageError",
    "DocumentStorageService",
    "FILE_TOO_LARGE_DETAIL",
    "FILE_TYPE_NOT_ALLOWED_DETAIL",
    "InMemoryDocumentStorage",
    "InMemoryLogoStorage",
    "LOGO_FILE_TOO_LARGE_DETAIL",
    "LOGO_FILE_TYPE_NOT_ALLOWED_DETAIL",
    "LOGO_MAX_FILE_BYTES",
    "LOGO_MAX_FILE_SIZE_MB",
    "LogoStorageError",
    "LogoStorageService",
    "MAX_FILE_BYTES",
    "MAX_FILE_SIZE_MB",
    "S3DocumentStorageService",
    "S3LogoStorageService",
    "StoredDocument",
    "StoredLogo",
    "build_logo_storage_key",
    "build_storage_key",
    "compute_checklist_completeness",
    "document_storage_bucket",
    "document_storage_endpoint_url",
    "document_storage_key_prefix",
    "document_storage_region",
    "get_document_storage",
    "get_logo_storage",
    "reset_document_storage",
    "reset_logo_storage",
    "set_document_storage",
    "set_logo_storage",
    "validate_file_size",
    "validate_file_type",
    "validate_logo_file_size",
    "validate_logo_file_type",
]
