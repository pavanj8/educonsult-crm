"""Authentication routes (E5; Journey J44)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.db.database import get_db
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.user import AuthenticatedUser
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Authentication service is temporarily unavailable"


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
    try:
        user = (
            db.query(User)
            .filter(func.lower(User.email) == normalized_email)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    authenticated_user = _user_to_authenticated_user(user)
    return TokenResponse(
        access_token=create_access_token(authenticated_user),
        refresh_token=create_refresh_token(authenticated_user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange a valid refresh token for new JWT access and refresh tokens."""
    try:
        token_user = verify_refresh_token(payload.refresh_token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        ) from None
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from None

    try:
        user = db.get(User, token_user.id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    authenticated_user = _user_to_authenticated_user(user)
    return TokenResponse(
        access_token=create_access_token(authenticated_user),
        refresh_token=create_refresh_token(authenticated_user),
    )


@router.get("/me", response_model=MeResponse)
def me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> MeResponse:
    """Return the authenticated user's profile for session hydration."""
    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )
