# ADR-0020: Unified check gate + CI-failure feedback loop (autonomy)

**Status**: Accepted — implemented
**Date**: 2026-08-20

## Context

Two structural gaps kept forcing manual intervention in the delivery loop
(observed repeatedly while migrating the harness to MiniMax, docs/adr/0019):

1. **Split definition of "green."** The Dev Agent gated on its own `pytest`,
   but the merge-blocking CI ran `ruff` + `pytest` (backend) and
   `oxlint` + `build` (frontend). Agents shipped code that passed the harness
   gate and failed CI — the single biggest source of stuck-red PRs.
2. **CI status was not part of the harness gate.** The retry loop
   (`agent:needs-rework`, docs/adr/0015) is driven by the Test/Review/hard-gate
   labels, *not* by the checks that actually block merge. A PR could earn
   `agent:ready-to-merge`, still fail CI, and sit red forever with no self-heal.

## Decision

**① One source of truth for "is this green?" — `scripts/check.sh`.**
A single script runs the exact checks CI enforces (`backend-lint`,
`backend-test`, `frontend-lint`, `frontend-build`, or `all`). Both surfaces
call it:
- `ci-backend.yml` / `ci-frontend.yml` invoke it (job names unchanged, so
  required-check config is unaffected).
- The Dev Agent prompt requires `bash scripts/check.sh` to pass before it
  finishes.
`scripts/` is now a protected path (agents never edit it) and is overlaid from
`main` on every agent run, so the gate can't drift on a resumed branch.

**② CI failure → first-class rework feedback (`ci-feedback-loop.yml`).**
On a failed `CI Backend`/`CI Frontend` run for an `agent/issue-*` branch, post
the failing logs as a `## Harness iteration` comment (which the Dev Agent reads
via `prior_iteration_feedback`) and flag `agent:needs-rework` (dropping
`agent:ready-to-merge`). The existing queue picker then re-dispatches Dev within
`MAX_ITERATIONS` — the cap and Dev serialization are respected, not bypassed.

## Consequences

- With ①, agent-side "green" == CI "green", so CI failures become rare rather
  than routine; ② catches the residue and self-heals it without a human.
- `scripts/check.sh` and the CI workflows must stay in sync by construction
  (CI calls the script), removing the duplicate-command drift risk.
- A genuinely unfixable ticket still stops at `MAX_ITERATIONS` (fail-closed),
  which is the intended safety valve — not silent looping.
- **Merge gate under a free plan.** This repo has no branch protection
  available (private repo, free plan) and `allow_auto_merge=false`, so GitHub
  cannot enforce CI as a required check — `gh pr merge` would merge even with
  red CI. The harness therefore enforces it in `agent-finalize.yml`: the
  auto-merge step runs `gh pr checks --watch` and merges only if CI is green
  (or the PR has no checks at all), otherwise it withholds the merge and hands
  the issue back to the rework loop. This is the harness standing in for the
  branch protection GitHub can't provide here.
- Future direction: on a plan with branch protection, make CI required checks
  and use native `--auto` merge; consider GitHub Check Runs as the state store
  instead of the label set (docs/adr/0009 label model).
