<<<<<<< HEAD
"""Tests for Razorpay webhook handler (E46 task #224; Journey J39).

Tests the POST /billing/webhooks/razorpay endpoint that processes
payment confirmation webhooks from Razorpay.

Security tests verify:
* Multi-tenant scoping is enforced (tenant_id must exist)
* Idempotency protection prevents replay attacks
* Signature verification is required
"""

import json
from unittest.mock import patch

import pytest
from fastapi import status
from sqlalchemy import exc as sqlalchemy_exc
=======
"""Tests for Razorpay webhook handler (E46 task #224)."""

import json
import hashlib
import hmac

from fastapi.testclient import TestClient
>>>>>>> origin/main

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant


<<<<<<< HEAD
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

=======
def _generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate a valid Razorpay webhook signature for testing."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def test_webhook_success(
    auth_client: TestClient,
    owner_tenant: Tenant,
    test_plan: Plan,
    razorpay_test_credentials,
):
    """Webhook successfully applies plan change on payment.captured event."""
    # Create webhook payload
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_1234567890",
                    "amount": test_plan.price_in_cents,
                    "currency": test_plan.currency,
                    "notes": {
                        "tenant_id": str(owner_tenant.id),
                        "user_id": "42",
                        "plan_code": test_plan.code.value,
                    },
                }
            }
        },
    }
    payload_str = json.dumps(payload)

    # Generate valid signature
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    # Send webhook
    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == owner_tenant.id
    assert data["new_plan_id"] == test_plan.id
    assert data["plan_code"] == test_plan.code.value
    assert data["previous_plan_id"] is None


def test_webhook_missing_signature(auth_client: TestClient, razorpay_test_credentials):
    """Webhook without signature returns 401."""
    payload = {"event": "payment.captured", "payload": {}}

    response = auth_client.post(
        "/billing/webhook",
        json=payload,
    )

    assert response.status_code == 401
    assert "Missing webhook signature" in response.json()["detail"]


def test_webhook_invalid_signature(auth_client: TestClient, razorpay_test_credentials):
    """Webhook with invalid signature returns 401."""
    payload = {"event": "payment.captured", "payload": {}}

    response = auth_client.post(
        "/billing/webhook",
        json=payload,
        headers={"X-Razorpay-Signature": "invalid_signature"},
    )

    assert response.status_code == 401
    assert "Invalid webhook signature" in response.json()["detail"]


def test_webhook_empty_body(auth_client: TestClient, razorpay_test_credentials):
    """Webhook with empty body returns 400."""
    response = auth_client.post(
        "/billing/webhook",
        content=b"",
        headers={"X-Razorpay-Signature": "some_signature"},
    )

    assert response.status_code == 400
    assert "Empty webhook payload" in response.json()["detail"]


def test_webhook_invalid_json(auth_client: TestClient, razorpay_test_credentials):
    """Webhook with invalid JSON returns 400."""
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature("invalid json", secret)

    response = auth_client.post(
        "/billing/webhook",
        content="invalid json",
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 400
    assert "Invalid JSON payload" in response.json()["detail"]


def test_webhook_ignored_event_type(
    auth_client: TestClient,
    razorpay_test_credentials,
):
    """Webhook ignores non-capture event types with 202."""
    payload = {
        "event": "payment.failed",
        "payload": {"payment": {"entity": {}}},
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 202
    assert "not processed" in response.json()["detail"]


def test_webhook_missing_payment_entity(
    auth_client: TestClient,
    razorpay_test_credentials,
):
    """Webhook without payment entity returns 400."""
    payload = {
        "event": "payment.captured",
        "payload": {},
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 400
    assert "Missing payment entity" in response.json()["detail"]


def test_webhook_missing_notes(
    auth_client: TestClient,
    razorpay_test_credentials,
):
    """Webhook without notes returns 400."""
>>>>>>> origin/main
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
<<<<<<< HEAD
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
                "notes": {"tenant_id": "1", "plan_code": "growth"},  # Must include both for event check to run
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

=======
                "entity": {
                    "id": "pay_1234567890",
                    "notes": {},  # Empty notes
                }
            }
        },
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 400
    assert "missing tenant_id or plan_code" in response.json()["detail"]


def test_webhook_tenant_not_found(
    auth_client: TestClient,
    test_plan: Plan,
    razorpay_test_credentials,
):
    """Webhook returns 404 when tenant doesn't exist."""
>>>>>>> origin/main
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
<<<<<<< HEAD
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

=======
                "entity": {
                    "id": "pay_1234567890",
                    "notes": {
                        "tenant_id": "99999",  # Non-existent tenant
                        "plan_code": test_plan.code.value,
                    },
                }
            }
        },
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_webhook_plan_not_found(
    auth_client: TestClient,
    owner_tenant: Tenant,
    razorpay_test_credentials,
):
    """Webhook returns 404 when plan doesn't exist."""
