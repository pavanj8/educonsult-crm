"""Counseling routes (E21, Journey J14).

GET /counseling/queue — returns applications assigned to the logged-in counselor.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.application import (
    APPLICATION_STAGES,
    VALID_APPLICATION_STAGES,
    Application,
)
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
    stage: str | None = Query(
        default=None,
        description="Filter by application stage (case-insensitive)",
        min_length=1,
        max_length=50,
    ),
    student_name: str | None = Query(
        default=None,
        description="Filter by student name (case-insensitive, partial match)",
        min_length=1,
        max_length=255,
    ),
) -> list[ApplicationQueueItem]:
    """Return applications assigned to the current counselor.

    The result is scoped to:
    - the caller's tenant,
    - the caller's branch,
    - applications where assigned_counselor_id == current_user.id.

    Note on scoping approach: unlike branches.py which uses apply_tenant_scope,
    this router hand-rolls the full security boundary (tenant + branch + counselor).
    We do this because apply_tenant_scope only handles tenant-level filtering.
    For counselors, we need branch-level isolation (a counselor sees only applications
    in their own branch) plus the assigned_counselor_id filter. The manual filter is
    explicit and self-documenting for the security boundary. See ADR-0001/ADR-0004
    for the broader tenant-scoping strategy.
    """
    if current_user.tenant_id is None or current_user.branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    # Build the base query: tenant + branch + counselor scoping
    # (apply_tenant_scope handles only tenant-level filtering, so we
    # explicitly add branch and counselor scopes here for correctness)
    statement = (
        select(Application)
        .where(Application.tenant_id == current_user.tenant_id)
        .where(Application.branch_id == current_user.branch_id)
        .where(Application.assigned_counselor_id == current_user.id)
        .order_by(Application.id)
    )

    if stage is not None:
        stage_normalized = stage.lower()
        if stage_normalized not in VALID_APPLICATION_STAGES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "invalid_stage",
                    "allowed_values": list(APPLICATION_STAGES),
                },
            )
        statement = statement.where(func.lower(Application.stage) == stage_normalized)

    if student_name is not None:
        # Use autoescape=True so that user-supplied '%' and '_' characters
        # are treated as literals rather than LIKE wildcards.  Without this,
        # a '%' in the search string would match any substring, potentially
        # returning more results than expected and enabling slow broad scans.
        statement = statement.where(
            func.lower(Application.student_name).contains(student_name.lower(), autoescape=True)
        )

    return list(db.scalars(statement).all())
