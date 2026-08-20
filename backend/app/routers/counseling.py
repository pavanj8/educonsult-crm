"""Counseling routes (E21, Journey J14).

GET /counseling/queue — returns applications assigned to the logged-in counselor.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import Application
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.application import ApplicationQueueItem

router = APIRouter()


@router.get("/queue", response_model=list[ApplicationQueueItem])
def get_counseling_queue(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.APPLICATION_READ_ASSIGNED))
    ],
    db: Session = Depends(get_db),
    stage: str | None = Query(default=None, description="Filter by application stage (case-insensitive)"),
    student_name: str | None = Query(
        default=None,
        description="Filter by student name (case-insensitive, partial match)",
    ),
) -> list[Application]:
    """Return applications assigned to the current counselor.

    The result is scoped to:
    - the caller's tenant,
    - the caller's branch,
    - applications where assigned_counselor_id == current_user.id.
    """
    if current_user.tenant_id is None or current_user.branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    statement = (
        select(Application)
        .where(Application.tenant_id == current_user.tenant_id)
        .where(Application.branch_id == current_user.branch_id)
        .where(Application.assigned_counselor_id == current_user.id)
        .order_by(Application.id)
    )

    if stage is not None:
        statement = statement.where(func.lower(Application.stage) == stage.lower())

    if student_name is not None:
        statement = statement.where(
            func.lower(Application.student_name).contains(student_name.lower())
        )

    return list(db.scalars(statement).all())
