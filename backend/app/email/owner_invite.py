"""Owner invite email for new tenant provisioning (E8; Journey J1)."""

from app.email.config import app_base_url
from app.email.service import send_email


def build_owner_invite_body(
    *,
    tenant_name: str,
    owner_email: str,
    temporary_password: str,
) -> str:
    login_url = f"{app_base_url()}/login"
    return (
        f"Hello,\n\n"
        f"You have been invited to manage {tenant_name} on EduConsult CRM.\n\n"
        f"Sign in with:\n"
        f"  Email: {owner_email}\n"
        f"  Temporary password: {temporary_password}\n\n"
        f"Log in at: {login_url}\n\n"
        f"Please change your password after your first sign-in.\n"
    )


def send_owner_invite_email(
    *,
    to_email: str,
    tenant_name: str,
    temporary_password: str,
) -> None:
    """Email the consultancy owner their temporary credentials."""
    subject = f"You're invited to manage {tenant_name} on EduConsult CRM"
    body = build_owner_invite_body(
        tenant_name=tenant_name,
        owner_email=to_email,
        temporary_password=temporary_password,
    )
    send_email(to=to_email, subject=subject, body_text=body)
