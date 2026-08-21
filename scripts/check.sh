#!/usr/bin/env bash
# Single source of truth for "is this change green?" — run by BOTH CI
# (ci-backend.yml / ci-frontend.yml) and the Dev agent before it finishes, so the
# agent can never ship something the merge-blocking checks reject (docs/adr/0019).
#
# Project dirs + check commands come from harness.config.json (docs/adr/0031), so
# a new project points this at its own stack without editing this file.
#
# Modes (default "all"):
#   backend-lint | backend-test | frontend-lint | frontend-build
#   backend | frontend | all
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-all}"
rc=0

# Load project-specific dirs/commands (falls back to sensible defaults).
eval "$(python3 "$ROOT/agents/harness_config.py" --shell 2>/dev/null || true)"
BE_DIR="${HARNESS_BACKEND_DIR:-backend}"
FE_DIR="${HARNESS_FRONTEND_DIR:-frontend}"
BE_LINT="${HARNESS_BACKEND_LINT:-ruff check .}"
BE_TEST="${HARNESS_BACKEND_TEST:-python -m pytest -q}"
FE_LINT="${HARNESS_FRONTEND_LINT:-npm run lint}"
FE_BUILD="${HARNESS_FRONTEND_BUILD:-npm run build}"

# Local runs (execution.mode=local, agents/run_local.py) install deps into a
# backend venv; CI installs them globally and has no venv. Prefer the venv when
# present so `python`/`pytest`/`ruff` resolve to it locally — a no-op on CI.
if [ -d "$ROOT/$BE_DIR/venv/bin" ]; then
  PATH="$ROOT/$BE_DIR/venv/bin:$PATH"; export PATH
fi

has_backend()  { [ -f "$ROOT/$BE_DIR/pyproject.toml" ] || [ -d "$ROOT/$BE_DIR/app" ]; }
has_frontend() { [ -f "$ROOT/$FE_DIR/package.json" ]; }

be_lint()  { echo "== backend: $BE_LINT =="; ( cd "$ROOT/$BE_DIR" && eval "$BE_LINT" ) || rc=1; }
be_test()  { echo "== backend: $BE_TEST =="; ( cd "$ROOT/$BE_DIR" && eval "$BE_TEST" ) || rc=1; }
fe_lint()  { echo "== frontend: $FE_LINT =="; ( cd "$ROOT/$FE_DIR" && eval "$FE_LINT" ) || rc=1; }
fe_build() { echo "== frontend: $FE_BUILD =="; ( cd "$ROOT/$FE_DIR" && eval "$FE_BUILD" ) || rc=1; }

case "$MODE" in
  backend-lint)   be_lint ;;
  backend-test)   be_test ;;
  frontend-lint)  fe_lint ;;
  frontend-build) fe_build ;;
  backend)   has_backend  && { be_lint; be_test; } || echo "(no $BE_DIR/ — skipped)" ;;
  frontend)  has_frontend && { fe_lint; fe_build; } || echo "(no $FE_DIR/ — skipped)" ;;
  all)
    has_backend  && { be_lint; be_test; }  || echo "(no $BE_DIR/ — skipped)"
    has_frontend && { fe_lint; fe_build; } || echo "(no $FE_DIR/ — skipped)"
    ;;
  *) echo "unknown mode: $MODE"; exit 2 ;;
esac

if [ "$rc" -ne 0 ]; then echo "CHECKS FAILED (mode=$MODE)"; else echo "CHECKS PASSED (mode=$MODE)"; fi
exit $rc
