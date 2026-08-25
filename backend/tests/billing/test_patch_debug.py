"""Debug test for patching."""

from unittest.mock import patch
from app.billing import razorpay_client


def test_patch_works(razorpay_test_credentials):
    """Test if patching the create_order function works."""
    mock_response = {"id": "order_123", "amount": 100000, "currency": "INR"}

    # Check what we're patching
    print(f"create_order before patch: {razorpay_client.create_order}")
    print(f"create_order module: {razorpay_client.create_order.__module__}")

    with patch("app.billing.razorpay_client.create_order") as mock_create_order:
        mock_create_order.return_value = mock_response

        print(f"create_order inside patch: {razorpay_client.create_order}")
        print(f"mock called: {mock_create_order.called}")

        result = razorpay_client.create_order(
            amount_in_paise=100000,
            currency="INR",
            receipt_id="test_receipt",
            notes={"test": "note"},
        )

        print(f"result: {result}")
        assert result == mock_response
        assert mock_create_order.called


def test_patch_in_router_call(db_session, auth_client, owner_user, owner_tenant, test_plan, razorpay_test_credentials):
    """Test if patching works when calling through the router."""
    from app.billing.razorpay_client import create_order

    mock_response = {"id": "order_123", "amount": 100000, "currency": "INR"}

    print(f"create_order id before patch: {id(create_order)}")

    # The patch in the router uses "app.billing.razorpay_client.create_order"
    # But the router imports it as: from app.billing.razorpay_client import create_order
    # So we need to patch where it's used
    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.return_value = mock_response

        print(f"create_order id inside patch: {id(create_order)}")
        print(f"mock id: {id(mock_create_order)}")

        response = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        assert response.status_code == 201
