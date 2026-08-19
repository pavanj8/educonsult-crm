"""SMTP configuration for outbound email (Requirements §2; MailHog in local dev)."""

import os

_DEFAULT_SMTP_HOST = "localhost"
_DEFAULT_SMTP_PORT = 1025
_DEFAULT_SMTP_FROM = "noreply@educonsult.test"
_DEFAULT_APP_BASE_URL = "http://localhost:5173"


def smtp_host() -> str:
    return os.environ.get("SMTP_HOST", _DEFAULT_SMTP_HOST)


def smtp_port() -> int:
    return int(os.environ.get("SMTP_PORT", str(_DEFAULT_SMTP_PORT)))


def smtp_from_address() -> str:
    return os.environ.get("SMTP_FROM", _DEFAULT_SMTP_FROM)


def app_base_url() -> str:
    return os.environ.get("APP_BASE_URL", _DEFAULT_APP_BASE_URL).rstrip("/")
