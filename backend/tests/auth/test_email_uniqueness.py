"""Unit tests for email uniqueness validation (E16; issue #137 + #140).

Per docs/requirements.md §1 the system is multi-tenant and "every table carries
a tenant_id"; the same identifier in different tenants is independent. Email
uniqueness is therefore scoped per tenant. ``find_user_by_email`` /
``ensure_email_available`` accept an optional ``tenant_id`` keyword argument
so registration can check uniqueness within the resolved tenant only while
login can still perform a global email lookup.
"""

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


def test_find_user_by_email_is_scoped_to_tenant_when_tenant_id_given(db_session):
    """Same email in a different tenant is independent (requirements §1)."""
    make_db_user(
        db_session,
        Role.STUDENT,
        email="shared@example.test",
        tenant_id=1,
    )

    # With tenant_id=2, the row in tenant 1 must NOT be returned.
    assert find_user_by_email(db_session, "shared@example.test", tenant_id=2) is None

    # With tenant_id=1, the row in tenant 1 IS returned.
    found = find_user_by_email(db_session, "shared@example.test", tenant_id=1)
    assert found is not None
    assert found.tenant_id == 1


def test_ensure_email_available_passes_when_email_exists_only_in_other_tenant(
    db_session,
):
    """An email used in another tenant is available for registration here."""
    make_db_user(
        db_session,
        Role.STUDENT,
        email="shared@example.test",
        tenant_id=1,
    )

    # No exception: tenant 2 sees the email as available.
    ensure_email_available(
        db_session,
        "shared@example.test",
        unavailable_detail="service unavailable",
        tenant_id=2,
    )


def test_ensure_email_available_raises_conflict_when_email_exists_in_same_tenant(
    db_session,
):
    """An email already used by someone in this tenant must still 409."""
    make_db_user(
        db_session,
        Role.STUDENT,
        email="shared@example.test",
        tenant_id=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        ensure_email_available(
            db_session,
            "shared@example.test",
            unavailable_detail="service unavailable",
            tenant_id=1,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == DUPLICATE_EMAIL_DETAIL


def test_find_user_by_email_excludes_null_tenant_rows_when_tenant_id_given(db_session):
    """A platform-level row (tenant_id IS NULL) must not collide with a tenant row."""
    make_db_user(
        db_session,
        Role.SUPER_ADMIN,
        email="super@example.test",
        tenant_id=None,
    )

    assert find_user_by_email(db_session, "super@example.test", tenant_id=1) is None
