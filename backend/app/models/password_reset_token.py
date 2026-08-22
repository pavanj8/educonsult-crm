"""Password reset token model (E6; Journey J45).

A single-use token issued by ``POST /auth/forgot-password`` (issue #90)
and consumed by ``POST /auth/reset-password`` (issue #91) to let a user
pick a new password after forgetting the old one.

Design (Requirements §8 "JWT auth with refresh tokens"; Journey J45
"Forgot-password flow via emailed reset link/token"):

* ``user_id`` FK -> ``users.id`` (ON DELETE CASCADE) -- the account
  that requested the reset. CASCADE so removing a user also removes
  any outstanding tokens (they can no longer be used anyway).
* ``token_hash`` stores a SHA-256 *hash* of the random token string,
  not the plaintext. The plaintext is only ever sent to the user's
  email; the database only ever sees the hash, so a DB leak does not
  expose live reset links (same hygiene as E5 refresh-token storage).
* ``expires_at`` is the deadline after which the token is invalid
  (default 1 hour from issue).
* ``used_at`` is the nullable timestamp set when the token is consumed
  by ``POST /auth/reset-password``. NULL = not yet used. The reset
  endpoint must reject tokens that already have ``used_at`` set.

Tenant scoping is inherited from :class:`TenantScopedBase` (ADR-0001:
every table carries ``tenant_id``).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["PasswordResetToken"]


class PasswordResetToken(TenantScopedBase):
    """A single-use password-reset token issued for one user (E6; J45)."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
