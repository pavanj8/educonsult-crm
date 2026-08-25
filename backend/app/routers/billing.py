"""Billing routes for Razorpay payment webhooks (E46; Journey J39).

* POST /webhooks/razorpay -- Razorpay webhook handler for payment confirmation

This endpoint receives and processes webhook events from Razorpay when payments
are completed. The webhook:

* Verifies the webhook signature to ensure it comes from Razorpay.
* Validates the payload contains a tenant_id in the notes.
* For payment.captured events, applies the plan change to the tenant.
* Returns 200 OK for successful processing or 400/401 for validation errors.

Security considerations:
* Webhooks must be verified using the Razorpay signature to prevent forgery.
* The webhook endpoint does NOT require authentication (Razorpay doesn't send JWT tokens).
* Tenant ID is extracted from the order notes (set during order creation).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.billing.razorpay_client import verify_webhook_signature
from app.db.database import get_db
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.schemas.billing import WebhookErrorResponse

router = APIRouter()

_logger = logging.getLogger(__name__)

# Razorpay sends the signature in this header
_RAZORPAY_SIGNATURE_HEADER = "X-Razorpay-Signature"

# Expected webhook event types
_EVENT_PAYMENT_CAPTURED = "payment.captured"

# Error messages
_ERROR_INVALID_SIGNATURE = "Invalid webhook signature"
_ERROR_MISSING_TENANT = "Webhook payload missing tenant_id in notes"
_ERROR_TENANT_NOT_FOUND = "Tenant not found"
_ERROR_PLAN_NOT_FOUND = "Plan not found"
_ERROR_UNSUPPORTED_EVENT = "Unsupported webhook event type"
_ERROR_DB_UNAVAILABLE = "Database temporarily unavailable"


@router.post(
    "/webhooks/razorpay",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Webhook processed successfully"},
        400: {"model": WebhookErrorResponse, "description": "Invalid webhook payload"},
        401: {"model": WebhookErrorResponse, "description": "Invalid signature"},
    },
)
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Handle Razorpay webhook events for payment confirmation (E46; Journey J39).

    This endpoint processes payment.captured events from Razorpay to apply
    plan upgrades/downgrades after successful payment. The webhook:

    1. Extracts the raw request body and X-Razorpay-Signature header.
    2. Verifies the signature using the Razorpay key secret.
    3. Parses the JSON payload and validates it contains tenant_id in notes.
    4. For payment.captured events, applies the plan change to the tenant.
    5. Returns 200 OK on success, or 401/400 for validation failures.

    The webhook does NOT require authentication - Razorpay doesn't send
    JWT tokens. Security is provided by signature verification.

    Returns:
        {"status": "ok"} on successful processing.

    Raises:
        HTTPException: 401 if signature is invalid, 400 for other validation errors.
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

    # Only process payment.captured events
    if event_type != _EVENT_PAYMENT_CAPTURED:
        _logger.info(f"Received unsupported event type: {event_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ERROR_UNSUPPORTED_EVENT,
        )

    # Get plan_code from notes
    plan_code = event_note.get("plan_code")
    if not plan_code:
        _logger.warning("Webhook payload missing plan_code in notes")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload missing plan_code in notes",
        )

    # Fetch tenant
    try:
        tenant = db.get(Tenant, int(tenant_id))
    except (ValueError, TypeError):
        _logger.warning(f"Invalid tenant_id in webhook: {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant_id",
        ) from None
    except OperationalError:
        _logger.error("Database error during webhook processing")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ERROR_DB_UNAVAILABLE,
        ) from None

    if tenant is None:
        _logger.warning(f"Tenant not found: {tenant_id}")
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
