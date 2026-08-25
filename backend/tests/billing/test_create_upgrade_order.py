"""Tests for plan upgrade order creation endpoint (E46 task #223)."""

from unittest.mock import patch

from fastapi import status


def test_create_upgrade_order_as_owner(
    db_session, auth_client, owner_user, owner_tenant, test_plan
):
    """Owner can create an upgrade order for their tenant."""
    # Mock Razorpay client to return a successful order
    mock_order_response = {
        "id": "order_123abc",
        "amount": 100000,  # 1000.00 INR in paisa
        "currency": "INR",
        "status": "created",
    }

    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.return_value = mock_order_response

        response = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["order_id"] == "order_123abc"
        assert data["amount"] == 100000
        assert data["currency"] == "INR"
        assert data["plan_code"] == "growth"
        assert data["plan_name"] == "Growth"

        # Verify create_order was called with correct parameters
        mock_create_order.assert_called_once()
        call_kwargs = mock_create_order.call_args.kwargs
        assert call_kwargs["amount_in_paise"] == test_plan.price_in_cents
        assert call_kwargs["currency"] == test_plan.currency
        assert "tenant_id" in call_kwargs["notes"]
        assert "user_id" in call_kwargs["notes"]
        assert call_kwargs["notes"]["plan_code"] == "growth"


def test_create_upgrade_order_plan_code_normalized(
    db_session, auth_client, owner_user, owner_tenant, test_plan
):
    """Plan code is normalized to lowercase (Growth -> growth)."""
    mock_order_response = {
        "id": "order_456def",
        "amount": test_plan.price_in_cents,
        "currency": "INR",
        "status": "created",
    }

    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.return_value = mock_order_response

        response = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "GROWTH"},  # Uppercase input
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["plan_code"] == "growth"  # Normalized in response


def test_create_upgrade_order_unknown_plan(db_session, auth_client, owner_user):
    """Unknown plan code returns 404."""
    response = auth_client.post(
        "/billing/create-upgrade-order",
        json={"plan_code": "unknown"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Plan not found" in response.json()["detail"]


def test_create_upgrade_order_inactive_plan(
    db_session, auth_client, owner_user, owner_tenant, inactive_plan
):
    """Inactive plan returns 409."""
    response = auth_client.post(
        "/billing/create-upgrade-order",
        json={"plan_code": "starter"},  # This plan is inactive
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "no longer active" in response.json()["detail"]


def test_create_upgrade_order_requires_billing_manage(
    db_session, client, student_user
):
    """Students cannot create upgrade orders (lack billing:manage)."""
    from app.auth.jwt import create_access_token
    from app.rbac.user import AuthenticatedUser

    token = create_access_token(
        AuthenticatedUser(
            id=student_user.id,
            role=student_user.role,
            tenant_id=student_user.tenant_id,
            branch_id=student_user.branch_id,
        )
    )
    response = client.post(
        "/billing/create-upgrade-order",
        json={"plan_code": "growth"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_create_upgrade_order_requires_authentication(db_session, client):
    """Unauthenticated requests are rejected."""
    response = client.post(
        "/billing/create-upgrade-order",
        json={"plan_code": "growth"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_upgrade_order_razorpay_unavailable(
    db_session, auth_client, owner_user, owner_tenant, test_plan
):
    """Razorpay service errors return 503."""
    import razorpay.errors

    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.side_effect = razorpay.errors.RazorpayError(
            "Razorpay API error"
        )

        response = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Payment gateway" in response.json()["detail"]


def test_create_upgrade_order_razorpay_not_configured(
    db_session,
    client,
    owner_user,
    owner_tenant,
    test_plan,
    monkeypatch,
):
    """Missing Razorpay credentials return 503."""
    # Create authenticated client first (before removing credentials)
    from app.auth.jwt import create_access_token
    from app.rbac.user import AuthenticatedUser

    token = create_access_token(
        AuthenticatedUser(
            id=owner_user.id,
            role=owner_user.role,
            tenant_id=owner_user.tenant_id,
            branch_id=owner_user.branch_id,
        )
    )
    client.headers.update({"Authorization": f"Bearer {token}"})

    # Remove the RAZORPAY_KEY_ID environment variable
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)

    # Also need to clear the cached config value
    import app.billing.config
    app.billing.config.razorpay_key_id.cache_clear()

    response = client.post(
        "/billing/create-upgrade-order",
        json={"plan_code": "growth"},
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "not configured" in response.json()["detail"]


def test_create_upgrade_order_empty_plan_code(
    db_session, auth_client, owner_user
):
    """Empty plan code returns 422."""
    response = auth_client.post(
        "/billing/create-upgrade-order",
        json={"plan_code": ""},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_upgrade_order_missing_plan_code(
    db_session, auth_client, owner_user
):
    """Missing plan code returns 422."""
    response = auth_client.post(
        "/billing/create-upgrade-order",
        json={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_upgrade_order_no_tenant_id(
    db_session, client, super_admin_user
):
    """Users without tenant_id (e.g., super admin) are rejected."""
    from app.auth.jwt import create_access_token
    from app.rbac.user import AuthenticatedUser

    token = create_access_token(
        AuthenticatedUser(
            id=super_admin_user.id,
            role=super_admin_user.role,
            tenant_id=super_admin_user.tenant_id,
            branch_id=super_admin_user.branch_id,
        )
    )
    response = client.post(
        "/billing/create-upgrade-order",
        json={"plan_code": "growth"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "not associated with a tenant" in response.json()["detail"]


def test_create_upgrade_order_enterprise_to_growth(
    db_session, auth_client, owner_user, owner_tenant, enterprise_plan
):
    """Downgrade from Enterprise to Growth works."""
    mock_order_response = {
        "id": "order_789xyz",
        "amount": enterprise_plan.price_in_cents,
        "currency": "INR",
        "status": "created",
    }

    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.return_value = mock_order_response

        response = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["plan_code"] == "growth"
        assert data["plan_name"] == "Growth"


def test_create_upgrade_order_multiple_orders_same_plan(
    db_session, auth_client, owner_user, owner_tenant, test_plan
):
    """Creating multiple orders for the same plan is allowed (idempotent)."""
    mock_order_response = {
        "id": "order_new_id",
        "amount": test_plan.price_in_cents,
        "currency": "INR",
        "status": "created",
    }

    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.return_value = mock_order_response

        # First order
        response1 = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Second order (different order_id, same plan)
        mock_create_order.return_value = {
            "id": "order_another_id",
            "amount": test_plan.price_in_cents,
            "currency": "INR",
            "status": "created",
        }
        response2 = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )
        assert response2.status_code == status.HTTP_201_CREATED

        # Verify two different orders were created
        assert response1.json()["order_id"] != response2.json()["order_id"]
