"""In-process per-client rate limiting for public auth endpoints (E7; Journey J46).

Implements a simple sliding-window counter to protect:

* ``POST /auth/login`` — from credential-stuffing / brute-force password probes
* ``POST /auth/register-student`` — from mass account creation
* ``POST /auth/forgot-password`` — from email-bombing / enumeration via timing

The limiter is intentionally simple:

* Process-local (a single FastAPI worker); no external cache. This is
  appropriate for the v1 rate-limiting threat model and matches the
  requirements of Requirements §8 ("Basic rate limiting on public auth
  endpoints").
* Keyed by ``(endpoint_name, client_ip)`` so two different endpoints'
  buckets never share state, and so different clients (IPs) get
  independent budgets.
* Login also keys a *secondary* per-account bucket so the same email
  being hammered from many IPs still gets capped (this is the per-account
  component the issue calls for).

It exposes two FastAPI-compatible dependency callables:

* ``rate_limit(endpoint, max_requests, window_seconds)`` — generic
  per-IP limiter, used by ``register-student`` and ``forgot-password``.
* ``login_rate_limit(max_requests, window_seconds)`` — per-IP *and*
  per-account, used by ``/auth/login``.

Both raise ``HTTPException(429)`` with a ``Retry-After`` header when the
budget is exhausted.

The bucket store has a ``reset()`` helper used by tests so a test that
trips the limiter cannot leak state into siblings (the shared
``client`` fixture in ``tests/conftest.py`` reuses one app, so without a
reset hook the second test would see a pre-spent bucket).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Deque

from fastapi import HTTPException, Request, status

# Per-endpoint name constants. Used as the first half of the bucket key
# so distinct endpoints never share state.
ENDPOINT_LOGIN = "login"
ENDPOINT_REGISTER_STUDENT = "register-student"
ENDPOINT_FORGOT_PASSWORD = "forgot-password"


@dataclass
class _Bucket:
    """A sliding-window counter for a single (endpoint, key) pair."""

    timestamps: Deque[float]


class RateLimiter:
    """Thread-safe in-process sliding-window rate limiter.

    Each ``(endpoint, identifier)`` pair gets its own deque of hit
    timestamps. A hit is admitted iff its timestamp falls outside the
    active window from the OLDEST timestamp currently in the deque, or
    the deque is empty. On admission the timestamp is appended; on
    rejection the deque is unchanged.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, endpoint: str, identifier: str, max_requests: int, window_seconds: float) -> bool:
        """Record an attempt and return True if it is admitted, False if rate-limited.

        ``window_seconds`` may be a float for short windows; in practice
        we always pass integers >= 1.
        """
        key = (endpoint, identifier)
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            self._evict_expired(bucket, now, window_seconds)
            if len(bucket) >= max_requests:
                return False
            bucket.append(now)
            return True

    def retry_after(self, endpoint: str, identifier: str, window_seconds: float) -> int:
        """Return the number of whole seconds the caller must wait before retry.

        Called only when ``hit()`` returned False, so the bucket is
        guaranteed to be non-empty.
        """
        key = (endpoint, identifier)
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            if not bucket:
                return 1
            oldest = bucket[0]
            elapsed = now - oldest
            remaining = window_seconds - elapsed
            if remaining <= 0:
                return 1
            # Round up so we never tell the caller "retry now" when they
            # are still inside the window.
            return int(remaining) + 1

    def reset(self) -> None:
        """Clear every bucket. Intended for test isolation only."""
        with self._lock:
            self._buckets.clear()

    @staticmethod
    def _evict_expired(bucket: Deque[float], now: float, window_seconds: float) -> None:
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()


