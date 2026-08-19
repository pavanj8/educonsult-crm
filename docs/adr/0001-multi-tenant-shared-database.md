# ADR-0001: Multi-tenant architecture: shared database with `tenant_id`

**Status**: Accepted
**Date**: 2026-08-19

## Context

EduConsult CRM must serve many educational consultancies (tenants), each
with multiple branches, from one deployable application, while also
supporting on-prem installs for a single tenant (ADR-0003). We need a
tenancy model that is cheap to operate at SaaS scale but doesn't
over-complicate the on-prem case.

## Decision

Use a single shared PostgreSQL database for all tenants. Every
tenant-scoped table carries a `tenant_id` column, and all queries are
scoped by `tenant_id` (enforced at the application/ORM layer). Branches are
a child concept of a tenant (`branch_id` nested under `tenant_id`), not a
separate tenancy dimension.

## Alternatives considered

- **Database-per-tenant** — strongest isolation, but operationally
  expensive to migrate/scale/monitor at SaaS scale, and overkill for the
  on-prem deployment (which only ever has one tenant anyway).
- **Schema-per-tenant** (single Postgres instance, one schema per tenant) —
  middle ground, but still multiplies migration/connection-pool complexity
  as tenant count grows, for isolation benefits this product doesn't need
  (no tenant runs untrusted code or needs physical data segregation).

## Consequences

- Every data-access path must filter by `tenant_id`; a missing filter is a
  cross-tenant data leak, so this needs to be enforced centrally (e.g. a
  base repository/query helper), not left to each endpoint.
- Onboarding a new tenant is just inserting rows, not provisioning
  infrastructure — fast SaaS signup path.
- On-prem installs still get the same schema/codebase; they simply only
  ever have one `tenant_id` in use.
