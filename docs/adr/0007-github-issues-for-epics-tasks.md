# ADR-0007: GitHub Issues as system of record for epics and tasks

**Status**: Accepted
**Date**: 2026-08-19

## Context

Having written `docs/requirements.md`, `docs/journeys.md`, and
`docs/epics.md`, the team needed a trackable, assignable unit-of-work
system consistent with ADR-0006's traceability chain, without introducing
a separate project-management tool.

## Decision

Use GitHub Issues on `pavanj8/educonsult-crm` as the system of record:

- Epics become GitHub issues, labeled and grouped by milestone.
- Tasks become smaller GitHub issues linked to their parent epic issue.
- `scripts/setup_github_issues.py` is the single source that creates
  labels, milestones, epics, and tasks from the `EPICS` data structure, so
  the GitHub state is regenerable/consistent with the planning docs rather
  than hand-maintained.

## Alternatives considered

- **External PM tool** (Jira/Linear/etc.) — rejected to avoid another
  system of record diverging from the code repository; GitHub Issues keep
  planning artifacts next to the code and its PRs/commits.
- **Docs-only tracking** (epics.md as the only source, no issues) —
  rejected: doesn't give assignable, closeable units of work or
  integrate with PR linking.

## Consequences

- `scripts/setup_github_issues.py` must be re-run (or diffed) whenever
  `docs/epics.md` changes, or GitHub state and docs drift apart.
- This same "issue = unit of work" pattern is echoed in the agent harness
  project's own move to GitHub-Issues-as-tickets (see
  `harness-demo/adr/0008-github-actions-execution.md`), for consistency
  across both projects.
