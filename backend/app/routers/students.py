"""Staff-created student records (E17; Journey J10)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.auth.email_uniqueness import ensure_email_available
from app.auth.password import hash_password
from app.db.database import get_db
from app.models.branch import Branch
from app.models.user import User
from app.rbac.dependencies import require_permission
from app.rbac.permissions import Permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.student import StaffCreateStudentRequest, StaffCreateStudentResponse

router = APIRouter()
_DB_UNAVAILABLE_DETAIL = "Student service is temporarily unavailable"


def _get_tenant_branch(branch_id: int, current_user: AuthenticatedUser, db: Session) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None or (
        current_user.tenant_id is not None and branch.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


@router.post("", response_model=StaffCreateStudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StaffCreateStudentRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.STUDENT_CREATE))
    ],
    db: Session = Depends(get_db),
) -> User:
    """Create a walk-in student record in the receptionist's tenant/branch."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    if current_user.branch_id is not None and payload.branch_id != current_user.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    _get_tenant_branch(payload.branch_id, current_user, db)
    ensure_email_available(
        db,
        payload.email,
        unavailable_detail=_DB_UNAVAILABLE_DETAIL,
    )
    student = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=Role.STUDENT,
        tenant_id=current_user.tenant_id,
        branch_id=payload.branch_id,
        name=payload.name,
        phone=payload.phone,
        date_of_birth=payload.date_of_birth,
        target_country_id=payload.target_country_id,
        target_university_id=payload.target_university_id,
        target_program_id=payload.target_program_id,
    )
    db.add(student)
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
    db.refresh(student)
    return student
