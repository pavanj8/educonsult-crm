"""SMTP email delivery seam (E49 / Journey J42; issue #232).

The public surface of this package is intentionally minimal: the
low-level :func:`send_email` chokepoint and the :class:`EmailDeliveryError`
sentinel. Per the contract pinned by
``tests/email/test_e49_abstraction.py``, ``__all__`` is exactly these
two names; anything else (the key-event templates, owner-invite
senders, password-reset senders) lives in a dedicated submodule
(``app.email.notifications``, ``app.email.owner_invite``,
``app.email.password_reset``) and is imported from there.
"""

from app.email.service import EmailDeliveryError, send_email

__all__ = ["EmailDeliveryError", "send_email"]
