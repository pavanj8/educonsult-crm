# ADR-0011: Auto-merge agent harness PRs once all gates pass

**Status**: Accepted — implemented
**Date**: 2026-08-19

## Context

ADR-0009 shipped the harness with an explicitly open question: "Auto-merge
on green — not decided... Revisit once there's confidence in the pipeline."
Until now, the workflow opened/updated a PR and reported gate status, but a
human had to run `gh pr merge` by hand.

Two pilot runs were executed manually against the real repo to build that
confidence:

- Issue #54 (backend FastAPI skeleton) — Dev Agent, hard test gate, Test
  Agent, and Review Agent all passed; the user reviewed and merged
  [PR #247](https://github.com/pavanj8/educonsult-crm/pull/247) by hand.
- Issue #59 (SQLAlchemy engine/session + base model) — same four gates
  passed; [PR #248](https://github.com/pavanj8/educonsult-crm/pull/248) was
  left open pending this decision.

Having seen the pipeline produce two clean, correctly-scoped, fully-tested
results in a row, the user asked to auto-merge all harness PRs going
forward rather than reviewing and clicking merge on every one.

## Decision

The workflow itself merges the PR, in the same job run, the moment all
three gates for an iteration pass:

1. Hard test gate (`agents/check_test_gate.py`)
2. Test Agent (`agents/test_agent.py`)
3. Review Agent (`agents/review_agent.py`)

This is exactly the condition `agents/github_ticket_utils.py:
finalize_iteration()` already used to decide between labeling an issue
`agent:ready-to-merge` vs. `agent:needs-rework` (ADR-0010's Definition of
Done, §6 Delivery). The new "Auto-merge PR" step in
`.github/workflows/agent-harness.yml` runs right after "Finalize
iteration", checks for that same `ready-to-merge` outcome, and if present
runs `gh pr merge <n> --merge --delete-branch`. The PR body's `Closes #N`
then closes the issue automatically as part of that merge — no separate
close step needed.

If any gate fails, the PR is left open (labeled via `agent:needs-rework`)
for a human to inspect, or for a later iteration (re-adding
`agent:ready-for-dev`) to fix and retry. Auto-merge never applies to a
failing iteration.

## Alternatives considered

- **GitHub's native "auto-merge" (`gh pr merge --auto`)** — waits for
  required status checks configured on the branch/PR before merging.
  Not used: this repo has no required status checks (the gates run as
  steps inside this same job, not as separate GitHub Check Runs the PR
  could wait on), so native auto-merge would have nothing to wait for.
  A direct, conditional `gh pr merge` in the same job is simpler and
  equivalent given that constraint.
- **Squash merge** — not chosen, to stay consistent with the merge-commit
  method already used for the two manually-merged pilot PRs.
- **Keep requiring a human to merge** — this was the ADR-0009 default;
  superseded by this decision now that two pilot runs validated the gate
  chain end-to-end.

## Consequences

- Every future issue that clears all three gates ships to `main`
  unattended, closing the loop that ADR-0009 set up but left manual.
  Given "even if I close my laptop it should work," this is a necessary
  step for the harness to be actually autonomous end-to-end.
- Raises the blast radius of a bad merge if the agents ever pass gates on
  subtly-wrong code. Mitigations already in place and unchanged by this
  decision: the hard, mechanical test-existence/count gate; a Test Agent
  that writes black-box tests from requirements/journeys/epics without
  ever reading the implementation; a Review Agent covering five
  perspectives (security, architecture, code quality, UX, test adequacy).
  A `agent:needs-rework` PR is never auto-merged.
- This repository currently has no branch protection rules (private repo
  on GitHub's free plan cannot configure them), so `gh pr merge` succeeds
  as a plain merge with no override flags needed. If branch protection is
  added later (e.g. after making the repo public or upgrading plans),
  this step may need `--admin` or the protection rules will need to allow
  the `agent-harness-bot` actor / `GITHUB_TOKEN` to merge.
- `docs/definition-of-done.md` §6 (Delivery) updated to describe
  harness-driven auto-merge instead of "a human merges the PR."
- Implemented entirely in `.github/workflows/agent-harness.yml` (new
  "Auto-merge PR" step); no changes needed to `agents/*.py`.
