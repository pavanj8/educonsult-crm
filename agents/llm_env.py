"""Provider-agnostic LLM credential + client wiring for the harness.

docs/adr/0019 (MiniMax) generalized in docs/adr/0031. The harness is no longer
tied to MiniMax: `harness.config.json > llm` selects a provider, and each provider
declares its API shape — "anthropic" (Messages API, used by MiniMax's
Anthropic-compatible endpoint and by Anthropic/Claude itself) or "openai" (Chat
Completions, used by OpenAI and OpenAI-compatible gateways). This module builds
the right client for whichever provider is active; `minimax_agent.run_agent`
drives the matching tool-loop shape.

Point the harness at a different model/provider by editing config alone — set
`llm.provider` and the per-tier `models`, and provide that provider's key in the
env var named by its `auth_env` (defaults: MiniMax→ANTHROPIC_AUTH_TOKEN,
Anthropic→ANTHROPIC_API_KEY, OpenAI→OPENAI_API_KEY).
"""
from __future__ import annotations

import os

import harness_config

# Kept for callers/tests that imported these names. Defaults now come from config.
DEFAULT_ANTHROPIC_BASE_URL = "https://api.minimax.io/anthropic"
DEFAULT_DEV_MODEL = harness_config.model("dev") or "MiniMax-M3"
DEFAULT_VERIFY_MODEL = harness_config.model("verify") or "MiniMax-M3"
DEFAULT_PLANNER_MODEL = harness_config.model("planner") or DEFAULT_VERIFY_MODEL


def _auth_token() -> str:
    """The active provider's key, from its configured env var (with fallbacks)."""
    prov = harness_config.active_provider()
    env_name = prov.get("auth_env", "ANTHROPIC_AUTH_TOKEN")
    return (
        os.environ.get(env_name, "").strip()
        # Legacy fallbacks so an existing MiniMax setup keeps working.
        or os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        or os.environ.get("MINIMAX_API_KEY", "").strip()
    )


def credentials_configured() -> bool:
    """True when the active provider has a key configured."""
    return bool(_auth_token())


# Back-compat alias (older callers/tests).
def configure_minimax_env() -> bool:
    return credentials_configured()


def _base_url(prov: dict) -> str:
    # Legacy override: existing workflows export ANTHROPIC_BASE_URL. Honor it only
    # for anthropic-shape providers so it can't leak onto an OpenAI provider.
    legacy = os.environ.get("ANTHROPIC_BASE_URL", "").strip() if prov.get("api") == "anthropic" else ""
    return (legacy or prov.get("base_url") or DEFAULT_ANTHROPIC_BASE_URL).strip().rstrip("/")


def client_and_api():
    """Return ``(client, api)`` for the active provider.

    ``api`` is "anthropic" or "openai" — the engine uses it to pick the matching
    tool-loop. Raises a clear error if no key is configured, so a misconfigured
    run fails at startup with an actionable message instead of a cryptic 401.
    """
    prov = harness_config.active_provider()
    api = prov.get("api", "anthropic")
    token = _auth_token()
    if not token:
        raise RuntimeError(
            f"No LLM credentials: set {prov.get('auth_env', 'the provider auth env var')} "
            f"for provider {prov.get('name', '?')!r} (harness.config.json > llm; docs/adr/0031)."
        )
    base = _base_url(prov)

    if api == "openai":
        from openai import OpenAI
        return OpenAI(base_url=base, api_key=token), "openai"

    # anthropic-shape (MiniMax compat endpoint, Anthropic/Claude, or compatible).
    from anthropic import Anthropic
    scheme = prov.get("auth_scheme")
    if not scheme:
        scheme = "x-api-key" if "api.anthropic.com" in base else "bearer"
    if scheme == "x-api-key":
        return Anthropic(base_url=base, api_key=token), "anthropic"
    # bearer -> Authorization: Bearer <token> (MiniMax's Anthropic-compatible endpoint).
    return Anthropic(base_url=base, auth_token=token), "anthropic"


def minimax_client():
    """Back-compat: the anthropic-shape client for the active provider.

    Retained for callers that predate the provider abstraction. Raises if the
    active provider is OpenAI-shape (they should call ``client_and_api``).
    """
    client, api = client_and_api()
    if api != "anthropic":
        raise RuntimeError(
            "minimax_client() requires an anthropic-shape provider; the active provider "
            "uses the OpenAI API. Use llm_env.client_and_api() instead (docs/adr/0031)."
        )
    return client
