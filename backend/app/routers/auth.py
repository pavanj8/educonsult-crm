"""Authentication routes (E5; Journey J44)."""

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
from app.auth.email_uniqueness import DUPLICATE_EMAIL_DETAIL, ensure_email_available
from app.auth.master_data_validation import validate_target_master_data
from app.db.database import get_db
from app.models.branch import Branch
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse
from app.schemas.student import RegisterStudentRequest, RegisterStudentResponse

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


@router.post(
    "/register-student",
    response_model=RegisterStudentResponse,
    status_code=status.HTTP_201_CREATED,
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

    ensure_email_available(
        db,
        payload.email,
        unavailable_detail=_DB_UNAVAILABLE_DETAIL,
        tenant_id=tenant.id,
    )
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
