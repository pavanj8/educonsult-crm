# Agent Harness (Dev / Test / Review)

Three agents, built on the [Cursor SDK](https://cursor.com/docs/sdk/python),
that implement "no ticket, no code" (`docs/adr/0006`) for the EduConsult
CRM repo. This is the graduated version of the harness originally proven
out against a disposable toy app under `harness-demo/` (see
`harness-demo/adr/` for that design history, and `docs/adr/0008`/`0009`
for the graduation and execution-model decisions).

- **`dev_agent.py`** — implements a GitHub Issue.
- **`test_agent.py`** — independently black-box tests it against a live
  server, without reading the Dev Agent's implementation or its tests. If
  there's no live app yet (infra-only ticket), it reports PASS-by-N/A and
  defers to Review + the hard gate.
- **`review_agent.py`** — reviews the Dev Agent's actual diff (vs `main`)
  from five senior perspectives: Security Analyst, Software Architect,
  Senior Developer, UX Architect, Test Engineer.
- **`check_test_gate.py`** — hard, deterministic gate: fails if app code
  changed without a corresponding test change, or if the test count
  dropped, or if `pytest` doesn't pass. Runs independently of the Review
  Agent's judgment.
- **`github_ticket_utils.py`** — the GitHub Issue is the ticket. State is
  tracked via labels (`agent:ready-for-dev`, `agent:iteration-N`,
  `agent:{dev,test,review}-{pass,fail}`, `agent:ready-to-merge`,
  `agent:needs-rework`); every agent run posts a comment with its report.
- **`prepare_iteration.py`** / **`finalize_iteration.py`** — small
  workflow-glue scripts that bump the iteration label before Dev Agent
  runs, and set the final pass/fail label + summary comment after
  Gate+Test+Review have all run.

## Where this runs

**GitHub Actions, not your machine** (`.github/workflows/agent-harness.yml`,
see `docs/adr/0009`). Triggers:

- Adding the `agent:ready-for-dev` label to an issue.
- Commenting `/dev-agent` on an issue.
- Manually, via the Actions tab -> "Agent Harness" -> "Run workflow", passing
  an issue number.

One workflow run = one iteration, sequentially: Dev Agent -> commit+push ->
hard gate -> Test Agent -> Review Agent -> open/update a PR -> finalize
labels + summary comment -> auto-merge if green
(`docs/adr/0011-auto-merge-agent-harness-prs.md`). If anything fails, the
issue gets `agent:needs-rework` and the PR stays open with the branch
as-is; re-add `agent:ready-for-dev` (or comment `/dev-agent` again) to run
another iteration on the same branch. A repo-wide `concurrency:` group on
the workflow means only one iteration runs at a time.

## Required repo setup (one-time)

1. ✅ **Secret**: `CURSOR_API_KEY` set in repo Settings -> Secrets and
   variables -> Actions (done 2026-08-19).
2. ✅ **Labels**: `agent:ready-for-dev`, `agent:iteration-1` through
   `agent:iteration-10`, `agent:{dev,test,review}-{pass,fail}`,
   `agent:ready-to-merge`, `agent:needs-rework` — all created on
   `pavanj8/educonsult-crm` (done 2026-08-19). If more than 10 iterations
   are ever needed for one issue, create more `agent:iteration-N` labels
   the same way.
3. ⬜ **Tickets**: run `scripts/setup_github_issues.py` (not yet run
   against this repo) to create the actual epic/task issues from
   `docs/epics.md` before triggering the harness on anything real.

## Local / manual usage (debugging only)

```bash
cd agents
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export CURSOR_API_KEY="cursor_..."
gh auth login   # gh CLI must be authenticated with repo write access

python prepare_iteration.py 123        # bumps agent:iteration-N, prints new N
python dev_agent.py 123 --iteration 1
python check_test_gate.py --base origin/main
python test_agent.py 123 --iteration 1
python review_agent.py 123 --iteration 1 --base origin/main
python finalize_iteration.py 123 1 --hard-gate true --test true --review true
```

## Known gaps (tracked, not yet resolved)

- No auto-looping across iterations yet (docs/adr/0009's "deferred"
  alternative) — a human/comment must trigger each retry on a
  `agent:needs-rework` issue; nothing retries it automatically.
- `check_test_gate.py`'s test-to-code mapping is a repo-wide heuristic
  (did *any* test change when *any* app code changed), not per-ticket
  traceability.
- GitHub's `Closes #N` PR-body keyword has not reliably auto-closed the
  issue on every merge done via `gh pr merge` in practice; worth
  double-checking, or closing the issue explicitly as a fallback in the
  auto-merge workflow step.
