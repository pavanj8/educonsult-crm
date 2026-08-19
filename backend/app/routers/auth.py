"""Authentication routes (E5; Journey J44)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import create_access_token, create_refresh_token, verify_password
from app.db.database import get_db
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.user import AuthenticatedUser
from app.schemas.auth import LoginRequest, TokenResponse, UserMeResponse

router = APIRouter()


def _user_to_authenticated_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate with email and password; return JWT access and refresh tokens."""
    normalized_email = payload.email.strip().lower()
    user = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .one_or_none()
    )

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    authenticated_user = _user_to_authenticated_user(user)
    return TokenResponse(
        access_token=create_access_token(authenticated_user),
        refresh_token=create_refresh_token(authenticated_user),
    )


@router.get("/me", response_model=UserMeResponse)
def me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> UserMeResponse:
    """Return the authenticated user's profile from a valid access token."""
    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    return UserMeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )
