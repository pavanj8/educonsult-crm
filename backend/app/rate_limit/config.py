"""Env-driven rate-limit configuration (E7; Journey J46).

Each named "scope" (``login``, ``signup``, ``forgot_password``, ...)
gets its own (max_requests, window_seconds) pair. The defaults here
are the platform baseline described in Requirements §8 ("Basic rate
limiting on public auth endpoints") and Journey J46 ("System
rate-limits repeated failed login attempts").

The values can be overridden via env vars so tests can crank the
window down (e.g. set ``RATE_LIMIT_LOGIN_MAX_REQUESTS=2`` for a fast
trip-after-N test) without changing application code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Scope -> (default max_requests, default window_seconds).
_DEFAULT_SCOPE_LIMITS: dict[str, tuple[int, int]] = {
    "login": (5, 60),
    "signup": (5, 60),
    "forgot_password": (5, 60),
}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value


@dataclass(frozen=True)
class RateLimitConfig:
    """Per-scope rate-limit policy (max requests per window in seconds)."""

    max_requests: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.max_requests <= 0:
            raise ValueError("max_requests must be a positive integer")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be a positive integer")


def _limit_for_scope(scope: str, fallback: tuple[int, int]) -> RateLimitConfig:
    default_max, default_window = fallback
    scope_upper = scope.upper()
    max_name = f"RATE_LIMIT_{scope_upper}_MAX_REQUESTS"
    window_name = f"RATE_LIMIT_{scope_upper}_WINDOW_SECONDS"
    return RateLimitConfig(
        max_requests=_env_int(max_name, default_max),
        window_seconds=_env_int(window_name, default_window),
    )


def get_rate_limit_config(scope: str) -> RateLimitConfig:
    """Return the rate-limit policy for *scope*.

    Unknown scopes fall back to a conservative generic policy so a
    caller cannot accidentally get *unlimited* traffic just by
    mistyping a scope name.
    """
    fallback = _DEFAULT_SCOPE_LIMITS.get(scope, (5, 60))
    return _limit_for_scope(scope, fallback)


def default_scopes() -> tuple[str, ...]:
    """Return the scope names that have non-fallback defaults configured."""
    return tuple(_DEFAULT_SCOPE_LIMITS.keys())
