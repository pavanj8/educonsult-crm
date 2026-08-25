"""Tests for Razorpay configuration (E46 task #222)."""



from app.billing.config import razorpay_key_id, razorpay_key_secret


def test_razorpay_key_id_returns_env_value(monkeypatch):
    """Key ID reads from RAZORPAY_KEY_ID environment variable."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "test_key_123")
    assert razorpay_key_id() == "test_key_123"


def test_razorpay_key_id_returns_default_when_env_not_set(monkeypatch):
    """Key ID falls back to test default when env var is not set."""
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    # Default is the test key ID from config
    key_id = razorpay_key_id()
    assert key_id == "rzp_test_1234567890abcdef"


def test_razorpay_key_secret_returns_env_value(monkeypatch):
    """Key secret reads from RAZORPAY_KEY_SECRET environment variable."""
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_secret_abc")
    assert razorpay_key_secret() == "test_secret_abc"


def test_razorpay_key_secret_returns_default_when_env_not_set(monkeypatch):
    """Key secret falls back to test default when env var is not set."""
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    # Default is the test key secret from config
    secret = razorpay_key_secret()
    assert secret == "1234567890abcdef"


def test_config_returns_non_empty_strings(monkeypatch):
    """Both config functions return non-empty strings."""
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    assert razorpay_key_id()
    assert razorpay_key_secret()
    assert len(razorpay_key_id()) > 0
    assert len(razorpay_key_secret()) > 0
