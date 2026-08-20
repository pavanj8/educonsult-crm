"""Wire MiniMax Token Plan credentials into the Cursor local agent runtime.

The Cursor SDK still requires ``CURSOR_API_KEY`` for agent orchestration.
MiniMax model inference is routed through OpenAI-compatible env vars that
the local runtime reads when a custom model ID (e.g. ``MiniMax-M3``) is
selected. See docs/adr/0017.
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


def cursor_api_key() -> str | None:
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    return key or None
