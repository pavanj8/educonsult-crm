# ADR-0008: Move agent execution to GitHub (Actions runners, GitHub Issues as tickets, hard test gate)

**Status**: Superseded by [CRM ADR-0009](../../docs/adr/0009-agent-harness-github-actions-execution.md)
**Date**: 2026-08-19

## Context

All three agents were only ever run from the user's own Mac
(`CURSOR_API_KEY` exported in a local shell, scripts invoked manually).
The user wants the harness to work "even if I close my laptop" — i.e. not
depend on any machine they personally control being on — and separately
wants a **hard, deterministic** requirement (not just an LLM judgment call)
that every ticket ships with committed unit tests before it can be
considered fixed.

## Decision (as agreed, at the time this ADR was written)

1. **Runtime**: run the agents on GitHub-hosted Actions runners (`local`
   Cursor SDK mode, with `cwd` = the Actions checkout) rather than Cursor
   Cloud Agents — the runner IS the "local" machine for SDK purposes, and
   GitHub-hosted runners exist independently of any personal laptop.
2. **Ticket source**: migrate tickets from markdown files in the repo to
   GitHub Issues, so the flow is fully GitHub-native.
3. **Trigger**: a label (e.g. `agent:ready-for-dev`) or slash-comment
   (e.g. `/dev-agent`) on the issue kicks off the workflow; a manual
   `workflow_dispatch` remains as a fallback.
4. **Test gate**: in addition to the Review Agent's judgment-based "Test
   Engineer" perspective, add a deterministic CI check that fails the
   workflow if application code changed without a corresponding test file
   change, and requires pytest to pass with no drop in test count/coverage.

## Why this ADR is superseded rather than deleted

This decision was made while `harness-demo/` was still being treated as a
project separate from the real CRM. Immediately afterward, the decision in
[ADR-0009 of this log](0009-graduate-to-real-crm.md) retired that
separation: the harness now targets the real EduConsult CRM repository
directly, not the toy Student Registration app. The four sub-decisions
above still stand on their merits — they're just recorded canonically as
[docs/adr/0009](../../docs/adr/0009-agent-harness-github-actions-execution.md)
in the CRM's own ADR log instead of here, since there is now one project,
not two.

## Consequences

- This entry is kept for history (it explains *when* and *why* these four
  choices were made) but should not be treated as the active spec —
  follow the CRM-log version for anything forward-looking.
