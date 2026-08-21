"""Counselor auto-assignment service (E19; Journey J12).

Round-robin assignment of a new application to a counselor within the
application's branch, so applications are distributed evenly across the branch's
active counselors. Implemented as *least-loaded* selection: each new application
goes to the branch counselor with the fewest current assignments (ties broken by
lowest user id for determinism). Over K counselors and N applications the loads
differ by at most one, which is exactly round-robin distribution.

The service is a pure selection function (no commit); the caller (#151, on
application creation) persists ``assigned_counselor_id``.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.user import User
from app.rbac.roles import Role


def assign_counselor_round_robin(
    db: Session,
    *,
    tenant_id: int,
    branch_id: int | None,
) -> int | None:
    """Return the id of the counselor who should take the next application in this
    branch, or ``None`` when the branch has no active counselor (or no branch).

    Only active ``COUNSELOR`` users in the same tenant + branch are eligible.
    """
    if branch_id is None:
        return None

    counselors = db.scalars(
        select(User).where(
            User.tenant_id == tenant_id,
            User.branch_id == branch_id,
            User.role == Role.COUNSELOR,
            User.is_active.is_(True),
        )
    ).all()
    if not counselors:
        return None

    load_rows = db.execute(
        select(Application.assigned_counselor_id, func.count())
        .where(
            Application.tenant_id == tenant_id,
            Application.branch_id == branch_id,
            Application.assigned_counselor_id.is_not(None),
        )
        .group_by(Application.assigned_counselor_id)
    ).all()
    loads = {counselor_id: count for counselor_id, count in load_rows}

    # Least-loaded first; lowest id breaks ties -> deterministic round-robin.
    return min(counselors, key=lambda user: (loads.get(user.id, 0), user.id)).id
