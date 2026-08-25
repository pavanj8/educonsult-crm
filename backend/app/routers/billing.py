"""Billing routes for plan upgrade checkout (E46; Journey J39).

<<<<<<< HEAD
This module contains:

* E46 task #223: ``POST /billing/create-upgrade-order`` endpoint that creates
  a Razorpay order for plan upgrades/downgrades.
* E46 task #224: ``POST /billing/webhooks/razorpay`` endpoint that processes
  payment confirmation webhooks from Razorpay.
* E46 task #225: Plan change application logic (called by webhook handler).
=======
* E46 task #223 owns the ``POST /billing/create-upgrade-order``
  endpoint that creates a Razorpay order for plan upgrades/downgrades.
* E46 task #224 owns the ``POST /billing/webhook`` endpoint for payment
  confirmation.
* E46 task #225 owns the plan change application logic.
>>>>>>> origin/main

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

<<<<<<< HEAD
The webhook handler processes payment.captured events from Razorpay to apply
plan upgrades/downgrades after successful payment. It:

1. Verifies the webhook signature to ensure it comes from Razorpay.
2. Validates the payload contains tenant_id and plan_code in the notes.
3. Verifies multi-tenant scoping by checking the tenant exists.
4. Implements idempotency to prevent replay attacks.
5. Applies the plan change to the tenant.
6. Returns 200 OK for successful processing or 400/401 for validation errors.
=======
The webhook endpoint (task #224) receives payment confirmation from Razorpay:

1. Verifies the Razorpay webhook signature for authenticity.
2. Parses the ``payment.captured`` event payload.
3. Extracts ``tenant_id`` and ``plan_code`` from the payment notes.
4. Calls ``apply_plan_change()`` from the plan_change module (task #225).
5. Returns 200 OK on success, 401/400/404 for validation errors.

The order creation endpoint is idempotent in the sense that calling it multiple
times with the same ``plan_code`` creates separate Razorpay orders (each order
is a unique checkout attempt). This is intentional: a user may initiate checkout,
cancel, and try again without completing payment.
>>>>>>> origin/main

The webhook endpoint is idempotent -- duplicate webhook delivery results in
the same plan being applied again (tenant.plan_id is set to the same value).

Security
--------

* The order creation endpoint requires the ``billing:manage`` permission,
  which is granted only to ``CONSULTANCY_OWNER`` (see :mod:`app.rbac.permissions`).
* The ``tenant_id`` from the JWT is embedded in the Razorpay order notes
  for webhook reconciliation (task #224).
<<<<<<< HEAD
* The webhook endpoint does NOT require authentication (Razorpay doesn't send
  JWT tokens). Security is provided by signature verification.
* The webhook implements idempotency by checking if the plan change is already
  applied before updating, preventing duplicate processing.
* Multi-tenant scoping is verified by ensuring the tenant exists before applying
  any changes.
=======
* The ``plan_code`` is validated against the catalog before creating the
  order, ensuring only valid, active plans can be purchased.
* The webhook endpoint verifies Razorpay signature using HMAC SHA256 to
  ensure the webhook originated from Razorpay and not from a malicious actor.
>>>>>>> origin/main

Error handling
--------------

<<<<<<< HEAD
Order creation errors:
=======
Order creation endpoint:
>>>>>>> origin/main
* 401 -- caller is not authenticated.
* 403 -- caller lacks ``billing:manage`` permission.
* 404 -- ``plan_code`` is unknown (not in the catalog).
* 409 -- plan exists but is inactive (``is_active=False``).
* 422 -- ``plan_code`` is missing, empty, or not a valid tier code.
* 503 -- database or Razorpay service is unavailable.

<<<<<<< HEAD
Webhook errors:
* 401 -- signature verification failed.
* 400 -- invalid payload, unsupported event, or missing required fields.
* 404 -- tenant or plan not found.
* 503 -- database temporarily unavailable.
=======
Webhook endpoint:
* 400 -- invalid webhook payload (missing required fields).
* 401 -- signature verification failed (potential forgery).
* 404 -- tenant or plan not found.
* 409 -- plan is inactive.
* 500 -- database error during plan change application.
>>>>>>> origin/main

Traceability
------------

* Requirements §4 (Billing & Subscription: 3 tiers, Razorpay integration).
* Journey J39 (Consultancy Owner upgrades/downgrades plan via Razorpay checkout).
* Epic E46 (Plan Upgrade/Downgrade Checkout (Razorpay)).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
<<<<<<< HEAD
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.billing.config import razorpay_key_id
=======
from sqlalchemy.orm import Session

from app.billing.config import razorpay_key_id, razorpay_key_secret
from app.billing.plan_change import (
    PlanInactive,
    PlanNotFound,
    TenantNotFound,
    apply_plan_change,
)
>>>>>>> origin/main
from app.billing.razorpay_client import create_order, verify_webhook_signature
from app.db.database import get_db
from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.billing import (
    CreateUpgradeOrderRequest,
<<<<<<< HEAD
    UpgradeOrderResponse,
    WebhookErrorResponse,
=======
    PlanChangeResponse,
    UpgradeOrderResponse,
>>>>>>> origin/main
)

router = APIRouter()
logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)

# Order creation error messages
_DB_UNAVAILABLE_DETAIL = "Billing service is temporarily unavailable"
_RAZORPAY_UNAVAILABLE_DETAIL = "Payment gateway is temporarily unavailable"
_PLAN_NOT_FOUND_DETAIL = "Plan not found"
_PLAN_RETIRED_DETAIL = "Plan is no longer active"
_NO_TENANT_DETAIL = "User account is not associated with a tenant"
_KEY_ID_MISSING_DETAIL = "Payment gateway is not configured"

# Webhook constants
_RAZORPAY_SIGNATURE_HEADER = "X-Razorpay-Signature"
_EVENT_PAYMENT_CAPTURED = "payment.captured"
_ERROR_INVALID_SIGNATURE = "Invalid webhook signature"
_ERROR_MISSING_TENANT = "Webhook payload missing tenant_id in notes"
_ERROR_MISSING_PLAN = "Webhook payload missing plan_code in notes"
_ERROR_TENANT_NOT_FOUND = "Tenant not found"
_ERROR_PLAN_NOT_FOUND = "Plan not found"
_ERROR_UNSUPPORTED_EVENT = "Unsupported webhook event type"
_ERROR_DB_UNAVAILABLE = "Database temporarily unavailable"


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


@router.post(
<<<<<<< HEAD
    "/webhooks/razorpay",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Webhook processed successfully"},
        400: {"model": WebhookErrorResponse, "description": "Invalid webhook payload"},
        401: {"model": WebhookErrorResponse, "description": "Invalid signature"},
    },
=======
    "/webhook",
    response_model=PlanChangeResponse,
    status_code=status.HTTP_200_OK,
>>>>>>> origin/main
)
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
<<<<<<< HEAD
) -> dict[str, str]:
    """Handle Razorpay webhook events for payment confirmation (E46 task #224; Journey J39).

    This endpoint processes payment.captured events from Razorpay to apply
    plan upgrades/downgrades after successful payment. The webhook:

    1. Extracts the raw request body and X-Razorpay-Signature header.
    2. Verifies the signature using the Razorpay key secret.
    3. Parses the JSON payload and validates it contains tenant_id and plan_code in notes.
    4. Verifies multi-tenant scoping by checking the tenant exists.
    5. Implements idempotency by checking if the plan is already applied.
    6. For payment.captured events, applies the plan change to the tenant.
    7. Returns 200 OK on success, or 401/400 for validation failures.

    The webhook does NOT require authentication - Razorpay doesn't send
    JWT tokens. Security is provided by signature verification and multi-tenant
    scoping checks.

    Idempotency protection
    ----------------------
    To prevent replay attacks and duplicate processing:
    * The handler checks if the tenant's current plan_id already matches the
      target plan before applying any change.
    * This ensures that duplicate webhook delivery (which Razorpay may do on
      retry) will not cause double-billing or inconsistent state.

    Multi-tenant scoping
    --------------------
    The webhook verifies that the tenant_id extracted from the notes corresponds
    to a valid tenant in the database. This prevents a malicious actor from
    injecting arbitrary tenant_id values to upgrade other tenants.

    Returns:
        {"status": "ok"} on successful processing.

    Raises:
        HTTPException: 401 if signature is invalid, 400/404/503 for other errors.
    """
    # Read raw body for signature verification
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    # Get signature from header
    signature = request.headers.get(_RAZORPAY_SIGNATURE_HEADER)
    if not signature:
        _logger.warning("Webhook request missing signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_ERROR_INVALID_SIGNATURE,
        )

    # Verify webhook signature
    if not verify_webhook_signature(body_str, signature):
        _logger.warning("Webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_ERROR_INVALID_SIGNATURE,
        )

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        _logger.warning("Webhook payload is not valid JSON")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from None

    # Extract event type and payload
    event_type = payload.get("event")
    event_data = payload.get("payload", {})
    event_note = event_data.get("payment", {}).get("notes", {})

    # Validate tenant_id in notes
    tenant_id = event_note.get("tenant_id")
    if not tenant_id:
        _logger.warning("Webhook payload missing tenant_id in notes")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ERROR_MISSING_TENANT,
        )

    # Validate plan_code in notes
    plan_code = event_note.get("plan_code")
    if not plan_code:
        _logger.warning("Webhook payload missing plan_code in notes")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ERROR_MISSING_PLAN,
        )

    # Only process payment.captured events
    if event_type != _EVENT_PAYMENT_CAPTURED:
        _logger.info(f"Received unsupported event type: {event_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ERROR_UNSUPPORTED_EVENT,
        )

    # Parse tenant_id as integer
    try:
        tenant_id_int = int(tenant_id)
    except (ValueError, TypeError):
        _logger.warning(f"Invalid tenant_id in webhook: {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant_id",
        ) from None

    # Fetch tenant with row lock for idempotency check
    try:
        # Use SELECT FOR UPDATE to prevent concurrent webhook processing
        tenant = db.execute(
            db.query(Tenant).filter(Tenant.id == tenant_id_int).with_for_update()
        ).scalar_one_or_none()
    except OperationalError:
        _logger.error("Database error during tenant lookup")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ERROR_DB_UNAVAILABLE,
        ) from None

    if tenant is None:
        _logger.warning(f"Tenant not found: {tenant_id_int}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_ERROR_TENANT_NOT_FOUND,
        )

    # Fetch plan
    try:
        plan = db.query(Plan).filter(Plan.code == plan_code).one_or_none()
    except OperationalError:
        _logger.error("Database error during plan lookup")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ERROR_DB_UNAVAILABLE,
        ) from None

    if plan is None:
        _logger.warning(f"Plan not found: {plan_code}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_ERROR_PLAN_NOT_FOUND,
        )

    # IDEMPOTENCY CHECK: If tenant already has this plan, skip update
    # This prevents duplicate processing of the same webhook
    if tenant.plan_id == plan.id:
        _logger.info(f"Tenant {tenant.id} already has plan {plan.code}, skipping update")
        return {"status": "ok"}

    # Apply plan change
    _logger.info(f"Applying plan change for tenant {tenant.id}: {plan.code}")
    tenant.plan_id = plan.id

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        _logger.error("Database error during plan update")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ERROR_DB_UNAVAILABLE,
        ) from None

    _logger.info(f"Successfully applied plan {plan.code} to tenant {tenant.id}")
    return {"status": "ok"}
=======
) -> PlanChangeResponse:
    """Handle Razorpay payment confirmation webhook (E46 task #224; Journey J39).

    This endpoint receives Razorpay webhook events for payment confirmation
    and applies the plan change when a payment is successfully captured.

    The webhook:
    1. Verifies the ``X-Razorpay-Signature`` header for authenticity.
    2. Parses the ``payment.captured`` event payload.
    3. Extracts ``tenant_id`` and ``plan_code`` from the payment notes.
    4. Calls ``apply_plan_change()`` to update the tenant's plan.
    5. Returns 200 OK on success, appropriate error code on failure.

    The endpoint is idempotent -- duplicate webhook delivery results in
    the same plan being applied again (tenant.plan_id is set to the same value).

    Security
    --------
    * Webhook signature is verified using HMAC SHA256 to ensure the webhook
      originated from Razorpay and not from a malicious actor.
    * The webhook does NOT require authentication (Razorpay can't provide JWT).
    * Payment notes are used to extract ``tenant_id`` and ``plan_code`` -- these
      were embedded by the authenticated order creation endpoint.

    Error responses
    ----------------
    * 400 -- invalid webhook payload (missing required fields).
    * 401 -- signature verification failed (potential forgery).
    * 404 -- tenant or plan not found.
    * 409 -- plan is inactive.
    * 500 -- database error during plan change application.

    Traceability
    ------------
    * Requirements §4 (Billing & Subscription: Razorpay integration).
    * Journey J39 (Consultancy Owner upgrades/downgrades plan via Razorpay checkout).
    * Epic E46 (Plan Upgrade/Downgrade Checkout (Razorpay)).

    Razorpay webhook documentation
    -------------------------------
    https://razorpay.com/docs/payment-gateway/webhooks/
    """
    # Get the webhook signature from the header
    webhook_signature = request.headers.get("x-razorpay-signature")
    if not webhook_signature:
        logger.warning("Webhook received without signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
        )

    # Read the raw request body for signature verification
    webhook_body = await request.body()
    if not webhook_body:
        logger.warning("Webhook received with empty body")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty webhook payload",
        )

    # Verify the webhook signature
    try:
        is_valid = verify_webhook_signature(
            webhook_body=webhook_body.decode("utf-8"),
            webhook_signature=webhook_signature,
            webhook_secret=razorpay_key_secret(),
        )
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        ) from e

    if not is_valid:
        logger.warning("Webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse the webhook payload
    try:
        import json

        payload = json.loads(webhook_body.decode("utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from e

    # Extract event type and payment entity
    event_type = payload.get("event")
    if event_type != "payment.captured":
        # Ignore other event types (e.g., payment.failed, order.paid)
        logger.info(f"Ignoring non-capture event: {event_type}")
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Event type {event_type} is not processed",
        )

    # Extract payment entity from the payload
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if not payment:
        logger.error("Webhook payload missing payment entity")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing payment entity in webhook payload",
        )

    # Extract notes from the payment (contains tenant_id and plan_code)
    notes = payment.get("notes", {})
    tenant_id_str = notes.get("tenant_id")
    plan_code = notes.get("plan_code")

    if not tenant_id_str or not plan_code:
        logger.error(f"Webhook payment notes missing tenant_id or plan_code: {notes}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment notes missing tenant_id or plan_code",
        )

    # Apply the plan change
    try:
        result = apply_plan_change(
            db=db,
            tenant_id=int(tenant_id_str),
            plan_code=plan_code,
        )
        # Commit the transaction
        db.commit()
    except (TenantNotFound, PlanNotFound, PlanInactive) as e:
        # Domain errors -- log and return appropriate status
        logger.error(f"Plan change domain error: {e}")
        db.rollback()
        if isinstance(e, TenantNotFound):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        elif isinstance(e, PlanNotFound):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        elif isinstance(e, PlanInactive):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
    except Exception as e:
        # Database or unexpected error
        logger.error(f"Plan change database error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply plan change",
        ) from e

    logger.info(
        f"Successfully applied plan change for tenant {result.tenant_id}: "
        f"plan {result.plan_code} (ID {result.new_plan_id})"
    )

    return PlanChangeResponse(
        tenant_id=result.tenant_id,
        previous_plan_id=result.previous_plan_id,
        new_plan_id=result.new_plan_id,
        plan_code=result.plan_code,
    )
>>>>>>> origin/main


__all__ = ["router"]
