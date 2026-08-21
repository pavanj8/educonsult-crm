"""Conventions the harness expects the real EduConsult CRM backend to
follow, so the Test Agent can boot it generically. These match the task
text of Epic E1 in docs/epics.md ("Scaffold backend FastAPI app skeleton
... health check endpoint", "Configure SQLAlchemy engine/session").

Until that scaffolding ticket lands, `backend/app/main.py` won't exist --
callers should check `has_app()` and degrade gracefully (see
agents/test_agent.py), since early infra-only tickets have no HTTP surface
to black-box test.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
BACKEND_APP_MODULE = "app.main:app"
BACKEND_HEALTH_PATH = "/health"
BACKEND_TESTS_DIR = BACKEND_DIR / "tests"

# Env var the FastAPI app is expected to honor to point at an isolated
# scratch DB for a single Test Agent run. Not enforced until the
# DB-layer ticket lands; Test Agent runs against whatever default DB the
# app defines until then.
DATABASE_OVERRIDE_ENV_VAR = "DATABASE_OVERRIDE"

# Paths the Dev/Review agents must never modify -- planning docs and the
# harness's own tooling are out of scope for any ticket's implementation.
PROTECTED_PATHS = ["docs/", "agents/", ".github/", ".cursor/", "scripts/"]

APP_CODE_GLOBS = ["backend/app/**/*.py", "frontend/src/**/*.ts", "frontend/src/**/*.tsx"]
TEST_CODE_GLOBS = ["backend/tests/**/*.py", "frontend/**/*.test.ts", "frontend/**/*.test.tsx"]


def has_app() -> bool:
    return (BACKEND_DIR / "app" / "main.py").exists()


def has_backend_tests() -> bool:
    return BACKEND_TESTS_DIR.exists() and any(BACKEND_TESTS_DIR.glob("test_*.py"))


def backend_venv_python() -> str:
    venv_python = BACKEND_DIR / "venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    import sys
    return sys.executable
