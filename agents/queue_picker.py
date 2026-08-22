#!/usr/bin/env python3
"""Single source of truth for which ticket the harness runs next (docs/adr/0024,
0031). Used by BOTH the local runner (agents/run_local.py) and the cloud queue
picker (.github/workflows/agent-harness-queue-picker.yml), so they never disagree.

Eligible tickets: never-touched (no agent:* label) OR agent:needs-rework with
iteration < MAX_ITERATIONS.

Order is topological — it minimizes the dominant failure class, a ticket whose
dependencies aren't merged yet:

  1. needs-rework before new work — address Test/Review feedback first (ADR-0024).
  2. epic order: ascending "[E#]" from the title — foundational epics land first.
  3. discipline within an epic: Backend -> Frontend -> Tests (a frontend/test
     ticket almost always depends on its epic's backend being merged; #171).
  4. issue number as the final tiebreak.

CLI: `python agents/queue_picker.py [<repo>]` prints the next issue number (or
nothing). It shells out to `gh` for the open `task,phase:<phase>` issues, where
<phase> is `queue.phase` from harness.config.json (env: HARNESS_QUEUE_PHASE),
defaulting to `mvp`. That knob is how the harness advances to the next phase
once a phase's backlog is complete (ADR-0024).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "5"))
_EPIC_RE = re.compile(r"\[E(\d+)\]")
_NO_EPIC = 10 ** 6  # sorts issues without an [E#] tag last within their rework tier


def _names(i: dict) -> list[str]:
    return [l["name"] for l in i.get("labels", [])]


def _iteration(i: dict) -> int:
    vals = [int(n.rsplit("-", 1)[-1]) for n in _names(i) if n.startswith("agent:iteration-")]
    return vals[0] if vals else 0


def _untouched(i: dict) -> bool:
    return not any(n.startswith("agent:") for n in _names(i))


def _retryable(i: dict, max_iter: int) -> bool:
    return "agent:needs-rework" in _names(i) and _iteration(i) < max_iter


def _is_rework(i: dict) -> int:
    return 0 if "agent:needs-rework" in _names(i) else 1


def _epic_num(i: dict) -> int:
    m = _EPIC_RE.search(i.get("title", "") or "")
    return int(m.group(1)) if m else _NO_EPIC


def _discipline(i: dict) -> int:
    """Backend -> 0, Frontend -> 1, Tests -> 2 (neutral 1 if none matches)."""
    t = i.get("title", "") or ""
    if re.search(r"\btests?:", t, re.I):
        return 2
    if re.search(r"\bback[\s/-]?end", t, re.I):  # also matches "Backend/Frontend:"
        return 0
    if re.search(r"\bfront[\s/-]?end", t, re.I):
        return 1
    return 1


def sort_key(i: dict):
    return (_is_rework(i), _epic_num(i), _discipline(i), i["number"])


def eligible(issues: list[dict], max_iter: int = MAX_ITERATIONS) -> list[dict]:
    return sorted(
        [i for i in issues if _untouched(i) or _retryable(i, max_iter)],
        key=sort_key,
    )


def _phase() -> str:
    """Phase label to filter on, from HARNESS_QUEUE_PHASE or harness.config.json."""
    if os.environ.get("HARNESS_QUEUE_PHASE"):
        return os.environ["HARNESS_QUEUE_PHASE"].strip()
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import harness_config
        return harness_config.queue_phase()
    except Exception:
        return "mvp"


def _open_tasks(repo: str, phase: str | None = None) -> list[dict]:
    phase = phase or _phase()
    out = subprocess.run(
        ["gh", "issue", "list", "-R", repo, "--label", f"task,phase:{phase}",
         "--state", "open", "--limit", "300", "--json", "number,labels,title"],
        capture_output=True, text=True,
    )
    return json.loads(out.stdout or "[]")


def next_issue(repo: str, max_iter: int = MAX_ITERATIONS, phase: str | None = None) -> int | None:
    picks = eligible(_open_tasks(repo, phase), max_iter)
    return picks[0]["number"] if picks else None


def main() -> None:
    repo = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HARNESS_REPO", "")
    if not repo:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import harness_config
        repo = harness_config.repo()
    if not repo:
        sys.exit("No repo given and none configured (harness.config.json > project.repo).")
    n = next_issue(repo)
    if n is not None:
        print(n)


if __name__ == "__main__":
    main()
