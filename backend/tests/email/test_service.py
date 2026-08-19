"""Unit tests for owner invite email content and delivery."""

from unittest.mock import patch

import pytest

from app.email.owner_invite import build_owner_invite_body, send_owner_invite_email
from app.email.service import EmailDeliveryError


def test_build_owner_invite_body_includes_credentials(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.com/")

    body = build_owner_invite_body(
        tenant_name="Apex EduConsult",
        owner_email="owner@apex.test",
        temporary_password="temp-secret-123",
    )

    assert "Apex EduConsult" in body
    assert "owner@apex.test" in body
    assert "temp-secret-123" in body
    assert "https://app.example.com/login" in body


def test_send_owner_invite_email_delegates_to_smtp():
    with patch("app.email.owner_invite.send_email") as mock_send:
        send_owner_invite_email(
            to_email="owner@apex.test",
            tenant_name="Apex EduConsult",
            temporary_password="temp-secret-123",
        )

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to"] == "owner@apex.test"
    assert "Apex EduConsult" in mock_send.call_args.kwargs["subject"]
    assert "temp-secret-123" in mock_send.call_args.kwargs["body_text"]


def test_send_email_raises_delivery_error_on_smtp_failure(monkeypatch):
    from app.email import service as email_service

    class BrokenSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, _message):
            raise email_service.smtplib.SMTPException("connection refused")

    monkeypatch.setattr(email_service.smtplib, "SMTP", BrokenSMTP)

    with pytest.raises(EmailDeliveryError, match="connection refused"):
        email_service.send_email(
            to="owner@apex.test",
            subject="Test",
            body_text="Hello",
        )
