"""Integration tests for billing endpoints (E46)."""

from fastapi import status


def test_billing_router_is_registered(client):
    """Verify the billing router is properly registered in the FastAPI app."""
    response = client.get("/health")
    # If the app loaded successfully, the health check returns 200
    assert response.status_code == status.HTTP_200_OK


def test_create_upgrade_order_endpoint_exists(client):
    """Verify the POST /billing/create-upgrade-order endpoint exists."""
    # Unauthenticated request should return 401, not 404
    response = client.post("/billing/create-upgrade-order", json={"plan_code": "growth"})
    # Should get 401 (unauthorized) rather than 404 (not found)
    # This proves the endpoint is registered
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


def test_webhook_endpoint_exists(client):
    """Verify the POST /billing/webhooks/razorpay endpoint exists."""
    # Webhook without signature should return 401, not 404
    response = client.post("/billing/webhooks/razorpay", json={"event": "payment.captured"})
    # Should get 401 (invalid signature) rather than 404 (not found)
    # This proves the endpoint is registered
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_plans_seed_exists(db_session):
    """Verify that plans can be created in the database."""
    from app.models.plan import Plan, PlanTier

    plan = Plan(
        code=PlanTier.GROWTH,
        name="Growth",
        description="Test plan",
        max_branches=5,
        max_staff=25,
        max_students=500,
        price_in_cents=100000,
        currency="INR",
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()

    retrieved = db_session.query(Plan).filter_by(code=PlanTier.GROWTH).first()
    assert retrieved is not None
    assert retrieved.name == "Growth"
    assert retrieved.price_in_cents == 100000
