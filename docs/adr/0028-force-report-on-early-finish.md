# ADR-0028: Force the report tool when a Test/Review agent finishes early

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

ADR-0019 gave Test/Review agents a `submit_report` tool and forced it via
`tool_choice` on the last turn. But an agent that *finishes early* (stop_reason
`end_turn`) after printing its verdict as text — without calling the tool —
slipped through: `run_agent` returned raw text, the caller could not parse a
```json report, and recorded `UNKNOWN` → a false `fail`. On a ticket already at
`MAX_ITERATIONS`, that stuck it for good even though the review was clean (0
findings). Observed on #140: green CI + "No findings", yet `review-fail`.

## Decision

When the agent ends (non-tool-use) and a `report_tool` is configured but was not
called, `run_agent` now injects a "call the tool NOW" message and makes one more
turn with `tool_choice` forcing the report tool, capturing the structured report
— rather than returning unparseable text. This complements the existing forced
submit on the final turn, so a structured report is obtained on early finish too.

## Consequences

- Eliminates the `UNKNOWN`/false-fail class for Test/Review when the model
  reports in prose instead of via the tool — fewer needless rework cycles and
  stuck-at-cap tickets.
- One extra model call only in the (now rarer) early-finish-without-tool case.
- If the forced call itself fails, it falls back to the previous behavior.
