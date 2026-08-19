"""Staff management routes (E12; Journey J5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.db.database import get_db
from app.models.branch import Branch
from app.models.user import User
from app.rbac import Permission, RoleHierarchyError, assert_can_act_on_user
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.staff import StaffCreateRequest, StaffResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Staff service is temporarily unavailable"

_CREATABLE_STAFF_ROLES = frozenset(
    {
        Role.BRANCH_MANAGER,
        Role.COUNSELOR,
        Role.DOCUMENT_VERIFIER,
        Role.VISA_PROCESSOR,
        Role.RECEPTIONIST,
    }
)


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
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_staff(
    payload: StaffCreateRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.STAFF_CREATE))
    ],
    db: Session = Depends(get_db),
) -> User:
    """Create a staff account with role and branch assignment (owner or branch manager)."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if payload.role not in _CREATABLE_STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid staff role",
        )

    _get_tenant_branch(payload.branch_id, current_user, db)

    try:
        assert_can_act_on_user(
            current_user,
            target_role=payload.role,
            target_tenant_id=current_user.tenant_id,
            target_branch_id=payload.branch_id,
        )
    except RoleHierarchyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None

    try:
        existing_user = (
            db.query(User)
            .filter(func.lower(User.email) == payload.email)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    staff_user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        tenant_id=current_user.tenant_id,
        branch_id=payload.branch_id,
    )
    db.add(staff_user)

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

    db.refresh(staff_user)
    return staff_user
