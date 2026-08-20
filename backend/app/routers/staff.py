"""Staff management routes (E12; Journey J5; E13; Journey J6)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.db.branch_scope import BranchScopeError, apply_branch_scope
from app.db.database import get_db
from app.models.branch import Branch
from app.models.user import User
from app.rbac import Permission, RoleHierarchyError, assert_can_act_on_user
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.staff import StaffCreateRequest, StaffResponse, StaffUpdateRequest

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

_STAFF_ACCOUNT_ROLES = _CREATABLE_STAFF_ROLES


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


def _get_staff_member(
    staff_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> User:
    """Load a staff account the caller may read or update, or raise 404/403."""
    try:
        staff_user = db.get(User, staff_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if (
        staff_user is None
        or staff_user.role not in _STAFF_ACCOUNT_ROLES
        or staff_user.tenant_id is None
        or (
            current_user.tenant_id is not None
            and staff_user.tenant_id != current_user.tenant_id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )

    try:
        assert_can_act_on_user(
            current_user,
            target_role=staff_user.role,
            target_tenant_id=staff_user.tenant_id,
            target_branch_id=staff_user.branch_id,
        )
    except RoleHierarchyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None

    return staff_user


def _assert_can_assign_staff(
    current_user: AuthenticatedUser,
    *,
    role: Role,
    branch_id: int,
) -> None:
    if role not in _CREATABLE_STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid staff role",
        )

    try:
        assert_can_act_on_user(
            current_user,
            target_role=role,
            target_tenant_id=current_user.tenant_id,
            target_branch_id=branch_id,
        )
    except RoleHierarchyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None


@router.get("", response_model=list[StaffResponse])
def list_staff(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.STAFF_READ))
    ],
    db: Session = Depends(get_db),
) -> list[User]:
    """List staff accounts visible to the caller within their tenant/branch scope."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        statement = (
            select(User)
            .where(User.role.in_(_STAFF_ACCOUNT_ROLES))
            .where(User.tenant_id == current_user.tenant_id)
            .order_by(User.id)
        )
        statement = apply_branch_scope(statement, User, current_user)
        return list(db.scalars(statement).all())
    except BranchScopeError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/{staff_id}", response_model=StaffResponse)
def get_staff(
    staff_id: int,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.STAFF_READ))
    ],
    db: Session = Depends(get_db),
) -> User:
    """Return a single staff account when the caller may view it."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return _get_staff_member(staff_id, current_user, db)


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

    _assert_can_assign_staff(
        current_user,
        role=payload.role,
        branch_id=payload.branch_id,
    )
    _get_tenant_branch(payload.branch_id, current_user, db)

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


@router.patch("/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id: int,
    payload: StaffUpdateRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.STAFF_UPDATE))
    ],
    db: Session = Depends(get_db),
) -> User:
    """Update role and/or branch assignment for an existing staff account."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    staff_user = _get_staff_member(staff_id, current_user, db)

    new_role = update_data.get("role", staff_user.role)
    new_branch_id = update_data.get("branch_id", staff_user.branch_id)

    if new_branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Staff member must be assigned to a branch",
        )

    _get_tenant_branch(new_branch_id, current_user, db)
    _assert_can_assign_staff(
        current_user,
        role=new_role,
        branch_id=new_branch_id,
    )

    staff_user.role = new_role
    staff_user.branch_id = new_branch_id

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(staff_user)
    return staff_user


def _set_staff_active_status(
    staff_id: int,
    *,
    is_active: bool,
    current_user: AuthenticatedUser,
    db: Session,
) -> User:
    """Deactivate or reactivate a staff account when the caller has permission."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if staff_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change your own active status",
        )

    staff_user = _get_staff_member(staff_id, current_user, db)

    if staff_user.is_active == is_active:
        state = "active" if is_active else "inactive"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Staff member is already {state}",
        )

    staff_user.is_active = is_active

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(staff_user)
    return staff_user


@router.post("/{staff_id}/deactivate", response_model=StaffResponse)
def deactivate_staff(
    staff_id: int,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.STAFF_DEACTIVATE))
    ],
    db: Session = Depends(get_db),
) -> User:
    """Deactivate a staff account (owner or branch manager)."""
    return _set_staff_active_status(
        staff_id,
        is_active=False,
        current_user=current_user,
        db=db,
    )


@router.post("/{staff_id}/reactivate", response_model=StaffResponse)
def reactivate_staff(
    staff_id: int,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.STAFF_DEACTIVATE))
    ],
    db: Session = Depends(get_db),
) -> User:
    """Reactivate a previously deactivated staff account (owner or branch manager)."""
    return _set_staff_active_status(
        staff_id,
        is_active=True,
        current_user=current_user,
        db=db,
    )
