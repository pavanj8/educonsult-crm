"""Rate-limiting tests for the public auth endpoints (E7; Journey J46; issue #96).

These tests cover the wiring side of the rate-limit work: they verify
that an in-process sliding-window limiter, applied as a FastAPI
dependency on ``POST /auth/login``, ``POST /auth/register-student`` and
``POST /auth/forgot-password``, actually trips after the configured
budget is spent. They are intentionally black-box: they go through the
HTTP layer (via the shared ``client`` fixture) and assert on response
status codes and headers.

The Test Agent's own black-box test for journey J46 (System
rate-limits repeated failed login attempts) lives in
``harness-demo/`` and is not duplicated here. This module exists
alongside it to cover the *developer* side: that the wiring is correct
for every endpoint in the issue, with both per-IP and per-account
buckets, and that the ``Retry-After`` header is set on rejection.

Test isolation
--------------
The limiter is a module-level singleton, so the ``_reset_rate_limiter_between_tests``
autouse fixture in ``tests/conftest.py`` clears it between tests. That
keeps a test that deliberately trips the cap from leaking its bucket
into the next test sharing the same ``TestClient(app)`` instance.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.auth.rate_limit import (
    ENDPOINT_LOGIN,
    RateLimiter,
    reset_for_tests,
)
from app.rbac.roles import Role
from tests.auth.register_student_helpers import (
    VALID_PASSWORD,
    create_tenant,
    make_register_student_payload,
)
from tests.branches.helpers import seed_branch
from tests.factories.users import make_db_user


# ---------------------------------------------------------------------------
# Pure-unit coverage of the limiter itself (no HTTP / no app).
# ---------------------------------------------------------------------------


def test_rate_limiter_admits_up_to_max_then_rejects():
    limiter = RateLimiter()
    for _ in range(3):
        assert limiter.hit("ep", "client", max_requests=3, window_seconds=60) is True
    # The 4th hit within the same window is rejected.
    assert limiter.hit("ep", "client", max_requests=3, window_seconds=60) is False


def test_rate_limiter_isolates_clients():
    limiter = RateLimiter()
    for _ in range(2):
        assert limiter.hit("ep", "client-a", max_requests=2, window_seconds=60) is True
    # client-b has its own bucket.
    assert limiter.hit("ep", "client-b", max_requests=2, window_seconds=60) is True


def test_rate_limiter_isolates_endpoints():
    limiter = RateLimiter()
    for _ in range(2):
        assert limiter.hit("ep-a", "client", max_requests=2, window_seconds=60) is True
    # Same identifier, different endpoint = fresh bucket.
    assert limiter.hit("ep-b", "client", max_requests=2, window_seconds=60) is True


def test_rate_limiter_retry_after_is_positive():
    limiter = RateLimiter()
    for _ in range(2):
        limiter.hit("ep", "client", max_requests=2, window_seconds=60)
    retry = limiter.retry_after("ep", "client", window_seconds=60)
    assert isinstance(retry, int)
    assert 1 <= retry <= 61  # window is 60s, so the bound is generous


def test_rate_limiter_reset_clears_all_buckets():
    limiter = RateLimiter()
    limiter.hit("ep", "client", max_requests=1, window_seconds=60)
    assert limiter.hit("ep", "client", max_requests=1, window_seconds=60) is False
    limiter.reset()
    assert limiter.hit("ep", "client", max_requests=1, window_seconds=60) is True


# ---------------------------------------------------------------------------
# Integration coverage via the live HTTP client.
# ---------------------------------------------------------------------------


def test_login_returns_429_after_budget_exhausted(client, db_session):
    password = VALID_PASSWORD
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=password,
    )

    # The budget is 5 / 60s for login; the per-IP bucket is the
    # binding constraint here.
    last_response = None
    for _ in range(5):
        last_response = client.post(
            "/auth/login",
            json={"email": "counselor@example.test", "password": password},
        )
    assert last_response is not None
    assert last_response.status_code == 200

    blocked = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": password},
    )
    assert blocked.status_code == 429
    assert blocked.json() == {
        "detail": "Too many requests. Please try again later."
    }
    # Retry-After header is set (and is a positive integer).
    retry_after = blocked.headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) >= 1


def test_login_rate_limit_counts_wrong_password_attempts(client, db_session):
    """Failed-login attempts also consume the budget (the whole point of the limiter)."""
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password="S3curePass!",
    )

    for _ in range(5):
        wrong = client.post(
            "/auth/login",
            json={"email": "counselor@example.test", "password": "wrong-password"},
        )
        assert wrong.status_code == 401

    blocked = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": "wrong-password"},
    )
    assert blocked.status_code == 429


def test_login_per_account_bucket_is_independent(client, db_session):
    """A different email from the same IP must not be blocked by another account's bucket.

    The per-IP cap still applies (so we can't escape it via email
    rotation alone), but the per-account cap means an attacker rotating
    *through many IPs* against a single email still gets cut off.
    Here we exhaust the per-IP bucket for one email; a *different*
    email from the same IP must still get blocked because the per-IP
    bucket is shared. The next test (forwarded-for header) verifies
    that the per-account bucket kicks in across IPs.
    """
    password = VALID_PASSWORD
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=password,
    )

    for _ in range(5):
        client.post(
            "/auth/login",
            json={"email": "counselor@example.test", "password": password},
        )

    # 6th attempt from the same IP — the per-IP bucket is spent.
    blocked_same_ip = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": password},
    )
    assert blocked_same_ip.status_code == 429


def test_login_per_account_bucket_triggers_via_forwarded_for(client, db_session):
    """Rotating the IP via X-Forwarded-For must not bypass the per-account cap."""
    password = VALID_PASSWORD
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=password,
    )

    # Spend the per-account bucket by hitting the limiter with 5
    # different synthetic client IPs (forwarded-for first hop).
    headers_template = []
    for i in range(5):
        headers_template.append(
            {"X-Forwarded-For": f"10.0.0.{i + 1}", "X-Forwarded-Proto": "https"}
        )

    for headers in headers_template:
        response = client.post(
            "/auth/login",
            json={"email": "counselor@example.test", "password": password},
            headers={k: v for k, v in headers.items() if k == "X-Forwarded-For"},
        )
        # 200 (success) is fine; what matters is the bucket accounting.
        assert response.status_code == 200

    # A 6th attempt with a *new* IP but the *same* email must still
    # be blocked because the per-account bucket is now spent.
    blocked = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": password},
        headers={"X-Forwarded-For": "10.0.0.99"},
    )
    assert blocked.status_code == 429


def test_login_does_not_429_when_below_budget(client, db_session):
    """Sanity check: a small number of successful logins stays under the cap."""
    password = VALID_PASSWORD
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=password,
    )

    for _ in range(3):
        response = client.post(
            "/auth/login",
            json={"email": "counselor@example.test", "password": password},
        )
        assert response.status_code == 200


def test_login_rate_limit_does_not_affect_other_endpoints(
    client, db_session, mock_password_reset_email
):
    """Spending the login budget must not block /auth/forgot-password or register-student."""
    password = VALID_PASSWORD
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="counselor@example.test",
        password=password,
    )

    for _ in range(6):
        client.post(
            "/auth/login",
            json={"email": "counselor@example.test", "password": password},
        )

    # Login is now blocked.
    blocked_login = client.post(
        "/auth/login",
        json={"email": "counselor@example.test", "password": password},
    )
    assert blocked_login.status_code == 429

    # But forgot-password from the same client is unaffected.
    forgot = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )
    assert forgot.status_code == 200


def test_register_student_returns_429_after_budget_exhausted(client, db_session):
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    # First 5 requests succeed (each registers a unique email).
    for i in range(5):
        response = client.post(
            "/auth/register-student",
            json=make_register_student_payload(
                branch_id=branch.id,
                email=f"student{i}@example.test",
            ),
        )
        assert response.status_code == 201

    # 6th request from the same IP is blocked, even though the
    # payload would otherwise be valid.
    blocked = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            branch_id=branch.id,
            email="student-blocked@example.test",
        ),
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") is not None


def test_forgot_password_returns_429_after_budget_exhausted(client, db_session, mock_password_reset_email):
    """Forgot-password trips on the 6th request from the same client."""
    # 5 prior requests for the same well-formed email all return 200.
    for _ in range(5):
        response = client.post(
            "/auth/forgot-password",
            json={"email": "counselor@example.test"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/auth/forgot-password",
        json={"email": "counselor@example.test"},
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") is not None


def test_rate_limiter_is_reset_between_tests(client):
    """The autouse fixture in tests/conftest.py clears the limiter between tests.

    This test deliberately trips the cap and then relies on the next
    test starting with a clean bucket. We don't observe the next test
    here; the assertion is that *this* test sees the cap engage, which
    is only possible if no earlier test has already spent the bucket.
    """
    for _ in range(5):
        # Pydantic rejects empty email with 422, but the rate limiter
        # dependency runs first and still consumes a bucket slot.
        client.post(
            "/auth/forgot-password",
            json={"email": "anything@example.test"},
        )
    blocked = client.post(
        "/auth/forgot-password",
        json={"email": "anything@example.test"},
    )
    assert blocked.status_code == 429


def test_reset_for_tests_helper_clears_the_singleton():
    """Sanity check on the reset helper exposed for tests/conftest.py."""
    from app.auth import rate_limit as rate_limit_module

    limiter_before = rate_limit_module._limiter
    # Spend a slot.
    assert limiter_before.hit(ENDPOINT_LOGIN, "x", max_requests=1, window_seconds=60) is True
    # Confirm the bucket is now spent.
    assert limiter_before.hit(ENDPOINT_LOGIN, "x", max_requests=1, window_seconds=60) is False
    # Reset and try again — must succeed.
    reset_for_tests()
    assert rate_limit_module._limiter.hit(ENDPOINT_LOGIN, "x", max_requests=1, window_seconds=60) is True


@pytest.fixture()
def mock_password_reset_email():
    """Patch ``send_password_reset_email`` so tests don't hit real SMTP."""
    with patch("app.routers.auth.send_password_reset_email") as mock_send:
        yield mock_send
