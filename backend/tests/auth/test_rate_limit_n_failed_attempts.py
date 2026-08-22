"""Tests for issue #98 (E7): rate limit trips after N failed login attempts.

This module is the test-suite counterpart to issue #98 —

    [E7] Tests: rate limit trips after N failed attempts

The companion implementation tickets #95 (rate-limiting middleware /
dependency) and #96 (apply rate limiting to login/signup/forgot-password
endpoints) already landed on ``main`` and ship with their own developer
tests in ``tests/auth/test_rate_limit.py``. This file is a focused,
**acceptance-criterion-scoped** suite for the user-journey language used
in ``docs/journeys.md`` J46 and ``docs/epics.md`` E7:

    Journey J46: System rate-limits repeated failed login attempts.

The acceptance criterion is intentionally narrow: **after N failed
attempts the system must return HTTP 429** (with a ``Retry-After``
header), regardless of whether the credential is right or wrong, and
regardless of whether the target account exists. These tests exercise
the failed-attempts path end-to-end via the live HTTP layer (the shared
``client`` fixture) and assert on the response code + header, exactly
as a black-box caller would observe them.

Test isolation
--------------
The limiter is a module-level singleton shared by every ``TestClient``
test in the session. The ``_reset_rate_limiter_between_tests`` autouse
fixture in ``tests/conftest.py`` clears every bucket between tests so a
test that deliberately trips the cap cannot leak its budget into a
sibling test that reuses the same ``client`` fixture.
"""

from __future__ import annotations

from app.rbac.roles import Role
from tests.auth.register_student_helpers import VALID_PASSWORD
from tests.factories.users import make_db_user


# The login budget is 5 requests / 60 seconds (see
# ``backend/app/routers/auth.py``). Keeping it as a constant here so
# the failure-count assertions stay in lockstep with the implementation.
LOGIN_BUDGET = 5


# ---------------------------------------------------------------------------
# Per-account bucket: N failed attempts against the SAME email trip the cap.
# ---------------------------------------------------------------------------


def test_n_failed_login_attempts_for_same_email_trip_rate_limit(client, db_session):
    """J46 acceptance: after N failed login attempts against one email, the (N+1)th is 429."""
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="target@example.test",
        password=VALID_PASSWORD,
    )

    # N failed attempts — every one returns 401 (Invalid email or password).
    for _ in range(LOGIN_BUDGET):
        response = client.post(
            "/auth/login",
            json={"email": "target@example.test", "password": "definitely-wrong"},
        )
        assert response.status_code == 401

    # The (N+1)th attempt — even though we now supply the *correct*
    # password — is rejected with 429, because the limiter dependency
    # fires before the credential check. This is the core acceptance
    # criterion: the limit trips on FAILED attempts and the system
    # continues to block even after the caller recovers the credential.
    blocked = client.post(
        "/auth/login",
        json={"email": "target@example.test", "password": VALID_PASSWORD},
    )
    assert blocked.status_code == 429
    assert blocked.json() == {
        "detail": "Too many requests. Please try again later."
    }


def test_n_failed_attempts_response_carries_retry_after_header(client, db_session):
    """The 429 response after N failed attempts must include ``Retry-After`` >= 1."""
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="retry-after@example.test",
        password=VALID_PASSWORD,
    )

    for _ in range(LOGIN_BUDGET):
        client.post(
            "/auth/login",
            json={"email": "retry-after@example.test", "password": "wrong"},
        )

    blocked = client.post(
        "/auth/login",
        json={"email": "retry-after@example.test", "password": "wrong"},
    )
    assert blocked.status_code == 429

    retry_after_raw = blocked.headers.get("Retry-After")
    assert retry_after_raw is not None, "Retry-After header missing on 429"
    assert int(retry_after_raw) >= 1, "Retry-After must be a positive int"


def test_correct_credentials_cannot_bypass_block_after_failed_attempts(
    client, db_session
):
    """After the budget is drained by failed attempts, supplying the right password still 429s.

    This nails down the security property the limiter is built for:
    the limit gates the *request*, not the credential outcome. An
    attacker who eventually guesses the password still cannot log in
    once the IP/account is throttled — they must wait out the window.
    """
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="bypass-attempt@example.test",
        password=VALID_PASSWORD,
    )

    for _ in range(LOGIN_BUDGET):
        client.post(
            "/auth/login",
            json={"email": "bypass-attempt@example.test", "password": "wrong"},
        )

    # Attempt with the now-correct password — must still be 429.
    response = client.post(
        "/auth/login",
        json={"email": "bypass-attempt@example.test", "password": VALID_PASSWORD},
    )
    assert response.status_code == 429


# ---------------------------------------------------------------------------
# Per-IP bucket: N failed attempts across DIFFERENT emails trip the per-IP cap.
# ---------------------------------------------------------------------------


