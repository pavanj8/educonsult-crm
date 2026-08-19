"""SMTP email delivery (E8 owner invite; pluggable for E49 notifications)."""

from app.email.service import EmailDeliveryError, send_email

__all__ = ["EmailDeliveryError", "send_email"]
