"""FastAPI rate-limit dependency (E7; Journey J46).

The dependency factory :func:`make_rate_limit_dependency` builds a
FastAPI ``Depends``-compatible callable that:

1. Resolves the rate-limit key for the incoming request via a caller-
   supplied ``key_extractor`` -- by default :func:`client_ip_key`
   (the request's client IP, optionally honouring ``X-Forwarded-For``
   when explicitly opted in for trusted proxies).
2. Consults the shared :class:`RateLimiter` for the configured scope.
3. Raises :class:`fastapi.HTTPException` 429 with a ``Retry-After``
   header on a trip, or returns ``None`` to let the request continue.

.. note::
   This module deliberately does **not** import
   :mod:`from __future__ import annotations`. The dependency closure
   uses ``Annotated[str, Depends(key_extractor)]`` and FastAPI
   inspects that annotation at runtime to wire up the sub-dependency;
   under PEP 563 lazy annotations the ``Depends`` wrapper would
   survive as a string instead of being resolved, so the parameter
   would silently fall back to being treated as a query field.

Layered "per-IP + per-account" usage
------------------------------------

Per the issue, a single endpoint may need to be rate-limited on two
dimensions at once (per-IP *and* per-account). Routes do this by
stacking two dependencies built with different ``key_extractor``
callables; the second one is only invoked if the first passes, which
gives us AND semantics without changing this module.

The ``key_extractor`` is itself a FastAPI dependency -- it can declare
whatever parameters FastAPI knows how to inject (``Request``, a
Pydantic body model, query params, etc.) and must return a string.
Typical usage:

.. code-block:: python

    from fastapi import Depends, Request
    from app.schemas.auth import LoginRequest

    def _per_ip(request: Request) -> str:
        return client_ip_key(request)

    def _per_account(payload: LoginRequest) -> str:
        return payload.email

    @router.post(
        "/login",
        dependencies=[
            Depends(make_rate_limit_dependency("login", _per_ip)),
            Depends(make_rate_limit_dependency("login", _per_account)),
        ],
    )

The wiring above is owned by issue #96 -- this module only ships the
factory + default key extractors so that ticket has a clean API to
build on.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.rate_limit.bucket import RateLimiter, get_default_rate_limiter
from app.rate_limit.config import RateLimitConfig, get_rate_limit_config

__all__ = [
    "client_ip_key",
    "make_rate_limit_dependency",
]

# Trusted-proxy mode is opt-in: the env var must be explicitly set so a
# misconfigured deployment does not silently accept client-supplied
# ``X-Forwarded-For`` headers (which would let any caller spoof their
# IP and bypass the limiter).
_TRUSTED_PROXY_ENV = "RATE_LIMIT_TRUST_FORWARDED_FOR"


def _forwarded_for_trusted() -> bool:
    import os

    return os.environ.get(_TRUSTED_PROXY_ENV, "").lower() in {"1", "true", "yes"}


def client_ip_key(request: Request) -> str:
    """Return the client IP to use as the rate-limit key.

    Prefers ``X-Forwarded-For`` (first hop) only when the deployment
    has opted into trusted-proxy mode via
    ``RATE_LIMIT_TRUST_FORWARDED_FOR=1``. Falls back to
    ``request.client.host`` otherwise -- which is the safe default
    because the SPA backend runs directly behind the FastAPI process
    in E1's Docker Compose layout.
    """
    if _forwarded_for_trusted():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",", 1)[0].strip()
            if first:
                return first
    if request.client is None:
        # Some ASGI test transports don't expose ``client``; treat
        # that as the empty-key case the limiter already handles
        # defensively.
        return ""
    return request.client.host


def make_rate_limit_dependency(
    scope: str,
    key_extractor: Callable[..., str] = client_ip_key,
    *,
    limiter: RateLimiter | None = None,
    config: RateLimitConfig | None = None,
):
    """Build a FastAPI dependency that rate-limits *scope* by *key_extractor*.

    Parameters
    ----------
    scope:
        Short identifier of the rate-limit policy (e.g. ``"login"``).
    key_extractor:
        Callable accepting whatever FastAPI knows how to inject
        (``Request``, a Pydantic body model, query params, ...) and
        returning the rate-limit key string. Defaults to
        :func:`client_ip_key`.
    limiter, config:
        Optional overrides; tests inject them, production code does
        not.
    """
    # ``key_extractor`` is wrapped in ``Depends`` so FastAPI's DI
    # resolves its declared parameters (Request, Pydantic body model,
    # ...) for us -- this is what lets the per-account extractor read
    # ``payload.email`` from the request body without the factory
    # needing to know the request schema.
    def _dependency(
        key: Annotated[str, Depends(key_extractor)],
    ) -> None:
        resolved_limiter = limiter if limiter is not None else get_default_rate_limiter()
        resolved_config = config if config is not None else get_rate_limit_config(scope)
        decision = resolved_limiter.check(scope, key, resolved_config)
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many requests for {scope}; "
                    f"retry in {decision.retry_after_seconds} seconds"
                ),
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

    return _dependency
