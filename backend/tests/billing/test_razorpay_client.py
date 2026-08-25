"""Tests for Razorpay client wrapper (E46 task #222)."""

from unittest.mock import MagicMock, patch

import razorpay

from app.billing.razorpay_client import create_order, get_client, verify_webhook_signature


def test_get_client_returns_singleton():
    """get_client returns the same instance across calls."""
    client1 = get_client()
    client2 = get_client()
    assert client1 is client2
    assert isinstance(client1, razorpay.Client)


def test_get_client_is_initialized_with_credentials(monkeypatch):
    """Client is initialized with credentials from config."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "test_key_id")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_key_secret")

    # Clear the singleton to force re-initialization
    import app.billing.razorpay_client
    app.billing.razorpay_client._client = None

    client = get_client()
    assert client is not None
    assert isinstance(client, razorpay.Client)


@patch("app.billing.razorpay_client.get_client")
def test_create_order_calls_razorpay_api(mock_get_client):
    """create_order calls Razorpay order.create with correct parameters."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.order.create.return_value = {
        "id": "order_123",
        "amount": 1000,
        "currency": "INR",
        "status": "created",
    }

    result = create_order(
        amount_in_paise=1000,
        currency="INR",
        receipt_id="receipt_001",
        notes={"plan_code": "growth"},
    )

    mock_client.order.create.assert_called_once()
    call_args = mock_client.order.create.call_args
    assert call_args is not None
    order_data = call_args.kwargs.get("data") or call_args[1].get("data")
    assert order_data is not None
    assert order_data["amount"] == 1000
    assert order_data["currency"] == "INR"
    assert order_data["receipt"] == "receipt_001"
    assert order_data["notes"]["plan_code"] == "growth"
    assert result == {
        "id": "order_123",
        "amount": 1000,
        "currency": "INR",
        "status": "created",
    }


@patch("app.billing.razorpay_client.get_client")
def test_create_order_without_optional_params(mock_get_client):
    """create_order works without receipt_id and notes."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.order.create.return_value = {
        "id": "order_456",
        "amount": 500,
        "currency": "INR",
        "status": "created",
    }

    result = create_order(amount_in_paise=500, currency="INR")

    mock_client.order.create.assert_called_once()
    call_args = mock_client.order.create.call_args
    order_data = call_args.kwargs.get("data") or call_args[1].get("data")
    assert order_data is not None
    assert "receipt" not in order_data
    assert "notes" not in order_data
    assert result["id"] == "order_456"


@patch("app.billing.razorpay_client.get_client")
def test_verify_webhook_signature_valid(mock_get_client):
    """verify_webhook_signature returns True for valid signature."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    # Mock successful verification (no exception raised)
    mock_client.utility.verify_webhook_signature.return_value = None

    result = verify_webhook_signature(
        webhook_body='{"event":"payment.authenticated"}',
        webhook_signature="valid_signature",
        webhook_secret="test_secret",
    )

    mock_client.utility.verify_webhook_signature.assert_called_once_with(
        '{"event":"payment.authenticated"}',
        "valid_signature",
        "test_secret",
    )
    assert result is True


@patch("app.billing.razorpay_client.get_client")
def test_verify_webhook_signature_invalid(mock_get_client):
    """verify_webhook_signature returns False for invalid signature."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    # Mock failed verification (raises exception)
    mock_client.utility.verify_webhook_signature.side_effect = Exception("Invalid signature")

    result = verify_webhook_signature(
        webhook_body='{"event":"payment.authenticated"}',
        webhook_signature="invalid_signature",
    )

    assert result is False


@patch("app.billing.razorpay_client.get_client")
def test_verify_webhook_signature_uses_default_secret(mock_get_client, monkeypatch):
    """verify_webhook_signature uses key_secret if webhook_secret not provided."""
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "default_secret")
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.utility.verify_webhook_signature.return_value = None

    verify_webhook_signature(
        webhook_body='{"event":"payment.authenticated"}',
        webhook_signature="valid_signature",
    )

    mock_client.utility.verify_webhook_signature.assert_called_once()
    call_args = mock_client.utility.verify_webhook_signature.call_args
    # Third argument is the secret
    assert call_args[0][2] == "default_secret"
