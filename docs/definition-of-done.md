# Definition of Done

This is the single Definition of Done (DoD) for every epic and task issue
in this repository. It applies uniformly, whether the work is done by a
human or by the Dev/Test/Review agent harness (`agents/`,
`docs/adr/0008`, `docs/adr/0009`). An **epic** is Done only when every
task linked under it is Done.

A task/issue is **Done** — eligible for the `agent:ready-to-merge` label
and eventual merge — only when **all** of the following hold for the same
iteration:

## 1. Scope
- [ ] Implements exactly what the issue's acceptance criteria describe. No unrelated changes bundled in.
- [ ] Does not modify protected paths (`docs/`, `agents/`, `harness-demo/`, `.github/`, `.cursor/`) unless the issue is specifically about one of those.

## 2. Tests
- [ ] Automated tests (unit, and integration/E2E where applicable) are added or updated alongside any application code change, and committed in the same PR — not left for a follow-up.
- [ ] The number of test functions has not decreased relative to `main` (mechanically enforced by `agents/check_test_gate.py`).
- [ ] All tests pass: `pytest` for the backend, Playwright for E2E flows where relevant.

## 3. Independent verification
- [ ] The Test Agent's black-box tests pass. These are derived only from `docs/requirements.md` / `docs/journeys.md` / `docs/epics.md` and the issue itself — never from reading the implementation or the developer's own tests first (`docs/adr/0008`, `harness-demo/adr/0004`). For infra-only issues with no live HTTP surface yet, this step is marked PASS-by-N/A instead of skipped silently.

## 4. Review
- [ ] The Review Agent's five-perspective review passes with no HIGH-severity finding from any of: Security Analyst, Software Architect, Senior Developer, UX Architect, Test Engineer.

## 5. Traceability
- [ ] The change traces back to a stated requirement: Requirement -> Journey -> Epic -> Issue -> Code (`docs/adr/0006`, "no ticket, no code").

## 6. Delivery
- [ ] A pull request exists, linked to the issue (`Closes #N`), containing all commits for this iteration.
- [ ] The harness auto-merges the PR the moment all gates above pass in the same iteration (`docs/adr/0011`); merging is what closes the issue. If any gate fails, the PR stays open with `agent:needs-rework` and the harness auto-retries with that feedback until `MAX_ITERATIONS` (`docs/adr/0015`).

## How this is enforced

| DoD item | Enforced by |
|---|---|
| Tests exist, didn't shrink, pass | `agents/check_test_gate.py` (mechanical, cannot be talked around) |
| Independent functional correctness | `agents/test_agent.py` |
| Security / architecture / code quality / API design / test quality | `agents/review_agent.py` |
| No scope creep, protected paths untouched | `agents/dev_agent.py` prompt + Review Agent |
| Traceability | `docs/epics.md` / `docs/journeys.md` structure + issue body (`scripts/setup_github_issues.py`) |
| Final sign-off / label | `agents/github_ticket_utils.py: finalize_iteration()` |
| Auto-merge on pass | `.github/workflows/agent-harness.yml` ("Auto-merge PR" step, `docs/adr/0011`) |
| Auto-retry on fail | `.github/workflows/agent-finalize.yml` + queue picker (`docs/adr/0015`) |
| Parallel Test/Review | `.github/workflows/agent-test.yml` + `agent-review.yml` (`docs/adr/0016`) |

If any item fails, the issue gets `agent:needs-rework` instead of
`agent:ready-to-merge`, and the harness starts another iteration with
that feedback (`docs/adr/0015`), until `MAX_ITERATIONS`.
