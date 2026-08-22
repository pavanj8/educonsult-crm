"""Password reset email for the E6 forgot-password flow (Journey J45).

Companion to ``send_owner_invite_email`` (E8) -- a plain-text message
that includes the reset link with the one-shot token. The link target
points at the frontend's reset-password page so the user can pick a
new password (issue #91 consumes the token, issue #93 owns the page).
"""

from app.email.config import app_base_url
from app.email.service import send_email


def build_password_reset_body(*, reset_url: str) -> str:
    return (
        "Hello,\n\n"
        "We received a request to reset the password on your "
        "EduConsult CRM account.\n\n"
        f"Reset your password by visiting the following link:\n  {reset_url}\n\n"
        "This link will expire in 1 hour and can only be used once.\n"
        "If you did not request a password reset, you can safely "
        "ignore this email.\n"
    )


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    """Email the recipient a single-use password-reset link."""
    subject = "Reset your EduConsult CRM password"
    body = build_password_reset_body(reset_url=reset_url)
    send_email(to=to_email, subject=subject, body_text=body)


def build_password_reset_url(*, token: str) -> str:
    """Return the full URL pointing at the frontend reset-password page."""
    return f"{app_base_url()}/reset-password?token={token}"