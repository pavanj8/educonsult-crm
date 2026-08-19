# ADR-0010: Formal, written Definition of Done for every epic and task

**Status**: Accepted
**Date**: 2026-08-19

## Context

[ADR-0006](0006-no-ticket-no-code-policy.md) established "no ticket, no
code," and [ADR-0009](0009-agent-harness-github-actions-execution.md)
built a hard, mechanical test gate plus independent Test/Review agent
sign-off. Those pieces existed as enforcement mechanisms, but there was no
single, explicit, written statement of what "done" means that a human or
an agent could check an issue against — the criteria were implicit,
scattered across ADRs and code (`agents/check_test_gate.py`,
`agents/github_ticket_utils.py`).

## Decision

Add `docs/definition-of-done.md` as the single, canonical Definition of
Done, covering: scope discipline, tests (written + committed + passing +
non-decreasing), independent Test Agent verification, Review Agent sign-off
(no HIGH-severity findings across all five perspectives), requirement
traceability, and PR-based delivery with human merge.

Make it visible everywhere a ticket lives, not just in `docs/`:

- `scripts/setup_github_issues.py` embeds the same checklist (`DOD_CHECKLIST`
  constant) directly into every epic and task issue body it creates, so
  it's visible on GitHub without following a link.
- `agents/dev_agent.py`'s prompt includes the full DoD text and instructs
  the agent it must satisfy every item before finishing.
- `agents/review_agent.py`'s prompt includes the full DoD text and
  instructs the Senior Developer / Test Engineer perspectives to check the
  diff against it explicitly, not just general code-quality instinct.
- `agents/check_test_gate.py` is documented as the mechanical enforcement
  of the DoD's "Tests" section specifically.

## Alternatives considered

- **Rely on ADR-0006/0009 alone** — rejected: those explain *why* the
  harness is designed the way it is, not a checkable, issue-by-issue
  checklist someone (human or agent) can tick off. A DoD needs to be a
  concrete, standalone artifact, not something reconstructed by reading
  multiple ADRs.
- **Only add it to `docs/`, not embed in issue bodies** — rejected: the
  whole point of ADR-0009's GitHub-native execution model is that the
  issue is the ticket; the DoD needs to be visible there directly, not
  require following a link into the repo.

## Consequences

- `docs/definition-of-done.md` and `scripts/setup_github_issues.py`'s
  `DOD_CHECKLIST` constant must be kept in sync by hand — there's no
  single-source-of-truth templating between the two yet. A future
  improvement could generate one from the other.
- Existing epics/tasks were not yet created on GitHub as of this ADR
  (`scripts/setup_github_issues.py` hasn't been run against the real repo
  — see ADR-0009's consequences), so this DoD lands in every issue body
  from the very first batch, rather than needing a backfill.
- Any future change to what "done" means (e.g. adding a security-scan
  requirement, or a coverage percentage threshold) should update
  `docs/definition-of-done.md` first, then propagate to
  `scripts/setup_github_issues.py` and the two agent prompts — per the
  `.cursor/rules/adr.mdc` process, that change itself should get a new
  ADR superseding this one if it's a material shift, or a note added here
  if it's a minor addition.
