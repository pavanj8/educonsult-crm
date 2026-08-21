# ADR-0023: Build gate before Test/Review + PR authored via GH_PAT

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

Two throughput/waste problems observed after ~7h of running:

1. **Wasted verification on broken Dev output.** The Dev Agent step is
   `continue-on-error`, and the workflow unconditionally dispatched the
   expensive Test + Review agents (and their CI) even when Dev crashed or wrote
   code that doesn't build. So a doomed iteration still burned two M3 agent runs
   + CI before failing — and only ~7 tickets merged in 7h despite constant
   churn.
2. **CI gated by first-time-contributor approval.** After going public, CI runs
   on PRs authored by `github-actions[bot]` were held as `action_required`
   (the repo's `first_time_contributors` approval policy), stalling those PRs.

## Decision

1. **Build gate.** After Dev commits, a gate step decides whether to spend
   Test/Review: skip if the Dev Agent step failed, produced no changes, or the
   code fails `scripts/check.sh backend`. On skip, post the failure as a
   `## Harness iteration` feedback comment, set `agent:needs-rework`, and kick
   the picker (which re-picks within `MAX_ITERATIONS`). Test/Review run only on
   output that already passes the mechanical gate.
2. **PR via GH_PAT.** Create the PR with `GH_PAT` (a real user) instead of the
   default `GITHUB_TOKEN`, so its CI isn't gated by the public-repo
   first-time-contributor approval policy. Security for genuine external forks
   is unchanged (they still need approval).

## Consequences

- Broken iterations cost ~1 gate run instead of Dev + Test + Review + CI +
  finalize; the freed capacity and faster rework should raise merged/hour.
- The gate adds ~30s–2m (backend deps + check.sh) to *every* Dev run, including
  good ones — a net win only because a large fraction were failing. Revisit if
  first-pass success gets high.
- Frontend-only quality is still caught by CI + the feedback loop, not the
  backend gate.
- Reconfirms docs/adr/0012: bot-authored actions get gated on public repos;
  attributing to a real user (GH_PAT) is the fix.
