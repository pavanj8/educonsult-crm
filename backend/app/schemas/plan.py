"""Pydantic schemas for plan and usage endpoints (E45; Journey J38).

* E45 task #221 (this ticket) owns the ``PlanAndUsageResponse``
  schema and the ``GET /me/plan-usage`` endpoint that returns it.
* The plan detail shape reuses :class:`PlanResponse` from
  ``app.schemas.tenant`` (E9 task #106).
"""

from pydantic import BaseModel, ConfigDict

from app.schemas.tenant import PlanResponse


class TenantUsage(BaseModel):
    """Current usage counts for a tenant's resources (E45; Journey J38).

    Reflects the current consumption against the plan's limits:
    * ``branches`` -- number of branches created by this tenant.
    * ``staff`` -- number of staff accounts (non-student users).
    * ``students`` -- number of student accounts.
    """

    branches: int
    staff: int
    students: int


class PlanAndUsageResponse(BaseModel):
    """Combined plan and usage response for a tenant (E45; Journey J38).

    Returned by ``GET /me/plan-usage``. Includes the tenant's assigned
    plan (tier details and limits) and current usage counts. If no plan
    has been assigned to the tenant yet, ``plan`` is ``null`` and the
    frontend displays a "contact platform admin" message.
    """

    model_config = ConfigDict(from_attributes=True)

    plan: PlanResponse | None
    usage: TenantUsage


__all__ = ["PlanAndUsageResponse", "TenantUsage"]
