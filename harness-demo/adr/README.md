# Architecture Decision Records — Agent Harness (ARCHIVED / FROZEN at ADR-0009)

> **This log is frozen.** As of [ADR-0009](0009-graduate-to-real-crm.md),
> the agent harness targets the real EduConsult CRM repository directly —
> there is one project, not two. New harness-related decisions belong in
> [`../../docs/adr/README.md`](../../docs/adr/README.md). This log is kept
> for historical record of how the harness was designed and validated
> against a disposable toy app before graduating.

This log tracks the design decisions made while building and proving out
the **agent harness** (Dev/Test/Review agents + shared ticket state
machine) against an independent, disposable Student Registration demo app
(see `../README.md`, `../requirements.md`, `../epics.md`, and
[ADR-0006 of the CRM project](../../docs/adr/0006-no-ticket-no-code-policy.md)
for why this existed at all).

## Process

- One ADR per decision, numbered sequentially, named `NNNN-kebab-title.md`.
- Never edit a past decision's Context/Decision retroactively. If a
  decision changes, write a **new** ADR that supersedes it, and update the
  old ADR's status line to `Superseded by ADR-NNNN`.
- Use `TEMPLATE.md` as the starting point.
- Update the index table below whenever an ADR is added or its status
  changes.

## Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [0001](0001-isolated-demo-app.md) | Build an isolated Student Registration demo app to prototype the harness | Accepted | 2026-08-19 |
| [0002](0002-sqlite-for-demo.md) | SQLite (not PostgreSQL) for the harness demo app | Accepted | 2026-08-19 |
| [0003](0003-three-agent-separation.md) | Three-agent separation of concerns: Dev / Test / Review | Accepted | 2026-08-19 |
| [0004](0004-test-agent-independence.md) | Test Agent independence: black-box, no access to implementation before testing | Accepted | 2026-08-19 |
| [0005](0005-ticket-closure-policy.md) | Ticket closure policy: update in place, close only when Test + Review both pass same iteration | Accepted | 2026-08-19 |
| [0006](0006-cursor-sdk-automation.md) | Cursor SDK as the automation substrate for all agents | Accepted | 2026-08-19 |
| [0007](0007-isolated-test-agent-database.md) | Isolated scratch database per Test Agent run | Accepted | 2026-08-19 |
| [0008](0008-github-actions-execution.md) | Move agent execution to GitHub (Actions runners, GitHub Issues as tickets, hard test gate) | Superseded by [CRM ADR-0009](../../docs/adr/0009-agent-harness-github-actions-execution.md) | 2026-08-19 |
| [0009](0009-graduate-to-real-crm.md) | Graduate the harness to the real EduConsult CRM; retire the toy app as active target | Accepted — **log frozen here** | 2026-08-19 |
