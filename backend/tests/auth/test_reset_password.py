"""POST /auth/reset-password endpoint tests (E6, Journey J45, issue #91).

The endpoint must:

* Return 200 with a generic success message when given a valid, unexpired,
  unused token, and actually rotate the user's ``password_hash`` so the
  new password works on the next login.
* Mark the consumed token by setting ``used_at`` (single-use enforcement).
* Reject unknown tokens (no row with that ``token_hash``) with 400.
* Reject already-used tokens with 400 -- a second use must not change the
  password.
* Reject expired tokens (``expires_at`` in the past) with 400.
* Reject tokens issued for a user that has since been deactivated or deleted
  with 400 (same generic response so the caller cannot probe state).
* Enforce the platform strong-password policy on the new password
  (Requirements §8).
* Return 503 when the database is unreachable while looking up the token,
  loading the user, or committing the password update.

All "invalid token" outcomes share the same generic ``detail`` so the
endpoint cannot be used to probe whether a token exists, has been used, or
has expired (mirrors the account-enumeration defense on
``/auth/forgot-password``).
"""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.auth.password import verify_password
from app.db.database import get_db
from app.main import app
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.rbac.roles import Role
from tests.factories.users import make_db_user


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _make_reset_token(
    db_session,
    *,
    user: User,
    token: str,
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
) -> PasswordResetToken:
    """Persist a ``PasswordResetToken`` row tied to ``user``."""
    now = datetime.now(timezone.utc)
    row = PasswordResetToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=_hash(token),
        expires_at=expires_at if expires_at is not None else now + timedelta(hours=1),
        used_at=used_at,
        created_at=now,
        updated_at=now,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_reset_password_rotates_hash_for_valid_token(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password="OldPass1!",
    )
    raw_token = "valid-reset-token-1234567890"
    _make_reset_token(db_session, user=user, token=raw_token)
    original_hash = user.password_hash

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "NewSecret1!"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Your password has been reset successfully."}

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.password_hash != original_hash
    assert verify_password("NewSecret1!", refreshed.password_hash)
    # The old password must no longer work after the reset.
    assert not verify_password("OldPass1!", refreshed.password_hash)


def test_reset_password_marks_token_used(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "single-use-token-abcdef"
    _make_reset_token(db_session, user=user, token=raw_token)

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "BrandNew1!"},
    )

    assert response.status_code == 200

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    assert token_row.used_at is not None
    stored_used_at = token_row.used_at
    if stored_used_at.tzinfo is None:
        stored_used_at = stored_used_at.replace(tzinfo=timezone.utc)
    # The used_at timestamp is set to the moment we served the request,
    # so it must be recent (within a small window of "now").
    now = datetime.now(timezone.utc)
    assert now - timedelta(seconds=10) <= stored_used_at <= now + timedelta(seconds=10)


def test_reset_password_rejects_unknown_token(client, db_session):
    response = client.post(
        "/auth/reset-password",
        json={"token": "never-issued-token", "new_password": "BrandNew1!"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token"}
    assert db_session.query(PasswordResetToken).count() == 0


def test_reset_password_rejects_already_used_token(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "already-used-token"
    _make_reset_token(
        db_session,
        user=user,
        token=raw_token,
        used_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherNew1!"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token"}
    # The user's hash must NOT have been touched.
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("test-password", refreshed.password_hash)


def test_reset_password_rejects_expired_token(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "expired-token-value"
    _make_reset_token(
        db_session,
        user=user,
        token=raw_token,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherNew1!"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token"}
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("test-password", refreshed.password_hash)


def test_reset_password_rejects_token_for_deactivated_user(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        is_active=False,
    )
    raw_token = "token-for-deactivated-user"
    _make_reset_token(db_session, user=user, token=raw_token)

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherNew1!"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token"}
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("test-password", refreshed.password_hash)


def test_reset_password_rejects_weak_password(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "weak-password-token"
    _make_reset_token(db_session, user=user, token=raw_token)

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "password"},
    )

    assert response.status_code == 400
    # The error detail comes from validate_password_strength -- the
    # endpoint must surface the policy reason so the UI can guide the
    # user, but the password must not be applied.
    assert "common" in response.json()["detail"].lower()

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    assert token_row.used_at is None
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("test-password", refreshed.password_hash)


def test_reset_password_rejects_short_password(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "short-password-token"
    _make_reset_token(db_session, user=user, token=raw_token)

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "Ab1!"},
    )

    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]


