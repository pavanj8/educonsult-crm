"""Rate-limiting primitives for the backend (E7; Journey J46).

This package implements the per-IP + per-account rate-limiting
infrastructure referenced by issue #95. Issue #96 is responsible for
*applying* this dependency to specific endpoints (login, signup,
forgot-password); this issue only ships the reusable pieces.

Public surface:

* :class:`RateLimitConfig` -- env-driven limits, keyed by a short
  ``scope`` string (``"login"``, ``"signup"``, ``"forgot_password"``,
  ...).
* :class:`RateLimiter` -- thread-safe, in-memory token-bucket registry.
  Exposes :meth:`check` (consume one slot) and :meth:`reset` (clear all
  state; used by tests).
* :func:`make_rate_limit_dependency` -- FastAPI dependency factory. The
  factory builds a per-scope dependency closure that carries its own
  scope/limit/window without global state.

Storage note: the bucket registry is **process-local and in-memory**.
That is deliberate -- single-process deployment matches E1's Docker
Compose layout (one backend service, not horizontally scaled yet). A
future task can swap in Redis without changing the public surface.
"""

from app.rate_limit.bucket import (
    RateLimiter,
    get_default_rate_limiter,
    set_default_rate_limiter,
)
from app.rate_limit.config import RateLimitConfig, get_rate_limit_config
from app.rate_limit.dependency import client_ip_key, make_rate_limit_dependency

__all__ = [
    "RateLimitConfig",
    "RateLimiter",
    "client_ip_key",
    "get_default_rate_limiter",
    "get_rate_limit_config",
    "make_rate_limit_dependency",
    "set_default_rate_limiter",
]
