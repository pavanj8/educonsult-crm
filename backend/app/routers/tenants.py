"""Tenant management routes (E8; Journey J1)."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.db.database import get_db
from app.email.owner_invite import send_owner_invite_email
from app.email.service import EmailDeliveryError
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.tenant import TenantCreateRequest, TenantResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Tenant service is temporarily unavailable"
_EMAIL_UNAVAILABLE_DETAIL = "Unable to send owner invite email"


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant(
    payload: TenantCreateRequest,
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_CREATE))
    ],
    db: Session = Depends(get_db),
) -> Tenant:
    """Create a new consultancy tenant and invite its owner (super admin only)."""
    try:
        existing_owner = (
            db.query(User)
            .filter(func.lower(User.email) == payload.owner_email)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if existing_owner is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with this slug already exists",
        ) from None
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    temporary_password = secrets.token_urlsafe(16)
    owner = User(
        email=payload.owner_email,
        password_hash=hash_password(temporary_password),
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant.id,
        branch_id=None,
    )
    db.add(owner)

    try:
        send_owner_invite_email(
            to_email=payload.owner_email,
            tenant_name=payload.name,
            temporary_password=temporary_password,
        )
    except EmailDeliveryError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_EMAIL_UNAVAILABLE_DETAIL,
        ) from None

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from None
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(tenant)
    return tenant


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_READ))
    ],
    db: Session = Depends(get_db),
) -> list[Tenant]:
    """List all consultancy tenants (super admin only)."""
    try:
        return db.query(Tenant).order_by(Tenant.id).all()
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_READ))
    ],
    db: Session = Depends(get_db),
) -> Tenant:
    """Retrieve a single consultancy tenant by id (super admin only)."""
    try:
        tenant = db.get(Tenant, tenant_id)
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

    return tenant