# Module-level singleton — one process, one limiter, shared by every
# FastAPI dependency call below. Tests call ``_limiter.reset()`` from
# an autouse fixture so buckets don't leak between tests.
_limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    """Best-effort client identifier for the bucket key.

    Prefers the ``X-Forwarded-For`` first hop (so deployments behind a
    reverse proxy still bucket per real client), then falls back to
    ``request.client.host``. Starlette's ``TestClient`` uses
    ``"testclient"`` by default, which means tests share a bucket unless
    the test injects custom headers — that is intentional, because the
    whole point of the limiter is to cap a single offender.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first (leftmost) entry — the original client.
        return forwarded_for.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _too_many_requests(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def rate_limit(
    endpoint: str,
    max_requests: int,
    window_seconds: float,
) -> Callable[..., None]:
    """Build a FastAPI dependency that rate-limits per client IP.

    Usage::

        @router.post("/auth/forgot-password",
                     dependencies=[Depends(rate_limit(
                         ENDPOINT_FORGOT_PASSWORD,
                         max_requests=10, window_seconds=60))])
        def forgot_password(...): ...

    ``max_requests`` and ``window_seconds`` are evaluated once when the
    route module imports this function (the returned dependency is then
    closed over those values). This is the standard FastAPI dependency
    factory pattern.
    """

    def _dependency(request: Request) -> None:
        ip = _client_ip(request)
        if not _limiter.hit(endpoint, ip, max_requests, window_seconds):
            raise _too_many_requests(_limiter.retry_after(endpoint, ip, window_seconds))

    return _dependency


def login_rate_limit(
    max_requests: int,
    window_seconds: float,
) -> Callable[..., None]:
    """Build a per-IP + per-account limiter for ``POST /auth/login``.

    In addition to the per-IP cap, the same payload's ``email`` (if any)
    consumes a separate per-account bucket. So an attacker rotating
    through IPs against a single email still gets cut off, and a single
    IP hitting many distinct emails still gets cut off.

    The email is read from ``request.state`` when the route has already
    validated the body, or — when ``request.state`` is unset — by
    peeking at the JSON body once. To keep the dependency simple and
    independent of Pydantic models, we read the raw body here. Starlette
    caches the body so the downstream route can still consume it.
    """

    def _dependency(request: Request) -> None:
        ip = _client_ip(request)

        # Per-IP bucket — always enforced.
        if not _limiter.hit(ENDPOINT_LOGIN, ip, max_requests, window_seconds):
            raise _too_many_requests(
                _limiter.retry_after(ENDPOINT_LOGIN, ip, window_seconds)
            )

        # Per-account bucket — read the email out of the request body.
        # We accept missing/invalid bodies (the route will return 422),
        # but in that case the IP bucket alone still applies.
        identifier = _extract_login_identifier(request)
        if identifier is not None:
            account_key = f"account:{identifier}"
            if not _limiter.hit(
                ENDPOINT_LOGIN, account_key, max_requests, window_seconds
            ):
                raise _too_many_requests(
                    _limiter.retry_after(
                        ENDPOINT_LOGIN, account_key, window_seconds
                    )
                )

    return _dependency


def _extract_login_identifier(request: Request) -> str | None:
    """Best-effort extraction of the login email for the per-account bucket.

    Starlette has already buffered the body by the time a dependency
    runs, so we can safely ``await request.json()``. If the body is not
    JSON or has no ``email``, we return ``None`` — the per-IP bucket is
    still in force.
    """
    import json

    try:
        body = request.state._rate_limit_body  # type: ignore[attr-defined]
    except AttributeError:
        body = None

    if body is None:
        # Synchronously read the already-buffered body. Starlette's
        # ``Request`` keeps the raw bytes around after the first await,
        # so the route handler can still call ``await request.json()``.
        try:
            raw = request._body  # type: ignore[attr-defined]
        except Exception:
            return None
        if not raw:
            return None
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        # Cache for any later dependency in the same request.
        request.state._rate_limit_body = body

    if not isinstance(body, dict):
        return None
    email = body.get("email")
    if not isinstance(email, str):
        return None
    normalized = email.strip().lower()
    return normalized or None


def reset_for_tests() -> None:
    """Reset the limiter's bucket store.

    Exposed as a module-level function so test modules can call it from
    an autouse fixture (``backend/tests/auth/conftest.py``-style) and
    guarantee that a rate-limited test does not leak its bucket into
    the next test sharing the same ``TestClient`` app instance.
    """
    _limiter.reset()


__all__ = [
    "ENDPOINT_FORGOT_PASSWORD",
    "ENDPOINT_LOGIN",
    "ENDPOINT_REGISTER_STUDENT",
    "RateLimiter",
    "login_rate_limit",
    "rate_limit",
    "reset_for_tests",
]


# Quiet ruff F401 — these names are re-exported for tests.
_ = Annotated
