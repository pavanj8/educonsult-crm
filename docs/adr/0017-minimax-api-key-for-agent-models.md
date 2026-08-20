# ADR-0017: MiniMax API key for agent harness model inference

**Status**: Superseded by [ADR-0018](0018-revert-minimax-sdk-model-ids.md)
**Date**: 2026-08-20

## Context

The agent harness runs Dev/Test/Review on GitHub Actions via the Cursor
SDK local runtime (`local=LocalAgentOptions(cwd=...)`). Model inference
was previously billed through Cursor's default models (`composer-2.5` for
Dev, `grok-4.6` for Test/Review — see ADR-0013/0014).

The project owner added a MiniMax Token Plan key as the GitHub Actions
secret `MINIMAX_API_KEY` and wants the harness to use it for LLM calls
instead of relying solely on Cursor-included model quota.

MiniMax exposes an OpenAI-compatible HTTP API. Cursor (IDE and local
agent runtime) routes custom model IDs through `OPENAI_API_KEY` +
`OPENAI_BASE_URL` when those env vars are set — the same mechanism
documented for Cursor + MiniMax-M3 in MiniMax's own setup guide.

## Decision

1. Keep `CURSOR_API_KEY` — still required for Cursor SDK authentication
   and local agent orchestration (tool use, file edits, shell).
2. Pass `MINIMAX_API_KEY` from GitHub Actions secrets into all three
   agent workflows.
3. Before each agent run, map MiniMax credentials into OpenAI-compatible
   env vars via `agents/llm_env.py`:
   - `OPENAI_API_KEY` ← `MINIMAX_API_KEY`
   - `OPENAI_BASE_URL` ← `MINIMAX_BASE_URL` (default
     `https://api.minimax.io/v1`; use `https://api.minimaxi.com/v1` in
     China if needed)
4. Switch workflow model IDs to MiniMax, preserving ADR-0013's asymmetric
   tiering intent:
   - Dev Agent: `MiniMax-M2.5-highspeed` (fast/cheap generation)
   - Test + Review Agents: `MiniMax-M3` (stronger verification)
5. Pass `api_key=` explicitly to `Agent.create()` from `CURSOR_API_KEY`.

## Alternatives considered

- **Replace `CURSOR_API_KEY` with `MINIMAX_API_KEY` entirely** — rejected.
  The Cursor SDK refuses to start without a Cursor API key; MiniMax alone
  does not provide the local agent runtime.
- **Keep Cursor default models and ignore MiniMax** — rejected; owner
  explicitly provisioned the key for harness use.
- **Use `MiniMax-M3` for all three roles** — rejected for now; Dev runs
  many iterations across a large backlog and M2.5-highspeed is the
  documented cost/speed tier. Revisit if verification quality on M2.5
  proves insufficient.

## Consequences

- LLM inference cost shifts to the MiniMax Token Plan; Cursor API key
  usage is limited to SDK/agent-runtime overhead.
- MiniMax model local executability on GitHub-hosted runners is not yet
  empirically proven the way `composer-2.5` / `grok-4.6` were in
  ADR-0014. If a MiniMax ID fails silently on Actions, the harness will
  still fail closed (`agent:needs-rework`) with the ADR-0014 diagnostic.
- China-region deployments must set `MINIMAX_BASE_URL` to the `.com`
  endpoint in workflow env.
- ADR-0013/0014 model IDs are superseded by this ADR's MiniMax IDs.
