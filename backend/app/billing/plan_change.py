"""Apply plan change on confirmed payment (E46 task #225; Journey J39).

This module provides the core business logic for applying a subscription
plan change when a Razorpay payment is confirmed. It is called by the
webhook handler (task #224) after verifying the payment webhook signature.

The plan change logic validates the webhook payload, checks that the
target plan exists and is active, and updates the tenant's plan_id
reference atomically within a database transaction.

Security considerations
-----------------------

* The webhook is verified by task #224 before calling this service.
* The tenant_id in the webhook notes must match the authenticated payment
  flow (validated by webhook signature verification).
* The plan_code is validated against the catalog to ensure only
  legitimate, active plans can be applied.
* Idempotency: applying the same plan multiple times (e.g., duplicate
  webhook delivery) is safe -- the tenant.plan_id is updated to the
  same value.

Error handling
--------------

* ``TenantNotFound`` -- tenant_id from webhook doesn't exist.
* ``PlanNotFound`` -- plan_code doesn't exist in the catalog.
* ``PlanInactive`` -- plan exists but is not active (retired).
* ``DatabaseError`` -- transaction conflict or database error.

These exceptions are raised as domain errors for the webhook handler
to translate into appropriate HTTP responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import DatabaseError, SQLAlchemyError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class BillingError(Exception):
    """Base exception for billing domain errors."""

    pass


class TenantNotFound(BillingError):
    """Tenant from webhook notes not found."""

    def __init__(self, tenant_id: int | str) -> None:
        self.tenant_id = int(tenant_id)
        super().__init__(f"Tenant {self.tenant_id} not found")


class PlanNotFound(BillingError):
    """Plan from webhook notes not found."""

    def __init__(self, plan_code: str) -> None:
        self.plan_code = plan_code
        super().__init__(f"Plan '{plan_code}' not found")


class PlanInactive(BillingError):
    """Plan from webhook notes is inactive (retired)."""

    def __init__(self, plan_code: str) -> None:
        self.plan_code = plan_code
        super().__init__(f"Plan '{plan_code}' is no longer active")


@dataclass(frozen=True)
class PlanChangeResult:
    """Result of a successful plan change operation.

    Attributes:
        tenant_id: The tenant whose plan was changed.
        previous_plan_id: The previous plan ID (None if tenant had no plan).
        new_plan_id: The new plan ID that was applied.
        plan_code: The plan tier code (starter, growth, enterprise).
    """

    tenant_id: int
    previous_plan_id: int | None
    new_plan_id: int
    plan_code: str


def apply_plan_change(
    db: Session,
    tenant_id: int | str,
    plan_code: str,
) -> PlanChangeResult:
    """Apply a plan change to a tenant after confirmed payment.

    This function is called by the webhook handler after verifying
    the Razorpay webhook signature and confirming payment capture.
    It updates the tenant's plan_id reference within a transaction.

    Args:
        db: SQLAlchemy database session (will be committed by caller).
        tenant_id: The tenant ID from the webhook notes.
        plan_code: The target plan tier code from the webhook notes.

    Returns:
        A ``PlanChangeResult`` containing the tenant ID, previous plan ID,
        new plan ID, and plan code.

    Raises:
        TenantNotFound: If the tenant doesn't exist.
        PlanNotFound: If the plan code doesn't exist in the catalog.
        PlanInactive: If the plan exists but is inactive.
        DatabaseError: If a database error occurs (transaction conflict).
    """
    from app.models.plan import Plan, PlanTier
    from app.models.tenant import Tenant

    # Convert tenant_id to int (from webhook string)
    tenant_id_int = int(tenant_id)

    # Normalize plan_code to lowercase for lookup
    plan_code_normalized = plan_code.strip().lower()

    # Validate plan_code is a valid PlanTier enum value
    try:
        plan_tier = PlanTier(plan_code_normalized)
    except ValueError:
        raise PlanNotFound(plan_code_normalized) from None

    # Resolve the plan from the catalog
    plan = db.execute(
        select(Plan).filter_by(code=plan_tier)
    ).scalar_one_or_none()

    if plan is None:
        raise PlanNotFound(plan_code_normalized)

    if not plan.is_active:
        raise PlanInactive(plan_code_normalized)

    # Resolve the tenant
    tenant = db.execute(
        select(Tenant).filter_by(id=tenant_id_int)
    ).scalar_one_or_none()

    if tenant is None:
        raise TenantNotFound(tenant_id_int)

    # Store previous plan_id for result
    previous_plan_id = tenant.plan_id

    # Update the tenant's plan reference
    tenant.plan_id = plan.id

    try:
        db.flush()  # Flush to validate constraints before commit
    except SQLAlchemyError as e:
        # Transaction conflict or constraint violation
        raise DatabaseError(f"Failed to apply plan change: {e}") from e

    return PlanChangeResult(
        tenant_id=tenant_id_int,
        previous_plan_id=previous_plan_id,
        new_plan_id=plan.id,
        plan_code=plan.code.value,
    )


__all__ = [
    "apply_plan_change",
    "PlanChangeResult",
    "BillingError",
    "TenantNotFound",
    "PlanNotFound",
    "PlanInactive",
]
