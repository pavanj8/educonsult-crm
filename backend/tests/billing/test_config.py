"""Tests for Razorpay configuration (E46 task #222)."""

import pytest

from app.billing.config import razorpay_key_id, razorpay_key_secret


def test_razorpay_key_id_returns_env_value(monkeypatch):
    """Key ID reads from RAZORPAY_KEY_ID environment variable."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "test_key_123")
    assert razorpay_key_id() == "test_key_123"


def test_razorpay_key_id_raises_when_env_not_set(monkeypatch):
    """Key ID raises RuntimeError when env var is not set."""
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    with pytest.raises(RuntimeError, match="RAZORPAY_KEY_ID environment variable is required"):
        razorpay_key_id()


def test_razorpay_key_id_raises_when_env_empty_string(monkeypatch):
    """Key ID raises RuntimeError when env var is empty string."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    with pytest.raises(RuntimeError, match="RAZORPAY_KEY_ID environment variable is required"):
        razorpay_key_id()


def test_razorpay_key_id_strips_whitespace(monkeypatch):
    """Key ID strips whitespace from env var value."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "  test_key_123  ")
    assert razorpay_key_id() == "test_key_123"


def test_razorpay_key_secret_returns_env_value(monkeypatch):
    """Key secret reads from RAZORPAY_KEY_SECRET environment variable."""
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_secret_abc")
    assert razorpay_key_secret() == "test_secret_abc"


def test_razorpay_key_secret_raises_when_env_not_set(monkeypatch):
    """Key secret raises RuntimeError when env var is not set."""
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="RAZORPAY_KEY_SECRET environment variable is required"):
        razorpay_key_secret()


def test_razorpay_key_secret_raises_when_env_empty_string(monkeypatch):
    """Key secret raises RuntimeError when env var is empty string."""
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    with pytest.raises(RuntimeError, match="RAZORPAY_KEY_SECRET environment variable is required"):
        razorpay_key_secret()


def test_razorpay_key_secret_strips_whitespace(monkeypatch):
    """Key secret strips whitespace from env var value."""
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "  test_secret_abc  ")
    assert razorpay_key_secret() == "test_secret_abc"
