# ADR-0032: Epics are title tags, not GitHub issues

**Status**: Accepted — implemented
**Date**: 2026-08-22

## Context

`scripts/setup_github_issues.py` created one GitHub issue per epic (labelled
`epic`, titled `[EPIC] E28: ...`) in addition to one issue per task. The
harness never picks epic issues — `queue_picker` filters to `task,phase:mvp`
— and nothing closes an epic issue automatically: it stays open until a human
manually ticks its checklist. In practice this meant that after the entire MVP
backlog of *tasks* was delivered and closed, 23 epic issues sat open forever,
polluting `gh issue list` and repeatedly prompting "why are there still
`phase:mvp` issues open?".

Every task already carries its epic in the title as an `[E<n>]` prefix
(e.g. `[E28] Backend: notification model`). That tag — not a "Part of #N" body
link to an epic issue — is what `github_ticket_utils.epic_sibling_status()`
needs to tell the Dev Agent which sibling tickets already merged. The epic
*issue* was carrying no weight the title tag didn't already carry.

## Decision

1. **Stop creating epic issues.** `setup_github_issues.py` creates only task
   issues. Each task keeps its `[E<n>]` title prefix and records its epic in
   the body (`Part of epic E28: <title>` + traceability), with no link to a
   (now non-existent) epic issue. The per-epic checklist update step is gone.
2. **Group siblings by the title tag.** `epic_sibling_status()` matches
   siblings on the `[E<n>]` title prefix via `gh issue list` instead of parsing
   `Part of #N` from bodies. This works for the legacy tasks too, since they
   already carry the same tag.
3. **`docs/epics.md` is the human-readable epic record.** The epic → journey →
   requirement traceability lives in that generated document; GitHub issues
   track only the atomic, closeable units of work (tasks).

## Consequences

- `gh issue list` reflects real outstanding work: once every task in an epic is
  closed, the epic simply has no open issues — there is nothing to manually
  close and nothing left dangling.
- The `epic` label remains defined (harmless) but is no longer applied to any
  issue; existing epic issues from earlier runs are closed out by hand once.
- No behavioural change for the Dev/Test/Review pipeline: the picker already
  ignored epic issues, and sibling awareness is preserved via the title tag.
