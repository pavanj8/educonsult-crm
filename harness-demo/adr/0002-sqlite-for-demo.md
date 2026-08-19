# ADR-0002: SQLite (not PostgreSQL) for the harness demo app

**Status**: Accepted
**Date**: 2026-08-19

## Context

The demo app (ADR-0001) exists purely to exercise the agent harness, not
to be production infrastructure. It needs to boot instantly, in parallel,
possibly many times per Test Agent run, on a laptop and (per
[ADR-0008](0008-github-actions-execution.md)) later on ephemeral CI
runners.

## Decision

Use SQLite via SQLAlchemy for the harness demo app, with a
`DATABASE_OVERRIDE` environment variable (see
[ADR-0007](0007-isolated-test-agent-database.md)) so each Test Agent run
gets its own throwaway file/in-memory database.

## Alternatives considered

- **PostgreSQL, matching the real CRM stack** (ADR-0002 of the CRM) —
  rejected for the demo specifically: adds a service dependency
  (Docker/Postgres install) to every environment the harness runs in
  (laptop, CI runner) for no benefit, since the demo app's job is to have
  bugs injected/fixed, not to validate Postgres-specific behavior.

## Consequences

- The demo app's persistence layer is not representative of the real
  CRM's — that's fine, since the harness is being validated on agent
  behavior (ticket-driven implementation, independent testing, review),
  not on database choice.
- If/when the harness is pointed at the real CRM, the harness scripts must
  not assume SQLite; they should treat the target app's stack as opaque.
