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
| [0009](0009-agent-harness-github-actions-execution.md) | Agent harness execution model: GitHub Actions, GitHub Issues as tickets, hard test gate | Accepted — sequential job superseded by ADR-0016 | 2026-08-19 |
| [0010](0010-formal-definition-of-done.md) | Formal, written Definition of Done for every epic and task | Accepted — implemented | 2026-08-19 |
| [0011](0011-auto-merge-agent-harness-prs.md) | Auto-merge agent harness PRs once all gates pass | Accepted — implemented | 2026-08-19 |
| [0012](0012-paced-queue-picker-for-backlog.md) | Paced queue picker for processing a large issue backlog unattended | Accepted — implemented | 2026-08-19 |
| [0013](0013-asymmetric-model-tiering.md) | Asymmetric model tiering: cheap model to write, high-end model to verify | Accepted — model IDs superseded by ADR-0014 | 2026-08-19 |
| [0014](0014-local-sdk-runtime-model-subset.md) | Local SDK runtime only executes a subset of listed models | Accepted — implemented | 2026-08-19 |
| [0015](0015-auto-retry-needs-rework.md) | Auto-retry `agent:needs-rework` with Test/Review feedback | Accepted — implemented | 2026-08-19 |
| [0016](0016-pipeline-parallelism.md) | Pipeline parallelism: Dev, Test, and Review on different tickets | Accepted — implemented | 2026-08-19 |
| [0017](0017-minimax-api-key-for-agent-models.md) | MiniMax API key for agent harness model inference | Superseded by ADR-0018 | 2026-08-20 |
| [0018](0018-revert-minimax-sdk-model-ids.md) | Revert MiniMax model IDs — not valid on Cursor SDK local runtime | Superseded by ADR-0019 | 2026-08-20 |
| [0019](0019-minimax-agent-loop-replaces-cursor-sdk.md) | Replace the Cursor SDK engine with a direct-MiniMax agent loop | Accepted — implemented | 2026-08-20 |
| [0020](0020-unified-gate-and-ci-feedback-loop.md) | Unified check gate (`scripts/check.sh`) + CI-failure feedback loop | Accepted — implemented | 2026-08-20 |
| [0021](0021-agent-latency-context-pack.md) | Cut agent latency with a context pack + efficiency prompts | Accepted — implemented | 2026-08-20 |
