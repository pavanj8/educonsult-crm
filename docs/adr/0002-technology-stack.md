# ADR-0002: Technology stack: FastAPI + React/Vite/TS + PostgreSQL

**Status**: Accepted
**Date**: 2026-08-19

## Context

Needed a stack that supports both SaaS and on-prem/Docker deployment,
has strong typing/testing support, and is productive for a small team to
build a fairly data- and workflow-heavy CRM (roles, pipelines, documents,
notifications, analytics).

## Decision

- **Backend**: FastAPI (Python), SQLAlchemy + Alembic for ORM/migrations,
  JWT-based auth with an RBAC permission layer.
- **Frontend**: React + Vite + TypeScript.
- **Database**: PostgreSQL.
- **Testing**: pytest for backend unit/integration tests, Playwright for
  frontend E2E.

## Alternatives considered

- **Node.js backend** (originally suggested) — FastAPI was chosen instead
  for stronger typed request/response validation (Pydantic), async
  performance, and auto-generated OpenAPI docs useful for a multi-role API
  surface.
- **MySQL** — PostgreSQL preferred for richer constraint/JSON support and
  ecosystem fit with SQLAlchemy/Alembic tooling.

## Consequences

- Pydantic schemas double as API documentation and validation, reducing a
  class of bugs at tenant/role boundaries.
- Alembic migrations become the single source of truth for schema
  evolution across both SaaS and on-prem deployments — they must ship in
  lockstep with releases.
- Two languages in the repo (Python backend, TypeScript frontend) — CI must
  run separate lint/test pipelines for each.
