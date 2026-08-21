# ADR-0030: Planning Agent — requirements → journeys → epics → tasks → issues

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

Until now the backlog (journeys.md, epics.md, and the GitHub issues) was
hand-authored, with `scripts/setup_github_issues.py` holding the epics/tasks as
an inline Python structure. To reuse the harness on a new project — "write only
requirements, get the whole backlog automatically" — the planning itself must be
automated, at scale (a project can be ~40 journeys → ~200 epics → ~1600 tasks;
cardinality is not fixed).

## Decision

Add `agents/planner_agent.py`: a MiniMax-driven Planning Agent (same engine as
Dev/Test/Review) that decomposes `docs/requirements.md` in staged, batched steps:

- **journeys**: requirements → atomic user journeys → `docs/journeys.md`
- **epics**: each journey → one or more epics (batched by journey group)
- **tasks**: each epic → atomic, single-PR tasks (one call per epic, resumable —
  progress saved to `docs/plan.json` after every epic)
- **render**: `plan.json` → `docs/epics.md` (traceable record)
- **issues**: `scripts/setup_github_issues.py` now loads `docs/plan.json` when
  present and creates the labels/milestones/epic+task issues from it

Run via the manual `agent-plan.yml` workflow (stage-by-stage or `all`). The
Dev/Test/Review harness then delivers the generated tickets unchanged.

## Consequences

- A new project needs only `docs/requirements.md`; the planner produces the
  entire journeys → epics → tasks → issues cascade, and the harness builds it —
  end to end from requirements to shipped code.
- Batching + per-epic resumability keeps generation within model output limits
  and lets a large plan be produced (and re-run) safely.
- `plan.json` is the machine artifact; `journeys.md`/`epics.md` are the
  human-readable traceable records. The inline EPICS in `setup_github_issues.py`
  remains as a fallback/example when no `plan.json` exists.
- Cardinality is model-driven, not fixed — the planner produces as many
  journeys/epics/tasks as the requirements imply.
