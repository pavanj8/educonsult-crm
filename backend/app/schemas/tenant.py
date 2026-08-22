<<<<<<< HEAD
"""Pydantic schemas for tenant management endpoints (E8; Journey J1; E10 branding)."""
=======
"""Pydantic schemas for tenant management endpoints (E8; Journey J1; E10 task #109)."""
>>>>>>> origin/main

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.i18n.currency import InvalidCurrencyCodeError, normalize_currency_code

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
<<<<<<< HEAD
# Canonical CSS hex colour: leading "#", exactly six lowercase or uppercase hex digits.
_BRAND_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Permissive logo-URL shape; stricter URL/HTTP scheme validation is left to the
# logo-upload endpoint (E10 ticket #111) which knows the storage backend.
_LOGO_URL_PATTERN = re.compile(r"^https?://.+", re.IGNORECASE)
=======
_BRAND_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
>>>>>>> origin/main


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100)
    owner_email: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name must not be empty")
        return stripped

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Slug must not be empty")
        if not _SLUG_PATTERN.match(normalized):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return normalized

    @field_validator("owner_email")
    @classmethod
    def normalize_owner_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Owner email must not be empty")
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Owner email must be a valid email address")
        return normalized


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    logo_url: str | None = None
    brand_color: str | None = None
<<<<<<< HEAD
    currency: str | None = None
=======
    currency: str
>>>>>>> origin/main
    created_at: datetime
    updated_at: datetime


class TenantBrandingUpdateRequest(BaseModel):
    """Partial update payload for ``PATCH /tenants/{id}/branding`` (E10, J3).

    Every field is optional; the endpoint applies only the fields the
    caller explicitly supplied (``model_dump(exclude_unset=True)``). At
    least one field must be present, otherwise the endpoint rejects the
    request as unprocessable.

    Field semantics:

    * ``logo_url`` -- opaque URL returned by the E10 logo-upload
      endpoint (#111). The schema accepts any string that looks like
      an ``http://`` / ``https://`` URL so that a freshly-issued signed
      S3/MinIO URL is accepted without the logo-upload endpoint having
      to round-trip through Pydantic again.
    * ``brand_color`` -- canonical CSS hex form ``#RRGGBB`` (case
      insensitive on input; stored as the caller-supplied case).
    * ``currency`` -- ISO 4217 three-letter code; whitespace is
      stripped and the result upper-cased. Validation is delegated to
      :func:`app.i18n.currency.normalize_currency_code` so the PATCH
      endpoint and the E52 currency formatter stay in lock-step.
    """

    logo_url: str | None = Field(default=None, max_length=2048)
    brand_color: str | None = Field(default=None, max_length=7)
    currency: str | None = Field(default=None, max_length=3)

    @field_validator("logo_url")
    @classmethod
    def _normalize_logo_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Logo URL must not be empty")
        if not _LOGO_URL_PATTERN.match(stripped):
            raise ValueError("Logo URL must be an http(s) URL")
        return stripped

    @field_validator("brand_color")
    @classmethod
    def _normalize_brand_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Brand color must not be empty")
        if not _BRAND_COLOR_PATTERN.match(stripped):
            raise ValueError("Brand color must be a #RRGGBB hex value")
        return stripped

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Currency must be a string")
        candidate = value.strip()
        if not candidate:
            raise ValueError("Currency must not be empty")
        try:
            return normalize_currency_code(candidate)
        except InvalidCurrencyCodeError as exc:
            raise ValueError(str(exc)) from exc
