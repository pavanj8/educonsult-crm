# ADR-0024: Surgical edit tool + defer test tickets in the picker

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

Analysis of a real Dev run (#171) surfaced two big per-ticket inefficiencies:

1. **No surgical edit tool.** The engine only exposed `write_file`, so to fix
   two failing functions the agent **regenerated an entire 1,139-line file from
   scratch** — it literally said "I only have write_file for edits; regenerate
   from scratch." On M3 that is huge token/time waste and a correctness risk.
2. **Test tickets picked before their implementation.** #171 ("Tests: …") was
   dispatched while #169 (the endpoint under test) was still unmerged. The agent
   spent a large fraction of its turns discovering that dependency (`gh issue
   view` on siblings, diffing the unmerged branch) and agonizing over scope.
   Issues only declare epic membership (`Part of #25`), not explicit deps.

## Decision

1. **Add a `str_replace` tool** to `minimax_agent.py`: replace an exact, unique
   block of text in a file (like an IDE edit). Fails if the target is missing or
   non-unique, so it can't silently corrupt a file. The Dev prompt now says:
   new files → `write_file`; edits → `str_replace`; never rewrite a whole large
   file for a few lines; never write via shell heredocs.
2. **Order the queue picker** so, among eligible issues: needs-rework first,
   then **non-test before test**, then by number. A `Tests:`-titled ticket
   almost always depends on its epic's implementation tickets, so deferring it
   until non-test work drains avoids the wasted dependency-discovery churn. No
   per-issue dependency markers required.

## Consequences

- Edits become cheap and reliable; expect a large drop in turns/tokens on any
  ticket that iterates on an existing file (most of them).
- Test tickets run after their implementation siblings, so the Dev (and Test)
  agents stop burning turns on code that isn't merged yet.
- The ordering is a heuristic on the title; an explicit `Depends on #N` /
  `Blocked by #N` convention (skip until closed) is the natural future
  generalization if finer control is needed.