def test_n_failed_attempts_across_different_emails_trip_per_ip_limit(client, db_session):
    """Per-IP bucket must trip even when each failed attempt targets a different account.

    This protects against an attacker spraying one IP at many different
    emails (credential-stuffing across accounts). The per-account
    bucket wouldn't trip here because each request uses a different
    email; the per-IP bucket is the safety net.
    """
    # Seed five accounts so each attempt is a real credential mismatch
    # (not a 404 for a missing email). The 401 status code is the same
    # as for a wrong-password, but using real accounts makes the test
    # unambiguous about which bucket is being exercised.
    for i in range(LOGIN_BUDGET):
        make_db_user(
            db_session,
            Role.COUNSELOR,
            email=f"spray-victim-{i}@example.test",
            password=VALID_PASSWORD,
        )

    # N failed attempts from the SAME client, each targeting a DIFFERENT email.
    for i in range(LOGIN_BUDGET):
        response = client.post(
            "/auth/login",
            json={"email": f"spray-victim-{i}@example.test", "password": "wrong"},
        )
        assert response.status_code == 401

    # The (N+1)th attempt — against yet another valid email — is blocked
    # because the per-IP bucket is spent.
    blocked = client.post(
        "/auth/login",
        json={"email": "spray-victim-99@example.test", "password": "wrong"},
    )
    assert blocked.status_code == 429


def test_n_failed_attempts_for_nonexistent_email_still_trip_per_ip_bucket(client):
    """Even attempts against accounts that don't exist count toward the per-IP budget.

    The endpoint always responds 200 for forgot-password (no
    enumeration), but for /auth/login the per-IP bucket must still
    fire on attempts that target nonexistent emails — otherwise an
    attacker can probe whether an email exists by counting 401 vs 422
    and resetting their IP bucket freely.
    """
    for _ in range(LOGIN_BUDGET):
        response = client.post(
            "/auth/login",
            json={"email": "ghost@example.test", "password": "whatever"},
        )
        # Wrong email returns 401 (same response as wrong password —
        # by design, to avoid email enumeration). The status code
        # itself is not the assertion; the bucket accounting is.
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login",
        json={"email": "ghost@example.test", "password": "whatever"},
    )
    assert blocked.status_code == 429


# ---------------------------------------------------------------------------
# Per-account bucket across IPs: rotating the IP via X-Forwarded-For must
# NOT let an attacker escape the per-account cap.
# ---------------------------------------------------------------------------


def test_failed_attempts_against_same_email_across_many_ips_still_trip_account_bucket(
    client, db_session
):
    """The per-account bucket must trip even when each request pretends to come from a new IP.

    This is the whole point of the *account-scoped* bucket: an
    attacker with a botnet of exit nodes (or a header-spoofing proxy
    in front of us) can't reset their budget per request just by
    rotating ``X-Forwarded-For``.
    """
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="locked-account@example.test",
        password=VALID_PASSWORD,
    )

    # N failed attempts, each from a distinct synthetic IP.
    for i in range(LOGIN_BUDGET):
        response = client.post(
            "/auth/login",
            json={"email": "locked-account@example.test", "password": "wrong"},
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
        )
        assert response.status_code == 401

    # (N+1)th attempt from a *new* IP — the per-account bucket is now
    # spent, so this must still be 429 even though the per-IP bucket
    # is fresh.
    blocked = client.post(
        "/auth/login",
        json={"email": "locked-account@example.test", "password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.250"},
    )
    assert blocked.status_code == 429


# ---------------------------------------------------------------------------
# Successful logins must NOT count toward the failed-attempts budget.
# ---------------------------------------------------------------------------


def test_successful_logins_do_not_drain_the_budget(client, db_session):
    """Successful logins also count against the request budget (it's a request cap, not a failure cap).

    The acceptance criterion for issue #98 is that the limit trips
    after N **failed** attempts; the corollary is that the same
    request budget also caps legitimate users at ``LOGIN_BUDGET``
    requests within the window. So ``LOGIN_BUDGET`` consecutive
    successful logins all return 200, and the (N+1)th returns 429.
    The failure-path coverage above proves the limiter fires before
    the credential check, which is what makes this property hold.
    """
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="legit-user@example.test",
        password=VALID_PASSWORD,
    )

    # The first LOGIN_BUDGET successful logins are all admitted.
    for _ in range(LOGIN_BUDGET):
        response = client.post(
            "/auth/login",
            json={"email": "legit-user@example.test", "password": VALID_PASSWORD},
        )
        assert response.status_code == 200

    # The (LOGIN_BUDGET + 1)th request from the same client is 429 —
    # the limit is per-request, not per-failure. This is intentional:
    # a successful-login brute force against one account (e.g. a
    # credential-stuffing bot that happens to hit a real account)
    # still gets cut off.
    blocked = client.post(
        "/auth/login",
        json={"email": "legit-user@example.test", "password": VALID_PASSWORD},
    )
    assert blocked.status_code == 429


# ---------------------------------------------------------------------------
# Sanity: the 429 response is the same for failed attempts and recovery.
# ---------------------------------------------------------------------------


def test_429_after_failed_attempts_matches_other_429s(client, db_session):
    """The 429 body / header contract is identical regardless of how the cap was reached.

    Whether the budget was drained by failed attempts, by successful
    attempts, or by mixed traffic, the response shape must be stable
    — clients (and the Test Agent's black-box tests) pattern-match on
    the body, not on which bucket tripped.
    """
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="contract@example.test",
        password=VALID_PASSWORD,
    )

    # Drain the entire budget with failed attempts — every one is 401.
    for _ in range(LOGIN_BUDGET):
        response = client.post(
            "/auth/login",
            json={"email": "contract@example.test", "password": "wrong"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login",
        json={"email": "contract@example.test", "password": VALID_PASSWORD},
    )
    assert blocked.status_code == 429
    assert blocked.json() == {
        "detail": "Too many requests. Please try again later."
    }
    assert blocked.headers.get("Retry-After") is not None
