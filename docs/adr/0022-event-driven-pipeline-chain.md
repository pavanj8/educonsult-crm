# ADR-0022: Event-driven drain — kick the picker from finalize

**Status**: Accepted — implemented (supersedes the workflow_run approach)
**Date**: 2026-08-20

## Context

The queue picker paces draining on a `*/2` schedule (docs/adr/0012), but GitHub
throttles scheduled workflows hard — observed 10–30 min gaps and a full ~30 min
idle stall. The reliable triggers are event-driven, but the existing ones only
fire on a merge ("Start next Dev") or a needs-rework retry (same ticket); a
stretch of non-merge finalizes left the drain waiting on the throttled cron.

A first attempt used a `workflow_run`-on-Dev-completion workflow to kick the
picker. It never fired: the Dev runs are dispatched by the picker/finalize
using `GITHUB_TOKEN`, and GitHub's recursion prevention means
`GITHUB_TOKEN`-triggered runs do not emit events that start other workflows —
the same limitation recorded in docs/adr/0012. So `workflow_run` is a dead end
here (proven: 5 Dev completions after the workflow merged, 0 chain runs).

## Decision

Kick the picker from **finalize on every run** (`if: always()`), not just on
merge. finalize runs after each ticket's Test+Review join and dispatches via
`gh workflow run` (workflow_dispatch — the documented exception to the
recursion rule, docs/adr/0012), so it reliably fires. After any ticket's
verification completes — merged, needs-rework, waiting, or capped — the picker
runs and starts the next eligible issue. Its own busy/eligibility guards keep
it safe and self-limiting. The `*/2` cron is kept only as a cold-start
fallback. The dead `agent-pipeline-chain.yml` (workflow_run) is removed.

## Consequences

- The drain advances at the harness's real cycle rate, not GitHub's throttled
  schedule; no more idle stalls between tickets.
- One cheap (~10s) picker run per finalize; redundant with the merge/retry
  paths but de-duplicated by the picker's busy guard.
- Reconfirms docs/adr/0012: only `workflow_dispatch`/`repository_dispatch`
  cross-workflow kicks work under `GITHUB_TOKEN`; `workflow_run` does not.
