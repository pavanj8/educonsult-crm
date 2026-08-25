"""Pydantic schemas for tenant management endpoints (E8; Journey J1; E10 branding; E9 plan assignment).

* E10 task #109 owns the three new columns on ``Tenant``
  (``logo_url`` / ``brand_color`` / ``currency``) and surfaces them
  on ``TenantResponse``.
* E10 task #110 owns ``TenantBrandingUpdateRequest`` and the
  ``PATCH /tenants/{id}/branding`` endpoint that consumes it.
* E10 task #111 owns the separate logo-upload endpoint and the
  storage backend that hands back a signed URL for ``logo_url``.
* E9 task #106 owns the ``PlanResponse`` / ``AssignPlanRequest``
  schemas and the ``POST /tenants/{id}/plan`` super-admin
  assign/change-plan endpoint (Journey J2; Requirements §4
  Billing & Subscription). The plan catalog itself (the rows) is
  defined by E9 task #105; this module only ships the wire shape.
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.i18n.currency import InvalidCurrencyCodeError, normalize_currency_code
from app.models.plan import PlanTier

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Canonical CSS hex colour: leading "#", exactly six lowercase or uppercase hex digits.
_BRAND_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
# The logo URL is the opaque object key returned by the E10 task #111
# logo-upload endpoint. The endpoint runs against S3/MinIO whose URLs
# are https:// — accepting ``http://`` here would let a JWT-compromised
# owner downgrade their tenant's logo to a mixed-content / cleartext
# URL. The schema therefore requires ``https://`` and leaves any
# deeper host allow-listing (e.g. pinning to the configured bucket
# CName) to the upload endpoint that produces the key.
_LOGO_URL_PATTERN = re.compile(r"^https://.+", re.IGNORECASE)


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


class PlanResponse(BaseModel):
    """Wire shape for a row in the platform-level plans catalog (E9; Journey J2).

    Mirrors :class:`app.models.plan.Plan` -- the stable string tier
    code (the wire value, not the enum member), the display name, the
    per-tier limit columns, and the ``is_active`` retirement flag.
    The full description is intentionally omitted from the default
    shape to keep the cross-tenant list endpoint payload small; the
    plan-detail UI in E45 / J38 is a future ticket.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: PlanTier
    name: str
    max_branches: int | None
    max_staff: int | None
    max_students: int | None
    is_active: bool


