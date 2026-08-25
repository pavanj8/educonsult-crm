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
    mock_response = {"id": "order_123", "amount": 100000, "currency": "INR"}

    # Patch at the router's import location
    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.return_value = mock_response

        response = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        assert response.status_code == 201
