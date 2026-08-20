"""Email uniqueness validation for user registration (E16; issue #137).

Email uniqueness is scoped per tenant (docs/requirements.md §1 — every table
carries ``tenant_id``; the same identifier in different tenants is
independent). ``find_user_by_email`` and ``ensure_email_available`` accept
an optional ``tenant_id`` keyword argument so that:

* Registration can check uniqueness within the resolved tenant only (the
  tenant-scoped case required by J9 / E16).
* Login can perform a global email lookup (no tenant filter), preserving
  the existing single-account-per-email behaviour for any role.

When ``tenant_id`` is provided, a ``NULL`` tenant_id means the user row is
a platform-level account (e.g. ``super_admin``) — those rows are excluded
from the scoped lookup because their ``tenant_id`` does not match any
non-null tenant id.
"""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.user import User

DUPLICATE_EMAIL_DETAIL = "A user with this email already exists"


def find_user_by_email(
    db: Session,
    email: str,
    *,
    tenant_id: int | None = None,
) -> User | None:
    """Return an existing user with the same email (case-insensitive), if any.

    When ``tenant_id`` is provided, only users belonging to that tenant are
    considered; platform-level rows (``tenant_id IS NULL``) are excluded so
    a student registering in tenant A does not collide with a
    ``super_admin`` (or any other NULL-tenant row) sharing the same email.
    """
    normalized_email = email.strip().lower()
    query = db.query(User).filter(func.lower(User.email) == normalized_email)
    if tenant_id is not None:
        query = query.filter(User.tenant_id == tenant_id)
    return query.one_or_none()


def ensure_email_available(
    db: Session,
    email: str,
    *,
    unavailable_detail: str,
    tenant_id: int | None = None,
) -> None:
    """Raise HTTP 409 if the email is already registered; 503 if DB is unavailable.

    ``tenant_id`` follows the same convention as :func:`find_user_by_email`:
    when provided, uniqueness is scoped to that tenant so that the same
    email may legitimately be reused across different consultancies.
    """
    try:
        existing_user = find_user_by_email(db, email, tenant_id=tenant_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=unavailable_detail,
        ) from None

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EMAIL_DETAIL,
        )
