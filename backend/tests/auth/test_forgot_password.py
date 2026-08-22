"""POST /auth/forgot-password endpoint tests (E6, Journey J45, issue #90).

The endpoint must:

* Return 200 with a generic acknowledgement for any well-formed email
  payload, whether or not the email matches a registered account
  (prevents account enumeration).
* Issue a single-use ``PasswordResetToken`` row for the matching user
  (verified via the DB; the plaintext token is never returned by the
  endpoint).
* Email the recipient a reset link pointing at the frontend's
  reset-password page; the link carries the plaintext token.
* Not send email / issue a token when the account is deactivated.
* Not send email / issue a token when the email does not match any
  user.
* Return 503 when the database is unavailable, or when SMTP delivery
  of the reset email fails.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.db.database import get_db
from app.email.service import EmailDeliveryError
from app.main import app
from app.models.password_reset_token import PasswordResetToken
from app.rbac.roles import Role
from tests.factories.users import make_db_user


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_forgot_password_returns_generic_message_for_known_email(
    client, db_session, mock_password_reset_email
):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "If an account exists for that email, a reset link has been sent."
    }
    mock_password_reset_email.assert_called_once()
    call_kwargs = mock_password_reset_email.call_args.kwargs
    assert call_kwargs["to_email"] == "counselor@example.test"
    assert "token=" in call_kwargs["reset_url"]


def test_forgot_password_persists_hashed_token(client, db_session, mock_password_reset_email):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )

    assert response.status_code == 200

    tokens = db_session.query(PasswordResetToken).all()
    assert len(tokens) == 1
    token_row = tokens[0]

    # The DB stores the hash, NOT the plaintext; the plaintext is
    # only ever in the email body. Verify the hash is consistent with
    # whatever token was embedded in the reset URL.
    reset_url = mock_password_reset_email.call_args.kwargs["reset_url"]
    plaintext_token = reset_url.split("token=", 1)[1]
    assert token_row.token_hash == _hash(plaintext_token)
    assert plaintext_token not in token_row.token_hash


def test_forgot_password_token_expires_within_one_hour(
    client, db_session, mock_password_reset_email
):
    user = make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    before = datetime.now(timezone.utc)
    response = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 200

    token_row = db_session.query(PasswordResetToken).one()
    # SQLite returns naive datetimes even when the column is
    # declared tz-aware; strip tzinfo for the comparison.
    stored_expires_at = token_row.expires_at
    if stored_expires_at.tzinfo is None:
        stored_expires_at = stored_expires_at.replace(tzinfo=timezone.utc)
    expected_min = before + timedelta(hours=1) - timedelta(seconds=2)
    expected_max = after + timedelta(hours=1) + timedelta(seconds=2)
    assert expected_min <= stored_expires_at <= expected_max
    assert token_row.tenant_id == user.tenant_id
    assert token_row.user_id == user.id
    assert token_row.used_at is None


def test_forgot_password_email_includes_frontend_reset_url(
    client, db_session, mock_password_reset_email, monkeypatch
):
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.com")
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )

    assert response.status_code == 200
    reset_url = mock_password_reset_email.call_args.kwargs["reset_url"]
    assert reset_url.startswith("https://app.example.com/reset-password?token=")


def test_forgot_password_returns_same_response_for_unknown_email(
    client, db_session, mock_password_reset_email
):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "nobody@example.test"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "If an account exists for that email, a reset link has been sent."
    }
    mock_password_reset_email.assert_not_called()
    assert db_session.query(PasswordResetToken).count() == 0


def test_forgot_password_does_not_email_unknown_account(
    client, db_session, mock_password_reset_email
):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "ghost@example.test"},
    )

    assert response.status_code == 200
    mock_password_reset_email.assert_not_called()


def test_forgot_password_does_not_email_deactivated_account(
    client, db_session, mock_password_reset_email
):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="deactivated@example.test",
        is_active=False,
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "deactivated@example.test"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "If an account exists for that email, a reset link has been sent."
    }
    mock_password_reset_email.assert_not_called()
    assert db_session.query(PasswordResetToken).count() == 0


def test_forgot_password_matches_email_case_insensitively(
    client, db_session, mock_password_reset_email
):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "Counselor@Example.TEST"},
    )

    assert response.status_code == 200
    mock_password_reset_email.assert_called_once()
    assert (
        mock_password_reset_email.call_args.kwargs["to_email"]
        == "counselor@example.test"
    )


def test_forgot_password_trims_email_whitespace(
    client, db_session, mock_password_reset_email
):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "  counselor@example.test  "},
    )

    assert response.status_code == 200
    mock_password_reset_email.assert_called_once()


def test_forgot_password_issues_unique_tokens_for_repeated_requests(
    client, db_session, mock_password_reset_email
):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    first = client.post(
        "/auth/forgot-password", json={"email": "counselor@example.test"}
    )
    second = client.post(
        "/auth/forgot-password", json={"email": "counselor@example.test"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_password_reset_email.call_count == 2

    tokens = db_session.query(PasswordResetToken).all()
    assert len(tokens) == 2
    assert tokens[0].token_hash != tokens[1].token_hash

    first_url = mock_password_reset_email.call_args_list[0].kwargs["reset_url"]
    second_url = mock_password_reset_email.call_args_list[1].kwargs["reset_url"]
    assert first_url != second_url


def test_forgot_password_rejects_missing_email(client):
    response = client.post("/auth/forgot-password", json={})

    assert response.status_code == 422


def test_forgot_password_rejects_empty_email(client):
    response = client.post("/auth/forgot-password", json={"email": ""})

    assert response.status_code == 422


def test_forgot_password_returns_503_when_database_unavailable(client):
    mock_session = MagicMock()
    mock_session.query.side_effect = OperationalError(
        "stmt", {}, Exception("no such table")
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/forgot-password",
            json={"email": "nobody@example.test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Authentication service is temporarily unavailable"
    }


def test_forgot_password_returns_503_when_email_delivery_fails(
    client, db_session, mock_password_reset_email, monkeypatch
):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )
    mock_password_reset_email.side_effect = EmailDeliveryError("SMTP down")

    response = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Unable to send password reset email"}


def test_forgot_password_does_not_leak_plaintext_token_in_response(
    client, db_session, mock_password_reset_email
):
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )

    assert response.status_code == 200
    body_text = response.text
    # The plaintext token is in the email body (verified separately
    # via the mock), but never in the HTTP response body. Guard
    # against accidentally returning it via JSON.
    reset_url = mock_password_reset_email.call_args.kwargs["reset_url"]
    plaintext_token = reset_url.split("token=", 1)[1]
    assert plaintext_token not in body_text


@pytest.fixture()
def mock_password_reset_email():
    """Patch ``send_password_reset_email`` so tests don't hit real SMTP."""
    with patch("app.routers.auth.send_password_reset_email") as mock_send:
        yield mock_send


@pytest.fixture(autouse=True)
def _autouse_mock_password_reset_email(mock_password_reset_email):
    """All forgot-password tests mock email delivery by default."""
    return mock_password_reset_email