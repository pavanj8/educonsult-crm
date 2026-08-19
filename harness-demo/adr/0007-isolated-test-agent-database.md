# ADR-0007: Isolated scratch database per Test Agent run

**Status**: Accepted
**Date**: 2026-08-19

## Context

The Test Agent boots a live server instance to black-box test it (ADR-0004)
and needs its own data, without corrupting the Dev Agent's own `app.db` or
colliding with a concurrently running instance.

## Decision

`harness-demo/backend/app/database.py` reads a `DATABASE_OVERRIDE`
environment variable (falling back to `sqlite:///./app.db` when unset).
The Test Agent's `ServerHandle` sets this to a per-run, per-port scratch
file (`qa_run_<port>.db`), and deletes it on teardown regardless of test
outcome.

## Alternatives considered

- **Share the Dev Agent's app.db** — rejected: a failed or partial test run
  would leave polluted data behind, and concurrent/repeated runs would
  produce flaky, order-dependent results.
- **In-memory SQLite for the live server too** (as already used in
  `backend/tests/conftest.py`'s pytest fixtures) — rejected specifically
  for the Test Agent: it runs the server as a separate `uvicorn`
  subprocess, which can't share an in-process SQLite `:memory:` connection
  with the test client making real HTTP calls from outside that process.

## Consequences

- `.gitignore` must exclude the scratch DB pattern (`qa_run_*.db`) so these
  never get committed.
- Any future target application (e.g. the real CRM once the harness
  graduates, per [ADR-0009](0009-graduate-to-real-crm.md)) will need an
  equivalent "point me at an isolated database for this run" mechanism —
  this is a hard requirement for the Test Agent pattern to keep working,
  not specific to SQLite.
