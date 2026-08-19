# Architecture Decision Records — EduConsult CRM

This is the **single, canonical ADR log for this repository** — there is
one project (EduConsult CRM), built using an agent-harnessed delivery
process (ADR-0008/0009). It tracks significant, hard-to-reverse design
decisions for the product (the multi-tenant educational consultancy
management SaaS — see `../requirements.md`, `../journeys.md`,
`../epics.md`) and for the agent harness that builds it.

`../../harness-demo/adr/` is a **frozen, historical** log from when the
harness was being designed/validated against a disposable toy app, before
it graduated to building this product directly (see
[ADR-0008](0008-agent-harness-adopted-for-delivery.md)). It's kept for
context on *why* the harness is designed the way it is; it does not
receive new entries.

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
| [0001](0001-multi-tenant-shared-database.md) | Multi-tenant architecture: shared database with `tenant_id` | Accepted | 2026-08-19 |
| [0002](0002-technology-stack.md) | Technology stack: FastAPI + React/Vite/TS + PostgreSQL | Accepted | 2026-08-19 |
| [0003](0003-deployment-model.md) | Deployment model: SaaS-first, on-prem via Docker Compose | Accepted | 2026-08-19 |
| [0004](0004-rbac-role-model.md) | Role-based access control model and scoping rules | Accepted | 2026-08-19 |
| [0005](0005-student-pipeline-state-machine.md) | Student pipeline as an explicit state machine | Accepted | 2026-08-19 |
| [0006](0006-no-ticket-no-code-policy.md) | "No ticket, no code" delivery policy with full traceability | Accepted | 2026-08-19 |
| [0007](0007-github-issues-for-epics-tasks.md) | GitHub Issues as system of record for epics and tasks | Accepted | 2026-08-19 |
| [0008](0008-agent-harness-adopted-for-delivery.md) | Adopt the Dev/Test/Review agent harness for CRM delivery | Accepted | 2026-08-19 |
| [0009](0009-agent-harness-github-actions-execution.md) | Agent harness execution model: GitHub Actions, GitHub Issues as tickets, hard test gate | Accepted — implemented, not yet run | 2026-08-19 |
| [0010](0010-formal-definition-of-done.md) | Formal, written Definition of Done for every epic and task | Accepted — implemented | 2026-08-19 |
| [0011](0011-auto-merge-agent-harness-prs.md) | Auto-merge agent harness PRs once all gates pass | Accepted — implemented | 2026-08-19 |
