"""Low-level SMTP send helper (mock-friendly for tests).

E49 / Issue #232 — Email service abstraction (SMTP client wrapper).

This module is the single, well-tested seam through which every
outbound transactional email leaves the backend. Its sole job is to
take a rendered (subject + body_text) message and deliver it via SMTP,
raising :class:`EmailDeliveryError` on transport-level failure.

Design constraints (Requirements §2 "architecture kept pluggable for
SMS/WhatsApp later"; E49 description "pluggable for future
SMS/WhatsApp providers"):

* The public surface is a single :func:`send_email` function plus the
  :class:`EmailDeliveryError` sentinel. Callers (forgot-password,
  owner-invite, and the future E49 templates / wiring tickets) never
  touch ``smtplib`` directly — this is the only place SMTP is used.
* SMTP host/port/from-address are read from environment variables via
  :mod:`app.email.config` so a future SMS/WhatsApp backend can ship
  behind the same call site without rewriting the call sites that
  produce emails today.
* :func:`send_email` is deliberately import-and-patch friendly: every
  consumer patches ``app.email.<module>.send_email`` (or the module
  path of the caller) rather than reaching into this module. That is
  the contract that lets the E49 tests (issue #235) stub the network
  layer cleanly.

Out of scope (tracked as separate issues in E49):

* Email templates for key events (stage change, doc review, meeting,
  invite) — issue #233. That ticket composes the (subject, body)
  pair; this module only carries them.
* Wiring email sends into the existing notification triggers — issue
  #234. That ticket calls ``send_email`` from the E48 hooks; this
  module does not know about notifications.
* The mocked-SMTP integration tests — issue #235. That ticket owns
  end-to-end coverage; this module's tests focus on the wrapper
  itself (delegation + error translation).
"""

import smtplib
from email.message import EmailMessage

from app.email.config import smtp_from_address, smtp_host, smtp_port


class EmailDeliveryError(Exception):
    """Raised when an outbound email cannot be delivered via SMTP.

    This is the only failure sentinel the rest of the codebase is
    expected to handle — every SMTP-level exception (``OSError``,
    ``smtplib.SMTPException``) is translated to this single type at
    the boundary of :func:`send_email` so callers do not need to know
    about the underlying transport.

    For the upcoming E49 wiring ticket (issue #234), this means the
    notification-side error handling has exactly one thing to catch:
    ``from app.email.service import EmailDeliveryError``.
    """


def send_email(*, to: str, subject: str, body_text: str) -> None:
    """Send a plain-text email via SMTP.

    This is the *only* SMTP entry point in the codebase. Every email
    a user receives (forgot-password link, owner invite, future E49
    notifications) flows through here.

    Args:
        to: Recipient email address. Must be a single address; this
            wrapper does not parse comma-separated lists.
        subject: Email subject line.
        body_text: Plain-text body. Templating is the caller's job
            (the E49 templates ticket — issue #233 — owns that
            responsibility).

    Raises:
        EmailDeliveryError: If the SMTP transport refuses the
            message or the network is unreachable. Callers in the
            router layer (forgot-password, tenant creation, future
            E49 hooks) are expected to map this to a 503.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from_address()
    message["To"] = to
    message.set_content(body_text)

    try:
        with smtplib.SMTP(smtp_host(), smtp_port(), timeout=10) as server:
            server.send_message(message)
    except OSError as exc:
        raise EmailDeliveryError(str(exc)) from exc
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(str(exc)) from exc
