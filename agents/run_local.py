#!/usr/bin/env python3
"""Run tickets on THIS machine instead of a GitHub Actions runner (docs/adr/0031).

`harness.config.json > execution.mode` documents intent ("github" vs "local");
this is the local driver. With no issue number it **auto-picks the next ticket**
using the same rules as the cloud queue-picker (agent-harness-queue-picker.yml),
so you don't have to choose — just run it. It executes the same Dev → check →
(optional) Test/Review flow, using whichever LLM provider is configured, and
leaves work on a local branch unless you pass --commit/--push.

It still talks to GitHub for issue state (via `gh`), so GH_TOKEN/GH_PAT and the
provider key must be in your environment.

Usage:
    python agents/run_local.py                  # auto-pick next ticket, Dev + check
    python agents/run_local.py --with-verify    # also run Test + Review
    python agents/run_local.py --loop --commit   # drain the queue, committing each
    python agents/run_local.py 246               # a specific issue
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import github_ticket_utils as ticket_utils
import harness_config

AGENTS = Path(__file__).resolve().parent
REPO_ROOT = AGENTS.parent
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "5"))


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> int:
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def _pick_next_issue(repo: str) -> int | None:
    """Next eligible ticket, mirroring the cloud queue-picker (docs/adr/0024).

    Eligible: never-touched (no agent:* label) OR agent:needs-rework with
    iteration < MAX_ITERATIONS. Order: needs-rework first, then non-"Tests:"
    before "Tests:", then by issue number.
    """
    out = subprocess.run(
        ["gh", "issue", "list", "-R", repo, "--label", "task,phase:mvp",
         "--state", "open", "--limit", "300", "--json", "number,labels,title"],
        capture_output=True, text=True,
    )
    issues = json.loads(out.stdout or "[]")

    def names(i: dict) -> list[str]:
        return [l["name"] for l in i.get("labels", [])]

    def iter_of(i: dict) -> int:
        vals = [int(n.rsplit("-", 1)[-1]) for n in names(i) if n.startswith("agent:iteration-")]
        return vals[0] if vals else 0

    def untouched(i: dict) -> bool:
        return not any(n.startswith("agent:") for n in names(i))

    def retryable(i: dict) -> bool:
        return "agent:needs-rework" in names(i) and iter_of(i) < MAX_ITERATIONS

    def is_rework(i: dict) -> int:
        return 0 if "agent:needs-rework" in names(i) else 1

    def is_test(i: dict) -> int:
        return 1 if re.search(r"\bTests?:", i.get("title", "") or "", re.I) else 0

    eligible = [i for i in issues if untouched(i) or retryable(i)]
    eligible.sort(key=lambda i: (is_rework(i), is_test(i), i["number"]))
    return eligible[0]["number"] if eligible else None


def _run_one(issue_number: int, iteration: int | None, with_verify: bool,
             commit: bool, push: bool, branch: str | None) -> int:
    """Dev → check → (optional) Test/Review for one ticket. Returns exit code."""
    if iteration is None:
        issue = ticket_utils.get_issue(issue_number)
        iteration = ticket_utils.start_new_iteration(issue_number, ticket_utils.get_current_iteration(issue))
    print(f"\n=== issue #{issue_number}, iteration {iteration} ===")

    branch = branch or f"agent/issue-{issue_number}"
    _run(["git", "checkout", "-B", branch])

    py = sys.executable
    if _run([py, str(AGENTS / "dev_agent.py"), str(issue_number), "--iteration", str(iteration)]) != 0:
        print("[run_local] Dev agent failed.")
        ticket_utils.add_label(issue_number, "agent:needs-rework")
        return 1

    if _run(["bash", str(REPO_ROOT / "scripts" / "check.sh"), "all"]) != 0:
        print("[run_local] checks FAILED — marking needs-rework, not committing.")
        ticket_utils.add_label(issue_number, "agent:needs-rework")
        return 1
    print("[run_local] checks passed.")

    if with_verify:
        _run([py, str(AGENTS / "test_agent.py"), str(issue_number), "--iteration", str(iteration)])
        _run([py, str(AGENTS / "review_agent.py"), str(issue_number), "--iteration", str(iteration)])

    if commit or push:
        _run(["git", "add", "-A"])
        _run(["git", "commit", "-m", f"Dev Agent (local): issue #{issue_number} iteration {iteration}"])
        if push:
            _run(["git", "push", "-u", "origin", branch])

    print(f"[run_local] issue #{issue_number} done — work on branch {branch!r}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run tickets locally, auto-picking the next (docs/adr/0031).")
    ap.add_argument("issue_number", type=int, nargs="?", default=None,
                    help="specific issue; omit to auto-pick the next eligible ticket")
    ap.add_argument("--iteration", type=int, default=None, help="override iteration (default: bump like the harness)")
    ap.add_argument("--with-verify", action="store_true", help="also run Test + Review agents")
    ap.add_argument("--commit", action="store_true", help="git commit locally when checks pass")
    ap.add_argument("--push", action="store_true", help="push the branch (implies --commit)")
    ap.add_argument("--branch", default=None, help="branch name (default agent/issue-N)")
    ap.add_argument("--loop", action="store_true", help="keep auto-picking + running until the queue is empty")
    args = ap.parse_args()

    mode = harness_config.execution_mode()
    if mode != "local":
        print(f"[run_local] note: execution.mode is {mode!r}; running locally anyway.")
    repo = harness_config.repo()
    if not repo:
        sys.exit("No repo configured (harness.config.json > project.repo).")

    if args.issue_number is not None:
        return _run_one(args.issue_number, args.iteration, args.with_verify,
                        args.commit, args.push, args.branch)

    # Auto-pick mode.
    while True:
        n = _pick_next_issue(repo)
        if n is None:
            print("[run_local] no eligible open phase:mvp task issues — nothing to do.")
            return 0
        print(f"[run_local] auto-picked issue #{n}")
        rc = _run_one(n, args.iteration, args.with_verify, args.commit, args.push, args.branch)
        if not args.loop:
            return rc
        # In --loop, keep going even if this one failed (it's now needs-rework and
        # will drop out once it hits MAX_ITERATIONS), so the queue still drains.


if __name__ == "__main__":
    raise SystemExit(main())
