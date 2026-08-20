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

One Dev run implements a ticket, commits, and opens/updates a PR, then
dispatches Test and Review as **separate workflows** on that ticket's
branch (`docs/adr/0016`). Test(A) and Review(A) can therefore overlap
each other and overlap Dev(B). Finalize joins their labels, then
auto-merges if green (`docs/adr/0011`) or auto-retries Dev with the
Test/Review comments (`docs/adr/0015`). Dev stays serialized
(overlapping-file risk); Test/Review do not sit idle waiting for it.

## Processing a large backlog unattended

Don't add `agent:ready-for-dev` to many issues in a tight loop — the
workflow's `concurrency:` group only holds "1 running + 1 queued" per
group (not an unbounded FIFO), so a burst of triggers gets almost all of
them cancelled (see `docs/adr/0012` for what happened when this was
tried). Instead, `.github/workflows/agent-harness-queue-picker.yml` runs
on a 5-minute cron, and whenever the harness is idle, triggers exactly
one untouched `task` + `phase:mvp` issue at a time (or a
`agent:needs-rework` issue still under `MAX_ITERATIONS` — those are
preferred, so feedback is addressed before starting a new ticket). To
queue a batch: leave the issues with no `agent:*` label and the picker
finds them on its own; failed tickets retry themselves.

## Required repo setup (one-time)

1. ✅ **Secret**: `ANTHROPIC_AUTH_TOKEN` — the harness's inference engine. All
   three agents run on MiniMax via its Anthropic-compatible Messages API
   (`agents/minimax_agent.py`, docs/adr/0019). Optional
   `ANTHROPIC_BASE_URL` (default `https://api.minimax.io/anthropic`; use the
   `.com` endpoint in China).
2. ➖ **Secret**: `CURSOR_API_KEY` — kept provisioned but **dormant**. The
   Cursor SDK engine was replaced by MiniMax (docs/adr/0019); no agent
   consumes this key. Left in place for a possible rollback. NOTE: the
   `cursor-sdk` *package* is deliberately uninstalled — its presence
   hijacks the `openai` client onto the Cursor gateway (docs/adr/0019). The
   env var is harmless; the package is not.
3. ⬜ **Secret**: `GH_PAT` — a token that can push `.github/workflows/*`
   (`workflow` scope). `GITHUB_TOKEN` cannot; issue #61 failed on that.
   Needed for any ticket that adds or edits GitHub Actions workflows.
2. ✅ **Labels**: `agent:ready-for-dev`, `agent:iteration-1` through
   `agent:iteration-10`,    `agent:{dev,test,review,gate}-{pass,fail}`,
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
export ANTHROPIC_AUTH_TOKEN="..."                            # MiniMax token
# export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"  # optional
gh auth login   # gh CLI must be authenticated with repo write access

python prepare_iteration.py 123        # bumps agent:iteration-N, prints new N
python dev_agent.py 123 --iteration 1
python check_test_gate.py --base origin/main
python test_agent.py 123 --iteration 1
python review_agent.py 123 --iteration 1 --base origin/main
python try_finalize.py 123 1           # no-ops until gate+test+review labels exist
```

## Known gaps (tracked, not yet resolved)

- `check_test_gate.py`'s test-to-code mapping is a repo-wide heuristic
  (did *any* test change when *any* app code changed), not per-ticket
  traceability.
- GitHub's `Closes #N` PR-body keyword has not reliably auto-closed the
  issue on every merge done via `gh pr merge` in practice; worth
  double-checking, or closing the issue explicitly as a fallback in the
  auto-merge workflow step.
- MiniMax model IDs (`MiniMax-M2.5-highspeed` Dev, `MiniMax-M3`
  Test/Review) are not yet verified against the live MiniMax catalog for
  this account (docs/adr/0019). The first real Dev run confirms them; a
  bad ID fails closed (`agent:needs-rework`) with a diagnostic from
  `minimax_agent.py`. Override via the `*_AGENT_MODEL` workflow env.
- `agents/sdk_run.py` (Cursor-specific run diagnostics) is now unused;
  left in place pending a cleanup ADR.
