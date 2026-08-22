"""End-to-end reset flow tests for issue #94 (E6, Journey J45).

The reset flow has three moving parts stitched together:

    1. ``POST /auth/forgot-password`` issues a single-use token and emails
       the reset link to the user (issue #90).
    2. The user clicks the link and posts ``{token, new_password}`` to
       ``POST /auth/reset-password`` (issue #91).
    3. The user logs in with the new password via ``POST /auth/login``
       (E5 / Journey J44).

Sibling tickets (#90, #91) ship their own per-endpoint test files.
Issue #94 is the epic-level coverage ticket: the **reset flow** end to
end, including the negative paths the per-endpoint tests already cover
but treated here as a single user-visible journey. Concretely, this
file must demonstrate that:

* The **happy path** -- user requests reset, receives a token in the
  email, posts the token back with a new password, and then logs in
  with the new password -- works as a single coherent flow.
* An **expired token** (past ``expires_at``) is rejected with the same
  generic 400 detail used for all invalid tokens, and the user's
  password is not rotated.
* An **invalid token** (never issued, or already consumed) is rejected
  with the same generic 400 detail, and the user's password is not
  rotated.

All three "invalid token" subcases must produce identical responses so
the endpoint cannot be used to probe token state (account-enumeration
hygiene, matching ``/auth/forgot-password``).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.auth.password import verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.rbac.roles import Role
from tests.factories.users import make_db_user

_INVALID_RESET_TOKEN_DETAIL = "Invalid or expired reset token"
_RESET_SUCCESS_MESSAGE = "Your password has been reset successfully."

# A password that satisfies the platform strong-password policy:
# 8+ chars, mixed case, a digit, and a symbol. Reused across the
# happy-path cases so each test reads as a single user action.
_NEW_PASSWORD = "BrandNew1!"
_OLD_PASSWORD = "OriginalPass1!"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _seed_reset_token(
    db_session,
    *,
    user: User,
    raw_token: str,
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
) -> PasswordResetToken:
    """Insert a ``PasswordResetToken`` row for ``user`` with the given state."""
    now = datetime.now(timezone.utc)
    row = PasswordResetToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=_hash(raw_token),
        expires_at=expires_at if expires_at is not None else now + timedelta(hours=1),
        used_at=used_at,
        created_at=now,
        updated_at=now,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _extract_token_from_reset_url(reset_url: str) -> str:
    """Return the plaintext token embedded in the reset URL the email contains."""
    return reset_url.split("token=", 1)[1]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_reset_flow_happy_path_full_chain(client, db_session, mock_email):
    """forgot-password -> reset-password -> login with the new password."""
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=_OLD_PASSWORD,
    )

    # 1. User requests a reset link.
    forgot_response = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )
    assert forgot_response.status_code == 200
    mock_email.assert_called_once()
    reset_url = mock_email.call_args.kwargs["reset_url"]
    plaintext_token = _extract_token_from_reset_url(reset_url)

    # The token row was persisted (hashed) and is unused.
    token_rows = db_session.query(PasswordResetToken).all()
    assert len(token_rows) == 1
    assert token_rows[0].used_at is None

    # 2. User posts the token + new password.
    reset_response = client.post(
        "/auth/reset-password",
        json={"token": plaintext_token, "new_password": _NEW_PASSWORD},
    )
    assert reset_response.status_code == 200
    assert reset_response.json() == {"message": _RESET_SUCCESS_MESSAGE}

    db_session.expire_all()
    refreshed = db_session.get(User, db_session.query(User).one().id)
    assert refreshed is not None
    assert verify_password(_NEW_PASSWORD, refreshed.password_hash)
    assert not verify_password(_OLD_PASSWORD, refreshed.password_hash)

    # 3. The old password no longer authenticates.
    login_old = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": _OLD_PASSWORD},
    )
    assert login_old.status_code == 401

    # 4. The new password authenticates and yields tokens.
    login_new = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": _NEW_PASSWORD},
    )
    assert login_new.status_code == 200
    body = login_new.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_reset_flow_marks_consumed_token_single_use(client, db_session):
    """After a successful reset, replaying the same token must be rejected."""
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=_OLD_PASSWORD,
    )
    raw_token = "happy-path-single-use-token"
    _seed_reset_token(db_session, user=user, raw_token=raw_token)

    first_reset = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": _NEW_PASSWORD},
    )
    assert first_reset.status_code == 200

    # Second use: same token, different new password -> must be rejected
    # because the token is single-use, regardless of the new password
    # being equally strong.
    replay = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherGood1!"},
    )
    assert replay.status_code == 400
    assert replay.json() == {"detail": _INVALID_RESET_TOKEN_DETAIL}

    # The user's hash was rotated exactly once -- by the first reset.
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_NEW_PASSWORD, refreshed.password_hash)
    assert not verify_password("AnotherGood1!", refreshed.password_hash)


# ---------------------------------------------------------------------------
# Expired token
# ---------------------------------------------------------------------------


def test_reset_flow_rejects_expired_token(client, db_session):
    """A token whose ``expires_at`` is in the past must be rejected."""
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=_OLD_PASSWORD,
    )
    raw_token = "expired-flow-token"
    _seed_reset_token(
        db_session,
        user=user,
        raw_token=raw_token,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": _NEW_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": _INVALID_RESET_TOKEN_DETAIL}

    # The user's password must NOT have been rotated.
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_OLD_PASSWORD, refreshed.password_hash)
    assert not verify_password(_NEW_PASSWORD, refreshed.password_hash)

    # The token is still marked unused: the expired-token rejection
    # happens before any state mutation, so a future replay of the
    # same (still-expired) token must also be rejected.
    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    assert token_row.used_at is None


def test_reset_flow_expired_token_does_not_block_subsequent_reset_request(
    client, db_session
):
    """An expired token does not poison later, freshly-issued tokens."""
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=_OLD_PASSWORD,
    )

    # First, an expired token that the user never gets to use.
    _seed_reset_token(
        db_session,
        user=user,
        raw_token="first-attempt-token",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    # Then, a fresh, valid token that the user does use.
    fresh_token = "second-attempt-fresh-token"
    _seed_reset_token(db_session, user=user, raw_token=fresh_token)

    response = client.post(
        "/auth/reset-password",
        json={"token": fresh_token, "new_password": _NEW_PASSWORD},
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_NEW_PASSWORD, refreshed.password_hash)


# ---------------------------------------------------------------------------
# Invalid token
# ---------------------------------------------------------------------------


def test_reset_flow_rejects_unknown_token(client, db_session):
    """A token that was never issued must be rejected with the generic detail."""
    # No user / no token row exists.
    response = client.post(
        "/auth/reset-password",
        json={"token": "never-issued-token-xyz", "new_password": _NEW_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": _INVALID_RESET_TOKEN_DETAIL}
    assert db_session.query(PasswordResetToken).count() == 0


def test_reset_flow_rejects_already_consumed_token(client, db_session):
    """A token that was used in a prior successful reset must be rejected."""
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=_OLD_PASSWORD,
    )
    raw_token = "consumed-flow-token"
    _seed_reset_token(
        db_session,
        user=user,
        raw_token=raw_token,
        used_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": _NEW_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": _INVALID_RESET_TOKEN_DETAIL}

    # Password unchanged.
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_OLD_PASSWORD, refreshed.password_hash)


def test_reset_flow_invalid_and_expired_share_identical_response(client, db_session):
    """The 400 response body must not distinguish invalid vs. expired tokens.

    This is the account-enumeration hygiene contract: a caller who
    replays a guessed token cannot tell whether the token exists /
    has been used / has expired -- they all collapse into the same
    response so a brute-force probe yields no information.
    """
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    expired_token = "shared-detail-expired"
    _seed_reset_token(
        db_session,
        user=user,
        raw_token=expired_token,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )

    expired_resp = client.post(
        "/auth/reset-password",
        json={"token": expired_token, "new_password": _NEW_PASSWORD},
    )
    unknown_resp = client.post(
        "/auth/reset-password",
        json={"token": "totally-unknown-token", "new_password": _NEW_PASSWORD},
    )

    assert expired_resp.status_code == 400
    assert unknown_resp.status_code == 400
    assert expired_resp.json() == unknown_resp.json()
    assert expired_resp.json() == {"detail": _INVALID_RESET_TOKEN_DETAIL}


def test_reset_flow_rejected_does_not_mark_token_consumed(client, db_session):
    """A failed reset attempt must not stamp ``used_at`` on the token.

    This guarantees a user who fat-fingers their new password can
    retry with the same valid token, and that an expired/invalid
    probe leaves no persistent trace that would lock a legitimate
    user out.
    """
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    raw_token = "retry-friendly-token"
    _seed_reset_token(db_session, user=user, raw_token=raw_token)

    # First attempt: weak new password -> 400, token must remain unused.
    weak_resp = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "password"},
    )
    assert weak_resp.status_code == 400

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    assert token_row.used_at is None

    # Second attempt: valid new password with the *same* token -> 200.
    retry_resp = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": _NEW_PASSWORD},
    )
    assert retry_resp.status_code == 200

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    assert token_row.used_at is not None


def test_reset_flow_does_not_reveal_token_existence_via_status_code(client):
    """Invalid and unknown tokens must both yield 400, never 404.

    A 404 would leak that the token does not exist; a 400 with the
    generic detail is the only acceptable shape.
    """
    invalid_resp = client.post(
        "/auth/reset-password",
        json={"token": "definitely-not-a-real-token", "new_password": _NEW_PASSWORD},
    )
    assert invalid_resp.status_code == 400
    assert invalid_resp.json() == {"detail": _INVALID_RESET_TOKEN_DETAIL}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_email():
    """Patch ``send_password_reset_email`` so tests don't hit real SMTP."""
    with patch("app.routers.auth.send_password_reset_email") as mock_send:
        yield mock_send


@pytest.fixture(autouse=True)
def _isolate_dependency_overrides():
    """Clear any ``app.dependency_overrides`` between tests in this module."""
    from app.main import app

    yield
    app.dependency_overrides.clear()
