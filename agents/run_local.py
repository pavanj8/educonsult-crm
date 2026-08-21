#!/usr/bin/env python3
"""Run a ticket on THIS machine instead of a GitHub Actions runner (docs/adr/0031).

`harness.config.json > execution.mode` selects "github" (the CI-driven harness,
default) or "local". This is the local driver: it runs the same Dev → check →
(optional) Test/Review flow the Dev workflow runs, but in your own checkout — so
you can iterate on a ticket without burning Actions minutes, using whatever LLM
provider is configured (MiniMax, Anthropic, OpenAI, …).

It still talks to GitHub for issue state (via the agents' own `gh` calls), so
GH_TOKEN/GH_PAT and the provider key must be in your environment. It does NOT
push or open a PR unless you pass --push; by default it leaves the work on a
local branch for you to review.

Usage:
    python agents/run_local.py 173                 # Dev + check, local branch
    python agents/run_local.py 173 --with-verify   # also run Test + Review
    python agents/run_local.py 173 --commit         # commit locally when green
    python agents/run_local.py 173 --iteration 2
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import harness_config

AGENTS = Path(__file__).resolve().parent
REPO_ROOT = AGENTS.parent


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> int:
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a ticket locally (docs/adr/0031).")
    ap.add_argument("issue_number", type=int)
    ap.add_argument("--iteration", type=int, default=1)
    ap.add_argument("--with-verify", action="store_true", help="also run Test + Review agents")
    ap.add_argument("--commit", action="store_true", help="git commit locally when checks pass")
    ap.add_argument("--push", action="store_true", help="push the branch (implies --commit)")
    ap.add_argument("--branch", default=None, help="branch name (default agent/issue-N)")
    args = ap.parse_args()

    mode = harness_config.execution_mode()
    if mode != "local":
        print(f"[run_local] note: execution.mode is {mode!r} in harness.config.json; "
              f"running locally anyway because you invoked run_local.py.")

    branch = args.branch or f"agent/issue-{args.issue_number}"
    _run(["git", "checkout", "-B", branch])

    py = sys.executable
    if _run([py, str(AGENTS / "dev_agent.py"), str(args.issue_number),
             "--iteration", str(args.iteration)]) != 0:
        print("[run_local] Dev agent failed.")
        return 1

    check = _run(["bash", str(REPO_ROOT / "scripts" / "check.sh"), "all"])
    if check != 0:
        print("[run_local] checks FAILED — not committing.")
        return 1
    print("[run_local] checks passed.")

    if args.with_verify:
        _run([py, str(AGENTS / "test_agent.py"), str(args.issue_number),
              "--iteration", str(args.iteration)])
        _run([py, str(AGENTS / "review_agent.py"), str(args.issue_number),
              "--iteration", str(args.iteration)])

    if args.commit or args.push:
        _run(["git", "add", "-A"])
        _run(["git", "commit", "-m", f"Dev Agent (local): issue #{args.issue_number} "
              f"iteration {args.iteration}"])
        if args.push:
            _run(["git", "push", "-u", "origin", branch])

    print(f"\n[run_local] done — work is on branch {branch!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
