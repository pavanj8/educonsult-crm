# ADR-0009: Graduate the agent harness to the real EduConsult CRM; retire the toy app as the active target

**Status**: Accepted
**Date**: 2026-08-19

## Context

[ADR-0001](0001-isolated-demo-app.md) deliberately built an isolated toy
Student Registration app so harness bugs (Dev/Test/Review agent behavior)
wouldn't be confused with real-CRM requirement ambiguity, per the user's
own original roadmap ("Milestone 1: build the actual Student Registration
application... once that works, we'll build the Dev Agent -> Test Agent ->
Fix -> Retest loop around it").

Once the harness (three agents + shared ticket state machine) was fully
built and validated in isolation (through code review/static checks — not
yet run live end-to-end), the user asked directly: "why are we saying 2
projects... it's same project... that educational crm but using agent
harnessing." The end goal was always one product (EduConsult CRM) built
via agent-harnessed delivery; the toy app was a means, not a parallel
product.

## Decision

Retire the toy Student Registration app (`harness-demo/backend`,
`harness-demo/qa`) as the **active target** of the agents. It remains in
the repo, unmodified, as a historical/reference implementation of the
harness pattern — it is not deleted, since it's a working, documented
example of the Dev/Test/Review loop and the design rationale in ADR-0001
through ADR-0008 remains valid engineering reasoning.

Going forward, the Dev Agent, Test Agent, and Review Agent
(`harness-demo/agents/*.py`, to be relocated/adapted) target the **real
EduConsult CRM repository** directly:

- Tickets come from GitHub Issues (the epics/tasks already created by
  `scripts/setup_github_issues.py`), not local markdown files.
- Requirements/journeys/epics context comes from `docs/requirements.md`,
  `docs/journeys.md`, `docs/epics.md` (the real CRM docs), not
  `harness-demo/requirements.md`/`epics.md`.
- The shared ticket-state-machine principle from
  [ADR-0005](0005-ticket-closure-policy.md) is preserved but re-targeted at
  GitHub Issues (labels + comments) instead of ticket markdown files — see
  [docs/adr/0009](../../docs/adr/0009-agent-harness-github-actions-execution.md).
- Execution moves to GitHub Actions per
  [ADR-0008](0008-github-actions-execution.md) /
  [docs/adr/0009](../../docs/adr/0009-agent-harness-github-actions-execution.md).

This `harness-demo/adr/` log is now frozen at ADR-0009. Any further
design decisions about the agent harness are recorded in
`docs/adr/` (the CRM's single ADR log), since there is one project.

## Alternatives considered

- **Run one full live cycle on the toy app first, then graduate** — this
  was the initially recommended path (safer, proves the loop before
  pointing it at real code) but the user explicitly chose to graduate
  immediately instead.
- **Keep both permanently** (toy app as a standing internal testbed) —
  not chosen; the user confirmed the toy app was only ever a means to the
  one CRM goal.

## Consequences

- The real CRM repository currently has **no application code** (deleted
  earlier per [CRM ADR-0006](../../docs/adr/0006-no-ticket-no-code-policy.md)
  to enforce "no ticket, no code" from a clean baseline) — so the first
  live Dev Agent run against the real repo will be a from-scratch
  implementation of whichever ticket/issue it's pointed at, not a bug fix
  on existing code. This is higher-stakes than the toy-app runs would have
  been, since there's no prior working baseline to fall back on if a run
  goes badly.
- Any harness assumptions baked in while targeting the toy app (SQLite,
  single FastAPI app, ticket-file paths) must be generalized before this
  works against the real CRM's stack (Postgres, Alembic migrations,
  Docker Compose) — tracked as follow-up implementation work, not yet
  done as of this ADR.
- `harness-demo/` stops receiving new milestones; it is not scheduled for
  deletion, but should be treated as archived reference material going
  forward.
