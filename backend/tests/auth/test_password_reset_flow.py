"""End-to-end acceptance tests for the password-reset flow (issue #94).

The reset flow stitches together three endpoints (see ``E6`` /
Journey J45):

    1. ``POST /auth/forgot-password`` issues a single-use token and
       emails the reset link (issue #90).
    2. The user posts ``{token, new_password}`` to
       ``POST /auth/reset-password`` to rotate their password
       (issue #91).
    3. ``POST /auth/login`` with the new password succeeds.

Per-endpoint coverage lives in ``test_forgot_password.py`` and
``test_reset_password.py``; this file is the **flow-level** coverage:
the user-visible happy path + the two negative-path branches the
issue explicitly calls out (expired token, invalid token). The
sibling ``test_reset_flow_e2e.py`` carries the additional
account-enumeration / single-use / weak-password edge cases; the two
files are deliberately complementary, not redundant.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.auth.password import verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.rbac.roles import Role
from tests.factories.users import make_db_user

_NEW_PASSWORD = "Replacement1!"
_OLD_PASSWORD = "Original1!"


def _extract_token_from_reset_url(reset_url: str) -> str:
    """Return the plaintext token embedded in the reset URL."""
    return reset_url.split("token=", 1)[1]


def _request_reset_token(client, mock_email, email: str) -> str:
    """Hit ``/auth/forgot-password`` and return the plaintext token it emailed."""
    response = client.post("/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    return _extract_token_from_reset_url(mock_email.call_args.kwargs["reset_url"])


# ---------------------------------------------------------------------------
# Happy path: forgot -> reset -> login with the new password
# ---------------------------------------------------------------------------


def test_password_reset_happy_path_changes_password(
    client, db_session, mock_password_reset_email
):
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email="happy.reset@example.test",
        password=_OLD_PASSWORD,
    )

    token = _request_reset_token(client, mock_password_reset_email, user.email)

    reset = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": _NEW_PASSWORD},
    )
    assert reset.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_NEW_PASSWORD, refreshed.password_hash)
    assert not verify_password(_OLD_PASSWORD, refreshed.password_hash)

    login = client.post(
        "/auth/login",
        json={"email": user.email, "password": _NEW_PASSWORD},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


# ---------------------------------------------------------------------------
# Invalid token: a token that was never issued must be rejected
# ---------------------------------------------------------------------------


def test_password_reset_rejects_invalid_token(
    client, db_session, mock_password_reset_email
):
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email="invalid.reset@example.test",
        password=_OLD_PASSWORD,
    )

    # A token that was never issued must yield the same generic 400
    # the endpoint uses for every invalid-token subcase, so a caller
    # cannot probe token state (account-enumeration hygiene).
    response = client.post(
        "/auth/reset-password",
        json={"token": "not-a-real-reset-token", "new_password": _NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token"}

    # The user's password must not have been rotated by the failed attempt.
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_OLD_PASSWORD, refreshed.password_hash)


# ---------------------------------------------------------------------------
# Expired token: a token past its ``expires_at`` must be rejected
# ---------------------------------------------------------------------------


def test_password_reset_rejects_expired_token(
    client, db_session, mock_password_reset_email
):
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email="expired.reset@example.test",
        password=_OLD_PASSWORD,
    )

    token = _request_reset_token(client, mock_password_reset_email, user.email)

    # Backdate the issued token so it is past ``expires_at`` while the
    # rest of the row stays consistent with what the endpoint saw.
    row = db_session.query(PasswordResetToken).filter_by(user_id=user.id).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": _NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token"}

    # Password unchanged after the rejected attempt.
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_OLD_PASSWORD, refreshed.password_hash)


# ---------------------------------------------------------------------------
# Single-use: replaying a consumed token must be rejected
# ---------------------------------------------------------------------------


def test_password_reset_token_is_single_use(
    client, db_session, mock_password_reset_email
):
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email="single-use.reset@example.test",
    )
    token = _request_reset_token(client, mock_password_reset_email, user.email)

    first = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": _NEW_PASSWORD},
    )
    second = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass1!"},
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json() == {"detail": "Invalid or expired reset token"}

    # The password was rotated exactly once, by the first request.
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password(_NEW_PASSWORD, refreshed.password_hash)
    assert not verify_password("AnotherPass1!", refreshed.password_hash)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_password_reset_email():
    """Patch ``send_password_reset_email`` so tests don't hit real SMTP."""
    with patch("app.routers.auth.send_password_reset_email") as mock_send:
        yield mock_send
