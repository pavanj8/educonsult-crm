# Reusing this agent harness as a template for a new project

This repo is two things layered together:

1. **The autonomous Dev/Test/Review agent harness** (reusable infrastructure).
2. **The EduConsult CRM product** it happens to be building (project-specific).

To start a new project, copy the harness (layer 1) and replace the product
(layer 2). **Everything project-specific lives in one file — `harness.config.json`
(ADR-0031).** You edit that JSON and write `docs/requirements.md`; the harness
code stays generic.

## The one file you edit: `harness.config.json`

```jsonc
{
  "project":  { "name": "My Product", "repo": "you/my-repo" },
  "backend":  { "dir": "backend", "app_module": "app.main:app", "health_path": "/health",
                "lint": "ruff check .", "test": "python -m pytest -q" },
  "frontend": { "dir": "frontend", "lint": "npm run lint", "build": "npm run build" },
  "execution": { "mode": "github" },          // "github" (Actions) or "local" (your laptop)
  "llm": {
    "provider": "minimax",                     // pick any provider below
    "providers": {
      "minimax":   { "api": "anthropic", "base_url": "https://api.minimax.io/anthropic", "auth_env": "ANTHROPIC_AUTH_TOKEN", "auth_scheme": "bearer" },
      "anthropic": { "api": "anthropic", "base_url": "https://api.anthropic.com",         "auth_env": "ANTHROPIC_API_KEY",    "auth_scheme": "x-api-key" },
      "openai":    { "api": "openai",    "base_url": "https://api.openai.com/v1",          "auth_env": "OPENAI_API_KEY" }
    }
  },
  "models": { "dev": "MiniMax-M3", "verify": "MiniMax-M3", "planner": "MiniMax-M3" },
  "protected_paths": ["docs/", "agents/", ".github/", ".cursor/", "scripts/"]
}
```

`agents/harness_config.py` loads it (with built-in defaults, so a missing file
still runs); `check.sh` reads it via `python agents/harness_config.py --shell`.

**Swap the LLM by config alone** — set `llm.provider` + `models` and provide that
provider's key. Anthropic-shape providers (MiniMax, Claude, compatible gateways)
and OpenAI-shape providers (OpenAI + compatible) both work; the engine picks the
matching tool-loop.

**Run on your laptop** instead of Actions: set `execution.mode` to `local` (or
just run it) and use `python agents/run_local.py <issue> [--with-verify] [--commit]`.

## Copy these — the reusable harness

| Path | What it is |
|---|---|
| `harness.config.json` | The single project + provider + execution config (edit this). |
| `agents/` | Engine + agents. `harness_config.py` (config loader), `minimax_agent.py` (provider-agnostic tool loop — Anthropic *and* OpenAI shapes), `dev_agent.py` / `test_agent.py` / `review_agent.py`, `planner_agent.py`, `run_local.py` (laptop runner), `llm_env.py`, `github_ticket_utils.py`, `target_app.py`, plus `check_test_gate.py`, `prepare_iteration.py`, `require_dev_completed.py`, `finalize_iteration.py`, `try_finalize.py`. `requirements.txt` = `anthropic` + `openai`. |
| `.github/workflows/agent-harness.yml` | Dev stage (build gate, sibling context, dispatch Test/Review). |
| `.github/workflows/agent-test.yml`, `agent-review.yml`, `agent-finalize.yml` | Test / Review / finalize (CI-gated auto-merge, event-driven picker kick). |
| `.github/workflows/agent-harness-queue-picker.yml` | Paces + orders the backlog (needs-rework → non-test → test → number). |
| `.github/workflows/ci-feedback-loop.yml` | Turns a red CI run into `needs-rework` feedback. |
| `.github/workflows/ci-backend.yml`, `ci-frontend.yml` | CI, wired through `scripts/check.sh`. Adjust to your stack. |
| `scripts/check.sh` | Single source of truth for "green" (backend ruff+pytest / frontend lint+build). Both CI and the Dev agent run it. |
| `docs/adr/0008`–`0025` + `docs/definition-of-done.md` | The harness's own design decisions + the Definition of Done the agents must satisfy. |

## Replace these — project-specific

| Path | Replace with |
|---|---|
| `backend/`, `frontend/` | Your app (or empty scaffolds). Point `harness.config.json > backend/frontend` at your dirs + lint/test/build commands. Defaults expect `backend/app/main.py` (FastAPI) + `backend/requirements.txt` and, optionally, `frontend/package.json`. |
| `docs/requirements.md`, `docs/journeys.md`, `docs/epics.md` | Your product's requirements → journeys → epics → task issues. |
| `docs/adr/0001`–`0007` | Your product's architecture ADRs (these are EduConsult's). |
| `README.md`, `infra/` | Your product overview + local infra. |

## One-time setup for a new repo

1. **Secrets** (Settings → Secrets and variables → Actions):
   - Your provider's key, in the env var its config names: `ANTHROPIC_AUTH_TOKEN`
     (MiniMax), `ANTHROPIC_API_KEY` (Claude), or `OPENAI_API_KEY` (OpenAI). The
     workflows pass all three; unset ones are ignored. `base_url` comes from
     `harness.config.json`, not the workflow.
   - `GH_PAT` — a fine-grained PAT with **Contents: write + Pull requests: write**
     (add Workflows: write if it pushes workflow files), so the harness pushes and
     authors PRs as a real user (avoids the first-time-contributor CI approval
     gate). If this PAT lacks Pull-requests write, Dev pushes branches but no PR is
     created — see ADR-0026/0031.
2. **Labels**: `task`, `phase:mvp`, `agent:ready-for-dev`, `agent:iteration-1..N`,
   `agent:{dev,test,review,gate}-{pass,fail}`, `agent:ready-to-merge`,
   `agent:needs-rework`.
3. **Repo settings**: allow merge commits; enable "delete branch on merge". On a
   public repo, Actions are free/unlimited; on a private repo you need a paid plan
   or the free-minute budget (the harness enforces the CI gate itself since branch
   protection isn't available on the free tier — see ADR-0020/0023).
4. **Models + provider**: set in `harness.config.json` (`models.dev/verify/planner`
   and `llm.provider`), not in workflow env. Per-run overrides still exist
   (`DEV_AGENT_MODEL`, `HARNESS_LLM_PROVIDER`, `LLM_BASE_URL`) but are optional.
5. **Seed issues**: write `docs/requirements.md` and run the Planning Agent
   (`agent-plan.yml`, ADR-0030) to generate journeys → epics → task issues; or
   seed manually. Label tasks `task,phase:mvp` and the queue picker drains them.

## How it runs (once seeded)

Queue picker → Dev (sync main, context pack, `check.sh` build gate) → Test +
Review in parallel (structured `submit_report`) → finalize (waits for CI green,
then merges, deletes branch) → picker kicked for the next ticket. CI failures and
build-gate skips feed back as `needs-rework` and retry up to `MAX_ITERATIONS`. The
whole loop is event-driven and needs no human once secrets + issues exist.

See `docs/adr/` (0008 onward) for the full rationale of every design choice.
