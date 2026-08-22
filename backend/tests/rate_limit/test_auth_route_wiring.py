"""End-to-end wiring tests: the rate-limit dependency is attached to the
public auth routes (E7; issue #95).

These tests hit the real ``/auth/login``, ``/auth/register-student``, and
``/auth/forgot-password`` endpoints through the FastAPI test client and
prove the dependency actually fires -- i.e. that the dependency factory
shipped by this issue is wired into the auth router, not just defined in
isolation. Without these tests, the same wiring work could silently
regress to "dependency defined, route handler bare" and nothing in the
unit-test layer would notice.

The scope is strictly the wiring surface this issue owns: per-IP on
every public auth endpoint, plus per-account (email) on ``/auth/login``.
All three endpoints share a default 5 / 60 s policy from
:mod:`app.rate_limit.config`, which is plenty for a test that fires
six requests in a row.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.rate_limit import RateLimiter, set_default_rate_limiter
from app.rbac.roles import Role
from tests.auth.register_student_helpers import (
    create_tenant,
    make_register_student_payload,
)
from tests.branches.helpers import seed_branch
from tests.factories.users import make_db_user
from tests.master_data.helpers import seed_master_data_chain


@pytest.fixture(autouse=True)
def _fresh_limiter() -> Iterator[None]:
    """Wipe the process-wide limiter before and after each test.

    The top-level conftest.py also installs a fresh limiter, but doing
    it here as well keeps these tests robust to a future refactor that
    might move or remove the conftest autouse fixture.
    """
    set_default_rate_limiter(RateLimiter())
    yield
    set_default_rate_limiter(None)


# ---------------------------------------------------------------------------
# /auth/login -- per-IP + per-account (E7; Journey J46)
# ---------------------------------------------------------------------------


def test_login_returns_429_after_per_ip_limit_is_exhausted(
    client: TestClient, db_session
) -> None:
    """Six failed logins from the same client -> 6th response is 429.

    Default per-IP login limit is 5 / 60 s; the 6th request trips it.
    """
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="victim@example.test",
        password="correct-password",
    )

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json={"email": "victim@example.test", "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"email": "victim@example.test", "password": "wrong-password"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) >= 1
    body = response.json()
    assert "detail" in body
    assert "Too many requests" in body["detail"]


def test_login_returns_429_via_per_account_bucket(
    client: TestClient, db_session
) -> None:
    """Per-account dimension enforces the same 5 / 60 s ceiling as per-IP.

    Both extractors share the same default scope ("login") and config, so
    when we exhaust the account's bucket the per-account dependency refuses
    and the route returns 429 even though there is only one "client" here.
    """
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="targeted@example.test",
        password="correct-password",
    )

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json={"email": "targeted@example.test", "password": "wrong"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"email": "targeted@example.test", "password": "wrong"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_login_happy_path_works_when_limiter_is_fresh(
    client: TestClient, db_session
) -> None:
    """A single correct login returns 200 -- the dependency does not break the happy path."""
    make_db_user(
        db_session,
        Role.COUNSELOR,
        email="happy@example.test",
        password="correct-password",
    )

    response = client.post(
        "/auth/login",
        json={"email": "happy@example.test", "password": "correct-password"},
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /auth/register-student -- per-IP (E7; Requirements §8)
# ---------------------------------------------------------------------------


def test_register_student_returns_429_after_per_ip_limit_is_exhausted(
    client: TestClient, db_session
) -> None:
    """Five signup attempts return 404 (unknown tenant); the 6th must be 429."""
    branch = seed_branch(db_session, tenant_id=1)
    seed_master_data_chain(db_session, tenant_id=1)

    for i in range(5):
        payload = make_register_student_payload(
            tenant_slug="missing-tenant",  # forces the 404 branch
            branch_id=branch.id,
            email=f"student{i}@example.test",
        )
        response = client.post("/auth/register-student", json=payload)
        assert response.status_code == 404

    payload = make_register_student_payload(
        tenant_slug="missing-tenant",
        branch_id=branch.id,
        email="student-blocked@example.test",
    )
    response = client.post("/auth/register-student", json=payload)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_register_student_happy_path_works_when_limiter_is_fresh(
    client: TestClient, db_session
) -> None:
    """A real signup still returns 201 when the per-IP bucket is empty."""
    tenant = create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    country, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)

    payload = make_register_student_payload(
        branch_id=branch.id,
        target_country_id=country.id,
        target_university_id=university.id,
        target_program_id=program.id,
    )
    response = client.post("/auth/register-student", json=payload)

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# /auth/forgot-password -- per-IP (E7)
# ---------------------------------------------------------------------------


def test_forgot_password_returns_429_after_per_ip_limit_is_exhausted(
    client: TestClient,
) -> None:
    """Five forgot-password calls return 200 (generic); the 6th must be 429."""
    payload = {"email": "flood-target@example.test"}

    for _ in range(5):
        response = client.post("/auth/forgot-password", json=payload)
        assert response.status_code == 200

    response = client.post("/auth/forgot-password", json=payload)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_forgot_password_happy_path_works_when_limiter_is_fresh(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/forgot-password",
        json={"email": "anyone@example.test"},
    )
    assert response.status_code == 200
