# ADR-0031: Config decoupling, provider-agnostic LLM, and local execution

**Status**: Accepted — implemented
**Date**: 2026-08-21

## Context

The harness had grown into a reusable Dev/Test/Review/Planner framework, but
three things were still hard-wired to *this* project and to *one* vendor, which
blocked copying it to a new repo:

1. **Project specifics** — backend/frontend dirs, check commands, the target
   repo, protected paths, and the project name — were spread across
   `agents/target_app.py`, `scripts/check.sh`, `scripts/setup_github_issues.py`,
   and the agent prompts.
2. **LLM vendor** — the engine, `llm_env.py`, and every workflow assumed MiniMax
   via its Anthropic-compatible endpoint (`minimax_client`, hardcoded
   `ANTHROPIC_BASE_URL`, `MiniMax-M3` model literals).
3. **Execution location** — agents only ran on GitHub Actions runners; there was
   no way to run a ticket on your own laptop.

## Decision

**One config file.** `harness.config.json` at the repo root is the single source
of project + provider + execution settings, read by `agents/harness_config.py`
(every value has a built-in default, so a missing file still runs). `check.sh`
sources it via `python agents/harness_config.py --shell`, so bash and Python
agree. To retarget the harness you edit only this JSON (and write
`docs/requirements.md`).

**Provider-agnostic LLM.** `llm.provider` selects a provider; each provider
declares its API shape — `"anthropic"` (Messages API: MiniMax's compatible
endpoint, Anthropic/Claude, or any compatible gateway) or `"openai"` (Chat
Completions: OpenAI and OpenAI-compatible gateways) — plus `base_url`, `auth_env`,
and `auth_scheme`. `llm_env.client_and_api()` builds the right client;
`minimax_agent.run_agent` dispatches to a matching tool-loop (`_run_anthropic` /
`_run_openai`). Per-tier `models` (dev/verify/planner) are config, not literals.
Legacy names (`minimax_client`, `configure_minimax_env`, `ANTHROPIC_BASE_URL`)
are kept as back-compat shims so the existing MiniMax setup is unchanged.

**Local execution.** `execution.mode` is `"github"` (default) or `"local"`.
`agents/run_local.py <issue>` runs the same Dev → `check.sh` → (optional)
Test/Review flow on your own machine — no Actions minutes — using whichever
provider is configured. It leaves work on a local branch unless `--commit`/`--push`.

## Consequences

- Reusing the harness on a new project = copy the files, edit
  `harness.config.json`, provide the provider's key, write `requirements.md`,
  run the Planner. No harness code changes.
- Not locked to MiniMax: switch to Claude or OpenAI (or any compatible gateway)
  by config alone; `openai` is now a declared dependency alongside `anthropic`.
- The current EduConsult/MiniMax/GitHub defaults are preserved, so the (live)
  harness behaves exactly as before this change.
- Workflows pass every provider key (`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`); unset secrets resolve to empty and are simply unused.
