"""Low-level SMTP send helper (mock-friendly for tests)."""

import smtplib
from email.message import EmailMessage

from app.email.config import smtp_from_address, smtp_host, smtp_port


class EmailDeliveryError(Exception):
    """Raised when an outbound email cannot be delivered via SMTP."""


def send_email(*, to: str, subject: str, body_text: str) -> None:
    """Send a plain-text email via SMTP."""
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
