"""S3-compatible storage configuration (E27; Requirements §2).

All settings are read from environment variables so the same code
serves both the SaaS deployment (AWS S3 — no ``endpoint_url``) and
the on-prem / Docker Compose local-dev deployment (MinIO — explicit
``endpoint_url``).

Environment variables
---------------------

``DOCUMENT_STORAGE_BUCKET``
    Bucket name to write uploads into. Default ``educonsult-documents``.
``DOCUMENT_STORAGE_ENDPOINT_URL``
    Optional S3-compatible endpoint URL. Set this for MinIO
    (e.g. ``http://minio:9000``); leave unset for AWS S3.
``DOCUMENT_STORAGE_REGION``
    AWS region. Default ``us-east-1`` (boto3 default; safe for MinIO too).
``DOCUMENT_STORAGE_KEY_PREFIX``
    Prefix prepended to every object key. Default ``tenants``.

Credentials are sourced via the boto3 default chain
(``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` / instance role /
etc.) so the same config works for both AWS IAM roles on the SaaS
side and static credentials in the on-prem Docker Compose.
"""

from __future__ import annotations

import os

_DEFAULT_BUCKET = "educonsult-documents"
_DEFAULT_REGION = "us-east-1"
_DEFAULT_KEY_PREFIX = "tenants"


def document_storage_bucket() -> str:
    """Return the configured S3 bucket name (default ``educonsult-documents``)."""
    bucket = os.environ.get("DOCUMENT_STORAGE_BUCKET", _DEFAULT_BUCKET)
    return bucket.strip() or _DEFAULT_BUCKET


def document_storage_endpoint_url() -> str | None:
    """Return the S3-compatible endpoint URL, or ``None`` for real AWS S3.

    For MinIO, set ``DOCUMENT_STORAGE_ENDPOINT_URL=http://minio:9000``
    (no trailing slash; boto3 normalizes).
    """
    value = os.environ.get("DOCUMENT_STORAGE_ENDPOINT_URL")
    if value is None:
        return None
    stripped = value.strip().rstrip("/")
    return stripped or None


def document_storage_region() -> str:
    """Return the AWS region (default ``us-east-1``)."""
    return os.environ.get("DOCUMENT_STORAGE_REGION", _DEFAULT_REGION).strip() or _DEFAULT_REGION


def document_storage_key_prefix() -> str:
    """Return the key prefix prepended to every uploaded object key.

    Default ``tenants``. Trailing slashes are normalized away so the
    caller can compose the rest of the path freely.
    """
    prefix = os.environ.get("DOCUMENT_STORAGE_KEY_PREFIX", _DEFAULT_KEY_PREFIX)
    return prefix.strip().strip("/") or _DEFAULT_KEY_PREFIX