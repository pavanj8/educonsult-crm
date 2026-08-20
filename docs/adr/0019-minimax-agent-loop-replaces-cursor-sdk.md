# ADR-0019: Replace the Cursor SDK engine with a direct-MiniMax agent loop

**Status**: Accepted — implemented
**Date**: 2026-08-20
**Supersedes**: [ADR-0018](0018-revert-minimax-sdk-model-ids.md) (and by
extension the Cursor-native model IDs of ADR-0013/0014 for harness inference)

## Context

[ADR-0017](0017-minimax-api-key-for-agent-models.md) tried to route model
inference through MiniMax while keeping the Cursor SDK (`cursor_sdk`) as the
agent engine, by pointing `OPENAI_API_KEY`/`OPENAI_BASE_URL` at MiniMax and
setting MiniMax model IDs. [ADR-0018](0018-revert-minimax-sdk-model-ids.md)
proved that fails: the SDK validates model IDs against Cursor's own catalog at
`Agent.create()` and rejects custom provider IDs
(`invalid_argument: Cannot use this model: MiniMax-M2.5-highspeed`). The
OpenAI-base-URL override is an IDE feature, not honored by the headless local
runtime. ADR-0018 concluded that actually using MiniMax "requires a different
architecture (direct MiniMax HTTP API agent loop), not passing MiniMax model
IDs through `Agent.create()`."

The project owner wants MiniMax to be the real inference path, not Cursor. This
ADR builds that different architecture.

## Decision

1. **New engine.** Add `agents/minimax_agent.py`: a self-contained
   tool-calling loop over MiniMax's OpenAI-compatible `chat/completions` API
   (via the `openai` client pointed at `MINIMAX_BASE_URL`). It exposes the same
   capabilities the Cursor local runtime gave the agents — `read_file`,
   `write_file`, `list_dir`, `run_command` — scoped to the repo working
   directory, with a max-turns rail and per-tool output truncation.
2. **Rewire all three agents.** `dev_agent.py`, `test_agent.py`,
   `review_agent.py` call `minimax_agent.run_agent(...)` instead of
   `cursor_sdk.Agent.create(...)`. Their prompts, report parsing, GitHub
   labelling, and (for Test) the live-server black-box flow are unchanged.
3. **Runs on GitHub-hosted runners, same as before.** The loop executes
   in-process inside the Actions job (`runs-on: ubuntu-latest`); the Test Agent
   still boots the backend on `127.0.0.1` *inside that runner*. No personal
   machine is involved. "Local" only ever meant "in the runner," never the
   owner's Mac.
4. **Keep `CURSOR_API_KEY` dormant.** The secret and workflow env var stay in
   place but no agent consumes them (`llm_env.cursor_api_key()` is retained,
   unused), mirroring how `MINIMAX_API_KEY` was kept dormant under ADR-0018.
   `cursor-sdk` stays in `requirements.txt` but is no longer imported.
5. **Model tiering preserved (ADR-0013).** Dev uses the cheap tier
   (`MiniMax-M2.5-highspeed`), Test + Review use the stronger tier
   (`MiniMax-M3`). All overridable via `*_AGENT_MODEL` workflow env.

## Alternatives considered

- **Keep Cursor and just accept its bill** — rejected; owner provisioned the
  MiniMax Token Plan specifically to be the inference path.
- **Adopt a heavyweight agent framework** (LangChain/OpenAI Agents SDK) —
  rejected for now; the tool surface is small (four tools) and a thin loop
  keeps the failure modes legible for the harness's fail-closed reporting.
- **Register MiniMax as a custom Cursor model** — rejected in ADR-0018
  (IDE-only, unavailable to headless runners).

## Consequences

- LLM inference cost moves to the MiniMax Token Plan; Cursor usage drops to
  zero (key retained only for a possible future rollback).
- The harness no longer depends on Cursor's model catalog, so ADR-0014's
  "listed-but-not-locally-executable" failure mode goes away. A bad model ID
  now surfaces as a MiniMax API error with an actionable diagnostic.
- **Model IDs are unverified against the live MiniMax catalog.** As with
  ADR-0014's local probe, the first real Dev run must confirm
  `MiniMax-M2.5-highspeed` / `MiniMax-M3` are valid for this account; adjust
  the `*_AGENT_MODEL` env if MiniMax names them differently. Failures fail
  closed (`agent:needs-rework`) with the diagnostic from `minimax_agent`.
- MiniMax tool-calling fidelity now determines agent quality; if it under-uses
  tools, revisit the loop (system prompt, temperature, or a stronger tier).
- China-region deployments set `MINIMAX_BASE_URL` to the `.com` endpoint.
- `agents/sdk_run.py` (Cursor-specific run diagnostics) is left in place but
  unreferenced; a future cleanup ADR may remove it.
