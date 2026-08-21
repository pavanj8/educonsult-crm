#!/usr/bin/env python3
"""Planning Agent -- turns a single requirements.md into the whole backlog
(docs/adr/0030): requirements -> journeys -> epics -> tasks -> GitHub issues.

It runs on the same MiniMax engine as the Dev/Test/Review agents, but instead of
writing code it writes the *plan*. Each stage produces a reviewable artifact:

  journeys : docs/requirements.md  ->  docs/journeys.md          (atomic journeys)
  epics    : journeys              ->  (accumulated in plan.json) (many epics / journey)
  tasks    : epics                 ->  docs/plan.json            (many tasks / epic)
  render   : plan.json             ->  docs/epics.md             (traceable record)
  issues   : plan.json             ->  GitHub issues (via scripts/setup_github_issues.py)

Cardinality is not fixed: a requirement yields as many journeys as it needs, a
journey as many epics, an epic as many tasks. Generation is BATCHED (per group /
per journey / per epic) so it scales to large plans (e.g. 40 journeys -> 200
epics -> 1600 tasks) without blowing a single model response.

Usage:
    python agents/planner_agent.py all            # full pipeline -> plan.json + docs
    python agents/planner_agent.py journeys       # one stage at a time
    python agents/planner_agent.py epics
    python agents/planner_agent.py tasks
    python agents/planner_agent.py render
    python agents/planner_agent.py issues         # create GitHub issues from plan.json
Options: --model MiniMax-M3  --project "My Product"  --max-journeys N  (cap for a dry run)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import llm_env
import target_app

REPO_ROOT = target_app.REPO_ROOT
DOCS = REPO_ROOT / "docs"
PLAN_PATH = DOCS / "plan.json"
DEFAULT_MODEL = os.environ.get("PLANNER_AGENT_MODEL", llm_env.DEFAULT_PLANNER_MODEL)
MAX_TOKENS = int(os.environ.get("PLANNER_MAX_TOKENS", "16384"))
# Batch sizes keep each model response well within MAX_TOKENS.
JOURNEYS_PER_EPIC_BATCH = int(os.environ.get("PLANNER_JOURNEY_BATCH", "6"))


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _load_plan() -> dict:
    return json.loads(PLAN_PATH.read_text()) if PLAN_PATH.exists() else {}


def _save_plan(plan: dict) -> None:
    PLAN_PATH.write_text(json.dumps(plan, indent=2))


def _chat(system: str, user: str, model: str) -> str:
    """One completion against the configured provider; returns the text.

    Provider-agnostic (docs/adr/0031): Anthropic Messages API or OpenAI Chat
    Completions depending on harness.config.json > llm.
    """
    client, api = llm_env.client_and_api()
    if api == "openai":
        resp = client.chat.completions.create(
            model=model, max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""
    resp = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _json_from(text: str):
    """Extract the first JSON array/object from a model response."""
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    start = min([i for i in (text.find("["), text.find("{")) if i != -1] or [0])
    depth, end, opener = 0, None, text[start] if start < len(text) else "["
    closer = "]" if opener == "[" else "}"
    for i in range(start, len(text)):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return json.loads(text[start:end])


# --------------------------------------------------------------------------- #
# Stage 1 — journeys
# --------------------------------------------------------------------------- #
def stage_journeys(model: str, project: str, max_journeys: int | None) -> list[dict]:
    requirements = _read(DOCS / "requirements.md")
    if not requirements:
        sys.exit("docs/requirements.md is empty or missing — write it first.")
    cap = f"Produce at most {max_journeys} journeys (this is a capped dry run)." if max_journeys else \
        "Produce as many journeys as the requirements genuinely imply — do not pad or trim to a round number."
    system = (
        "You are a senior product planner. You decompose product requirements into ATOMIC user "
        "journeys: each journey is exactly one actor performing one discrete goal, small enough "
        "to trace to concrete implementation. Output ONLY JSON."
    )
    user = (
        f"Project: {project}\n\n## Requirements\n{requirements}\n\n"
        f"{cap}\nReturn a JSON array; each item: "
        f'{{"id":"J1","actor":"...","goal":"...","requirement_trace":"§ or section name","group":"short theme"}}. '
        f"Number ids J1, J2, ... sequentially."
    )
    journeys = _json_from(_chat(system, user, model))
    plan = _load_plan()
    plan["project"] = project
    plan["journeys"] = journeys
    _save_plan(plan)
    _render_journeys_md(project, journeys)
    print(f"[planner] journeys: {len(journeys)} -> docs/journeys.md + plan.json")
    return journeys


def _render_journeys_md(project: str, journeys: list[dict]) -> None:
    lines = [f"# {project} — User Journeys", "",
             "Auto-generated by the Planning Agent (docs/adr/0030). Each journey is atomic "
             "(one actor, one goal) and traces to a requirements section; each is referenced "
             "by one or more epics in [`epics.md`](./epics.md).", ""]
    by_group: dict[str, list[dict]] = {}
    for j in journeys:
        by_group.setdefault(j.get("group", "General"), []).append(j)
    for group, items in by_group.items():
        lines.append(f"## {group}")
        trace = items[0].get("requirement_trace", "")
        if trace:
            lines.append(f"_Traces to {trace}_")
        lines.append("")
        for j in items:
            lines.append(f"- **{j['id']}**: {j.get('actor','')} — {j.get('goal','')}")
        lines.append("")
    (DOCS / "journeys.md").write_text("\n".join(lines))


# --------------------------------------------------------------------------- #
# Stage 2 — epics (many per journey)
# --------------------------------------------------------------------------- #
def stage_epics(model: str) -> list[dict]:
    plan = _load_plan()
    journeys = plan.get("journeys") or sys.exit("Run the `journeys` stage first.")
    system = (
        "You are a senior engineering lead. For each user journey you break it into one or more "
        "EPICS -- cohesive vertical slices of implementation (backend area, endpoints, UI, tests). "
        "A journey may need several epics; a purely trivial one may need just one. Output ONLY JSON."
    )
    epics: list[dict] = []
    counter = 1
    for i in range(0, len(journeys), JOURNEYS_PER_EPIC_BATCH):
        batch = journeys[i:i + JOURNEYS_PER_EPIC_BATCH]
        user = (
            "## Journeys\n" + json.dumps(batch, indent=2) + "\n\n"
            'For EACH journey, return epics as a JSON array; each item: '
            '{"title":"...","area":"short-kebab area e.g. auth/student/documents","phase":"mvp|phase-2|phase-3",'
            '"journey_id":"Jx","desc":"one-line summary"}. Do not include keys or task lists here.'
        )
        for e in _json_from(_chat(system, user, model)):
            e["key"] = f"E{counter}"
            counter += 1
            epics.append(e)
        print(f"[planner] epics: journeys {i + 1}-{i + len(batch)} -> {len(epics)} epics so far")
    plan["epics"] = epics
    _save_plan(plan)
    print(f"[planner] epics: {len(epics)} total -> plan.json")
    return epics


# --------------------------------------------------------------------------- #
# Stage 3 — tasks (many per epic)
# --------------------------------------------------------------------------- #
def stage_tasks(model: str) -> None:
    plan = _load_plan()
    epics = plan.get("epics") or sys.exit("Run the `epics` stage first.")
    system = (
        "You are a senior engineer. You split an epic into ATOMIC task issues: exactly one "
        "model / one endpoint / one UI component / one test suite per task -- each mergeable in a "
        "single small PR. Output ONLY JSON."
    )
    for idx, e in enumerate(epics, 1):
        if e.get("tasks"):
            continue  # resumable: skip epics already expanded
        user = (
            f"## Epic\n{json.dumps({k: e[k] for k in ('key','title','area','phase','desc') if k in e}, indent=2)}\n\n"
            'Return a JSON array of tasks; each item: {"title":"Backend: ...|Frontend: ...|Tests: ...","body":""}. '
            "Prefix each title with the discipline. Keep each task independently shippable."
        )
        tasks = _json_from(_chat(system, user, model))
        e["tasks"] = [[t.get("title", ""), t.get("body", "")] for t in tasks]
        _save_plan(plan)  # save after each epic (resumable)
        print(f"[planner] tasks: {e['key']} ({idx}/{len(epics)}) -> {len(e['tasks'])} tasks")
    total = sum(len(e.get("tasks", [])) for e in epics)
    print(f"[planner] tasks: {total} total across {len(epics)} epics -> plan.json")


# --------------------------------------------------------------------------- #
# Render epics.md + create issues
# --------------------------------------------------------------------------- #
def stage_render() -> None:
    plan = _load_plan()
    epics = plan.get("epics", [])
    project = plan.get("project", "Project")
    n_tasks = sum(len(e.get("tasks", [])) for e in epics)
    lines = [f"# {project} — Epics", "",
             f"Auto-generated by the Planning Agent (docs/adr/0030). "
             f"**{len(plan.get('journeys', []))} journeys → {len(epics)} epics → {n_tasks} tasks.** "
             f"Each epic traces to a journey; each task becomes a GitHub Issue via "
             f"`scripts/setup_github_issues.py`.", "",
             "| Key | Epic | Area | Phase | # Tasks | Journey |",
             "|---|---|---|---|---|---|"]
    for e in epics:
        lines.append(
            f"| {e['key']} | {e.get('title','')} | {e.get('area','')} | {e.get('phase','')} "
            f"| {len(e.get('tasks', []))} | {e.get('journey_id','')} |"
        )
    (DOCS / "epics.md").write_text("\n".join(lines) + "\n")
    print(f"[planner] render: docs/epics.md ({len(epics)} epics, {n_tasks} tasks)")


def stage_issues() -> None:
    if not PLAN_PATH.exists():
        sys.exit("docs/plan.json not found — run the earlier stages first.")
    # setup_github_issues.py loads plan.json when present (docs/adr/0030).
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "setup_github_issues.py")], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Planning Agent: requirements -> journeys -> epics -> tasks -> issues")
    ap.add_argument("stage", choices=["journeys", "epics", "tasks", "render", "issues", "all"])
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--project", default=os.environ.get("PROJECT_NAME", "Project"))
    ap.add_argument("--max-journeys", type=int, default=None, help="cap journeys for a dry run")
    args = ap.parse_args()

    if args.stage in ("journeys", "all"):
        stage_journeys(args.model, args.project, args.max_journeys)
    if args.stage in ("epics", "all"):
        stage_epics(args.model)
    if args.stage in ("tasks", "all"):
        stage_tasks(args.model)
    if args.stage in ("render", "all"):
        stage_render()
    if args.stage in ("issues", "all"):
        stage_issues()


if __name__ == "__main__":
    main()
