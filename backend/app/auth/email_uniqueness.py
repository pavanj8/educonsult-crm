"""Email uniqueness validation for user registration (E16; issue #137)."""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.user import User

DUPLICATE_EMAIL_DETAIL = "A user with this email already exists"


def find_user_by_email(db: Session, email: str) -> User | None:
    """Return an existing user with the same email (case-insensitive), if any."""
    normalized_email = email.strip().lower()
    return (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .one_or_none()
    )


def ensure_email_available(
    db: Session,
    email: str,
    *,
    unavailable_detail: str,
) -> None:
    """Raise HTTP 409 if the email is already registered; 503 if DB is unavailable."""
    try:
        existing_user = find_user_by_email(db, email)
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
