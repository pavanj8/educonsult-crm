#!/usr/bin/env python3
"""Single source of PROJECT-SPECIFIC config for the harness (docs/adr/0031).

Reads `harness.config.json` at the repo root. Every value has a built-in default,
so the harness still runs if the file is missing. To point the harness at a NEW
project you edit ONLY that JSON (project name/repo, backend/frontend dirs + check
commands, model tiers) — the harness code stays generic.

`python harness_config.py --shell` emits `export VAR=...` lines that scripts/check.sh
sources, so bash and Python read the same config.
"""
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "harness.config.json"

_DEFAULTS: dict = {
    "project": {"name": "Project", "repo": ""},
    "backend": {
        "dir": "backend", "app_module": "app.main:app", "health_path": "/health",
        "requirements": "requirements.txt", "lint": "ruff check .", "test": "python -m pytest -q",
    },
    "frontend": {
        "dir": "frontend", "lint": "npm run lint", "build": "npm run build",
        "test": "npm run test",
    },
    # Where the Dev/Test/Review/Planner agents run: "github" (GitHub Actions
    # runners, the default) or "local" (this machine, via agents/run_local.py).
    "execution": {"mode": "github"},
    # Which delivery phase the queue picker draws from. The picker only queues
    # open `task,phase:<phase>` issues, so this is how you advance the harness
    # from one phase to the next once a phase's backlog is complete (ADR-0024).
    "queue": {"phase": "mvp"},
    # LLM is provider-agnostic (docs/adr/0031): pick `provider`, and each provider
    # declares its API shape ("anthropic" Messages API or "openai" Chat Completions),
    # its base_url, and which env var holds the key. Point at MiniMax, Anthropic
    # (Claude), OpenAI, or any compatible gateway by editing config alone.
    "llm": {
        "provider": "minimax",
        "providers": {
            "minimax":   {"api": "anthropic", "base_url": "https://api.minimax.io/anthropic", "auth_env": "ANTHROPIC_AUTH_TOKEN", "auth_scheme": "bearer"},
            "anthropic": {"api": "anthropic", "base_url": "https://api.anthropic.com",         "auth_env": "ANTHROPIC_API_KEY",    "auth_scheme": "x-api-key"},
            "openai":    {"api": "openai",    "base_url": "https://api.openai.com/v1",          "auth_env": "OPENAI_API_KEY"},
        },
    },
    # Per-tier model IDs (must be valid for the selected provider).
    "models": {"dev": "MiniMax-M3", "verify": "MiniMax-M3", "planner": "MiniMax-M3"},
    "protected_paths": ["docs/", "agents/", ".github/", ".cursor/", "scripts/"],
}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load() -> dict:
    user: dict = {}
    if _CONFIG_PATH.exists():
        try:
            user = json.loads(_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            user = {}
    return _deep_merge(_DEFAULTS, user)


CONFIG = load()


def repo() -> str:
    return (os.environ.get("HARNESS_REPO") or CONFIG["project"].get("repo") or "").strip()


def project_name() -> str:
    return CONFIG["project"].get("name", "Project")


def execution_mode() -> str:
    """"github" (Actions runners) or "local" (this machine)."""
    return (os.environ.get("HARNESS_EXECUTION_MODE") or CONFIG["execution"].get("mode") or "github").strip()


def queue_phase() -> str:
    """The phase label the picker filters on (mvp | phase-2 | phase-3).

    HARNESS_QUEUE_PHASE overrides the config for a one-off run.
    """
    return (os.environ.get("HARNESS_QUEUE_PHASE") or CONFIG["queue"].get("phase") or "mvp").strip()


def active_provider() -> dict:
    """The selected LLM provider's {api, base_url, auth_env}, with env overrides.

    HARNESS_LLM_PROVIDER selects a different provider at runtime; LLM_BASE_URL /
    LLM_AUTH_ENV override individual fields for one-off use.
    """
    llm = CONFIG["llm"]
    name = (os.environ.get("HARNESS_LLM_PROVIDER") or llm.get("provider") or "minimax").strip()
    prov = dict(llm.get("providers", {}).get(name, {}))
    prov.setdefault("api", "anthropic")
    prov["name"] = name
    if os.environ.get("LLM_BASE_URL"):
        prov["base_url"] = os.environ["LLM_BASE_URL"].strip()
    if os.environ.get("LLM_AUTH_ENV"):
        prov["auth_env"] = os.environ["LLM_AUTH_ENV"].strip()
    return prov


def model(tier: str) -> str:
    """Model ID for a tier: dev | verify | planner."""
    return CONFIG["models"].get(tier, "")


def _emit_shell() -> None:
    c = CONFIG
    pairs = {
        "BACKEND_DIR": c["backend"]["dir"],
        "BACKEND_LINT": c["backend"]["lint"],
        "BACKEND_TEST": c["backend"]["test"],
        "FRONTEND_DIR": c["frontend"]["dir"],
        "FRONTEND_LINT": c["frontend"]["lint"],
        "FRONTEND_BUILD": c["frontend"]["build"],
        # .get(): a project config written before frontend tests were gated
        # still loads instead of raising KeyError on every check.sh run.
        "FRONTEND_TEST": c["frontend"].get("test", "npm run test"),
    }
    for k, v in pairs.items():
        print(f"export HARNESS_{k}={shlex.quote(str(v))}")


if __name__ == "__main__":
    if "--shell" in sys.argv:
        _emit_shell()
    else:
        print(json.dumps(CONFIG, indent=2))