def test_reset_password_does_not_reuse_hash_for_different_users(client, db_session):
    """Two users' tokens must not collide -- lookups are by hash, not by user."""
    alice = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="alice@example.test",
    )
    bob = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="bob@example.test",
    )
    alice_token = "alice-token-aaaaaaaaaaaaaa"
    bob_token = "bob-token-bbbbbbbbbbbbbbbb"
    _make_reset_token(db_session, user=alice, token=alice_token)
    _make_reset_token(db_session, user=bob, token=bob_token)

    # Use Alice's token: only Alice's hash should change.
    response = client.post(
        "/auth/reset-password",
        json={"token": alice_token, "new_password": "AliceNew1!"},
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed_alice = db_session.get(User, alice.id)
    refreshed_bob = db_session.get(User, bob.id)
    assert refreshed_alice is not None
    assert refreshed_bob is not None
    assert verify_password("AliceNew1!", refreshed_alice.password_hash)
    assert not verify_password("AliceNew1!", refreshed_bob.password_hash)
    assert verify_password("test-password", refreshed_bob.password_hash)


def test_reset_password_rejects_missing_fields(client):
    response = client.post("/auth/reset-password", json={})
    assert response.status_code == 422

    response = client.post("/auth/reset-password", json={"token": "anything"})
    assert response.status_code == 422

    response = client.post("/auth/reset-password", json={"new_password": "BrandNew1!"})
    assert response.status_code == 422


def test_reset_password_rejects_empty_fields(client):
    response = client.post(
        "/auth/reset-password",
        json={"token": "", "new_password": "BrandNew1!"},
    )
    assert response.status_code == 422

    response = client.post(
        "/auth/reset-password",
        json={"token": "some-token", "new_password": ""},
    )
    assert response.status_code == 422


def test_reset_password_returns_503_when_token_lookup_fails(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "token-when-db-flaky"
    _make_reset_token(db_session, user=user, token=raw_token)

    mock_session = MagicMock()
    mock_session.query.side_effect = OperationalError(
        "stmt", {}, Exception("no such table")
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "BrandNew1!"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Authentication service is temporarily unavailable"
    }


def test_reset_password_returns_503_when_commit_fails(client, db_engine):
    """A DB outage mid-update must roll back the password change (E5 hygiene).

    Routes through ``app.dependency_overrides[get_db]`` so we can patch
    ``commit`` on the *same* session instance the request handler uses,
    forcing the OperationalError to surface from the router's try/except.
    """
    from sqlalchemy.orm import sessionmaker

    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = testing_session_local()

    user = make_db_user(
        session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "commit-failure-token"
    _make_reset_token(session, user=user, token=raw_token)

    def override_get_db():
        s = session
        original_commit = s.commit
        s.commit = MagicMock(
            side_effect=OperationalError("stmt", {}, Exception("db down"))
        )
        try:
            yield s
        finally:
            s.commit = original_commit

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "BrandNew1!"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Authentication service is temporarily unavailable"
    }

    # The in-memory update was rolled back, so the user still has the
    # original password.
    session.expire_all()
    refreshed = session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("test-password", refreshed.password_hash)


def test_reset_password_does_not_leak_token_or_hash_in_response(client, db_session):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "private-token-zzzzzzzzzzzz"
    _make_reset_token(db_session, user=user, token=raw_token)

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "BrandNew1!"},
    )

    assert response.status_code == 200
    # The plaintext token and the stored hash must never appear in the
    # response body.
    token_hash = _hash(raw_token)
    assert raw_token not in response.text
    assert token_hash not in response.text


def test_reset_password_allows_login_with_new_password_after_reset(client, db_session):
    """End-to-end: forgot-password issued token -> reset -> login with new pwd."""
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password="OriginalPass1!",
    )
    raw_token = "end-to-end-flow-token"
    _make_reset_token(db_session, user=user, token=raw_token)

    reset_response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "RotatedPass1!"},
    )
    assert reset_response.status_code == 200

    login_with_old = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": "OriginalPass1!"},
    )
    assert login_with_old.status_code == 401

    login_with_new = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": "RotatedPass1!"},
    )
    assert login_with_new.status_code == 200
    assert "access_token" in login_with_new.json()


@pytest.fixture(autouse=True)
def _isolate_db_dependency_override():
    """Ensure dependency_overrides from this module never leak to other tests."""
    yield
    app.dependency_overrides.clear()
