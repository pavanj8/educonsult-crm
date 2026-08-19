# ADR-0001: Build an isolated Student Registration demo app to prototype the harness

**Status**: Accepted
**Date**: 2026-08-19

## Context

The end goal is a Dev/Test/Review agent harness that enforces "no ticket,
no code" (see CRM [ADR-0006](../../docs/adr/0006-no-ticket-no-code-policy.md))
on the real EduConsult CRM. Building and debugging that harness directly
against the CRM's real schema/scope would be slow and risky — failures
would be hard to attribute to "the harness is wrong" vs "the CRM ticket was
ambiguous."

## Decision

Build a small, independent Student Registration application (its own
`requirements.md`/`epics.md`/`tickets/`) purely as a harness test bed, in
`harness-demo/`, decoupled from the real CRM codebase. Validate the full
Dev -> Test -> Review -> feedback loop here first, in small milestones,
before ever pointing the harness at the CRM.

## Alternatives considered

- **Prototype directly on the CRM repo** — rejected: conflates harness bugs
  with CRM requirement ambiguity, and risks the CRM accumulating
  code that predates proper tickets while the harness is still unreliable.

## Consequences

- Two parallel sets of planning docs exist (`docs/*.md` for the CRM,
  `harness-demo/*.md` for the demo) — intentional, not drift to be
  reconciled.
- The harness must eventually be pointed at the real CRM repo as a
  deliberate, later milestone; nothing here assumes it stays scoped to the
  demo app forever.
