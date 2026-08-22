"""Password reset token model (E6 schema; Journey J45).

This module owns the persisted half of the E6 password-reset flow
("forgot-password flow via emailed reset link/token"; Journey J45).
The ``POST /auth/forgot-password`` endpoint that *issues* a token (and
sends the email) lands in sibling ticket #90; the
``POST /auth/reset-password`` endpoint that *consumes* a token (and
sets a new password) lands in sibling ticket #91. Here we only
provide the persisted shape those endpoints write/read.

Design (Requirements §8; Journey J45; Epic E6):

* Tenant-scoped (ADR-0001: every table carries ``tenant_id``).
  Inherited from :class:`TenantScopedBase`, which also provides
  ``id``, ``created_at``, and ``updated_at``. ``tenant_id`` is
  denormalised from the owning user so the reset endpoint can apply
  the standard tenant-scoping filter without a join to ``users``.
* ``user_id`` FK -> ``users.id`` (ON DELETE CASCADE) so deleting a
  user account also drops any pending reset tokens for them (a user
  with no account has no inbox and no pending resets).
* ``token_hash`` stores the SHA-256 hex digest of the random reset
  token, *not* the raw token itself. The raw token is emailed to the
  user (E6 email template, sibling ticket #92) and is never written
  to disk; only its hash is stored so a database leak does not
  expose usable reset links. SHA-256 is appropriate here because the
  token is high-entropy random bytes (it is not a user-chosen
  password). 64 chars (hex of 32 bytes). Unique-indexed because the
  reset endpoint's hot path is "look up token by its hash".
* ``expires_at`` is the absolute deadline after which the token is
  rejected (Journey J45; the E6 tests cover "expired token" via this
  column). Indexed because the cleanup query "find all expired,
  unused tokens" benefits from it.
* ``used_at`` is the nullable timestamp set when the token is
  consumed by the reset endpoint. NULL = unused. Combined with the
  lookup-by-hash query, ``used_at IS NULL AND expires_at > now()``
  is the canonical "valid token" predicate, and a non-NULL value
  enforces single-use (the reset endpoint refuses a token whose
  ``used_at`` is already set, which is the second half of the
  "expired/invalid token" E6 test scenarios).
* No FK from ``users`` back to ``password_reset_tokens``: tokens are
  transient and may be issued for a deactivated user (e.g. staff
  deactivating their own account, then requesting a reset). The
  reset endpoint applies its own validity check; we do not want to
  cascade-delete a still-pending token when a user is deactivated.

Indexes target the access patterns the endpoints above will use:

* ``token_hash`` -- unique; the per-request lookup at reset time.
* ``user_id`` -- listing "all tokens for a user" (cleanup, audit)
  and the ON DELETE CASCADE FK to ``users``.
* ``expires_at`` -- "find all expired, unused tokens" for cleanup.
* ``tenant_id`` -- tenant-scoping filter on the lookup query.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["PasswordResetToken"]


class PasswordResetToken(TenantScopedBase):
    """A single-use password-reset token issued for one user (E6; Journey J45).

    See module docstring for design rationale. Each row is created by
    the ``POST /auth/forgot-password`` endpoint and consumed (exactly
    once) by ``POST /auth/reset-password``. The raw token is never
    stored -- only its SHA-256 hash.
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )