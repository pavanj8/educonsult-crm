"""Debug test for endpoint."""

from unittest.mock import patch
from fastapi import status


def test_endpoint_with_fixture(
    db_session, auth_client, owner_user, owner_tenant, test_plan, razorpay_test_credentials
):
    """Test endpoint with all fixtures."""
    # First verify env vars are set
    import os
    print(f"DEBUG env RAZORPAY_KEY_ID: {os.environ.get('RAZORPAY_KEY_ID')}")

    # Mock Razorpay client
    mock_order_response = {
        "id": "order_123abc",
        "amount": 100000,
        "currency": "INR",
        "status": "created",
    }

    # Patch at the router's import location
    with patch("app.routers.billing.create_order") as mock_create_order:
        mock_create_order.return_value = mock_order_response

        response = auth_client.post(
            "/billing/create-upgrade-order",
            json={"plan_code": "growth"},
        )

        print(f"DEBUG response status: {response.status_code}")
        print(f"DEBUG response body: {response.text}")
        assert response.status_code == status.HTTP_201_CREATED
