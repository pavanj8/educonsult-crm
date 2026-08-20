#!/usr/bin/env bash
# Single source of truth for "is this change green?" (harness ①, docs/adr/0019
# follow-up). Run by BOTH:
#   - CI (ci-backend.yml / ci-frontend.yml), and
#   - the Dev agent, before it finishes,
# so the agent can never ship something the merge-blocking checks will reject.
#
# Modes (default "all"):
#   backend-lint | backend-test | frontend-lint | frontend-build
#   backend | frontend | all
#
# Exits non-zero if any selected check fails (aggregated, so you see every
# failure in one run, not just the first).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-all}"
rc=0

has_backend()  { [ -f "$ROOT/backend/pyproject.toml" ] || [ -d "$ROOT/backend/app" ]; }
has_frontend() { [ -f "$ROOT/frontend/package.json" ]; }

be_lint()  { echo "== backend: ruff check =="; ( cd "$ROOT/backend"  && ruff check . ) || rc=1; }
be_test()  { echo "== backend: pytest =="; ( cd "$ROOT/backend" && python -m pytest -q ) || rc=1; }
fe_lint()  { echo "== frontend: npm run lint =="; ( cd "$ROOT/frontend" && npm run lint ) || rc=1; }
fe_build() { echo "== frontend: npm run build =="; ( cd "$ROOT/frontend" && npm run build ) || rc=1; }

case "$MODE" in
  backend-lint)   be_lint ;;
  backend-test)   be_test ;;
  frontend-lint)  fe_lint ;;
  frontend-build) fe_build ;;
  backend)   has_backend  && { be_lint; be_test; } || echo "(no backend/ — skipped)" ;;
  frontend)  has_frontend && { fe_lint; fe_build; } || echo "(no frontend/ — skipped)" ;;
  all)
    has_backend  && { be_lint; be_test; }  || echo "(no backend/ — skipped)"
    has_frontend && { fe_lint; fe_build; } || echo "(no frontend/ — skipped)"
    ;;
  *) echo "unknown mode: $MODE"; exit 2 ;;
esac

if [ "$rc" -ne 0 ]; then
  echo "CHECKS FAILED (mode=$MODE)"
else
  echo "CHECKS PASSED (mode=$MODE)"
fi
exit $rc
