# ADR-0003: Deployment model: SaaS-first, on-prem via Docker Compose

**Status**: Accepted
**Date**: 2026-08-19

## Context

The product must be sellable both as a hosted SaaS (multi-tenant) and as
an on-prem install for consultancies that require local data residency.
Maintaining two divergent codebases/architectures for these would double
engineering cost.

## Decision

Build one codebase and one container image set (backend, frontend,
Postgres) orchestrated via Docker Compose. SaaS is this same stack run
multi-tenant behind the company's own infrastructure; on-prem is the
identical stack run single-tenant on the customer's infrastructure.

## Alternatives considered

- **Separate on-prem edition** (e.g. simplified single-tenant schema) —
  rejected: doubles maintenance burden and risks feature drift between
  editions.
- **Kubernetes-first packaging** — deferred: Docker Compose is sufficient
  for both current SaaS scale and on-prem customer environments, which
  typically don't run k8s. Can be revisited if SaaS scale requires it.

## Consequences

- Multi-tenancy (ADR-0001) must remain compatible with a "one tenant only"
  on-prem deployment — the schema doesn't get simpler for on-prem, it's
  just underutilized.
- Docker Compose files and environment-variable-driven config become part
  of the product's supported surface, not just a dev convenience.
- Scaling SaaS further (e.g. to k8s) later would need to happen without
  breaking the on-prem docker-compose path.
