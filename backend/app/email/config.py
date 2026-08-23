"""SMTP configuration for outbound email (Requirements §2; MailHog in local dev).

E49 / Issue #232 — Email service abstraction (SMTP client wrapper).

Every value in this module is read from an environment variable at
call time (never at import time) so:

* Local development points at MailHog (``localhost:1025``) via the
  E1 Docker Compose defaults — no code change required.
* On-prem / SaaS deployments override ``SMTP_HOST``, ``SMTP_PORT``,
  and ``SMTP_FROM`` via the deployment env file (E4 owns the env
  reference doc; the operator-facing knobs live here).
* The future E49 pluggable-transport story (SMS / WhatsApp providers
  shipping behind the same :func:`app.email.service.send_email` call
  site) can swap the transport without touching call sites — only
  this module needs to learn about a new backend's configuration.

The defaults below match the E1 docker-compose ``mailhog`` service so
a fresh checkout can send email with zero env configuration.
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
    """Return the SMTP server port (default: 1025 for MailHog in local dev)."""
    return int(os.environ.get("SMTP_PORT", str(_DEFAULT_SMTP_PORT)))


def smtp_from_address() -> str:
    """Return the From: address stamped on every outbound email."""
    return os.environ.get("SMTP_FROM", _DEFAULT_SMTP_FROM)


def app_base_url() -> str:
    """Return the public-facing frontend base URL used in email links.

    The trailing slash is stripped so callers can safely concatenate
    paths like ``f"{app_base_url()}/reset-password?token=..."`` without
    producing ``//reset-password``.
    """
    return os.environ.get("APP_BASE_URL", _DEFAULT_APP_BASE_URL).rstrip("/")
