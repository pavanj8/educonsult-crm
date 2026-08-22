"""Unit tests for the password reset email content and delivery (E6; J45).

Mirrors ``test_service.py`` for the owner invite email: exercises the
template body, the SMTP delegation, and the frontend reset-URL helper
in isolation from the router. Integration behaviour (token persistence,
account-enumeration defense, SMTP-failure → 503) is covered by
``tests/auth/test_forgot_password.py``.
"""

from unittest.mock import patch

from app.email.password_reset import (
    build_password_reset_body,
    build_password_reset_url,
    send_password_reset_email,
)


def test_build_password_reset_body_includes_reset_url():
    body = build_password_reset_body(
        reset_url="https://app.example.com/reset-password?token=abc123",
    )

    assert "https://app.example.com/reset-password?token=abc123" in body
    assert "EduConsult CRM" in body


def test_build_password_reset_body_mentions_one_hour_expiry():
    body = build_password_reset_body(
        reset_url="https://app.example.com/reset-password?token=abc123",
    )

    # The user must be told the link is short-lived and single-use so
    # they don't sit on it expecting it to keep working.
    assert "1 hour" in body
    assert "once" in body.lower()


def test_build_password_reset_body_reassures_unintended_recipients():
    body = build_password_reset_body(
        reset_url="https://app.example.com/reset-password?token=abc123",
    )

    # Defence-in-depth: a user who did not request the reset must be
    # told it is safe to ignore the message so they don't panic-click
    # a phishing-shaped link.
    assert "ignore" in body.lower()


def test_send_password_reset_email_delegates_to_smtp():
    with patch("app.email.password_reset.send_email") as mock_send:
        send_password_reset_email(
            to_email="user@example.test",
            reset_url="https://app.example.com/reset-password?token=abc123",
        )

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "user@example.test"
    assert "password" in kwargs["subject"].lower()
    assert "abc123" in kwargs["body_text"]
    assert "https://app.example.com/reset-password?token=abc123" in kwargs["body_text"]


def test_build_password_reset_url_targets_frontend_reset_page(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.com/")

    url = build_password_reset_url(token="abc123")

    assert url == "https://app.example.com/reset-password?token=abc123"


def test_build_password_reset_url_strips_trailing_slash_from_base(monkeypatch):
    # Trailing slashes in APP_BASE_URL must not produce a doubled slash
    # in the path, otherwise the frontend router would receive a
    # malformed path.
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.com/")

    url = build_password_reset_url(token="abc123")

    assert "//reset-password" not in url.replace("https://", "", 1)