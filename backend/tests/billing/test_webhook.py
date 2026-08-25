"""Tests for Razorpay webhook handler (E46 task #224)."""

import json
import hashlib
import hmac

from fastapi.testclient import TestClient

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant


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
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
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
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
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
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
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
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
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
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
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
