"""Tests for :mod:`app.rate_limit.config` (E7; issue #95)."""

import pytest

from app.rate_limit.config import (
    RateLimitConfig,
    default_scopes,
    get_rate_limit_config,
)


def test_default_config_for_known_scope() -> None:
    config = get_rate_limit_config("login")
    assert config.max_requests > 0
    assert config.window_seconds > 0


def test_unknown_scope_falls_back_to_safe_default() -> None:
    config = get_rate_limit_config("definitely-not-a-real-scope-xyz")
    assert config.max_requests > 0
    assert config.window_seconds > 0


def test_env_override_max_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX_REQUESTS", "2")
    config = get_rate_limit_config("login")
    assert config.max_requests == 2


def test_env_override_window_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "120")
    config = get_rate_limit_config("login")
    assert config.window_seconds == 120


def test_env_override_invalid_value_keeps_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Garbage values must not crash the limiter; they fall back to the
    # platform default rather than silently disabling protection.
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX_REQUESTS", "not-an-int")
    config = get_rate_limit_config("login")
    assert config.max_requests > 0


def test_default_scopes_includes_expected_names() -> None:
    scopes = set(default_scopes())
    assert {"login", "signup", "forgot_password"}.issubset(scopes)


def test_config_validates_positive_integers() -> None:
    with pytest.raises(ValueError):
        RateLimitConfig(max_requests=0, window_seconds=60)
    with pytest.raises(ValueError):
        RateLimitConfig(max_requests=5, window_seconds=0)
    with pytest.raises(ValueError):
        RateLimitConfig(max_requests=-1, window_seconds=60)
