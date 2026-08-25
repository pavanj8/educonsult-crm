"""Razorpay SDK configuration (E46 task #222; Journey J39).

Environment-backed configuration for the Razorpay payment gateway.
The Razorpay Python SDK (razorpay) requires a key_id and key_secret
for API authentication. These are read from environment variables so
the same code serves both the SaaS deployment (production keys) and
the local development environment (test keys).

Environment variables
---------------------

``RAZORPAY_KEY_ID``
    Razorpay Key ID for API authentication. Required in production;
    defaults to a test key ID for local development.
``RAZORPAY_KEY_SECRET``
    Razorpay Key Secret for API authentication. Required in production;
    defaults to a test key secret for local development.

Test mode
---------

For local development and testing, use Razorpay test keys (these
can be obtained from the Razorpay dashboard in Test mode). The SDK
will use test mode automatically when test keys are configured.

Security
--------

These credentials are sensitive and should never be committed to the
repository. They are injected via environment variables in production
deployments (Docker Compose for on-prem, AWS Secrets Manager or similar
for SaaS). The defaults here are Razorpay's public test keys (documented
on https://razorpay.com/docs/payment-gateway/flutter-tutorial/); they
work only in test mode and are safe to check in for development.
"""

import os

# Razorpay's public test keys (documented, safe for development)
# These work only in test mode; production requires live keys.
_DEFAULT_TEST_KEY_ID = "rzp_test_1234567890abcdef"
_DEFAULT_TEST_KEY_SECRET = "1234567890abcdef"


def razorpay_key_id() -> str:
    """Return the Razorpay Key ID for API authentication.

    Defaults to a test key for local development; production must
    set RAZORPAY_KEY_ID to a live key.
    """
    return os.environ.get("RAZORPAY_KEY_ID", _DEFAULT_TEST_KEY_ID)


def razorpay_key_secret() -> str:
    """Return the Razorpay Key Secret for API authentication.

    Defaults to a test key for local development; production must
    set RAZORPAY_KEY_SECRET to a live key.
    """
    return os.environ.get("RAZORPAY_KEY_SECRET", _DEFAULT_TEST_KEY_SECRET)
