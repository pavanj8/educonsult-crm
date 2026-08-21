"""Project paths/conventions the harness expects, so the Test Agent can boot the
backend generically. All project-specific values come from harness.config.json
via harness_config (docs/adr/0031) -- edit that JSON, not this file, for a new
project. Defaults describe a FastAPI backend under `backend/` with `app.main:app`.

Until the scaffolding ticket lands the backend app won't exist -- callers should
check `has_app()` and degrade gracefully (see agents/test_agent.py).
"""
from __future__ import annotations

from pathlib import Path

import harness_config

_C = harness_config.CONFIG

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / _C["backend"]["dir"]
BACKEND_APP_MODULE = _C["backend"]["app_module"]
BACKEND_HEALTH_PATH = _C["backend"]["health_path"]
BACKEND_TESTS_DIR = BACKEND_DIR / "tests"
_FRONTEND_DIR = _C["frontend"]["dir"]

# Env var the app is expected to honor to point at an isolated scratch DB for a
# single Test Agent run.
DATABASE_OVERRIDE_ENV_VAR = "DATABASE_OVERRIDE"

# Paths the Dev/Review agents must never modify -- planning docs + harness tooling.
PROTECTED_PATHS = list(_C["protected_paths"])

_bdir = _C["backend"]["dir"]
APP_CODE_GLOBS = [f"{_bdir}/app/**/*.py", f"{_FRONTEND_DIR}/src/**/*.ts", f"{_FRONTEND_DIR}/src/**/*.tsx"]
TEST_CODE_GLOBS = [f"{_bdir}/tests/**/*.py", f"{_FRONTEND_DIR}/**/*.test.ts", f"{_FRONTEND_DIR}/**/*.test.tsx"]


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