class AssignPlanRequest(BaseModel):
    """Request body for ``POST /tenants/{id}/plan`` (E9 task #106; Journey J2).

    The super admin supplies the stable tier code from
    :class:`PlanTier`; the endpoint resolves it against the plans
    catalog. The accepted values match the on-disk ``plans.code``
    column exactly so the wire format and the storage format stay in
    sync. Whitespace is stripped and the value is lower-cased to
    tolerate the case a JSON client might use.
    """

    plan_code: str = Field()

    @field_validator("plan_code", mode="before")
    @classmethod
    def _normalize_plan_code(cls, value: Any) -> str:
        if value is None:
            raise ValueError("plan_code must not be null")
        if not isinstance(value, str):
            raise ValueError("plan_code must be a string")
        candidate = value.strip().lower()
        if not candidate:
            raise ValueError("plan_code must not be empty")
        if len(candidate) > 32:
            raise ValueError("plan_code must be one of: enterprise, growth, starter")
        valid_codes = {member.value for member in PlanTier}
        if candidate not in valid_codes:
            raise ValueError(
                f"plan_code must be one of: {', '.join(sorted(valid_codes))}"
            )
        return candidate


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    logo_url: str | None = None
    brand_color: str | None = None
    # E10 task #109: ``currency`` is NOT NULL on the row (server default
    # ``"INR"``) and is therefore always populated on the response.
    currency: str
    # E9 task #106: populated via the SQLAlchemy ``Tenant.plan``
    # relationship after the assignment endpoint opts in with
    # ``selectinload``; this keeps ordinary tenant queries unjoined.
    plan: PlanResponse | None = None
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
      endpoint (#111). The schema accepts any ``https://`` URL so that
      a freshly-issued signed S3/MinIO URL is accepted without the
      logo-upload endpoint having to round-trip through Pydantic
      again.
    * ``brand_color`` -- canonical CSS hex form ``#RRGGBB`` (case
      insensitive on input; stored as the caller-supplied case).
    * ``currency`` -- ISO 4217 three-letter code; whitespace is
      stripped and the result upper-cased. Validation is delegated to
      :func:`app.i18n.currency.normalize_currency_code` so the PATCH
      endpoint and the E52 currency formatter stay in lock-step. The
      underlying ``tenants.currency`` column is NOT NULL with server
      default ``"INR"`` (E10 task #109 contract); the field is
      therefore *optional* but, when supplied, MUST be a non-empty
      ISO 4217 code -- an explicit ``null`` or empty-string payload
      value is rejected as a 422 so the caller cannot use the PATCH
      to silently clear the column. The router's
      ``model_dump(exclude_unset=True)`` already drops an *omitted*
      field, so omitting ``currency`` cleanly means "do not change".
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
            raise ValueError("Logo URL must be an https:// URL")
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
            # Explicit ``null`` from the caller is rejected: the
            # underlying column is NOT NULL (E10 task #109) and the
            # PATCH endpoint must not silently clear it. An *omitted*
            # ``currency`` is fine because Pydantic then uses the
            # default ``None`` which ``model_dump(exclude_unset=True)``
            # strips out before the row is touched.
            raise ValueError("Currency must not be null")
        if not isinstance(value, str):
            raise ValueError("Currency must be a string")
        candidate = value.strip()
        if not candidate:
            # Empty / whitespace-only strings are rejected for the
            # same reason as explicit ``null`` -- they would corrupt
            # the NOT NULL column if the field validator allowed them
            # through to ``setattr(tenant, "currency", ...)``.
            raise ValueError("Currency must not be empty")
        try:
            return normalize_currency_code(candidate)
        except InvalidCurrencyCodeError as exc:
            raise ValueError(str(exc)) from exc


class UsageSummary(BaseModel):
    """Current usage counts for a tenant's resources (E45; Journey J38).

    Surface the actual counts of branches, staff, and students used by
    a tenant. The owner plan-usage page consumes this to render
    progress bars against the plan's caps.

    All counts are non-negative integers. The ``unlimited`` flag on
    each resource indicates whether the plan has ``NULL`` for that
    cap (Enterprise tier) -- the owner UI should show "Unlimited"
    instead of a number.
    """

    branches_used: int = Field(ge=0, description="Current number of branches")
    branches_limit: int | None = Field(
        default=None, description="Plan cap for branches (null = unlimited)"
    )
    staff_used: int = Field(ge=0, description="Current number of staff accounts")
    staff_limit: int | None = Field(
        default=None, description="Plan cap for staff (null = unlimited)"
    )
    students_used: int = Field(ge=0, description="Current number of student accounts")
    students_limit: int | None = Field(
        default=None, description="Plan cap for students (null = unlimited)"
    )


class PlanAndUsageResponse(BaseModel):
    """Combined plan and current usage summary for a tenant (E45; Journey J38).

    Returned by ``GET /tenants/me/plan-usage`` for a consultancy owner
    to view their current subscription tier and how many of the plan's
    resources they are consuming.

    Fields:
    * ``plan`` -- the tenant's assigned plan row, or ``None`` if no
      plan has been assigned yet (the owner UI should prompt the owner
      to contact the platform in this case).
    * ``usage`` -- the actual counts of branches/staff/students used
      by the tenant, compared against the plan's limits.
    """

    plan: PlanResponse | None = Field(
        default=None, description="The tenant's assigned subscription plan"
    )
    usage: UsageSummary = Field(description="Current usage counts against plan caps")
