"""Razorpay SDK configuration (E46 task #222; Journey J39).

Environment-backed configuration for the Razorpay payment gateway.
The Razorpay Python SDK (razorpay) requires a key_id and key_secret
for API authentication. These are read from environment variables so
the same code serves both the SaaS deployment (production keys) and
the local development environment (test keys).

Environment variables
---------------------

``RAZORPAY_KEY_ID``
    Razorpay Key ID for API authentication. **Required** — the application
    will fail to start with a clear error if this is not set.
``RAZORPAY_KEY_SECRET``
    Razorpay Key Secret for API authentication. **Required** — the application
    will fail to start with a clear error if this is not set.

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
for SaaS). There are NO hardcoded defaults — credentials must be
explicitly configured or the application will raise a RuntimeError at
startup.
"""

import os


def razorpay_key_id() -> str:
    """Return the Razorpay Key ID for API authentication.

    Reads from the ``RAZORPAY_KEY_ID`` environment variable. This is
    required; if not set, a ``RuntimeError`` is raised.

    Returns:
        The Razorpay Key ID.

    Raises:
        RuntimeError: If ``RAZORPAY_KEY_ID`` is not set in the environment.
    """
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    if not key_id or not key_id.strip():
        raise RuntimeError(
            "RAZORPAY_KEY_ID environment variable is required but not set. "
            "Obtain test keys from https://dashboard.razorpay.com/testmode "
            "or live keys from your Razorpay dashboard."
        )
    return key_id.strip()


def razorpay_key_secret() -> str:
    """Return the Razorpay Key Secret for API authentication.

    Reads from the ``RAZORPAY_KEY_SECRET`` environment variable. This is
    required; if not set, a ``RuntimeError`` is raised.

    Returns:
        The Razorpay Key Secret.

    Raises:
        RuntimeError: If ``RAZORPAY_KEY_SECRET`` is not set in the environment.
    """
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_secret or not key_secret.strip():
        raise RuntimeError(
            "RAZORPAY_KEY_SECRET environment variable is required but not set. "
            "Obtain test keys from https://dashboard.razorpay.com/testmode "
            "or live keys from your Razorpay dashboard."
        )
    return key_secret.strip()
