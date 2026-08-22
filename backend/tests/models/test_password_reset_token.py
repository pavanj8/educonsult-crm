"""Tests for the PasswordResetToken ORM model (E6; Journey J45).

Exercises column shape, persistence, the unique ``token_hash``
constraint, the nullable ``used_at`` column, single-use semantics
(setting ``used_at`` round-trips), and tenant scoping. The full
end-to-end "issue token -> email -> reset password -> mark used"
flow lands in the sibling E6 backend tests (#94); here we pin the
schema-only contract.

The ``ON DELETE CASCADE`` on ``user_id`` is not exercised at the SQL
level -- SQLite requires ``PRAGMA foreign_keys = ON`` per connection,
which the project's conftest does not enable, and the production
PostgreSQL behaviour is verified by the alembic migration's
``ondelete="CASCADE"`` clause itself (matching the convention used by
``Notification``, ``StageHistory``, etc., which similarly do not have
cascade-verification tests on SQLite).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect

from app.models.password_reset_token import PasswordResetToken


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_password_reset_token_model_has_required_columns():
    column_names = {column.key for column in inspect(PasswordResetToken).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "user_id",
        "token_hash",
        "expires_at",
        "used_at",
        "created_at",
        "updated_at",
    }


def test_password_reset_token_persists_full_row(db_session):
    """A fresh PasswordResetToken row with every required field round-trips."""
    now = _utc_now()
    expires_at = now + timedelta(hours=1)
    token = PasswordResetToken(
        tenant_id=1,
        user_id=42,
        token_hash="a" * 64,
        expires_at=expires_at,
        used_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)

    assert token.id is not None
    assert token.tenant_id == 1
    assert token.user_id == 42
    assert token.token_hash == "a" * 64
    # SQLite drops the tzinfo on round-trip; compare the absolute UTC instant.
    assert token.expires_at.replace(tzinfo=timezone.utc) == expires_at
    assert token.used_at is None
    assert token.created_at is not None
    assert token.updated_at is not None


def test_password_reset_token_used_at_is_nullable(db_session):
    """``used_at`` is NULL until the reset endpoint consumes the token (Journey J45)."""
    now = _utc_now()
    token = PasswordResetToken(
        tenant_id=1,
        user_id=1,
        token_hash="b" * 64,
        expires_at=now + timedelta(hours=1),
        used_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)

    assert token.used_at is None


def test_password_reset_token_can_be_marked_used(db_session):
    """Setting ``used_at`` round-trips and persists the consumption timestamp.

    The reset endpoint sets ``used_at`` exactly once when it consumes a
    valid token (single-use enforcement); this test pins that the
    timestamp persists losslessly.
    """
    now = _utc_now()
    later = now + timedelta(minutes=5)
    token = PasswordResetToken(
        tenant_id=1,
        user_id=1,
        token_hash="c" * 64,
        expires_at=now + timedelta(hours=1),
        used_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)

    assert token.used_at is None

    token.used_at = later
    db_session.commit()
    db_session.refresh(token)

    assert token.used_at is not None
    assert token.used_at.replace(tzinfo=timezone.utc) == later


def test_password_reset_token_hash_is_unique(db_session):
    """The ``token_hash`` column has a unique constraint -- a duplicate insert fails."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    now = _utc_now()
    shared_hash = "d" * 64
    first = PasswordResetToken(
        tenant_id=1,
        user_id=1,
        token_hash=shared_hash,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )
    db_session.add(first)
    db_session.commit()

    second = PasswordResetToken(
        tenant_id=1,
        user_id=2,
        token_hash=shared_hash,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_password_reset_token_tenant_scoping(db_session):
    """Two tenants' tokens coexist and are addressable by id."""
    now = _utc_now()
    token_t1 = PasswordResetToken(
        tenant_id=1,
        user_id=10,
        token_hash="e" * 64,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )
    token_t2 = PasswordResetToken(
        tenant_id=2,
        user_id=20,
        token_hash="f" * 64,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([token_t1, token_t2])
    db_session.commit()
    db_session.refresh(token_t1)
    db_session.refresh(token_t2)

    assert token_t1.tenant_id == 1
    assert token_t2.tenant_id == 2
    assert token_t1.id != token_t2.id
    assert token_t1.token_hash != token_t2.token_hash


def test_password_reset_token_stores_sha256_hex_hash(db_session):
    """``token_hash`` round-trips a 64-char SHA-256 hex digest unchanged.

    The reset endpoint hashes the raw token (from the emailed link)
    with SHA-256 and looks it up here; this test pins that a 64-char
    hex string survives the round-trip without truncation or
    case-folding, so a token's hash is always re-derivable.
    """
    now = _utc_now()
    raw_hash = "0123456789abcdef" * 4  # exactly 64 chars, lowercase hex
    assert len(raw_hash) == 64

    token = PasswordResetToken(
        tenant_id=1,
        user_id=1,
        token_hash=raw_hash,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)

    assert token.token_hash == raw_hash
    assert len(token.token_hash) == 64