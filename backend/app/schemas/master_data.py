"""Pydantic schemas for master-data endpoints (E14; Journey J7).

This module defines the schemas for both:

* the public tenant-scoped master-data list endpoints used by the
  registration and application dropdowns (no auth; ``/tenants/{slug}/...``),
  and
* the admin-scoped CRUD endpoints used by consultancy owners and
  branch managers to maintain the same lists
  (``/master-data/admin/...``, gated by ``master_data:manage``).

The response shapes are deliberately shared between the public and
admin endpoints so the frontend can render the same ``MasterData``
types on either side (Journey J7 — Owner/Branch Manager manages master
data; Journey J9 — structured dropdowns).
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CountryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    code: str


class UniversityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    country_id: int
    name: str


class ProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    university_id: int
    name: str


class CountryCreateRequest(BaseModel):
    """Payload for ``POST /master-data/admin/countries`` (E14; Journey J7).

    Tenant id is taken from the authenticated caller; the body never
    carries it. ``name`` and ``code`` are required, stripped of
    surrounding whitespace, and rejected when blank.
    """

    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=10)

    @field_validator("name", "code")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped


class CountryUpdateRequest(BaseModel):
    """Payload for ``PATCH /master-data/admin/countries/{country_id}``."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("name", "code")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped


class UniversityCreateRequest(BaseModel):
    """Payload for ``POST /master-data/admin/universities``."""

    country_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped


class UniversityUpdateRequest(BaseModel):
    """Payload for ``PATCH /master-data/admin/universities/{university_id}``.

    Both fields are optional; when both are omitted the endpoint
    rejects the request with 422. Setting ``country_id`` to an id from
    another tenant (or to a country that does not exist) yields 422
    because the row is unresolvable inside the caller's tenant.
    """

    country_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped


class ProgramCreateRequest(BaseModel):
    """Payload for ``POST /master-data/admin/programs``."""

    university_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped


class ProgramUpdateRequest(BaseModel):
    """Payload for ``PATCH /master-data/admin/programs/{program_id}``."""

    university_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped
