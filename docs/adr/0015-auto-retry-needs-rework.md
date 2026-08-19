# ADR-0015: Auto-retry `agent:needs-rework` with Test/Review feedback

**Status**: Accepted — implemented
**Date**: 2026-08-19

## Context

ADR-0009 deferred "auto-loop iterations without human involvement": a
failed iteration posted Test/Review findings on the issue and waited for
a human to re-add `agent:ready-for-dev`. ADR-0012's picker then encoded
that stance — it only ever selected issues with no `agent:*` label at
all, so `agent:needs-rework` tickets sat forever.

The user rejected that. The intended loop, from the original harness
design, is:

```
Dev Agent → Test/Review → FAIL → Dev Agent reads that feedback → fix →
repeat until PASS or MAX_ITERATIONS
```

Waiting for a human (or an open laptop / chat session) to re-trigger
defeats ADR-0009's "even if I close my laptop it should work." The
feedback is already on the issue as comments; the only missing piece was
starting the next iteration.

## Decision

1. **Immediate retry from the harness job itself.** When finalize labels
   `agent:needs-rework` and the iteration that just finished is strictly
   less than `MAX_ITERATIONS` (default 5, workflow env var), the same
   job dispatches `agent-harness.yml` again for that issue via
   `workflow_dispatch` (the GITHUB_TOKEN-safe trigger, ADR-0012). The
   working branch `agent/issue-N` is reused, so Dev Agent continues on
   the existing PR.
2. **Picker is the safety net.** The queue picker now treats
   `agent:needs-rework` with `iteration < MAX_ITERATIONS` as eligible,
   preferred ahead of untouched issues. That covers retries whose
   in-job dispatch failed, and tickets already sitting in needs-rework
   when this decision landed.
3. **Dev Agent is given the feedback, not told to go look.** Prior
   Test Agent / Review Agent / harness-summary comments are fetched and
   injected into the Dev Agent prompt so iteration N+1 must address
   them.
4. **Cap, then stop.** After `MAX_ITERATIONS` failed iterations the
   issue stays `agent:needs-rework` and is no longer auto-picked. A
   human can still comment `/dev-agent` or `workflow_dispatch` to
   continue; that path is not capped, so a stuck ticket is never
   permanently locked out.

## Alternatives considered

- **Keep human-gated retries (ADR-0009 deferred default)** — rejected
  explicitly by the user; it made "close the laptop" false for any
  ticket that didn't go green on the first try.
- **Unbounded auto-retry** — rejected. A silent model/runtime failure
  (ADR-0014) or an impossible ticket would burn Cursor quota forever.
  Five iterations is the original harness `MAX_ITERATIONS` figure and
  matches the `agent:iteration-1`..`10` labels already on the repo with
  headroom.
- **Retry only from the picker, not from the harness job** — rejected as
  the sole mechanism; a 5-minute cron delay is unnecessary when the
  job already knows it failed. The picker remains as backup.
- **Retry only the same issue until it passes before picking any other
  ticket** — effectively what the in-job dispatch does (the retry
  occupies the concurrency slot). The picker preferring needs-rework
  extends that across stranded tickets. Untouched backlog still
  drains whenever nothing is in needs-rework.

## Consequences

- A first-iteration Test/Review fail no longer parks the ticket. The
  next Dev Agent run on GitHub Actions consumes those comments and
  tries again, laptop optional.
- Cost per stubborn ticket is bounded by `MAX_ITERATIONS` extra
  Dev+Test+Review runs, then human attention.
- ADR-0009's deferred alternative is now decided; ADR-0012's "picker
  never retries needs-rework" consequence is superseded by this file.
- In-flight harness runs that started before this workflow landed will
  not self-dispatch; the picker picks those needs-rework issues on the
  next idle tick.
