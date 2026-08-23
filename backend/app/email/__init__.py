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

from app.email.service import EmailDeliveryError, send_email

__all__ = ["EmailDeliveryError", "send_email"]
