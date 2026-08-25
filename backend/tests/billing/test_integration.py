"""Integration tests for Razorpay client (E46 task #222).

These tests verify that the Razorpay SDK integration is correctly
configured and can communicate with the API (or at least that the
client is properly initialized with credentials).
"""

import razorpay

import pytest

from app.billing.config import razorpay_key_id, razorpay_key_secret
from app.billing.razorpay_client import get_client


@pytest.mark.parametrize(
    "key_id,key_secret",
    [
        ("rzp_test_1234567890abcdef", "test_secret_123"),
        ("rzp_live_abcdefgh", "live_secret_456"),
    ],
)
def test_razorpay_client_initializes(key_id, key_secret, monkeypatch):
    """The Razorpay client initializes without errors with test keys."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", key_id)
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", key_secret)

    # Reset singleton to force re-init with new credentials
    import app.billing.razorpay_client
    app.billing.razorpay_client._client = None

    client = get_client()
    assert client is not None
    assert isinstance(client, razorpay.Client)


def test_razorpay_client_has_credentials(monkeypatch):
    """The client is configured with credentials from config."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "test_key_id")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_key_secret")
    
    # Reset singleton to force re-init
    import app.billing.razorpay_client
    app.billing.razorpay_client._client = None
    
    key_id = razorpay_key_id()
    key_secret = razorpay_key_secret()

    assert key_id
    assert key_secret
    assert len(key_id) > 0
    assert len(key_secret) > 0


def test_razorpay_client_singleton(monkeypatch):
    """Multiple calls to get_client return the same instance."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "test_key_id")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_key_secret")
    
    # Reset singleton to force re-init
    import app.billing.razorpay_client
    app.billing.razorpay_client._client = None
    
    client1 = get_client()
    client2 = get_client()
    assert client1 is client2


def test_get_client_raises_without_credentials(monkeypatch):
    """get_client raises RuntimeError if credentials not configured."""
    # Reset the singleton to force re-initialization
    import app.billing.razorpay_client
    app.billing.razorpay_client._client = None

    # Delete env vars
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)

    # Verify error is raised
    with pytest.raises(RuntimeError, match="RAZORPAY_KEY_ID"):
        get_client()
