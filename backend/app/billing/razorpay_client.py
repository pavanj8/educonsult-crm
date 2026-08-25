"""Razorpay SDK client wrapper (E46 task #222; Journey J39).

This module provides a thin wrapper around the Razorpay Python SDK
(razorpay package) to:

* Initialize a singleton Razorpay client with credentials from
  :mod:`app.billing.config`.
* Provide typed helper functions for order creation, webhook verification,
  and other operations used by the E46 endpoints.

The wrapper isolates the third-party SDK from the rest of the application
and makes testing easier (the client can be mocked/faked in tests).

Why a singleton client:
* The Razorpay SDK client is stateless and thread-safe for read operations.
* Reusing the same instance across requests avoids re-initializing the
  HTTP client on every call.
* This pattern matches the boto3 S3 client wrapper in
  :mod:`app.storage.service`.
"""

from __future__ import annotations

import razorpay

from app.billing.config import razorpay_key_id, razorpay_key_secret

# Singleton Razorpay client instance (initialized on first import)
_client: razorpay.Client | None = None


def get_client() -> razorpay.Client:
    """Return the singleton Razorpay SDK client.

    The client is initialized once with credentials from the environment
    and reused across all calls. This function is thread-safe because
    the Razorpay client itself is thread-safe.

    Returns:
        The configured Razorpay client instance.
    """
    global _client
    if _client is None:
        _client = razorpay.Client(auth=(razorpay_key_id(), razorpay_key_secret()))
    return _client


def create_order(
    amount_in_paise: int,
    currency: str,
    receipt_id: str | None = None,
    notes: dict | None = None,
) -> dict:
    """Create a Razorpay order for plan upgrade checkout.

    Wraps the Razorpay ``order.create`` API with typed parameters and
    returns the full response dict. This is called by the E46 task #223
    order creation endpoint.

    Args:
        amount_in_paise: Amount in smallest currency unit (paisa for INR).
        currency: ISO 4217 currency code (e.g., "INR").
        receipt_id: Optional receipt identifier for reconciliation (max 40 chars).
        notes: Optional key-value notes attached to the order.

    Returns:
        Razorpay order response dict with ``id``, ``amount``, ``currency``,
        ``status``, ``created_at``.

    Raises:
        razorpay.errors.RazorpayError: If the order creation fails.
    """
    client = get_client()
    order_data = {
        "amount": amount_in_paise,
        "currency": currency,
        "payment_capture": 1,  # Auto-capture payment
    }
    if receipt_id is not None:
        order_data["receipt"] = receipt_id
    if notes is not None:
        order_data["notes"] = notes

    response = client.order.create(data=order_data)
    return response


def verify_webhook_signature(
    webhook_body: str,
    webhook_signature: str,
    webhook_secret: str | None = None,
) -> bool:
    """Verify a Razorpay webhook signature for authenticity.

    Razorpay webhooks must be verified to ensure they originate from
    Razorpay and not from a malicious actor. This function implements
    the HMAC SHA256 verification logic described in the Razorpay docs.

    Args:
        webhook_body: Raw request body as a string.
        webhook_signature: ``X-Razorpay-Signature`` header value.
        webhook_secret: Optional webhook secret (defaults to key_secret).

    Returns:
        True if the signature is valid, False otherwise.
    """
    client = get_client()
    secret = webhook_secret or razorpay_key_secret()
    try:
        client.utility.verify_webhook_signature(webhook_body, webhook_signature, secret)
        return True
    except Exception:
        return False
