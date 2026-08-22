"""Unit tests for :class:`app.rate_limit.bucket.RateLimiter` (E7; issue #95).

These tests exercise the limiter in isolation -- no FastAPI app, no
HTTP -- because the limiter is a pure (scope, key) -> decision
function with an injectable clock. Trip-after-N integration tests
(login hammering, etc.) belong to issue #98.
"""

from collections.abc import Iterator

import pytest

from app.rate_limit import RateLimiter
from app.rate_limit.config import RateLimitConfig


@pytest.fixture()
def fake_clock() -> Iterator[list[float]]:
    """Return a mutable list holding a single float; tests mutate [0]."""
    clock = [0.0]
    yield clock


@pytest.fixture()
def limiter(fake_clock: list[float]) -> RateLimiter:
    rl = RateLimiter()
    rl.configure_time_source(lambda: fake_clock[0])
    return rl


@pytest.fixture()
def config() -> RateLimitConfig:
    return RateLimitConfig(max_requests=3, window_seconds=60)


def test_check_allows_under_limit(limiter: RateLimiter, config: RateLimitConfig) -> None:
    for i in range(3):
        decision = limiter.check("login", "1.2.3.4", config)
        assert decision.allowed is True, f"call #{i + 1} should be allowed"
        assert decision.limit == 3
        assert decision.remaining == 2 - i


def test_check_denies_over_limit(limiter: RateLimiter, config: RateLimitConfig) -> None:
    for _ in range(3):
        limiter.check("login", "1.2.3.4", config)

    decision = limiter.check("login", "1.2.3.4", config)
    assert decision.allowed is False
    assert decision.remaining == 0
    assert decision.limit == 3
    assert 1 <= decision.retry_after_seconds <= 60


def test_check_resets_after_window_elapses(
    limiter: RateLimiter, fake_clock: list[float], config: RateLimitConfig
) -> None:
    for _ in range(3):
        limiter.check("login", "1.2.3.4", config)

    # Still in the same window: must still be denied.
    denied = limiter.check("login", "1.2.3.4", config)
    assert denied.allowed is False

    # Advance past the window: counter resets.
    fake_clock[0] += 61
    after_reset = limiter.check("login", "1.2.3.4", config)
    assert after_reset.allowed is True
    assert after_reset.remaining == 2


def test_check_keys_are_isolated(limiter: RateLimiter, config: RateLimitConfig) -> None:
    # Exhaust the bucket for one key...
    for _ in range(3):
        limiter.check("login", "1.2.3.4", config)
    denied = limiter.check("login", "1.2.3.4", config)
    assert denied.allowed is False

    # ...and verify an unrelated key is unaffected.
    other = limiter.check("login", "5.6.7.8", config)
    assert other.allowed is True
    assert other.remaining == 2


def test_check_scopes_are_isolated(limiter: RateLimiter, config: RateLimitConfig) -> None:
    for _ in range(3):
        limiter.check("login", "1.2.3.4", config)
    denied = limiter.check("login", "1.2.3.4", config)
    assert denied.allowed is False

    other = limiter.check("signup", "1.2.3.4", config)
    assert other.allowed is True
    assert other.remaining == 2


def test_check_normalises_key_case_and_whitespace(
    limiter: RateLimiter, config: RateLimitConfig
) -> None:
    # Same logical key (case + whitespace variations) must share a bucket,
    # otherwise an attacker could trivially bypass the limiter by varying
    # the casing of their own email / IP string.
    for _ in range(3):
        limiter.check("login", "User@Example.com", config)

    decision = limiter.check("login", "  user@EXAMPLE.com  ", config)
    assert decision.allowed is False


def test_check_rejects_empty_key(limiter: RateLimiter, config: RateLimitConfig) -> None:
    decision = limiter.check("login", "", config)
    assert decision.allowed is False
    assert decision.retry_after_seconds == config.window_seconds
    assert decision.remaining == 0


def test_reset_clears_all_state(limiter: RateLimiter, config: RateLimitConfig) -> None:
    for _ in range(3):
        limiter.check("login", "1.2.3.4", config)
    assert limiter.check("login", "1.2.3.4", config).allowed is False

    limiter.reset()

    decision = limiter.check("login", "1.2.3.4", config)
    assert decision.allowed is True
    assert decision.remaining == 2


def test_reset_is_safe_when_empty(limiter: RateLimiter) -> None:
    # No state, no exception.
    limiter.reset()


def test_check_concurrent_calls_are_thread_safe(
    fake_clock: list[float], config: RateLimitConfig
) -> None:
    """Hammer the limiter from many threads; only ``max_requests`` succeed."""
    import threading

    rl = RateLimiter()
    rl.configure_time_source(lambda: fake_clock[0])

    allowed_count = 0
    denied_count = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal allowed_count, denied_count
        decision = rl.check("login", "1.2.3.4", config)
        with lock:
            if decision.allowed:
                allowed_count += 1
            else:
                denied_count += 1

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert allowed_count == config.max_requests
    assert denied_count == 50 - config.max_requests
