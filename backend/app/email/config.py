"""Environment-backed configuration for outbound email.

SMTP settings and the application base URL are read at call time so
deployments can override them without restarting the process.

The defaults match the local MailHog service. ``smtp_port`` raises
``ValueError`` for a non-integer ``SMTP_PORT`` value.
"""

import os

_DEFAULT_SMTP_HOST = "localhost"
_DEFAULT_SMTP_PORT = 1025
_DEFAULT_SMTP_FROM = "noreply@educonsult.test"
_DEFAULT_APP_BASE_URL = "http://localhost:5173"


def smtp_host() -> str:
    """Return the SMTP server hostname (default: MailHog in local dev)."""
    return os.environ.get("SMTP_HOST", _DEFAULT_SMTP_HOST)


def smtp_port() -> int:
    """Return the SMTP server port (default: 1025 for MailHog in local dev).

    Raises:
        ValueError: If ``SMTP_PORT`` is not an integer.
    """
    return int(os.environ.get("SMTP_PORT", str(_DEFAULT_SMTP_PORT)))


def smtp_from_address() -> str:
    """Return the From: address stamped on every outbound email."""
    return os.environ.get("SMTP_FROM", _DEFAULT_SMTP_FROM)


def app_base_url() -> str:
    """Return the public-facing frontend base URL used in email links.

    A trailing slash is stripped so paths can be concatenated safely.
    """
    return os.environ.get("APP_BASE_URL", _DEFAULT_APP_BASE_URL).rstrip("/")
