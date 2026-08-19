# EduConsult CRM

A multi-tenant SaaS + on-prem platform for education consultancies to
manage the full student journey — registration, counseling, shortlisting,
application, document verification, offer letters, visa processing, loan
processing, and enrollment — across multiple branches and roles.

This repository is built almost entirely by an autonomous **Dev / Test /
Review agent harness** running on GitHub Actions, under a strict
**"no ticket, no code"** policy: every change traces back to a GitHub
Issue, which traces back to an epic, a user journey, and a stated
requirement. See [`docs/adr/`](docs/adr/) for the full history of *why*
the project is built this way.

## Who this is for

- **Consultancy Owner** — full visibility across all branches of their
  consultancy.
- **Branch Manager** — visibility scoped to their own branch.
- **Counselor** — manages an assigned caseload of students end-to-end.
- **Document Verifier** — verifies uploaded student documents.
- **Visa Processor** — manages visa-stage document review and status.
- **Receptionist** — front-desk/admin support tasks.
- **Student** — registers, uploads documents, tracks application status
  and loan options in real time, receives notifications.
- **Super Admin** — manages multiple tenant consultancies.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python), SQLAlchemy 2.0 + Alembic |
| Database | PostgreSQL, shared schema with `tenant_id` scoping ([ADR-0001](docs/adr/0001-multi-tenant-shared-database.md)) |
| Frontend | React + Vite + TypeScript |
| Auth | JWT + RBAC ([ADR-0004](docs/adr/0004-rbac-role-model.md)) |
| Deployment | SaaS-first; on-prem via Docker Compose ([ADR-0003](docs/adr/0003-deployment-model.md)) |
| Testing | pytest (backend), Vitest (frontend), Playwright (E2E, planned) |
| Delivery | Autonomous Dev/Test/Review agent harness on GitHub Actions ([ADR-0008](docs/adr/0008-agent-harness-adopted-for-delivery.md), [ADR-0009](docs/adr/0009-agent-harness-github-actions-execution.md)) |

Full rationale for every one of these choices is recorded as an ADR in
[`docs/adr/`](docs/adr/README.md).

## Repository structure

```
backend/            FastAPI app (app/, tests/) — the product backend
frontend/            React + Vite + TS app (src/) — the product frontend
docs/
  requirements.md    What the product must do
  journeys.md        Atomic user journeys, traced to requirements
  epics.md           Epics + tasks, traced to journeys (source for GitHub Issues)
  definition-of-done.md   The single DoD every issue must satisfy
  adr/               Architecture Decision Records (canonical, active)
agents/              The Dev/Test/Review harness that implements issues
scripts/             One-off repo automation (e.g. GitHub Issues bootstrap)
.github/workflows/   agent-harness.yml — runs the harness on GitHub-hosted runners
infra/               Deployment/infra assets (Docker Compose, etc. — being built out)
harness-demo/        Frozen historical reference: the toy app used to design
                     and validate the harness before it graduated to build
                     this product directly ("harness-demo/adr/README.md")
```

## Running it locally

**Backend**

```bash
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/health  => {"status": "ok"}
```

Backend tests:

```bash
cd backend && pytest
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Frontend tests:

```bash
cd frontend && npm test
```

Both apps are still early scaffolding (foundation epic E1 in
[`docs/epics.md`](docs/epics.md)) — most product features described in
[`docs/requirements.md`](docs/requirements.md) don't exist yet and are
tracked as open GitHub Issues.

## How work happens here: the agent harness

1. Every unit of work is a GitHub Issue (an epic or a task), created from
   [`docs/epics.md`](docs/epics.md) by [`scripts/setup_github_issues.py`](scripts/setup_github_issues.py).
   Every issue embeds the [Definition of Done](docs/definition-of-done.md).
2. Adding the `agent:ready-for-dev` label to an issue triggers
   [`.github/workflows/agent-harness.yml`](.github/workflows/agent-harness.yml)
   on a GitHub-hosted runner — no dependency on anyone's laptop being on.
3. That workflow is the **Dev** stage: it implements the issue, commits,
   runs the hard test gate, and opens/updates the PR. It then starts
   **Test Agent** and **Review Agent** as separate GitHub Actions jobs
   ([ADR-0016](docs/adr/0016-pipeline-parallelism.md)). Those can run on
   *other* tickets Dev already finished; each job checks out that
   ticket's `agent/issue-N` branch. Test/Review never pick an issue Dev
   has not implemented.
4. If all of those pass, the harness **auto-merges the PR itself**
   ([ADR-0011](docs/adr/0011-auto-merge-agent-harness-prs.md)), which
   closes the issue. If anything fails, the issue is labeled
   `agent:needs-rework` and the harness **auto-retries** with that
   Test/Review feedback ([ADR-0015](docs/adr/0015-auto-retry-needs-rework.md)),
   up to `MAX_ITERATIONS` (default 5).
5. **Dev** is serialized one-at-a-time (overlapping files). Test and
   Review run in parallel on other tickets' branches
   ([ADR-0016](docs/adr/0016-pipeline-parallelism.md)).

See [`agents/README.md`](agents/README.md) for the harness internals, and
[`docs/adr/0009`](docs/adr/0009-agent-harness-github-actions-execution.md)
/ [`docs/adr/0011`](docs/adr/0011-auto-merge-agent-harness-prs.md) for the
design decisions behind this process.

## Key docs

- [`docs/requirements.md`](docs/requirements.md) — product requirements
- [`docs/journeys.md`](docs/journeys.md) — atomic user journeys
- [`docs/epics.md`](docs/epics.md) — epics + tasks, traced to journeys
- [`docs/definition-of-done.md`](docs/definition-of-done.md) — the DoD
- [`docs/adr/`](docs/adr/README.md) — all architecture decisions
- [GitHub Issues](https://github.com/pavanj8/educonsult-crm/issues) — the live backlog
