# ADR-0005: Student pipeline as an explicit state machine

**Status**: Accepted
**Date**: 2026-08-19

## Context

A student's journey through counseling, document verification, visa, and
loan processing needs to be visible in real time to the student and to
every staff role involved, and drives notifications.

## Decision

Model the student journey as a fixed, explicit pipeline of states:

```
Registered -> Counseling -> Shortlisting -> Application Submitted
  -> Document Verification -> Offer Letter -> Visa Processing
  -> Loan Processing -> Enrolled | Rejected | Withdrawn
```

Each transition is an auditable event (who, when, from/to state), which
also drives the student-facing notification feed and the admin/owner
time-windowed analytics (ADR referenced in requirements: weekly/15-day
stats).

## Alternatives considered

- **Freeform status field per module** (separate ad-hoc statuses for
  counseling/documents/visa/loan with no unifying pipeline) — rejected:
  makes it hard to answer "where is this student right now" as a single
  fact, and complicates analytics/dashboards that need one funnel view.

## Consequences

- New pipeline stages or branches (e.g. a new loan-rejection sub-state)
  require a deliberate schema/state-machine change, not an ad-hoc string
  value — keeps the funnel analytics and notifications reliable.
- The state machine is a natural place to hang authorization rules (e.g.
  only Visa Processor can move a student into/out of Visa Processing).
