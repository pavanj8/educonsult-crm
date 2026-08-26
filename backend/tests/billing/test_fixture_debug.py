"""Debug test for fixture issues."""

import os


def test_env_var_fixture(razorpay_test_credentials):
    """Check if the fixture sets environment variables."""
    print(f"RAZORPAY_KEY_ID: {os.environ.get('RAZORPAY_KEY_ID')}")
    print(f"RAZORPAY_KEY_SECRET: {os.environ.get('RAZORPAY_KEY_SECRET')}")

    assert os.environ.get("RAZORPAY_KEY_ID") == "rzp_test_1234567890abcdef"
    assert os.environ.get("RAZORPAY_KEY_SECRET") == "test_secret_1234567890abcdef"


def test_config_after_fixture(razorpay_test_credentials):
    """Check if config functions work after fixture."""
    from app.billing.config import razorpay_key_id, razorpay_key_secret

    key_id = razorpay_key_id()
    key_secret = razorpay_key_secret()

    assert key_id == "rzp_test_1234567890abcdef"
    assert key_secret == "test_secret_1234567890abcdef"
