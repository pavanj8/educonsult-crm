"""Low-level SMTP send helper.

This module is the single chokepoint for outbound email. It accepts a
rendered subject and plain-text body, then delivers them through the
SMTP settings exposed by :mod:`app.email.config`.

Keeping SMTP isolated here lets future notification transports be added
without changing template or trigger code.
"""

import smtplib
from email.message import EmailMessage

from app.email.config import smtp_from_address, smtp_host, smtp_port


class EmailDeliveryError(Exception):
    """Raised when outbound email cannot be delivered through the SMTP transport."""


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
