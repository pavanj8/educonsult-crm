# ADR-0022: Event-driven pipeline chain (don't depend on the cron)

**Status**: Accepted — implemented
**Date**: 2026-08-20

## Context

The queue picker paces backlog draining on a `*/2` schedule
(docs/adr/0012). But GitHub throttles scheduled workflows heavily — observed
gaps of 10–30 min between picker runs despite the 2-min cron, and a full ~30
min stall with the harness idle. The reliable triggers are event-driven
(finalize kicks the picker on merge; auto-retry re-dispatches on
needs-rework), but when no such event fires — e.g. a stretch where in-flight
tickets are mid-verification and only untouched backlog remains — the loop
falls back to the throttled cron and goes quiet.

## Decision

Add `agent-pipeline-chain.yml`: a `workflow_run` trigger on **Agent Harness
(Dev)** completion (any conclusion) that kicks the queue picker for the next
ticket. Since the Dev run has finished, the picker's active-Dev guard passes
and it dispatches the next eligible issue — a continuous, event-driven chain
that also lets Dev(next) overlap Test/Review(prev) (docs/adr/0016). The `*/2`
cron is kept only as a cold-start fallback.

## Consequences

- The backlog drains at the harness's real cycle rate, not GitHub's throttled
  schedule; no more idle stalls between tickets.
- One extra (cheap, ~10s) picker run per Dev completion; the picker's
  eligibility + busy guards keep it safe and self-limiting (goes quiet when no
  eligible issue remains).
- `gh workflow run` (workflow_dispatch) is used, which is exempt from GitHub's
  "GITHUB_TOKEN events can't trigger workflows" rule, so the chain actually
  fires (docs/adr/0012 amendment).