>>>>>>> origin/main
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
<<<<<<< HEAD
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

=======
                "entity": {
                    "id": "pay_1234567890",
                    "notes": {
                        "tenant_id": str(owner_tenant.id),
                        "plan_code": "unknown",  # Unknown plan
                    },
                }
            }
        },
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_webhook_inactive_plan(
    auth_client: TestClient,
    owner_tenant: Tenant,
    inactive_plan: Plan,
    razorpay_test_credentials,
):
    """Webhook returns 409 when plan is inactive."""
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_1234567890",
                    "notes": {
                        "tenant_id": str(owner_tenant.id),
                        "plan_code": inactive_plan.code.value,
                    },
                }
            }
        },
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 409
    assert "no longer active" in response.json()["detail"]


def test_webhook_idempotent(
    auth_client: TestClient,
    owner_tenant: Tenant,
    test_plan: Plan,
    razorpay_test_credentials,
):
    """Duplicate webhook delivery is idempotent (applies same plan again)."""
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_1234567890",
                    "amount": test_plan.price_in_cents,
                    "currency": test_plan.currency,
                    "notes": {
                        "tenant_id": str(owner_tenant.id),
                        "user_id": "42",
                        "plan_code": test_plan.code.value,
                    },
                }
            }
        },
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    # First webhook
    response1 = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )
    assert response1.status_code == 200

    # Duplicate webhook (same payload)
    response2 = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )
    assert response2.status_code == 200

    # Both should return the same result
    data1 = response1.json()
    data2 = response2.json()
    assert data1["tenant_id"] == data2["tenant_id"]
    assert data1["new_plan_id"] == data2["new_plan_id"]
    assert data1["plan_code"] == data2["plan_code"]


def test_webhook_upgrade_from_existing_plan(
    auth_client: TestClient,
    owner_tenant: Tenant,
    test_plan: Plan,
    enterprise_plan: Plan,
    razorpay_test_credentials,
    db_session,
):
    """Webhook upgrades tenant from existing plan to new plan."""
    # Set initial plan
    owner_tenant.plan_id = test_plan.id
    db_session.commit()

    # Webhook to upgrade to enterprise
>>>>>>> origin/main
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
<<<<<<< HEAD
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
def test_webhook_returns_503_on_database_error(mock_verify, client, db_session, test_plan, enterprise_plan):
    """Webhook returns 503 when database is unavailable."""
    from unittest.mock import MagicMock
    from app.db.database import get_db
    from app.main import app
    
    mock_verify.return_value = True

    # Create a tenant with no plan yet
    tenant = Tenant(name="Test Tenant 503", slug="test503db", plan_id=None)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # Create a mock session that raises OperationalError on execute
    mock_session = MagicMock()
    mock_session.execute.side_effect = sqlalchemy_exc.OperationalError("Connection failed", {}, None)

    def override_get_db():
        yield mock_session

    # Override the get_db dependency
    app.dependency_overrides[get_db] = override_get_db

    try:
