"""Tests for the FastAPI rate-limit dependency factory (E7; issue #95).

These tests exercise the dependency through a small FastAPI app built
specifically for them, so the dependency is verified end-to-end
(status code, headers, key-extractor integration) without coupling to
the real ``/auth/login`` endpoint -- that wiring is owned by issue #96.

The test app also verifies the layered "per-IP + per-account" usage
described in :mod:`app.rate_limit.dependency`, since that's the headline
acceptance criterion of issue #95.
"""

from collections.abc import Callable, Iterator

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.rate_limit import (
    RateLimiter,
    client_ip_key,
    make_rate_limit_dependency,
    set_default_rate_limiter,
)
from app.rate_limit.config import RateLimitConfig


class _ProbeBody(BaseModel):
    """Minimal Pydantic body so per-account extractors can read ``email``."""

    email: str


@pytest.fixture(autouse=True)
def _reset_default_limiter() -> Iterator[None]:
    """Each test sees a fresh bucket registry to avoid cross-test bleed."""
    set_default_rate_limiter(RateLimiter())
    yield
    set_default_rate_limiter(None)


def _build_app(
    *,
    per_account_extractor: Callable[..., str] | None = None,
    scope: str = "login",
    per_account_config: RateLimitConfig | None = None,
) -> FastAPI:
    """Build a test app that exercises the rate-limit dependency in isolation."""
    app = FastAPI()
    per_ip_dep = make_rate_limit_dependency(scope, client_ip_key)
    dependencies = [Depends(per_ip_dep)]
    if per_account_extractor is not None:
        per_account_dep = make_rate_limit_dependency(
            scope,
            per_account_extractor,
            config=per_account_config,
        )
        dependencies.append(Depends(per_account_dep))

    @app.post("/probe", dependencies=dependencies)
    def _probe(body: _ProbeBody) -> dict:  # pragma: no cover - trivial
        return {"ok": True}

    return app


def test_dependency_allows_under_limit() -> None:
    app = _build_app()
    client = TestClient(app)

    for _ in range(5):
        response = client.post("/probe", json={"email": "a@example.test"})
        assert response.status_code == 200


def test_dependency_returns_429_with_retry_after_after_ip_trips() -> None:
    app = _build_app()
    client = TestClient(app)

    for _ in range(5):
        client.post("/probe", json={"email": "a@example.test"})

    response = client.post("/probe", json={"email": "a@example.test"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) >= 1
    assert "Too many requests" in response.json()["detail"]


def test_dependency_treats_different_ips_as_independent_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_TRUST_FORWARDED_FOR", "1")
    app = _build_app()
    client = TestClient(app)

    for _ in range(5):
        response = client.post(
            "/probe",
            json={"email": "a@example.test"},
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        assert response.status_code == 200

    # Different IP -> independent bucket -> still allowed.
    response = client.post(
        "/probe",
        json={"email": "a@example.test"},
        headers={"X-Forwarded-For": "2.2.2.2"},
    )
    assert response.status_code == 200


def test_dependency_ignores_xff_when_trust_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RATE_LIMIT_TRUST_FORWARDED_FOR", raising=False)
    app = _build_app()
    client = TestClient(app)

    # All five requests pretend to come from different IPs, but we do
    # NOT trust X-Forwarded-For -> they all share one bucket keyed on
    # the testclient's loopback and the sixth one trips.
    for i in range(5):
        response = client.post(
            "/probe",
            json={"email": "a@example.test"},
            headers={"X-Forwarded-For": f"9.9.9.{i}"},
        )
        assert response.status_code == 200

    response = client.post(
        "/probe",
        json={"email": "a@example.test"},
        headers={"X-Forwarded-For": "9.9.9.99"},
    )
    assert response.status_code == 429


def test_per_ip_and_per_account_layered_with_and_semantics() -> None:
    """Both buckets must allow; tripping either one trips the endpoint."""

    def _per_account(body: _ProbeBody) -> str:
        return body.email

    app = _build_app(per_account_extractor=_per_account)
    client = TestClient(app)

    # Five requests from the same IP, same account -> all allowed.
    for _ in range(5):
        response = client.post("/probe", json={"email": "a@example.test"})
        assert response.status_code == 200

    # Sixth request: per-IP bucket is full -> 429.
    tripped_ip = client.post("/probe", json={"email": "a@example.test"})
    assert tripped_ip.status_code == 429

    # Same IP, DIFFERENT account -> per-IP bucket is still full, so it
    # must still trip. The per-account dimension doesn't relax the
    # per-IP dimension; the two are AND-ed.
    tripped_across_account = client.post("/probe", json={"email": "b@example.test"})
    assert tripped_across_account.status_code == 429


def test_per_account_key_normalised_across_calls() -> None:
    """Same account, different casing/whitespace -> same bucket."""

    def _per_account(body: _ProbeBody) -> str:
        return body.email

    # Use a tight per-account limit so the 4th request (across the
    # three normalised variants) trips the bucket and proves all three
    # landed in the same bucket key.
    app = _build_app(
        per_account_extractor=_per_account,
        per_account_config=RateLimitConfig(max_requests=3, window_seconds=60),
    )
    client = TestClient(app)

    for variant in ("a@example.test", "A@Example.test", "  a@EXAMPLE.test  "):
        response = client.post("/probe", json={"email": variant})
        assert response.status_code == 200

    response = client.post("/probe", json={"email": "a@example.test"})
    assert response.status_code == 429


def test_dependency_supports_custom_limiter_and_config() -> None:
    """Test seam: callers (and tests) can inject their own limiter/config."""
    custom_limiter = RateLimiter()
    custom_config = RateLimitConfig(max_requests=2, window_seconds=60)

    def _key(request: Request) -> str:
        return client_ip_key(request)

    dep = make_rate_limit_dependency(
        "custom",
        _key,
        limiter=custom_limiter,
        config=custom_config,
    )
    app = FastAPI()

    @app.post("/probe", dependencies=[Depends(dep)])
    def _probe() -> dict:  # pragma: no cover - trivial
        return {"ok": True}

    client = TestClient(app)

    assert client.post("/probe").status_code == 200
    assert client.post("/probe").status_code == 200
    assert client.post("/probe").status_code == 429
