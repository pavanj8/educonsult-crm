"""MiniMax (Anthropic-compatible) credential wiring for the agent harness.

docs/adr/0019 (+ follow-ups). The harness drives its Dev/Test/Review agents
against MiniMax's **Anthropic-compatible** Messages API (see `minimax_agent.py`)
using the `anthropic` client pointed at `ANTHROPIC_BASE_URL` and authenticated
with `ANTHROPIC_AUTH_TOKEN`.

`cursor_api_key()` is kept but dormant: `CURSOR_API_KEY` remains configured in
the workflows/secrets, we just no longer point any agent at it. The cursor-sdk
*package* is deliberately uninstalled because its presence hijacks HTTP clients
onto the Cursor gateway (docs/adr/0019).
"""
from __future__ import annotations

import os

DEFAULT_ANTHROPIC_BASE_URL = "https://api.minimax.io/anthropic"
DEFAULT_DEV_MODEL = "MiniMax-M2.5-highspeed"
DEFAULT_VERIFY_MODEL = "MiniMax-M3"


def configure_minimax_env() -> bool:
    """True when a MiniMax Anthropic-compatible auth token is configured."""
    return bool(
        os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        or os.environ.get("MINIMAX_API_KEY", "").strip()
    )


def minimax_client():
    """Build an `anthropic` client pointed at MiniMax's Anthropic endpoint.

    Raises a clear error if no token is configured, so a misconfigured workflow
    fails at startup with an actionable message instead of a cryptic 401.
    """
    from anthropic import Anthropic

    token = (
        os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        or os.environ.get("MINIMAX_API_KEY", "").strip()
    )
    if not token:
        raise RuntimeError(
            "ANTHROPIC_AUTH_TOKEN is not set. The harness drives MiniMax via its "
            "Anthropic-compatible endpoint (docs/adr/0019); set it in the "
            "workflow env / repo secrets."
        )
    base = os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_ANTHROPIC_BASE_URL).strip().rstrip("/")
    # auth_token -> Authorization: Bearer <token>, which is what MiniMax's
    # Anthropic-compatible endpoint expects (hence the ANTHROPIC_AUTH_TOKEN name).
    return Anthropic(base_url=base, auth_token=token)


def cursor_api_key() -> str | None:
    """Dormant: CURSOR_API_KEY is still provisioned but no agent consumes it."""
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    return key or None
