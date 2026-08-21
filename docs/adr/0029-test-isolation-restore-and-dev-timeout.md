# ADR-0029: Fix reload test-isolation leak + hard Dev wall-clock cap

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

Two recurring drags on Dev runs, both seen on #175 (~41 min):

1. **Order-dependent test failures.** Routers and `conftest` capture
   `app.db.database.get_db` at import time, but `tests/database/*` call
   `importlib.reload(app.db.database)`, which rebinds `get_db` (and `engine`,
   `SessionLocal`) to NEW objects. That mutation leaks to every later test:
   `get_db` no longer matches the object the routers use, so
   `dependency_overrides[get_db]` silently stop applying, and unrelated tests
   fail *only when run after* the reload suite. Agents burn long runs debugging
   this per-ticket (same class as earlier `ObjectDeletedError` flakiness).
2. **Unbounded Dev run time.** `DEV_MAX_TURNS` caps the turn *count*, but a turn
   that re-runs the full suite takes minutes, so a churning run can still hog the
   single Dev slot for ~41 min.

## Decision

1. **Restore the database module after each test.** An autouse `conftest`
   fixture snapshots the original `get_db`/`engine`/`SessionLocal` at import and
   re-binds them in teardown, so any `importlib.reload` is contained to the test
   that did it and the suite is order-independent.
2. **Hard wall-clock cap on the Dev Agent step**: `timeout-minutes: 30`. On
   timeout the step fails -> build gate -> `needs-rework` -> retry, which is
   cheaper than an unbounded run. Sized for a normal pass plus one in-run retry
   (docs/adr/0027 with `DEV_RETRY_MAX_TURNS`).

## Consequences

- Eliminates a whole class of flaky, order-dependent failures that agents
  repeatedly wasted long runs debugging -> faster, more reliable Dev/CI.
- Dev runs can no longer exceed ~30 min of wall clock; a genuinely stuck run
  fails-closed promptly instead of blocking the queue.
- `conftest.py` is product test code (not a protected path), so agents can still
  evolve it; this hardening lives on main until they do.
