"""Thread-safe in-memory token-bucket rate limiter (E7; Journey J46).

Backs :func:`app.rate_limit.dependency.make_rate_limit_dependency` and is
the *only* stateful component in this package. Designed for:

* **Single-process deployment** -- one backend container, matching E1's
  Docker Compose layout. No Redis / external store.
* **Thread safety** -- FastAPI's sync routes may run on a thread pool,
  so the registry uses a lock around the (now-or-window) updates.
* **Testability** -- :meth:`reset` clears state, and the limiter can be
  swapped via :func:`set_default_rate_limiter` so tests can inject a
  fresh instance per test.

Algorithm
---------
For each ``(scope, key)`` pair we keep the timestamp of the most recent
"full-window reset" and a count of consumed slots in the current
window. A request:

1. Looks up the bucket; if absent (or the window has elapsed), create
   it with count=0.
2. If the window has elapsed, reset count to 0 and bump the window
   start.
3. If count < max_requests, increment and allow.
4. Otherwise deny, returning the remaining seconds until the window
   resets (used for the ``Retry-After`` header).

This is the classic fixed-window counter; it is simple, fast, and
sufficient for the brute-force protection this epic targets. A
sliding-window or token-bucket variant is a future optimisation.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.rate_limit.config import RateLimitConfig

__all__ = ["RateLimiter", "RateLimitDecision", "get_default_rate_limiter", "set_default_rate_limiter"]


@dataclass(frozen=True)
class RateLimitDecision:
    """The outcome of a single ``RateLimiter.check`` call."""

    allowed: bool
    retry_after_seconds: int
    remaining: int
    limit: int


@dataclass
class _Bucket:
    window_start: float
    count: int


class RateLimiter:
    """Process-local, thread-safe fixed-window rate limiter."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = threading.Lock()
        # ``time_fn`` is injectable so tests can drive the clock without
        # monkey-patching the stdlib globally.
        self._time_fn = time.monotonic

    def configure_time_source(self, time_fn) -> None:
        """Override the monotonic clock used for window accounting.

        Intended for tests; production code should leave this alone.
        """
        with self._lock:
            self._time_fn = time_fn

    def check(
        self,
        scope: str,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitDecision:
        """Consume one slot for ``(scope, key)`` and return the decision.

        ``key`` is opaque to the limiter -- callers pick the dimension
        (IP address, account email, etc.). ``config`` carries the
        scope-specific limit + window.
        """
        normalised_key = key.strip().lower()
        if not normalised_key:
            # Empty keys would collapse every "unknown" caller into a
            # single bucket and let one of them DoS the others. Refuse
            # up-front instead.
            return RateLimitDecision(
                allowed=False,
                retry_after_seconds=config.window_seconds,
                remaining=0,
                limit=config.max_requests,
            )

        bucket_key = (scope, normalised_key)
        now = self._time_fn()

        with self._lock:
            bucket = self._buckets.get(bucket_key)
            if bucket is None or (now - bucket.window_start) >= config.window_seconds:
                bucket = _Bucket(window_start=now, count=0)
                self._buckets[bucket_key] = bucket

            if bucket.count >= config.max_requests:
                elapsed = now - bucket.window_start
                retry_after = max(1, int(config.window_seconds - elapsed))
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    remaining=0,
                    limit=config.max_requests,
                )

            bucket.count += 1
            remaining = max(0, config.max_requests - bucket.count)
            return RateLimitDecision(
                allowed=True,
                retry_after_seconds=0,
                remaining=remaining,
                limit=config.max_requests,
            )

    def reset(self) -> None:
        """Clear all bucket state. Used by tests; do not call from app code."""
        with self._lock:
            self._buckets.clear()


_default_rate_limiter: RateLimiter | None = None
_default_rate_limiter_lock = threading.Lock()


def get_default_rate_limiter() -> RateLimiter:
    """Return the process-wide singleton :class:`RateLimiter`.

    Created lazily so importing this module has no side effects until
    a dependency actually needs it.
    """
    global _default_rate_limiter
    with _default_rate_limiter_lock:
        if _default_rate_limiter is None:
            _default_rate_limiter = RateLimiter()
    return _default_rate_limiter


def set_default_rate_limiter(limiter: RateLimiter | None) -> RateLimiter | None:
    """Replace (or clear) the process-wide singleton. Used by tests."""
    global _default_rate_limiter
    with _default_rate_limiter_lock:
        previous = _default_rate_limiter
        _default_rate_limiter = limiter
    return previous
