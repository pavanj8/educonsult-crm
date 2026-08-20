# ADR-0018: Revert MiniMax model IDs — not valid on Cursor SDK local runtime

**Status**: Superseded by [ADR-0019](0019-minimax-agent-loop-replaces-cursor-sdk.md)
**Date**: 2026-08-20

## Context

[ADR-0017](0017-minimax-api-key-for-agent-models.md) wired `MINIMAX_API_KEY`
into GitHub Actions and switched Dev/Test/Review model IDs to
`MiniMax-M2.5-highspeed` / `MiniMax-M3`, assuming the Cursor local agent
runtime would route inference through OpenAI-compatible env vars the same
way the Cursor IDE does when "Override OpenAI Base URL" is enabled.

Issue #149's first Dev run on that config failed immediately:

```
invalid_argument: Cannot use this model: MiniMax-M2.5-highspeed.
Available models: composer-2.5, grok-4.6, ...
```

No code was written; the workflow then failed creating a PR ("No commits
between main and agent/issue-149").

MiniMax's Cursor IDE integration and the programmatic `cursor_sdk` local
runtime are not the same surface. The SDK validates model IDs against
Cursor's own list before starting an agent — custom OpenAI-provider model
names are rejected at startup, analogous to the ADR-0014 finding for
listed-but-unexecutable Cursor-native IDs.

## Decision

1. Revert workflow model IDs to the last known-good local-executable pair
   from ADR-0014:
   - Dev: `composer-2.5`
   - Test + Review: `grok-4.6`
2. Remove `MINIMAX_*` env vars from agent workflows for now (secret may
   remain in repo settings for a future non-SDK integration).
3. Keep `agents/llm_env.py` in the repo but unused until a separate
   MiniMax integration path exists.
4. Re-dispatch Dev for issue #149 after the revert lands on `main`.

Using MiniMax in this harness in the future requires a different
architecture (direct MiniMax HTTP API agent loop), not passing MiniMax
model IDs through `Agent.create()`.

## Alternatives considered

- **Keep MiniMax IDs and only set OPENAI env vars** — rejected; #149
  proved the SDK rejects the model ID regardless.
- **Register MiniMax-M3 as a custom model in Cursor account settings** —
  not available to headless GitHub Actions runners; IDE-only configuration.
- **Move Dev to cloud agents with MiniMax** — rejected for now; Test Agent
  still requires localhost (ADR-0014), and cloud adds clone/auth complexity.

## Consequences

- LLM inference cost returns to the Cursor API quota tied to
  `CURSOR_API_KEY`.
- ADR-0017 is superseded for model selection; asymmetric tiering intent
  from ADR-0013/0014 is restored.
- `MINIMAX_API_KEY` in GitHub secrets is inert until a future ADR defines
  a non-SDK integration.
