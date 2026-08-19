#!/usr/bin/env python3
"""Hard, deterministic test gate -- mechanically enforces item 2 ("Tests")
of docs/definition-of-done.md (docs/adr/0009), independently of the Review
Agent's judgment-based "Test Engineer" perspective. A ticket cannot be
marked ready-to-merge if this fails, no matter what the LLM agents
conclude.

Checks:
1. If any application code changed (backend/app, frontend/src) relative to
   `--base`, at least one corresponding test file must also have changed
   (backend/tests, frontend *.test.ts[x]). Infra-only changes (no
   APP_CODE_GLOBS touched) are exempt.
2. The number of `def test_` functions across backend/tests/**/*.py must
   not decrease relative to `--base` (a cheap, deterministic proxy for
   "tests weren't deleted/gutted to dodge the gate" -- not a full coverage
   analysis).
3. If backend/tests/ has any tests, `pytest` must exit 0.

This is a heuristic, not perfect ticket-to-test traceability -- see
docs/adr/0009's Consequences section.

Usage:
    python agents/check_test_gate.py [--base origin/main]
Exit code 0 = gate passes, 1 = gate fails.
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys

import target_app

REPO_ROOT = target_app.REPO_ROOT


def changed_files(base_ref: str) -> list[str]:
    committed = subprocess.run(
        ["git", "diff", "--name-only", base_ref], cwd=str(REPO_ROOT), capture_output=True, text=True,
    ).stdout.splitlines()
    uncommitted = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True,
    ).stdout.splitlines()
    uncommitted_paths = [line[3:].strip() for line in uncommitted if line.strip()]
    return sorted(set(committed) | set(uncommitted_paths))


def matches_any(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def count_test_functions_at_ref(ref: str) -> int:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref], cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0  # ref doesn't exist (e.g. brand-new repo with no base yet)
    count = 0
    for path in result.stdout.splitlines():
        if not fnmatch.fnmatch(path, "backend/tests/**/*.py") and not path.startswith("backend/tests/"):
            continue
        show = subprocess.run(
            ["git", "show", f"{ref}:{path}"], cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        if show.returncode == 0:
            count += show.stdout.count("def test_")
    return count


def count_test_functions_working_tree() -> int:
    count = 0
    for path in target_app.BACKEND_TESTS_DIR.rglob("*.py"):
        count += path.read_text(errors="ignore").count("def test_")
    return count


def run_pytest() -> tuple[bool, str]:
    if not target_app.has_backend_tests():
        return True, "(no backend/tests/ yet -- nothing to run)"
    python_bin = target_app.backend_venv_python()
    result = subprocess.run(
        [python_bin, "-m", "pytest", "-q"], cwd=str(target_app.BACKEND_DIR), capture_output=True, text=True,
    )
    return result.returncode == 0, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description="Hard deterministic test gate")
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()

    failures: list[str] = []
    changed = changed_files(args.base)

    app_changed = [p for p in changed if matches_any(p, target_app.APP_CODE_GLOBS)]
    test_changed = [p for p in changed if matches_any(p, target_app.TEST_CODE_GLOBS)]

    print(f"Changed files vs {args.base}: {len(changed)}")
    print(f"  App code changed:  {app_changed or '(none)'}")
    print(f"  Test code changed: {test_changed or '(none)'}")

    if app_changed and not test_changed:
        failures.append(
            "Application code changed but no test file changed alongside it. "
            "Every ticket that touches backend/app or frontend/src must add or "
            "update a corresponding test."
        )

    base_test_count = count_test_functions_at_ref(args.base)
    current_test_count = count_test_functions_working_tree()
    print(f"Test function count: base={base_test_count} current={current_test_count}")
    if current_test_count < base_test_count:
        failures.append(
            f"Number of test functions decreased ({base_test_count} -> {current_test_count}). "
            "Tests must not be deleted/weakened to pass this gate."
        )

    pytest_ok, pytest_output = run_pytest()
    print(pytest_output)
    if not pytest_ok:
        failures.append("pytest did not pass.")

    if failures:
        print("\n=== HARD TEST GATE: FAIL ===")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)

    print("\n=== HARD TEST GATE: PASS ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
