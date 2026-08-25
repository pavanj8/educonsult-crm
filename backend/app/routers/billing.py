"""Billing routes for plan upgrade checkout (E46; Journey J39).

* E46 task #223 (this ticket) owns the ``POST /billing/create-upgrade-order``
  endpoint that creates a Razorpay order for plan upgrades/downgrades.
* E46 task #224 will own the ``POST /billing/webhook`` endpoint for payment
  confirmation.
* E46 task #225 will own the plan change application logic.

Endpoint design
---------------

The order creation endpoint is consultancy-owner only (``billing:manage``
permission). It:

1. Validates the caller is a consultancy owner (has ``tenant_id``).
2. Resolves the requested ``plan_code`` against the platform-level catalog
   (404 if unknown, 409 if inactive).
3. Reads the plan's pricing (``price_in_cents`` / ``currency``).
4. Creates a Razorpay order via the E46 task #222 Razorpay client wrapper.
5. Returns the Razorpay order details (``order_id``, ``amount``, ``currency``)
   plus the target plan details for frontend display.

The endpoint is idempotent in the sense that calling it multiple times with
the same ``plan_code`` creates separate Razorpay orders (each order is a
unique checkout attempt). This is intentional: a user may initiate checkout,
cancel, and try again without completing payment.

Security
--------

* The endpoint requires the ``billing:manage`` permission, which is granted
  only to ``CONSULTANCY_OWNER`` (see :mod:`app.rbac.permissions`).
* The ``tenant_id`` from the JWT is embedded in the Razorpay order notes
  for webhook reconciliation (task #224).
* The ``plan_code`` is validated against the catalog before creating the
  order, ensuring only valid, active plans can be purchased.

Error handling
--------------

* 401 -- caller is not authenticated.
* 403 -- caller lacks ``billing:manage`` permission.
* 404 -- ``plan_code`` is unknown (not in the catalog).
* 409 -- plan exists but is inactive (``is_active=False``).
* 422 -- ``plan_code`` is missing, empty, or not a valid tier code.
* 503 -- database or Razorpay service is unavailable.

Traceability
------------

* Requirements §4 (Billing & Subscription: 3 tiers, Razorpay integration).
* Journey J39 (Consultancy Owner upgrades/downgrades plan via Razorpay checkout).
* Epic E46 (Plan Upgrade/Downgrade Checkout (Razorpay)).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.billing.config import razorpay_key_id
from app.billing.razorpay_client import create_order
from app.db.database import get_db
from app.models.plan import Plan, PlanTier
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.billing import CreateUpgradeOrderRequest, UpgradeOrderResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Billing service is temporarily unavailable"
_RAZORPAY_UNAVAILABLE_DETAIL = "Payment gateway is temporarily unavailable"
_PLAN_NOT_FOUND_DETAIL = "Plan not found"
_PLAN_RETIRED_DETAIL = "Plan is no longer active"
_NO_TENANT_DETAIL = "User account is not associated with a tenant"
_KEY_ID_MISSING_DETAIL = "Payment gateway is not configured"


def _resolve_plan_for_order(plan_code: str, db: Session) -> Plan:
    """Resolve a ``plan_code`` to an active catalog row, or raise 404/409.

    Failure modes (in order of preference):

    * Unknown code -- 404 ``_PLAN_NOT_FOUND_DETAIL``. The schema's
      ``plan_code`` validator already rejects *malformed* codes
      (anything outside the three ``PlanTier`` values) as 422; this
      branch handles the "schema-valid but the catalog row was
      removed" case.
    * Retired tier (``is_active=False``) -- 409 ``_PLAN_RETIRED_DETAIL``.
      Inactive plans cannot be purchased via self-service checkout.

    The endpoint is owner-only, but plan codes are part of the public
    pricing page, so a 404 here is honest about plan-code existence.
    """
    try:
        plan_tier = PlanTier(plan_code)
    except ValueError:
        # Unknown plan code (not one of the three PlanTier values)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PLAN_NOT_FOUND_DETAIL,
        ) from None

    try:
        plan = (
            db.query(Plan)
            .filter(Plan.code == plan_tier)
            .one_or_none()
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PLAN_NOT_FOUND_DETAIL,
        )

    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_PLAN_RETIRED_DETAIL,
        )

    return plan


@router.post(
    "/create-upgrade-order",
    response_model=UpgradeOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_upgrade_order(
    payload: CreateUpgradeOrderRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.BILLING_MANAGE))
    ],
    db: Session = Depends(get_db),
) -> UpgradeOrderResponse:
    """Create a Razorpay order for plan upgrade/downgrade (E46 task #223; Journey J39).

    Consultancy owner only (``billing:manage`` permission). The endpoint:

    1. Validates the caller has a ``tenant_id`` set (owners always do).
    2. Normalizes and validates the ``plan_code`` (lower-cased, must be one
       of the three ``PlanTier`` values).
    3. Resolves the plan against the catalog (404 if unknown, 409 if inactive).
    4. Creates a Razorpay order for the plan's price (``price_in_cents``).
    5. Returns the Razorpay order details plus target plan information.

    Razorpay order notes
    --------------------
    The order includes embedded notes for webhook reconciliation (task #224):
    * ``tenant_id`` -- the tenant ID (for applying the plan change).
    * ``user_id`` -- the user ID who initiated the order (for audit).
    * ``plan_code`` -- the target plan tier code (for confirmation).

    Error responses
    ----------------
    * 401 -- caller is not authenticated.
    * 403 -- caller lacks ``billing:manage`` permission.
    * 404 -- ``plan_code`` is unknown.
    * 409 -- plan exists but is inactive.
    * 422 -- ``plan_code`` is missing, empty, or not a valid tier code.
    * 503 -- database or Razorpay service is unavailable.

    Traceability
    ------------
    * Requirements §4 (Billing & Subscription: Razorpay integration).
    * Journey J39 (Consultancy Owner upgrades/downgrades plan via Razorpay checkout).
    * Epic E46 (Plan Upgrade/Downgrade Checkout (Razorpay)).
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_NO_TENANT_DETAIL,
        )

    # Normalize the plan code to lower case for validation
    plan_code = payload.plan_code.strip().lower()

    # Resolve the plan against the catalog (404 if unknown, 409 if inactive)
    plan = _resolve_plan_for_order(plan_code, db)

    # Verify Razorpay is configured (require key_id for order creation)
    try:
        _key_id = razorpay_key_id()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_KEY_ID_MISSING_DETAIL,
        ) from None

    # Create the Razorpay order with notes for webhook reconciliation
    try:
        razorpay_order = create_order(
            amount_in_paise=plan.price_in_cents,
            currency=plan.currency,
            receipt_id=f"tenant_{current_user.tenant_id}_upgrade",
            notes={
                "tenant_id": str(current_user.tenant_id),
                "user_id": str(current_user.id),
                "plan_code": plan.code.value,
            },
        )
    except Exception as e:
        # Any Razorpay SDK error is a 503 (payment gateway unavailable)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_RAZORPAY_UNAVAILABLE_DETAIL,
        ) from e

    # Extract the Razorpay order ID from the response
    order_id = razorpay_order.get("id")
    if not order_id:
        # This should never happen with a valid Razorpay response
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_RAZORPAY_UNAVAILABLE_DETAIL,
        )

    return UpgradeOrderResponse(
        order_id=order_id,
        amount=razorpay_order.get("amount", plan.price_in_cents),
        currency=razorpay_order.get("currency", plan.currency),
        plan_code=plan.code.value,
        plan_name=plan.name,
    )


__all__ = ["router"]
