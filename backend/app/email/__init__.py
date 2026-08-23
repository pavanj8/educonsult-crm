"""SMTP email delivery and key-event email templates (E49 / Journey J42).

The package exposes the low-level SMTP seam, existing owner-invite and
password-reset senders, and issue #233's stage-change, document-review,
and meeting-scheduled templates.
"""

from app.email.notifications import (
    build_document_approved_body,
    build_document_rejected_body,
    build_meeting_scheduled_body,
    build_stage_changed_body,
    send_document_approved_email,
    send_document_rejected_email,
    send_meeting_scheduled_email,
    send_stage_changed_email,
)
from app.email.owner_invite import send_owner_invite_email
from app.email.password_reset import send_password_reset_email
from app.email.service import EmailDeliveryError, send_email

__all__ = [
    "EmailDeliveryError",
    "build_document_approved_body",
    "build_document_rejected_body",
    "build_meeting_scheduled_body",
    "build_stage_changed_body",
    "send_document_approved_email",
    "send_document_rejected_email",
    "send_email",
    "send_meeting_scheduled_email",
    "send_owner_invite_email",
    "send_password_reset_email",
    "send_stage_changed_email",
]
