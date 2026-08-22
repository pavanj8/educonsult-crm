"""Authentication routes (E5; Journey J44)."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.auth import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from app.auth.email_uniqueness import (
    DUPLICATE_EMAIL_DETAIL,
    ensure_email_available,
    find_user_by_email,
)
from app.auth.master_data_validation import validate_target_master_data
from app.auth.password_policy import validate_password_strength
from app.auth.rate_limit import (
    ENDPOINT_FORGOT_PASSWORD,
    ENDPOINT_REGISTER_STUDENT,
    login_rate_limit,
    rate_limit,
)
from app.db.database import get_db
from app.email.password_reset import build_password_reset_url, send_password_reset_email
from app.email.service import EmailDeliveryError
from app.models.branch import Branch
from app.models.password_reset_token import PasswordResetToken
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
)
from app.schemas.student import RegisterStudentRequest, RegisterStudentResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Authentication service is temporarily unavailable"
_FORGOT_PASSWORD_GENERIC_MESSAGE = (
    "If an account exists for that email, a reset link has been sent."
)
_PASSWORD_RESET_TOKEN_TTL = timedelta(hours=1)
_INVALID_RESET_TOKEN_DETAIL = "Invalid or expired reset token"
_PASSWORD_RESET_GENERIC_MESSAGE = "Your password has been reset successfully."

# Rate-limit budgets (E7; Journey J46). Tuned to be tight enough to
# stop brute-force / credential-stuffing yet generous enough that the
# documented E2E flows (login, register, forgot password) still pass
# without hitting the cap.
_LOGIN_MAX_REQUESTS = 5
_LOGIN_WINDOW_SECONDS = 60
_REGISTER_STUDENT_MAX_REQUESTS = 5
_REGISTER_STUDENT_WINDOW_SECONDS = 60
_FORGOT_PASSWORD_MAX_REQUESTS = 5
_FORGOT_PASSWORD_WINDOW_SECONDS = 60


def _user_to_authenticated_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    _rate_limit: Annotated[  # noqa: B008 — FastAPI consumes the dep
        None,
        Depends(
            login_rate_limit(
                max_requests=_LOGIN_MAX_REQUESTS,
                window_seconds=_LOGIN_WINDOW_SECONDS,
            )
        ),
    ] = None,
) -> TokenResponse:
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


@router.post(
    "/register-student",
    response_model=RegisterStudentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit(
                ENDPOINT_REGISTER_STUDENT,
                max_requests=_REGISTER_STUDENT_MAX_REQUESTS,
                window_seconds=_REGISTER_STUDENT_WINDOW_SECONDS,
            )
        )
    ],
)
def register_student(
    payload: RegisterStudentRequest,
    db: Session = Depends(get_db),
) -> RegisterStudentResponse:
    """Public student self-registration with profile fields (E16; Journey J9)."""
    try:
        tenant = (
            db.query(Tenant)
            .filter(func.lower(Tenant.slug) == payload.tenant_slug)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    try:
        branch = db.get(Branch, payload.branch_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if branch is None or branch.tenant_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )

    ensure_email_available(db, payload.email, unavailable_detail=_DB_UNAVAILABLE_DETAIL)
    validate_target_master_data(db, tenant.id, payload)

    student_user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        name=payload.name,
        phone=payload.phone,
        date_of_birth=payload.date_of_birth,
        target_country_id=payload.target_country_id,
        target_university_id=payload.target_university_id,
        target_program_id=payload.target_program_id,
    )
    db.add(student_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EMAIL_DETAIL,
        ) from None
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(student_user)
    authenticated_user = _user_to_authenticated_user(student_user)
    return RegisterStudentResponse(
        id=student_user.id,
        email=student_user.email,
        role=student_user.role,
        tenant_id=student_user.tenant_id,
        branch_id=student_user.branch_id,
        name=student_user.name,
        phone=student_user.phone,
        date_of_birth=student_user.date_of_birth,
        target_country_id=student_user.target_country_id,
        target_university_id=student_user.target_university_id,
        target_program_id=student_user.target_program_id,
        access_token=create_access_token(authenticated_user),
        refresh_token=create_refresh_token(authenticated_user),
        created_at=student_user.created_at,
    )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    dependencies=[
        Depends(
            rate_limit(
                ENDPOINT_FORGOT_PASSWORD,
                max_requests=_FORGOT_PASSWORD_MAX_REQUESTS,
                window_seconds=_FORGOT_PASSWORD_WINDOW_SECONDS,
            )
        )
    ],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    """Issue a single-use password-reset token and email the reset link (E6; J45).

    Always returns the same generic response so callers cannot use the
    endpoint to enumerate which email addresses are registered (a basic
    account-enumeration defense). If no user matches the address, or
    the account is deactivated, the response is still 200 with the
    generic message and no email is sent.
    """
    try:
        user = find_user_by_email(db, payload.email)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if user is not None and user.is_active and user.tenant_id is not None:
        token_plain = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token_plain.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        reset_token = PasswordResetToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + _PASSWORD_RESET_TOKEN_TTL,
        )
        db.add(reset_token)
        try:
            db.commit()
        except OperationalError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_DB_UNAVAILABLE_DETAIL,
            ) from None

        reset_url = build_password_reset_url(token=token_plain)
        try:
            send_password_reset_email(to_email=user.email, reset_url=reset_url)
        except EmailDeliveryError:
            # The token row is already saved; rolling it back here would
            # let a user retry until the SMTP issue clears, but the
            # generic 200 response is the safer contract. We surface a
            # 503 instead so the caller knows delivery failed.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to send password reset email",
            ) from None

    return ForgotPasswordResponse(message=_FORGOT_PASSWORD_GENERIC_MESSAGE)


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    """Validate a reset token and set the user's new password (E6; J45).

    Companion to ``POST /auth/forgot-password``: the user clicks the link
    in their reset email and POSTs ``{token, new_password}`` here. The
    endpoint:

    * Hashes the supplied token with SHA-256 and looks up the matching
      ``PasswordResetToken`` row by ``token_hash``.
    * Rejects tokens that don't exist, have already been consumed, or
      are past their ``expires_at`` -- all with the same generic 400
      response so the caller cannot probe token state (matches the
      account-enumeration hygiene of the forgot-password endpoint).
    * Validates the new password against the platform strong-password
      policy (Requirements §8) before persisting.
    * Updates the matched ``User.password_hash`` and stamps the token's
      ``used_at`` to make it single-use.
    * Returns 503 if the database is unreachable.

    The token is matched by its SHA-256 hash because the database only
    ever stores the hash, never the plaintext (see ``PasswordResetToken``).
    """
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()

    try:
        reset_token = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.token_hash == token_hash)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    now = datetime.now(timezone.utc)

    if reset_token is None or reset_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_INVALID_RESET_TOKEN_DETAIL,
        )

    stored_expires_at = reset_token.expires_at
    if stored_expires_at.tzinfo is None:
        stored_expires_at = stored_expires_at.replace(tzinfo=timezone.utc)
    if stored_expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_INVALID_RESET_TOKEN_DETAIL,
        )

    try:
        user = db.get(User, reset_token.user_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if user is None or not user.is_active:
        # The user record was deleted or deactivated after the token was
        # issued. Treat as an invalid token -- the caller can request a
        # fresh reset if appropriate.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_INVALID_RESET_TOKEN_DETAIL,
        )

    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = now

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    return ResetPasswordResponse(message=_PASSWORD_RESET_GENERIC_MESSAGE)


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
