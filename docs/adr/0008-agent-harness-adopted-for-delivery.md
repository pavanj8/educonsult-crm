# ADR-0008: Adopt the Dev/Test/Review agent harness for EduConsult CRM delivery

**Status**: Accepted
**Date**: 2026-08-19

## Context

[ADR-0006](0006-no-ticket-no-code-policy.md) established "no ticket, no
code" with full requirements -> journeys -> epics -> tickets traceability.
To enforce this mechanically (not just by convention), a three-agent
harness (Dev Agent, Test Agent, Review Agent) was designed and built
against a disposable toy app — see `harness-demo/adr/` for the full design
history (isolation rationale, agent responsibilities, ticket state
machine, independence rules).

Once built, it was confirmed the harness was always meant to serve this
one product, not to remain a side project — see
[harness-demo/adr/0009](../../harness-demo/adr/0009-graduate-to-real-crm.md).

## Decision

Adopt the agent harness as the actual delivery mechanism for EduConsult
CRM implementation work, carrying forward these design principles
unchanged from the harness-demo phase:

- **Three-agent separation** (Dev / Test / Review) — see
  [harness-demo ADR-0003](../../harness-demo/adr/0003-three-agent-separation.md).
- **Test Agent independence** (black-box, no access to implementation or
  the Dev Agent's own tests before testing) — see
  [harness-demo ADR-0004](../../harness-demo/adr/0004-test-agent-independence.md).
- **Ticket closure policy**: update the same unit of work in place, close
  only when Test Agent and Review Agent both pass for the same iteration —
  see [harness-demo ADR-0005](../../harness-demo/adr/0005-ticket-closure-policy.md).
  Re-targeted at GitHub Issues instead of ticket markdown files (see
  [ADR-0009](0009-agent-harness-github-actions-execution.md)).
- **Cursor SDK** as the automation substrate — see
  [harness-demo ADR-0006](../../harness-demo/adr/0006-cursor-sdk-automation.md).

What changes relative to the harness-demo phase: the target is now the
real CRM repository (this repo, `docs/` for requirements/journeys/epics,
the real `backend/`/`frontend/` once implemented) instead of the toy
Student Registration app, and tickets are GitHub Issues instead of
markdown files (ADR-0009).

## Alternatives considered

- **Human-only delivery, agents as an occasional assist** — rejected: the
  entire point of ADR-0006 was to make "no ticket, no code" and
  requirement traceability structurally enforced, which needs an agent
  that literally cannot proceed without a ticket and independent
  verification, not a human policy that can be skipped under deadline
  pressure.
- **Keep the harness scoped to the toy app indefinitely** — rejected per
  the user's explicit decision (harness-demo ADR-0009).

## Consequences

- The real CRM repository currently has no application code (see
  ADR-0006's enforcement action) — the harness's first live runs against
  this repo will be greenfield implementation, not bug-fixing on an
  existing baseline. Higher stakes than the toy-app validation runs that
  were originally planned but skipped (harness-demo ADR-0009's
  alternatives-considered).
- The harness scripts (`harness-demo/agents/*.py`) need to be generalized
  beyond the toy app's assumptions (SQLite, single FastAPI process, local
  ticket files) before they can correctly target the real stack (Postgres,
  Alembic, Docker Compose, GitHub Issues) — tracked as follow-up
  implementation work.
