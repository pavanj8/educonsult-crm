"""MiniMax credential wiring for the agent harness (docs/adr/0019).

The harness runs its Dev/Test/Review agents on MiniMax via an OpenAI-compatible
client (see `minimax_agent.py`). This module builds that client and maps
MiniMax credentials into the OpenAI-compatible env vars any subprocess might
read.

`cursor_api_key()` is kept but dormant: `CURSOR_API_KEY` remains configured in
the workflows/secrets, we just no longer point any agent at it (docs/adr/0019).
"""
from __future__ import annotations

import os

DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_DEV_MODEL = "MiniMax-M2.5-highspeed"
DEFAULT_VERIFY_MODEL = "MiniMax-M3"


def configure_minimax_env() -> bool:
    """Map ``MINIMAX_API_KEY`` to OpenAI-compatible env vars when present."""
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        return False
    base = os.environ.get("MINIMAX_BASE_URL", DEFAULT_MINIMAX_BASE_URL).strip()
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = base.rstrip("/")
    return True


def minimax_client():
    """Build an OpenAI-compatible client pointed at MiniMax.

    Raises a clear error if no key is configured, so a misconfigured workflow
    fails at startup with an actionable message instead of a cryptic 401.
    """
    from openai import OpenAI

    configure_minimax_env()
    key = os.environ.get("MINIMAX_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "MINIMAX_API_KEY is not set. The harness now runs on MiniMax "
            "(docs/adr/0019); set it in the workflow env / repo secrets."
        )
    base = os.environ.get("MINIMAX_BASE_URL", DEFAULT_MINIMAX_BASE_URL).strip().rstrip("/")
    return OpenAI(api_key=key, base_url=base)


def cursor_api_key() -> str | None:
    """Dormant: CURSOR_API_KEY is still provisioned but no agent consumes it."""
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    return key or None
