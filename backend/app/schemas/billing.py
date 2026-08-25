"""Pydantic schemas for billing endpoints (E46; Journey J39).

<<<<<<< HEAD
Webhook schemas for Razorpay payment confirmation.
=======
* E46 task #223 (this ticket) owns ``CreateUpgradeOrderRequest`` and
  ``UpgradeOrderResponse`` for the plan upgrade order creation endpoint.
* E46 task #224 will own webhook schemas for payment confirmation.
* E46 task #225 will own the plan change confirmation schema.
>>>>>>> origin/main
"""

from pydantic import BaseModel, Field


<<<<<<< HEAD
class WebhookErrorResponse(BaseModel):
    """Response returned when webhook validation fails."""

    detail: str = Field(description="Error message describing why the webhook was rejected")


__all__ = ["WebhookErrorResponse"]
=======
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


__all__ = ["CreateUpgradeOrderRequest", "UpgradeOrderResponse"]
>>>>>>> origin/main
