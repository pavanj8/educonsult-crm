"""Unit tests for the E49 email service abstraction (Issue #232).

Issue #232 — "Backend: email service abstraction (SMTP client wrapper)"
— is the first task in the E49 / J42 "Email Notifications" epic. The
abstraction is the seam through which every outbound transactional
email leaves the backend; the other three E49 tasks (templates,
wiring, mocked-SMTP integration tests) build on top of it.

These tests pin the *contract* the abstraction exposes to the rest of
the codebase, so:

* The E49 templates ticket (issue #233) knows it composes
  ``(subject, body_text)`` and hands them to :func:`send_email`.
* The E49 wiring ticket (issue #234) knows it imports
  :class:`EmailDeliveryError` and maps it to a 503.
* The E49 mocked-SMTP integration tests (issue #235) can stub the
  network cleanly by patching the public :func:`send_email` symbol at
  its module of use — not by monkey-patching ``smtplib``.

Smoke coverage of the public package surface lives here too, so the
E49 epic has a single, dedicated test module that documents the
abstraction's contract. Existing ``tests/email/test_service.py`` and
``tests/email/test_password_reset.py`` cover the historical E6 / E8
use cases; this file is the E49 view.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from app.email import service as email_service
from app.email.config import (
    _DEFAULT_SMTP_FROM,
    _DEFAULT_SMTP_HOST,
    _DEFAULT_SMTP_PORT,
    app_base_url,
    smtp_from_address,
    smtp_host,
    smtp_port,
)
from app.email.service import EmailDeliveryError, send_email


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_package_exposes_send_email_and_delivery_error():
    """The package's public surface is exactly two symbols.

    E49 wiring (issue #234) will import ``send_email`` /
    ``EmailDeliveryError`` from ``app.email``. Pinning the surface
    here means adding a third public name would be a deliberate,
    reviewable decision rather than an accidental sprawl.
    """
    import app.email as email_pkg

    assert set(email_pkg.__all__) == {"EmailDeliveryError", "send_email"}
    assert email_pkg.send_email is send_email
    assert email_pkg.EmailDeliveryError is EmailDeliveryError


# ---------------------------------------------------------------------------
# Happy path: SMTP send_message receives a well-formed EmailMessage
# ---------------------------------------------------------------------------


def test_send_email_uses_smtp_host_port_and_from_address_from_config(monkeypatch):
    """send_email reads SMTP settings live from app.email.config.

    The env-driven config layer is what makes the abstraction
    pluggable for future SMS / WhatsApp providers: swapping the
    transport only requires changing :mod:`app.email.config`, never
    the call sites.
    """
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_FROM", "alerts@example.com")

    fake_server = MagicMock()
    fake_smtp = MagicMock()
    fake_smtp.return_value.__enter__.return_value = fake_server
    # ``__enter__`` / ``__exit__`` must be on the instance returned by
    # SMTP(...) for ``with smtplib.SMTP(...) as server:`` to work.
    fake_smtp.return_value.__enter__.return_value.send_message = fake_server.send_message

    with patch.object(email_service.smtplib, "SMTP", fake_smtp):
        send_email(
            to="recipient@example.test",
            subject="Hello",
            body_text="Body content.",
        )

    fake_smtp.assert_called_once_with(
        smtp_host(),
        smtp_port(),
        timeout=10,
    )
    assert smtp_host() == "smtp.example.com"
    assert smtp_port() == 2525

    fake_server.send_message.assert_called_once()
    sent_message = fake_server.send_message.call_args[0][0]
    assert isinstance(sent_message, EmailMessage)
    assert sent_message["Subject"] == "Hello"
    assert sent_message["From"] == "alerts@example.com"
    assert sent_message["To"] == "recipient@example.test"
    assert sent_message.get_content() == "Body content.\n"


def test_send_email_falls_back_to_default_smtp_settings(monkeypatch):
    """With no env overrides, the wrapper targets MailHog on localhost:1025.

    Mirrors the E1 docker-compose default so a fresh checkout can
    send email without env configuration. The defaults are exposed
    here so the test fails loudly if they drift away from what the
    local stack expects.
    """
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_FROM"):
        monkeypatch.delenv(var, raising=False)

    fake_smtp = MagicMock()
    fake_smtp.return_value.__enter__.return_value.send_message = MagicMock()

    with patch.object(email_service.smtplib, "SMTP", fake_smtp):
        send_email(
            to="recipient@example.test",
            subject="S",
            body_text="B",
        )

    fake_smtp.assert_called_once_with(
        _DEFAULT_SMTP_HOST,
        _DEFAULT_SMTP_PORT,
        timeout=10,
    )
    assert smtp_from_address() == _DEFAULT_SMTP_FROM


# ---------------------------------------------------------------------------
# Error translation: every SMTP failure mode becomes EmailDeliveryError
# ---------------------------------------------------------------------------


def test_send_email_translates_oserror_to_delivery_error(monkeypatch):
    """An unreachable SMTP host (OSError on connect) becomes EmailDeliveryError.

    The wrapper must collapse transport-level exceptions down to a
    single sentinel so the E49 wiring ticket (issue #234) has exactly
    one thing to catch at the router boundary.
    """

    class UnreachableSMTP:
        def __init__(self, *args, **kwargs):
            raise OSError("connection refused")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, _message):
            raise AssertionError("should not be reached")

    monkeypatch.setattr(email_service.smtplib, "SMTP", UnreachableSMTP)

    with pytest.raises(EmailDeliveryError, match="connection refused"):
        send_email(to="x@example.test", subject="s", body_text="b")


def test_send_email_translates_smtp_exception_to_delivery_error(monkeypatch):
    """A smtplib.SMTPException during send_message becomes EmailDeliveryError."""

    class RejectingSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, _message):
            raise smtplib.SMTPException("550 user unknown")

    monkeypatch.setattr(email_service.smtplib, "SMTP", RejectingSMTP)

    with pytest.raises(EmailDeliveryError, match="550 user unknown"):
        send_email(to="x@example.test", subject="s", body_text="b")


def test_send_email_translates_timeout_to_delivery_error(monkeypatch):
    """socket.timeout during SMTP connect becomes EmailDeliveryError.

    ``socket.timeout`` is an ``OSError`` subclass, so it is covered by
    the existing ``except OSError`` branch — this test pins that
    behaviour so a future refactor doesn't accidentally narrow the
    catch.
    """
    import socket

    class TimeoutSMTP:
        def __init__(self, *args, **kwargs):
            raise socket.timeout("timed out")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, _message):
            raise AssertionError("should not be reached")

    monkeypatch.setattr(email_service.smtplib, "SMTP", TimeoutSMTP)

    with pytest.raises(EmailDeliveryError, match="timed out"):
        send_email(to="x@example.test", subject="s", body_text="b")


# ---------------------------------------------------------------------------
# Mock-friendliness: the abstraction can be patched cleanly from any caller
# ---------------------------------------------------------------------------


def test_send_email_is_patchable_from_caller_module():
    """Caller modules can stub send_email via patch.object on the caller.

    The E49 mocked-SMTP integration tests (issue #235) and every
    unit test in this repo rely on being able to swap the SMTP
    network call out by patching ``<caller_module>.send_email`` —
    no test should have to monkey-patch ``smtplib.SMTP`` directly.

    This test imports a dummy caller, patches the symbol at the
    *caller's* import site, and confirms :func:`send_email` from the
    caller side is intercepted.
    """
    from tests.email import _dummy_caller  # noqa: WPS433 (test-only import)

    with patch.object(_dummy_caller, "send_email") as mock_send:
        _dummy_caller.send_a_via_abstraction(
            to="x@example.test",
            subject="S",
            body_text="B",
        )

    mock_send.assert_called_once_with(
        to="x@example.test",
        subject="S",
        body_text="B",
    )


# ---------------------------------------------------------------------------
# Configuration helpers exposed to the rest of the codebase
# ---------------------------------------------------------------------------


def test_app_base_url_strips_trailing_slash():
    """app_base_url must be safe to concatenate with a path.

    The E49 templates ticket (issue #233) will compose URLs like
    ``f"{app_base_url()}/some-path"``; a stray trailing slash on the
    operator-provided env value would otherwise produce ``//`` between
    host and path.
    """
    import os

    os.environ["APP_BASE_URL"] = "https://app.example.com/"
    try:
        assert app_base_url() == "https://app.example.com"
    finally:
        os.environ.pop("APP_BASE_URL", None)
