"""Pydantic schemas for billing endpoints (E46; Journey J39).

* E46 task #223 owns ``CreateUpgradeOrderRequest`` and ``UpgradeOrderResponse``
  for the plan upgrade order creation endpoint.
* E46 task #224 owns webhook schemas for payment confirmation.
* E46 task #225 owns the plan change confirmation schema.
"""

from pydantic import BaseModel, Field


class CreateUpgradeOrderRequest(BaseModel):
    """Request body for ``POST /billing/create-upgrade-order`` (E46 task #223; Journey J39).

    The consultancy owner supplies the target plan tier code they want to
    upgrade or downgrade to. The endpoint validates the plan exists and
    is active, then creates a Razorpay order for the plan's price.

    Field semantics:
    * ``plan_code`` -- The target plan tier code (starter, growth, enterprise).
      Must be one of the three values from :class:`app.models.plan.PlanTier`.
      Whitespace is stripped and lower-cased for tolerance.
    """

    plan_code: str = Field(
        min_length=1,
        max_length=32,
        description="Target plan tier code (starter, growth, enterprise)",
    )


class UpgradeOrderResponse(BaseModel):
    """Response from ``POST /billing/create-upgrade-order`` (E46 task #223; Journey J39).

    Returns the Razorpay order details needed to initiate checkout on the
    frontend. The frontend uses these values to open the Razorpay payment
    modal.

    Fields:
    * ``order_id`` -- Razorpay order ID (e.g., ``order_123abc``). Used by
      the frontend to open the checkout and by the webhook to reconcile
      payments.
    * ``amount`` -- Order amount in smallest currency unit (paisa for INR).
      Matches the plan's ``price_in_cents`` value.
    * ``currency`` -- ISO 4217 currency code (e.g., ``INR``).
    * ``plan_code`` -- The target plan tier code for this upgrade/downgrade.
      Echoed back from the request for confirmation.
    * ``plan_name`` -- Human-readable plan name for display on the checkout
      confirmation screen.
    """

    order_id: str = Field(description="Razorpay order ID for checkout")
    amount: int = Field(description="Amount in smallest currency unit (paisa for INR)")
    currency: str = Field(description="ISO 4217 currency code")
    plan_code: str = Field(description="Target plan tier code")
    plan_name: str = Field(description="Human-readable plan name")


class PlanChangeResponse(BaseModel):
    """Response for successful plan change application (E46 task #225; Journey J39).

    Returned by the webhook handler after applying a plan change.
    This is primarily for logging and webhook acknowledgment; the
    tenant will see their updated plan on the next authenticated request.

    Fields:
    * ``tenant_id`` -- The tenant whose plan was changed.
    * ``previous_plan_id`` -- The previous plan ID (null if tenant had no plan).
    * ``new_plan_id`` -- The new plan ID that was applied.
    * ``plan_code`` -- The plan tier code (starter, growth, enterprise).
    """

    tenant_id: int = Field(description="Tenant whose plan was changed")
    previous_plan_id: int | None = Field(
        description="Previous plan ID (null if tenant had no plan)"
    )
    new_plan_id: int = Field(description="New plan ID that was applied")
    plan_code: str = Field(description="Plan tier code")


__all__ = [
    "CreateUpgradeOrderRequest",
    "UpgradeOrderResponse",
    "PlanChangeResponse",
]
