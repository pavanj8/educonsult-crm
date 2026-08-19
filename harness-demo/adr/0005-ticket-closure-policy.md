# ADR-0005: Ticket closure policy — update in place, close only when Test + Review both pass same iteration

**Status**: Accepted
**Date**: 2026-08-19

## Context

The user asked that Test Agent findings "create issues and provide this
feedback to both dev and review agents... update the tickets with all the
details and close only when all the requirements are fulfilled." An
earlier implementation had the Test Agent file a brand-new ticket for
every failure, which fragments history and doesn't map to "close only
when fulfilled" for the original ticket.

## Decision

All three agents (Dev, Test, Review) append a timestamped entry to the
**same** ticket file under an `## Agent Activity Log` section
(`harness-demo/agents/ticket_utils.py`), and update one `**Status**:`
field on that ticket:

```
Open
  -> Dev Agent runs, own pytest green     -> Ready for Test & Review
  -> Dev Agent runs, own pytest red       -> Needs Rework
  -> Test Agent PASS (Review not yet)     -> Test Passed (awaiting review)
  -> Test Agent FAIL                      -> Needs Rework
  -> Review Agent PASS (Test not yet)     -> Review Passed (awaiting test)
  -> Review Agent FAIL                    -> Needs Rework
  -> Test PASS + Review PASS, same --iteration -> Closed
```

A ticket only reaches `Closed` when, for the identical iteration number,
both the Test Agent and Review Agent report PASS.

## Alternatives considered

- **File a new bug ticket per Test Agent failure** (original
  implementation) — rejected/superseded: fragments the audit trail across
  many ticket files for what is usually the same underlying ticket not yet
  meeting its own acceptance criteria, and doesn't match "close only when
  fulfilled" for the original unit of work.

## Consequences

- A ticket's full history (every Dev/Test/Review attempt) lives in one
  file, which is exactly the auditable trail needed for "no ticket, no
  code" traceability.
- Iteration numbers must be passed consistently across all three agents
  for a given cycle (`--iteration N` on the CLI) — a mismatch would falsely
  report "not yet closed" or (worse) closed against stale evidence, so this
  needs to become an automatically-managed value once the loop is
  orchestrated (Milestone 4/5), not a manually-typed flag.
- This same pattern (issue = single mutable unit of work, closed only on
  dual green) is being carried into the GitHub Issues migration
  ([ADR-0008](0008-github-actions-execution.md)).
