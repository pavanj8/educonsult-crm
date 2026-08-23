<<<<<<< HEAD
"""SMTP email delivery (E8 owner invite; E49 key-event notifications).
=======
"""SMTP email delivery — E49 Email Notifications (Journey J42; issue #232).

This package is the *only* place the backend talks to SMTP:

* :mod:`app.email.service` — the low-level SMTP client wrapper
  (:func:`send_email` + :class:`EmailDeliveryError`). E49 task #232.
* :mod:`app.email.config` — environment-driven SMTP host/port/from
  address plus the public-facing ``APP_BASE_URL`` used by email
  templates.
* :mod:`app.email.owner_invite` — owner-invite email used by the
  E8 tenant-creation flow (J1).
* :mod:`app.email.password_reset` — forgot-password email used by the
  E6 password-reset flow (J45).

The E49 epic splits the work across four issues:

* #232 (this module's :mod:`app.email.service`) — SMTP client wrapper.
* #233 — per-event email templates (stage change, document review,
  meeting scheduled, invite). Adds new modules that call
  :func:`send_email`.
* #234 — wire :func:`send_email` into the existing E48 notification
  triggers. Catches :class:`EmailDeliveryError` at the router/service
  boundary.
* #235 — mocked-SMTP integration tests covering the E49 flows.

The public surface other code is expected to import is intentionally
tiny — :func:`send_email` and :class:`EmailDeliveryError` — so the
upcoming E49 wiring has a single, stable call site.
"""
>>>>>>> origin/main

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
