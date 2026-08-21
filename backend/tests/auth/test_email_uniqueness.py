"""Unit tests for email uniqueness validation (E16; issue #137)."""

import pytest
from fastapi import HTTPException

from app.auth.email_uniqueness import (
    DUPLICATE_EMAIL_DETAIL,
    ensure_email_available,
    find_user_by_email,
)
from app.rbac.roles import Role
from tests.factories.users import make_db_user


def test_find_user_by_email_is_case_insensitive(db_session):
    make_db_user(db_session, Role.COUNSELOR, email="Staff@Example.test", tenant_id=1)

    found = find_user_by_email(db_session, "  staff@example.test  ")

    assert found is not None
    assert found.email == "Staff@Example.test"


def test_ensure_email_available_passes_for_new_email(db_session):
    ensure_email_available(
        db_session,
        "new.user@example.test",
        unavailable_detail="service unavailable",
    )


def test_ensure_email_available_raises_conflict_for_existing_email(db_session):
    make_db_user(db_session, Role.STUDENT, email="taken@example.test", tenant_id=1)

    with pytest.raises(HTTPException) as exc_info:
        ensure_email_available(
            db_session,
            "taken@example.test",
            unavailable_detail="service unavailable",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == DUPLICATE_EMAIL_DETAIL


def test_ensure_email_available_raises_conflict_for_case_insensitive_match(db_session):
    make_db_user(db_session, Role.STUDENT, email="Taken@Example.test", tenant_id=1)

    with pytest.raises(HTTPException) as exc_info:
        ensure_email_available(
            db_session,
            "  TAKEN@example.test  ",
            unavailable_detail="service unavailable",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == DUPLICATE_EMAIL_DETAIL
