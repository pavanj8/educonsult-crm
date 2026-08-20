# ADR-0021: Cut agent latency with a context pack + efficiency prompts

**Status**: Accepted — implemented
**Date**: 2026-08-20

## Context

Per-ticket wall-clock was dominated by the sequential agent tool-loop, not
infra. Measured on real MiniMax-M3 runs:

- **Dev**: ~10.5 min, **75 tool turns** (63 `run_command`, ~0 `write_file`) —
  most spent grepping/cat-ing to *understand the codebase*, plus writing files
  via shell heredocs (a source of `SyntaxError`s) and re-running the whole test
  suite repeatedly.
- **Test**: ~4 min, **79 tool turns** (66 `run_command`) — discovering
  endpoints by trial and re-running the full qa script.
- **Review**: ~40 sec — already fast; left unchanged.

Each turn is a full model round-trip, so turn count ≈ latency. Dependency
installs were seconds, so caching was deprioritized.

## Decision

Reduce turns by front-loading context and steering tool use (no model change
here — M2.7-highspeed is a separate future trial):

1. **Dev context pack.** `dev_agent.build_repo_map()` injects a flat listing of
   every existing `backend/app`, `backend/tests`, and `frontend/src` file into
   the prompt (bounded ~250/area). The agent no longer runs `find`/`ls`/`grep`
   to learn structure.
2. **Dev efficiency prompt.** Explicit guidance: don't re-explore; `read_file`
   only what you'll edit; use the `write_file` tool (not shell heredocs); run
   `scripts/check.sh` once at the end, not after every edit.
3. **Test contract load.** The Test agent first fetches `{base_url}/openapi.json`
   (FastAPI's full schema) — a black-box artifact, so independence is preserved
   — instead of discovering endpoints by trial. Plus the same "write once, run
   once, re-run only the failing case, submit promptly" guidance.

Review is unchanged (already ~40 sec).

## Consequences

- Expected Dev ~10.5 min → ~4–5 min and Test ~4 min → ~2–3 min by removing the
  exploration turns; also fewer heredoc-induced syntax errors (fewer retries).
- The repo map is regenerated per run from the working tree, so it's always
  current; it's bounded so it can't dominate the context window.
- Not addressed here (future): trial `MiniMax-M2.7-highspeed` for Dev, pip/venv
  caching, and purging the committed `.venv` from git history (2k+ dead blobs
  slow every full-depth checkout).
