# Student Registration — Agent Harness Demo (Milestone 1)

This is a deliberately tiny, standalone app used to prototype the Dev Agent /
Test Agent / Review Agent harness described in `docs/agent-harness-plan.md`
(top-level repo). It is **not** part of the EduConsult CRM build (that work is
parked in `docs/requirements.md`, `docs/journeys.md`, `docs/epics.md`) — this
is an isolated sandbox to prove out the agent loop before applying it there.

## Stack
- FastAPI + SQLite (via SQLAlchemy)
- pytest for backend tests

## What it does
A single feature: student registration.
- `POST /students/register` — create a student (name, email, password, age).
  Returns `201` on success, `400` for invalid email format or duplicate email.
- `GET /students/{id}` — fetch a student by id (`404` if not found).
- `GET /students` — list all students.
- `GET /health` — health check.

## Running locally

```bash
cd harness-demo/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Running tests

```bash
cd harness-demo/backend
source venv/bin/activate
python -m pytest -v
```

All 6 tests currently pass. This is the known-good baseline the harness will
later regress against (Milestone 1 complete). Next: Milestone 2 will build the
Dev Agent that can pick up a ticket, read the surrounding requirements/epic
context, and modify this codebase on its own.
