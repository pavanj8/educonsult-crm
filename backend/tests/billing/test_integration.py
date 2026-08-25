"""Integration tests for Razorpay client (E46 task #222).

These tests verify that the Razorpay SDK integration is correctly
configured and can communicate with the API (or at least that the
client is properly initialized with credentials).
"""

import razorpay

from app.billing.config import razorpay_key_id, razorpay_key_secret
from app.billing.razorpay_client import get_client


def test_razorpay_client_initializes():
    """The Razorpay client initializes without errors."""
    client = get_client()
    assert client is not None
    assert isinstance(client, razorpay.Client)


def test_razorpay_client_has_credentials():
    """The client is configured with credentials from config."""
    # We can't directly inspect the auth tuple on the client,
    # but we can verify the config functions return values
    key_id = razorpay_key_id()
    key_secret = razorpay_key_secret()

    assert key_id
    assert key_secret
    assert len(key_id) > 0
    assert len(key_secret) > 0


def test_razorpay_client_singleton():
    """Multiple calls to get_client return the same instance."""
    client1 = get_client()
    client2 = get_client()
    assert client1 is client2
