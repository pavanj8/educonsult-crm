"""Tests for Razorpay webhook handler (E46 task #224; Journey J39).

Tests the POST /billing/webhooks/razorpay endpoint that processes
payment confirmation webhooks from Razorpay.
"""

import json
from unittest.mock import patch

import pytest
from fastapi import status
from sqlalchemy import exc as sqlalchemy_exc

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant


# Fixture to set required environment variables before tests run
@pytest.fixture(autouse=True)
def set_razorpay_env_vars(monkeypatch):
    """Set Razorpay environment variables for all webhook tests."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "test_key_id")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_key_secret")
    # Reset the Razorpay client singleton to force re-initialization with test credentials
    import app.billing.razorpay_client
    app.billing.razorpay_client._client = None


def test_webhook_returns_401_without_signature_header(client, db_session):
    """Webhook returns 401 when X-Razorpay-Signature header is missing."""
    response = client.post(
        "/billing/webhooks/razorpay",
        json={"event": "payment.captured"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid webhook signature"


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_401_for_invalid_signature(mock_verify, client, db_session):
    """Webhook returns 401 when signature verification fails."""
    mock_verify.return_value = False

    response = client.post(
        "/billing/webhooks/razorpay",
        json={"event": "payment.captured"},
        headers={"X-Razorpay-Signature": "invalid_signature"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid webhook signature"
    mock_verify.assert_called_once()


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_400_for_invalid_json(mock_verify, client, db_session):
    """Webhook returns 400 when payload is not valid JSON."""
    mock_verify.return_value = True

    response = client.post(
        "/billing/webhooks/razorpay",
        content="not valid json",
        headers={"X-Razorpay-Signature": "some_signature"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid JSON payload" in response.json()["detail"]


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_400_when_tenant_id_missing(mock_verify, client, db_session):
    """Webhook returns 400 when tenant_id is not in notes."""
    mock_verify.return_value = True

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {},  # Missing tenant_id
                "entity": {"id": "pay_123"},
            }
        },
    }

    response = client.post(
        "/billing/webhooks/razorpay",
        json=payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "missing tenant_id" in response.json()["detail"]


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_400_for_unsupported_event_type(mock_verify, client, db_session):
    """Webhook returns 400 for unsupported event types."""
    mock_verify.return_value = True

    payload = {
        "event": "payment.failed",  # Unsupported event
        "payload": {
            "payment": {
                "notes": {"tenant_id": "1"},
                "entity": {"id": "pay_123"},
            }
        },
    }

    response = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported webhook event type" in response.json()["detail"]


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_400_when_plan_code_missing(mock_verify, client, db_session):
    """Webhook returns 400 when plan_code is not in notes."""
    mock_verify.return_value = True

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {"tenant_id": "1"},  # Missing plan_code
                "entity": {"id": "pay_123"},
            }
        },
    }

    response = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "missing plan_code" in response.json()["detail"]


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_404_when_tenant_not_found(mock_verify, client, db_session):
    """Webhook returns 404 when tenant_id does not exist."""
    mock_verify.return_value = True

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {"tenant_id": "99999", "plan_code": "growth"},
                "entity": {"id": "pay_123"},
            }
        },
    }

    response = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Tenant not found"


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_404_when_plan_not_found(mock_verify, client, db_session):
    """Webhook returns 404 when plan_code does not exist."""
    mock_verify.return_value = True

    # Create a tenant
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    db_session.add(tenant)
    db_session.commit()

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {"tenant_id": str(tenant.id), "plan_code": "nonexistent"},
                "entity": {"id": "pay_123"},
            }
        },
    }

    response = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plan not found"


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_applies_plan_change_on_success(mock_verify, client, db_session):
    """Webhook applies plan change when payment.captured event is valid."""
    mock_verify.return_value = True

    # Create tenant and plans
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    db_session.add(tenant)

    starter_plan = Plan(
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
        price_in_cents=100000,
        currency="INR",
    )
    growth_plan = Plan(
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=500,
        price_in_cents=500000,
        currency="INR",
    )
    db_session.add_all([starter_plan, growth_plan])
    db_session.commit()

    # Initially assign starter plan
    tenant.plan_id = starter_plan.id
    db_session.commit()
    assert tenant.plan_id == starter_plan.id

    # Simulate Razorpay webhook for upgrade to growth
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {"tenant_id": str(tenant.id), "plan_code": "growth"},
                "entity": {"id": "pay_123"},
            }
        },
    }

    response = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

    # Verify plan was updated
    db_session.refresh(tenant)
    assert tenant.plan_id == growth_plan.id


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_verifies_signature_with_body(mock_verify, client, db_session):
    """Webhook passes raw body to signature verification."""
    mock_verify.return_value = True

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {"tenant_id": "99999", "plan_code": "growth"},
                "entity": {"id": "pay_123"},
            }
        },
    }

    client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    # The signature verification should have been called with the raw body
    assert mock_verify.called
    call_args = mock_verify.call_args
    # First positional argument is the raw body string
    assert isinstance(call_args[0][0], str)
    # Verify it contains the expected JSON
    body_json = json.loads(call_args[0][0])
    assert body_json["event"] == "payment.captured"


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_returns_503_on_database_error(mock_verify, client, db_session):
    """Webhook returns 503 when database is unavailable."""
    mock_verify.return_value = True

    # Mock database error at the Tenant lookup level
    with patch("sqlalchemy.orm.Session.get", side_effect=sqlalchemy_exc.OperationalError("mock", {}, None)):
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "notes": {"tenant_id": "1", "plan_code": "growth"},
                    "entity": {"id": "pay_123"},
                }
            },
        }

        response = client_post_with_json_content(
            client,
            "/billing/webhooks/razorpay",
            payload,
            headers={"X-Razorpay-Signature": "valid_signature"},
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "temporarily unavailable" in response.json()["detail"]


def test_webhook_passes_signature_header_to_verification(client, db_session):
    """Webhook extracts and passes X-Razorpay-Signature header to verification."""
    with patch("app.routers.billing.verify_webhook_signature") as mock_verify:
        mock_verify.return_value = False

        response = client.post(
            "/billing/webhooks/razorpay",
            json={"event": "payment.captured"},
            headers={"X-Razorpay-Signature": "test_sig_abc"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_verify.assert_called_once()
        # Second positional argument is the signature
        assert mock_verify.call_args[0][1] == "test_sig_abc"


def client_post_with_json_content(client, url, payload, headers=None):
    """Helper to post JSON and have it available as raw body for signature verification."""
    # Convert payload to JSON string and post as content
    # This ensures the raw body is available for signature verification
    json_str = json.dumps(payload)
    return client.post(
        url,
        content=json_str,
        headers=headers or {},
    )
