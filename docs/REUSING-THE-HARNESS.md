# Reusing this agent harness as a template for a new project

This repo is two things layered together:

1. **The autonomous Dev/Test/Review agent harness** (reusable infrastructure).
2. **The EduConsult CRM product** it happens to be building (project-specific).

To start a new project, copy the harness (layer 1) and replace the product
(layer 2). Nothing in the harness is EduConsult-specific except the paths it
conventionally expects (`backend/`, `frontend/`) and the planning docs.

## Copy these — the reusable harness

| Path | What it is |
|---|---|
| `agents/` | The engine + the three agents. `minimax_agent.py` (MiniMax Anthropic-endpoint tool loop), `dev_agent.py` / `test_agent.py` / `review_agent.py`, `llm_env.py`, `github_ticket_utils.py`, `target_app.py` (conventions/paths), plus `check_test_gate.py`, `prepare_iteration.py`, `require_dev_completed.py`, `finalize_iteration.py`, `try_finalize.py`. `requirements.txt` = `anthropic` only. |
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
| `backend/`, `frontend/` | Your app (or empty scaffolds). The harness expects `backend/app/main.py` (FastAPI) + `backend/requirements.txt` and, optionally, `frontend/package.json`. If your stack differs, update `agents/target_app.py` and `scripts/check.sh`. |
| `docs/requirements.md`, `docs/journeys.md`, `docs/epics.md` | Your product's requirements → journeys → epics → task issues. |
| `docs/adr/0001`–`0007` | Your product's architecture ADRs (these are EduConsult's). |
| `README.md`, `infra/` | Your product overview + local infra. |

## One-time setup for a new repo

1. **Secrets** (Settings → Secrets and variables → Actions):
   - `ANTHROPIC_AUTH_TOKEN` — MiniMax token (Anthropic-compatible endpoint).
     `ANTHROPIC_BASE_URL` is set in-workflow to `https://api.minimax.io/anthropic`.
   - `GH_PAT` — a fine-grained PAT with `contents` + `pull-requests` write, so the
     harness pushes workflow files and authors PRs as a real user (avoids the
     first-time-contributor CI approval gate). `CURSOR_API_KEY` is legacy/dormant.
2. **Labels**: `task`, `phase:mvp`, `agent:ready-for-dev`, `agent:iteration-1..N`,
   `agent:{dev,test,review,gate}-{pass,fail}`, `agent:ready-to-merge`,
   `agent:needs-rework`.
3. **Repo settings**: allow merge commits; enable "delete branch on merge". On a
   public repo, Actions are free/unlimited; on a private repo you need a paid plan
   or the free-minute budget (the harness enforces the CI gate itself since branch
   protection isn't available on the free tier — see ADR-0020/0023).
4. **Model tiers** (workflow env): `DEV_AGENT_MODEL` / `TEST_AGENT_MODEL` /
   `REVIEW_AGENT_MODEL` (default `MiniMax-M3`). To swap providers, change
   `llm_env.minimax_client()` and the `*_BASE_URL`/token env.
5. **Seed issues** from your epics, label them `task,phase:mvp`, and the queue
   picker drains them autonomously.

## How it runs (once seeded)

Queue picker → Dev (sync main, context pack, `check.sh` build gate) → Test +
Review in parallel (structured `submit_report`) → finalize (waits for CI green,
then merges, deletes branch) → picker kicked for the next ticket. CI failures and
build-gate skips feed back as `needs-rework` and retry up to `MAX_ITERATIONS`. The
whole loop is event-driven and needs no human once secrets + issues exist.

See `docs/adr/` (0008 onward) for the full rationale of every design choice.
