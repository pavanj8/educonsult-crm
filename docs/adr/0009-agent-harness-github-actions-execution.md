# ADR-0009: Agent harness execution model — GitHub Actions runners, GitHub Issues as tickets, hard test gate

**Status**: Accepted — implemented; auto-loop in [ADR-0015](0015-auto-retry-needs-rework.md); sequential one-job pipeline superseded by [ADR-0016](0016-pipeline-parallelism.md)
**Date**: 2026-08-19 (implementation: 2026-08-19)

## Context

The agents (ADR-0008) were only ever run manually from the user's own
Mac, with `CURSOR_API_KEY` exported in a local shell. The user does not
want delivery to depend on their laptop being on, and separately wants a
**hard, deterministic** guarantee — not just an LLM judgment call — that
every ticket ships with committed unit tests before it can be considered
fixed.

This decision was originally drafted as
[harness-demo/adr/0008](../../harness-demo/adr/0008-github-actions-execution.md)
while the harness was still targeting the toy app; it's recorded
canonically here following the graduation decision
([harness-demo/adr/0009](../../harness-demo/adr/0009-graduate-to-real-crm.md)).

## Decision

1. **Runtime — GitHub Actions runners, `local` Cursor SDK mode.** The
   Actions job checks out this repo; the agent's `cwd` is that checkout.
   GitHub-hosted runners are spun up by GitHub itself in response to
   repository events, independent of any personal machine being powered
   on — this directly satisfies "even if I close my laptop it should
   work." (Considered but not chosen: Cursor Cloud Agents, which run on a
   Cursor-hosted VM against a freshly cloned repo — viable, but less
   visibility/control from Actions logs, and not needed since GitHub-hosted
   runners already remove the laptop dependency.)
2. **Tickets — GitHub Issues**, replacing the markdown ticket files used
   during the harness-demo phase. Epics/tasks already exist as issues via
   `scripts/setup_github_issues.py` (CRM ADR-0007). The ticket state
   machine from harness-demo ADR-0005 (Open -> Ready for Test & Review ->
   Needs Rework -> Closed only when Test + Review both pass the same
   iteration) is re-implemented against issue labels/comments instead of
   a markdown file's `Status:` field and `## Agent Activity Log` section.
3. **Trigger — label or comment on the issue** (e.g. a `ready-for-dev`
   label, or a `/dev-agent` comment) starts the workflow; a manual
   `workflow_dispatch` remains available as a fallback/debugging path.
4. **Hard test gate.** In addition to the Review Agent's judgment-based
   "Test Engineer" perspective (harness-demo ADR-0003), add a
   deterministic CI check that:
   - Fails the workflow if application code changed for a ticket but no
     test file changed alongside it.
   - Requires pytest to pass with no decrease in the number of test
     functions/coverage versus the prior state.
   A ticket/issue cannot be marked fixed by the harness if this gate
   fails, regardless of what the Review Agent or Test Agent conclude.

## Alternatives considered

- **Split Dev/Test/Review into separately-triggered Actions jobs**
  (label-per-stage, each queried for cross-job state via more labels) —
  considered, but rejected in favor of one sequential job per
  iteration (Dev -> hard gate -> Test -> Review -> report) to avoid
  cross-run race conditions and because the existing scripts are already
  sequential (Test/Review need the Dev Agent's diff to exist first).
- **Auto-loop iterations without human involvement** — deferred, not
  decided here. For now, a failed iteration posts its findings back to the
  issue and requires a human (or a follow-up label/comment) to trigger the
  next iteration, rather than the workflow auto-retrying up to a
  `MAX_ITERATIONS` limit. Full autonomous looping remains a candidate
  follow-up decision once this manual-iteration version is proven.
- **Auto-merge on green** — not decided; current default is the workflow
  opens/updates a PR and reports gate status, but a human merges. Revisit
  once there's confidence in the pipeline.

## Consequences

- `CURSOR_API_KEY` must be provisioned as a GitHub Actions secret (not a
  local shell env var) — a credential-handling change, not just a
  where-it-runs change.
- The harness scripts need adapting: ticket I/O moves from local file
  reads/writes (`ticket_utils.py`) to GitHub API calls (issue body,
  labels, comments) via `gh` CLI or `actions/github-script`.
- The hard test gate needs a concrete, scriptable definition of "which
  test files correspond to which app files for this ticket" — likely a
  git-diff-based heuristic (did anything under `backend/tests/` change
  when `backend/app/` changed) rather than perfect ticket-to-test mapping;
  this is a deliberate approximation, not full traceability.
- Implemented as `.github/workflows/agent-harness.yml` plus
  `agents/github_ticket_utils.py`, `agents/target_app.py`,
  `agents/check_test_gate.py`, `agents/prepare_iteration.py`,
  `agents/finalize_iteration.py`, and the re-pointed
  `agents/{dev,test,review}_agent.py` (moved out of `harness-demo/agents/`
  to `agents/` at repo root, since they now target this repo directly).
  One workflow run = one full Dev -> commit -> hard-gate -> Test -> Review
  iteration, sequentially in a single job (not split across
  separately-triggered jobs), per the "alternatives considered" above.
- **Repo setup progress** (see `agents/README.md`'s checklist):
  `CURSOR_API_KEY` is now set as a repo secret, and all `agent:*` labels
  (trigger, iteration counters, pass/fail per agent, ready-to-merge,
  needs-rework) exist on `pavanj8/educonsult-crm`, both done 2026-08-19.
  Still outstanding: `scripts/setup_github_issues.py` has not been run
  against the real repo, so there are no GitHub Issues to point the
  harness at yet, and the workflow itself has not been triggered. All
  verification so far is offline (syntax/compile checks, YAML parsing, and
  a mocked-`gh`-CLI unit test of the label state machine in
  `github_ticket_utils.py`) plus these two now-live, low-risk setup steps.

## Amendment (2026-08-19): `workflows: write` to push CI workflow files

Issue #61 (GitHub Actions CI for the backend) had Dev Agent write
`.github/workflows/ci-backend.yml`, then `git push` was rejected:

```
refusing to allow a GitHub App to create or update workflow
.github/workflows/ci-backend.yml without `workflows` permission
```

Test/Review never started; the issue sat with `agent:iteration-1` and
no `needs-rework`, so the picker would not retry it.

Fix: if commit/push fails, label `agent:needs-rework` so the ticket
re-enters the queue instead of stalling. Pushing workflow files also
requires a `GH_PAT` secret with the `workflow` scope — `GITHUB_TOKEN`
cannot create/update `.github/workflows/*` even with `contents: write`.
The Dev job's checkout uses `secrets.GH_PAT || github.token`.