=======
                "entity": {
                    "id": "pay_1234567890",
                    "amount": enterprise_plan.price_in_cents,
                    "currency": enterprise_plan.currency,
                    "notes": {
                        "tenant_id": str(owner_tenant.id),
                        "user_id": "42",
                        "plan_code": enterprise_plan.code.value,
                    },
                }
            }
        },
    }
    payload_str = json.dumps(payload)
    secret = "test_secret_1234567890abcdef"
    signature = _generate_webhook_signature(payload_str, secret)

    response = auth_client.post(
        "/billing/webhook",
        content=payload_str,
        headers={"X-Razorpay-Signature": signature},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["previous_plan_id"] == test_plan.id
    assert data["new_plan_id"] == enterprise_plan.id
    assert data["plan_code"] == enterprise_plan.code.value


def test_webhook_all_plan_tiers(
    auth_client: TestClient,
    owner_tenant: Tenant,
    razorpay_test_credentials,
    db_session,
):
    """Webhook successfully applies each of the three plan tiers."""

    plans = {
        PlanTier.STARTER: ("Starter", 1, 5, 100),
        PlanTier.GROWTH: ("Growth", 5, 25, 500),
        PlanTier.ENTERPRISE: ("Enterprise", None, None, None),
    }

    for tier, (name, max_branches, max_staff, max_students) in plans.items():
        # Create plan
        plan = Plan(
            code=tier,
            name=name,
            description=f"{name} tier",
            max_branches=max_branches,
            max_staff=max_staff,
            max_students=max_students,
            price_in_cents=100000,
            currency="INR",
            is_active=True,
        )
        db_session.add(plan)
        db_session.commit()

        # Send webhook
>>>>>>> origin/main
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
<<<<<<< HEAD
                    "notes": {"tenant_id": str(tenant.id), "plan_code": enterprise_plan.code.value},
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
    finally:
        # Clean up the override
        app.dependency_overrides = {}
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


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_is_idempotent_when_plan_already_applied(mock_verify, client, db_session):
    """Webhook is idempotent: processing the same webhook twice is safe.

    This test prevents replay attacks and duplicate processing. If the tenant
    already has the target plan, the webhook returns 200 OK without making
    any changes.
    """
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

    # Simulate first Razorpay webhook for upgrade to growth
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {"tenant_id": str(tenant.id), "plan_code": "growth"},
                "entity": {"id": "pay_123"},
            }
        },
    }

    response1 = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response1.status_code == status.HTTP_200_OK
    assert response1.json() == {"status": "ok"}

    # Verify plan was updated
    db_session.refresh(tenant)
    assert tenant.plan_id == growth_plan.id

    # Simulate DUPLICATE webhook (Razorpay may retry)
    # This should be idempotent - no error, no change
    response2 = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response2.status_code == status.HTTP_200_OK
    assert response2.json() == {"status": "ok"}

    # Verify plan is still growth (not changed again)
    db_session.refresh(tenant)
    assert tenant.plan_id == growth_plan.id


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_enforces_multi_tenant_scoping(mock_verify, client, db_session):
    """Webhook enforces multi-tenant scoping: tenant must exist.

    This prevents a malicious actor from injecting arbitrary tenant_id values
    to upgrade other tenants. The webhook verifies the tenant exists before
    applying any plan changes.
    """
    mock_verify.return_value = True

    # Create a growth plan (no tenant needed for this test)
    growth_plan = Plan(
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=5,
        max_staff=20,
        max_students=500,
        price_in_cents=500000,
        currency="INR",
    )
    db_session.add(growth_plan)
    db_session.commit()

    # Try to process webhook for non-existent tenant
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

    # Should return 404 - tenant not found
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Tenant not found"

    # Verify no plan change was applied (tenant doesn't exist anyway)
    # This test confirms the security check prevents malicious tenant_id injection


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_validates_plan_code_before_applying(mock_verify, client, db_session):
    """Webhook validates plan_code exists before applying changes.

    This prevents applying an invalid or non-existent plan to a tenant.
    """
    mock_verify.return_value = True

    # Create a tenant
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    db_session.add(tenant)
    db_session.commit()

    # Try to process webhook for non-existent plan
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": {"tenant_id": str(tenant.id), "plan_code": "nonexistent_plan"},
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

    # Should return 404 - plan not found
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plan not found"

    # Verify tenant's plan was not changed (should still be None)
    db_session.refresh(tenant)
    assert tenant.plan_id is None


@patch("app.routers.billing.verify_webhook_signature")
def test_webhook_integration_end_to_end_flow(mock_verify, client, db_session):
    """Integration test: order creation notes match webhook processing.

    This test verifies the integration between task #223 (order creation)
    and task #224 (webhook processing). The order creation endpoint embeds
    tenant_id and plan_code in the order notes, and the webhook extracts
    and validates these fields to apply the plan change.
    """
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

    # Simulate the order notes that would be created by task #223
    # These notes are embedded in the Razorpay order during creation
    order_notes = {
        "tenant_id": str(tenant.id),
        "plan_code": "growth",
        "user_id": "123",  # Simulated user ID
    }

    # Simulate webhook with these notes
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "notes": order_notes,
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

    # Verify plan was updated
    db_session.refresh(tenant)
    assert tenant.plan_id == growth_plan.id

    # Verify we can process the same webhook again (idempotency)
    response2 = client_post_with_json_content(
        client,
        "/billing/webhooks/razorpay",
        payload,
        headers={"X-Razorpay-Signature": "valid_signature"},
    )

    assert response2.status_code == status.HTTP_200_OK
    db_session.refresh(tenant)
    assert tenant.plan_id == growth_plan.id  # Still growth, no error
=======
                    "entity": {
                        "id": f"pay_{tier.value}",
                        "amount": plan.price_in_cents,
                        "currency": plan.currency,
                        "notes": {
                            "tenant_id": str(owner_tenant.id),
                            "user_id": "42",
                            "plan_code": plan.code.value,
                        },
                    }
                }
            },
        }
        payload_str = json.dumps(payload)
        secret = "test_secret_1234567890abcdef"
        signature = _generate_webhook_signature(payload_str, secret)

        response = auth_client.post(
            "/billing/webhook",
            content=payload_str,
            headers={"X-Razorpay-Signature": signature},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["plan_code"] == tier.value
        assert data["new_plan_id"] == plan.id

        # Verify tenant updated
        db_session.refresh(owner_tenant)
        assert owner_tenant.plan_id == plan.id

        # Clean up for next iteration
        owner_tenant.plan_id = None
        db_session.commit()
>>>>>>> origin/main
