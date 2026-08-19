# ADR-0006: Cursor SDK as the automation substrate for all agents

**Status**: Accepted
**Date**: 2026-08-19

## Context

Needed a way to programmatically drive an LLM agent that can read a repo,
write/edit code, and run shell commands (pytest, uvicorn), without
building a bespoke tool-calling harness from scratch, and reusing the same
model/tooling access the user already has through Cursor.

## Decision

Use the Cursor SDK (`cursor-sdk`, Python) for all three agents, in `local`
mode (`LocalAgentOptions(cwd=...)`), model `composer-2.5`, via the
`Agent.create(...)` + `agent.send(...)` + `run.messages()` / `run.wait()`
pattern (durable session, streamed output, independent final verification
by the calling script rather than trusting the agent's self-report alone).

## Alternatives considered

- **Bespoke LLM tool-calling loop** (direct model API + hand-rolled
  file/shell tools) — rejected: reimplements what the SDK already
  provides, for no added control, and loses Cursor's existing
  editor/tooling integration.
- **Cloud agent mode** at this stage — deferred, not rejected outright; see
  [ADR-0008](0008-github-actions-execution.md), which revisits local vs
  cloud runtime specifically for the GitHub-hosted execution move.

## Consequences

- Requires Python 3.10+ (the SDK's minimum), which forced installing
  Python 3.12 via Homebrew and a dedicated venv under `harness-demo/agents/`
  separate from the demo app's own venv.
- Requires a `CURSOR_API_KEY` in the environment wherever an agent script
  runs — a credential that must be provisioned securely for every runtime
  this moves to (laptop env var today; a GitHub Actions secret once
  ADR-0008 is implemented).
- Each script independently re-verifies outcomes (Dev Agent re-runs pytest
  itself; Test Agent asserts over real HTTP) rather than trusting the
  agent's own narrated success — this is a deliberate hedge against LLM
  self-report being wrong.
