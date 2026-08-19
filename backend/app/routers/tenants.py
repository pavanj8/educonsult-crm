"""Tenant management routes (E8; Journey J1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.tenant import Tenant
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.tenant import TenantCreateRequest, TenantResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Tenant service is temporarily unavailable"


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
    """Create a new consultancy tenant (super admin only)."""
    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    try:
        db.commit()
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
