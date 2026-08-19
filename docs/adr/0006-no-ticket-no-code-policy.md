# ADR-0006: "No ticket, no code" delivery policy with full traceability

**Status**: Accepted
**Date**: 2026-08-19

## Context

Early in the project, code was at risk of being written ahead of agreed
requirements. The user explicitly asked for a policy preventing this, plus
full traceability from requirements down to individual units of work, so
that every line of code can be justified back to a stated requirement.

## Decision

Adopt "no ticket, no code": no implementation work happens without a
corresponding ticket (small, GitHub-issue-sized unit of work). Tickets
must trace to an epic, epics must trace to one or more user journeys, and
journeys must trace to a stated requirement. Concretely:

```
Requirement -> Journey -> Epic -> Ticket -> Code
```

Documentation for each layer (`docs/requirements.md`, `docs/journeys.md`,
`docs/epics.md`) is the source of truth, produced and reviewed **before**
any implementation ticket is opened.

An enforcement consequence of this policy: pre-existing code that predated
this traceability chain was deleted rather than retrofitted, at the user's
explicit direction, to establish a clean baseline.

## Alternatives considered

- **Lightweight backlog without formal traceability** — rejected: doesn't
  give the guarantee the user wanted, that every change can be justified
  back to a requirement, which matters for an agent-driven (as opposed to
  purely human-driven) delivery process where "why was this built" needs
  to be answerable without relying on a human's memory.

## Consequences

- Planning overhead front-loads before coding starts (this is intentional,
  not a bug).
- Granularity of epics/journeys must stay close to 1:1 (see epics.md
  history — epics were expanded from 37 to 53 specifically to preserve
  this near-1:1 traceability against 46 journeys) — coarse epics break the
  "backtrack from ticket to requirement" guarantee.
- This policy is the direct motivation for building an automated
  Dev/Test/Review agent harness (see `harness-demo/adr/`) that structurally
  cannot write code without reading a ticket first.
