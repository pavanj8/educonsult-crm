"""SMTP email delivery (E8 owner invite; E49 key-event notifications).

Public surface:
* :func:`send_email` / :class:`EmailDeliveryError` -- low-level SMTP
  send helper shared by every template below.
* :func:`send_owner_invite_email` -- E8 / J1 owner-invite template.
* :func:`send_password_reset_email` -- E6 / J45 password-reset template.
* :func:`send_stage_changed_email` / :func:`send_document_approved_email` /
  :func:`send_document_rejected_email` / :func:`send_meeting_scheduled_email`
  -- E49 / J42 key-event templates (issue #233).
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
