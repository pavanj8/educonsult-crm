# ADR-0004: Role-based access control model and scoping rules

**Status**: Accepted
**Date**: 2026-08-19

## Context

The product has a deep hierarchy of actors (platform operator down to
individual students) each of whom must see only their own slice of data,
with two roles (Super Admin, Consultancy Owner) needing broad
cross-branch/cross-tenant visibility by design.

## Decision

Seven roles, each with a fixed visibility scope enforced server-side:

1. **Super Admin** — all tenants, platform/billing oversight.
2. **Consultancy Owner** — full visibility/control across all branches
   within their own tenant.
3. **Branch Manager** — their own branch only; cannot see other branches
   even within the same tenant.
4. **Counselor** — only students assigned to them.
5. **Document Verifier** — document review/approval queue.
6. **Visa Processor** — visa-stage data (type, embassy interview, outcome).
7. **Receptionist** — intake-only: can create/register students, no
   verification or stage-progression rights.

Plus a separate **Student** identity with a self-service dashboard scoped
to their own application only.

## Alternatives considered

- **Flat permission-per-user model** (no fixed roles) — rejected as
  overkill for the known, stable set of job functions in this domain;
  fixed roles are simpler to reason about and audit.
- **Branch Manager sees all branches read-only** — rejected per explicit
  requirement: Branch Manager visibility is strictly limited to their own
  branch, unlike the Owner.

## Consequences

- Every API endpoint needs an explicit role+scope check, not just
  authentication — this is a security-critical, testable surface and
  should have direct unit test coverage per role combination.
- Adding a new role later means auditing all existing endpoints for
  whether/how the new role should be scoped, not just adding an enum value.
