#!/usr/bin/env python3
"""Run tickets on THIS machine instead of a GitHub Actions runner (docs/adr/0031).

`harness.config.json > execution.mode` documents intent ("github" vs "local");
this is the local driver. With no issue number it **auto-picks the next ticket**
using the same rules as the cloud queue-picker (agent-harness-queue-picker.yml),
so you don't have to choose — just run it. It executes the same Dev → check →
(optional) Test/Review flow, using whichever LLM provider is configured.

Finalize options (increasing autonomy): --commit (local commit), --push (+ push
branch), --merge (push, open a PR that `Closes #N`, and squash-merge it — the
issue closes automatically). --merge is immediate: local `check.sh` already
passed, so it does not wait for the PR's CI re-run.

It still talks to GitHub for issue state (via `gh`), so GH_TOKEN/GH_PAT and the
provider key must be in your environment.

Usage:
    python agents/run_local.py                       # auto-pick, Dev + check
    python agents/run_local.py --with-verify          # also Test + Review
    python agents/run_local.py --loop --merge          # drain queue, merge+close each
    python agents/run_local.py 246 --merge             # a specific issue, finalized
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import github_ticket_utils as ticket_utils
import harness_config
import llm_env
import queue_picker

AGENTS = Path(__file__).resolve().parent
REPO_ROOT = AGENTS.parent
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "5"))


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> int:
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def _q(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)


def _has_changes() -> bool:
    """True if the Dev agent produced any file change in the working tree."""
    return bool(_q(["git", "status", "--porcelain"]).stdout.strip())


def _changed_paths() -> list[str]:
    return [l[3:].strip() for l in _q(["git", "status", "--porcelain"]).stdout.splitlines() if l.strip()]


def _is_test_only(paths: list[str]) -> bool:
    """True if EVERY changed path is a test file (adds coverage, no app behavior
    change) — the condition under which a Tests ticket can skip Test/Review."""
    def is_test(f: str) -> bool:
        name = f.rsplit("/", 1)[-1]
        return "/tests/" in f or name.startswith("test_") or name.endswith((".test.ts", ".test.tsx"))
    return bool(paths) and all(is_test(f) for f in paths)


def _verify(py: str, issue_number: int, iteration: int) -> bool:
    """Run Test + Review; return True only if neither failed (labels they set)."""
    _run([py, str(AGENTS / "test_agent.py"), str(issue_number), "--iteration", str(iteration)])
    _run([py, str(AGENTS / "review_agent.py"), str(issue_number), "--iteration", str(iteration)])
    labels = ticket_utils.get_issue(issue_number).get("label_names", [])
    return not ("agent:test-fail" in labels or "agent:review-fail" in labels)


def _checkout_fresh_main() -> None:
    """Move to an up-to-date main without destroying uncommitted work.

    Between tickets (especially after a merge) each branch must fork from current
    remote main. Any leftover changes from a failed attempt are stashed, not
    deleted, so nothing of the user's is lost.
    """
    if _q(["git", "checkout", "main"]).returncode != 0:
        _q(["git", "stash", "push", "-u", "-m", "run_local-leftover"])
        _q(["git", "checkout", "main"])
    _q(["git", "pull", "--ff-only", "-q"])


def _finalize_merge(repo: str, issue_number: int, branch: str, title: str) -> int:
    """Push, open a PR that closes the issue, and squash-merge it."""
    _run(["git", "push", "-u", "origin", branch])
    body = (f"Automated implementation by the local agent harness (run_local.py). "
            f"Closes #{issue_number}.")
    # Create the PR (may already exist if resuming).
    cp = _q(["gh", "pr", "create", "-R", repo, "--head", branch, "--base", "main",
             "--title", f"Issue #{issue_number}: {title}", "--body", body])
    if cp.returncode != 0 and "already exists" not in (cp.stderr + cp.stdout):
        print(f"[run_local] PR create failed: {cp.stderr.strip() or cp.stdout.strip()}")
        return 1
    # Squash-merge (retry briefly for GitHub to compute mergeability).
    for attempt in range(3):
        m = _q(["gh", "pr", "merge", branch, "-R", repo, "--squash", "--delete-branch"])
        if m.returncode == 0:
            print(f"[run_local] merged + closed #{issue_number}.")
            return 0
        time.sleep(4)
    print(f"[run_local] merge failed: {m.stderr.strip() or m.stdout.strip()}")
    return 1


def _run_one(repo: str, issue_number: int, iteration: int | None, *, with_verify: bool,
             commit: bool, push: bool, merge: bool, branch: str | None) -> int:
    """Dev → check → (optional) Test/Review → finalize, for one ticket."""
    _checkout_fresh_main()
    issue = ticket_utils.get_issue(issue_number)
    if iteration is None:
        iteration = ticket_utils.start_new_iteration(issue_number, ticket_utils.get_current_iteration(issue))
    title = issue.get("title", f"issue {issue_number}")
    print(f"\n=== issue #{issue_number} — {title} (iteration {iteration}) ===")

    branch = branch or f"agent/issue-{issue_number}"
    _run(["git", "checkout", "-B", branch])

    py = sys.executable
    # Dev exits non-zero when its pytest run FAILS -> a genuine failure.
    if _run([py, str(AGENTS / "dev_agent.py"), str(issue_number), "--iteration", str(iteration)]) != 0:
        print("[run_local] Dev agent failed (tests failed or hard error) — marking needs-rework.")
        ticket_utils.add_label(issue_number, "agent:needs-rework")
        return 1

    # Empty diff is NOT automatically a failure: the requirement may already be
    # satisfied by existing code, or Dev may have genuinely failed to implement it
    # (the #180 case). Dev doesn't get to decide — Test + Review do (docs/adr/0031).
    if not _has_changes():
        print("[run_local] Dev produced NO code changes — asking Test + Review whether the requirement is already met.")
        if not with_verify:
            print("[run_local] can't judge an empty diff without --with-verify — marking needs-rework.")
            ticket_utils.add_label(issue_number, "agent:needs-rework")
            return 1
        if _verify(py, issue_number, iteration):
            print(f"[run_local] Test + Review pass with no changes — requirement already satisfied; closing #{issue_number}.")
            _q(["gh", "issue", "close", str(issue_number), "-R", repo, "--reason", "completed",
                "--comment", "Closed by run_local (docs/adr/0031): no code change was needed — the "
                "requirement is already satisfied by existing code, independently confirmed by the "
                "Test and Review agents."])
            return 0
        print("[run_local] empty diff AND verification failed — genuine miss; marking needs-rework.")
        ticket_utils.add_label(issue_number, "agent:needs-rework")
        return 1

    if _run(["bash", str(REPO_ROOT / "scripts" / "check.sh"), "all"]) != 0:
        print("[run_local] checks FAILED — marking needs-rework, not finalizing.")
        ticket_utils.add_label(issue_number, "agent:needs-rework")
        return 1
    print("[run_local] checks passed.")

    # A pure Tests ticket that touched ONLY test files needs no black-box Test or
    # code Review — the tests plus check.sh's full green suite ARE the verification
    # (docs/adr/0031). The black-box Test agent can't meaningfully verify added
    # tests, and Review false-fails such tickets on empty-deliverable grounds
    # (#158). If it also touched app/ code it changes behavior, so fall through to
    # the full Test + Review gate.
    tests_only = queue_picker._discipline(issue) == 2 and _is_test_only(_changed_paths())
    if tests_only:
        print("[run_local] Tests-only ticket, test-only diff, full suite green — "
              "skipping Test/Review and merging on Dev + check.sh.")
    elif with_verify:
        # Gate merge on the agents' verdicts — do NOT merge a ticket that failed
        # Test or Review, matching the cloud finalize (docs/adr/0031).
        if not _verify(py, issue_number, iteration):
            print("[run_local] verification FAILED — marking needs-rework, not merging.")
            ticket_utils.add_label(issue_number, "agent:needs-rework")
            return 1
        print("[run_local] Test + Review passed.")

    if merge:
        _run(["git", "add", "-A"])
        _run(["git", "commit", "-m", f"Dev Agent (local): issue #{issue_number} iteration {iteration}"])
        return _finalize_merge(repo, issue_number, branch, title)
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
    ap.add_argument("--push", action="store_true", help="commit + push the branch")
    ap.add_argument("--merge", action="store_true", help="push, open a PR (Closes #N) and squash-merge it")
    ap.add_argument("--branch", default=None, help="branch name (default agent/issue-N)")
    ap.add_argument("--loop", action="store_true", help="keep auto-picking + running until the queue is empty")
    args = ap.parse_args()

    mode = harness_config.execution_mode()
    if mode != "local":
        print(f"[run_local] note: execution.mode is {mode!r}; running locally anyway.")
    repo = harness_config.repo()
    if not repo:
        sys.exit("No repo configured (harness.config.json > project.repo).")

    # Preflight: fail fast if the LLM key is missing, BEFORE touching any ticket —
    # otherwise --loop would churn the whole backlog marking everything needs-rework
    # and burning iteration counts (docs/adr/0031).
    if not llm_env.credentials_configured():
        prov = harness_config.active_provider()
        sys.exit(
            f"No LLM credentials: set {prov.get('auth_env', 'the provider key')} for provider "
            f"{prov.get('name', '?')!r}. If it's in ~/.zshrc, this shell predates it — run "
            f"`source ~/.zshrc` or open a new terminal, then retry."
        )

    def one(n: int) -> int:
        return _run_one(repo, n, args.iteration, with_verify=args.with_verify,
                        commit=args.commit, push=args.push, merge=args.merge, branch=args.branch)

    if args.issue_number is not None:
        return one(args.issue_number)

    while True:
        n = queue_picker.next_issue(repo)
        if n is None:
            print("[run_local] no eligible open phase:mvp task issues — nothing to do.")
            return 0
        print(f"[run_local] auto-picked issue #{n}")
        rc = one(n)
        if not args.loop:
            return rc
        # In --loop, keep going even if this one failed — it's now needs-rework and
        # drops out of the queue once it hits MAX_ITERATIONS, so the queue drains.


if __name__ == "__main__":
    raise SystemExit(main())
