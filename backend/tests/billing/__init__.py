"""Tests for billing & subscription functionality (E46; Journey J39)."""

import pytest


@pytest.fixture()
def razorpay_test_credentials(monkeypatch):
    """Set test Razorpay credentials for tests that need them.

    Most billing tests need valid credentials to avoid RuntimeError.
    Tests that specifically test the error case should not use this fixture.
    """
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_1234567890abcdef")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_secret_1234567890abcdef")
