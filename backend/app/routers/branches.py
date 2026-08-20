"""Branch management routes (E11; Journey J4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.branch import Branch
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.branch import BranchCreateRequest, BranchResponse, BranchUpdateRequest

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Branch service is temporarily unavailable"


def _get_tenant_branch(
    branch_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Branch:
    """Load a branch belonging to the caller's tenant, or raise 404."""
    try:
        branch = db.get(Branch, branch_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if branch is None or (
        current_user.tenant_id is not None
        and branch.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )

    return branch


@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    payload: BranchCreateRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.BRANCH_CREATE))
    ],
    db: Session = Depends(get_db),
) -> Branch:
    """Create a branch under the caller's tenant (consultancy owner only)."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    branch = Branch(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        city=payload.city,
    )
    db.add(branch)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(branch)
    return branch


@router.get("", response_model=list[BranchResponse])
def list_branches(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.BRANCH_READ))
    ],
    db: Session = Depends(get_db),
) -> list[Branch]:
    """List branches visible to the caller within their tenant."""
    try:
        statement = apply_tenant_scope(
            select(Branch).order_by(Branch.id),
            Branch,
            current_user,
        )
        return list(db.scalars(statement).all())
    except TenantScopeError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.patch("/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    payload: BranchUpdateRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.BRANCH_UPDATE))
    ],
    db: Session = Depends(get_db),
) -> Branch:
    """Update a branch within the caller's tenant (consultancy owner only)."""
    branch = _get_tenant_branch(branch_id, current_user, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    for field, value in update_data.items():
        setattr(branch, field, value)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(branch)
    return branch
