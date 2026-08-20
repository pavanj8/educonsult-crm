"""Pydantic schemas for student registration endpoints (E16; Journey J9)."""

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_password_strength,
)
from app.rbac.roles import Role

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_MIN_STUDENT_AGE_YEARS = 10
_MAX_STUDENT_AGE_YEARS = 80


class RegisterStudentRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=100)
    branch_id: int = Field(ge=1)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    date_of_birth: date
    target_country_id: int | None = Field(default=None, ge=1)
    target_university_id: int | None = Field(default=None, ge=1)
    target_program_id: int | None = Field(default=None, ge=1)

    @field_validator("tenant_slug")
    @classmethod
    def normalize_tenant_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Tenant slug must not be empty")
        if not _SLUG_PATTERN.match(normalized):
            raise ValueError(
                "Tenant slug must contain only lowercase letters, numbers, and hyphens"
            )
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Email must not be empty")
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Email must be a valid email address")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("name", "phone")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty")
        return stripped

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        today = date.today()
        if value >= today:
            raise ValueError("Date of birth must be in the past")

        age = today.year - value.year - (
            (today.month, today.day) < (value.month, value.day)
        )
        if age < _MIN_STUDENT_AGE_YEARS:
            raise ValueError(
                f"Student must be at least {_MIN_STUDENT_AGE_YEARS} years old"
            )
        if age > _MAX_STUDENT_AGE_YEARS:
            raise ValueError("Date of birth is not valid for a student")
        return value


class RegisterStudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
    tenant_id: int
    branch_id: int
    name: str
    phone: str
    date_of_birth: date
    target_country_id: int | None
    target_university_id: int | None
    target_program_id: int | None
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    created_at: datetime
