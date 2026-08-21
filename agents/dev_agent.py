#!/usr/bin/env python3
"""Dev Agent -- implements a GitHub Issue against the real EduConsult CRM
repo (see docs/adr/0008, docs/adr/0009). Meant to run inside the GitHub
Actions workflow (.github/workflows/agent-harness.yml) on a branch checked
out from `main`, but can also be run manually for debugging.

Usage:
    export MINIMAX_API_KEY=...
    python agents/dev_agent.py <issue_number> --iteration 1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import github_ticket_utils as ticket_utils
import harness_config
import llm_env
import minimax_agent
import target_app

llm_env.configure_minimax_env()

REPO_ROOT = target_app.REPO_ROOT
PROJECT_NAME = harness_config.project_name()
# Dev model tier from config (docs/adr/0031). Overridable via env.
DEFAULT_MODEL = os.environ.get("DEV_AGENT_MODEL", llm_env.DEFAULT_DEV_MODEL)
# Dev caps at fewer turns than the tool-heavy Test/Review agents (which use the
# engine's MAX_TURNS=140). With the context pack + str_replace + "run check.sh
# once" guidance, a well-behaved Dev run finishes well under this; the lower cap
# stops a churning run from holding the single Dev slot for ~49 min before the
# rail trips (docs/adr/0026). Overridable via env.
DEV_MAX_TURNS = int(os.environ.get("DEV_MAX_TURNS", "50"))
# In-run build-gate retries (docs/adr/0027): after the agent finishes, run the
# canonical backend gate; if it fails, feed the failure straight back and let the
# agent fix it IN THE SAME RUN, up to this many total attempts, before the ticket
# ever bounces out to needs-rework + a fresh re-dispatched job. Cheaper than
# restarting on a new runner. Test/Review still run in their own jobs afterward.
DEV_BUILD_ATTEMPTS = int(os.environ.get("DEV_BUILD_ATTEMPTS", "2"))
# Retry (in-run fix) attempts get a tighter turn budget than the first pass:
# a focused "fix exactly what check.sh reports" pass shouldn't need a full
# DEV_MAX_TURNS, and this caps worst-case Dev run time (docs/adr/0027) so the
# in-run retries don't hog the single Dev slot for ~2x DEV_MAX_TURNS.
DEV_RETRY_MAX_TURNS = int(os.environ.get("DEV_RETRY_MAX_TURNS", "20"))

_backend_deps_ready = False


def _ensure_backend_deps() -> None:
    global _backend_deps_ready
    if _backend_deps_ready:
        return
    req = target_app.BACKEND_DIR / "requirements.txt"
    if req.exists():
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(req), "ruff==0.16.3"],
            capture_output=True, text=True,
        )
    _backend_deps_ready = True


def _dev_gate() -> tuple[int, str]:
    """In-run gate: backend lint + ONLY the tests the agent added/changed — NOT
    the whole suite. The full regression + build runs exactly once, at the merge
    gate (`run_local`'s `check.sh all`) and in CI, so we don't re-run hundreds of
    tests on every in-run attempt/iteration (docs/adr/0031)."""
    if not (target_app.BACKEND_DIR / "requirements.txt").exists():
        return 0, "(no backend to check)"
    _ensure_backend_deps()
    lint = subprocess.run(
        ["bash", "scripts/check.sh", "backend-lint"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    out = lint.stdout + lint.stderr
    if lint.returncode != 0:
        return lint.returncode, out
    rc, tout = run_targeted_tests()
    return rc, out + "\n" + tout


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else f"[missing: {path}]"


@dataclass
class DevAgentReport:
    issue_number: int
    timestamp: str
    agent_run_status: str
    agent_final_message: str
    files_changed: list[str] = field(default_factory=list)
    pytest_returncode: int | None = None
    pytest_summary: str = ""
    pytest_passed: bool = True  # true (vacuously) when there's nothing to test yet

    def to_dict(self) -> dict:
        return {
            "issue_number": self.issue_number,
            "timestamp": self.timestamp,
            "agent_run_status": self.agent_run_status,
            "agent_final_message": self.agent_final_message,
            "files_changed": self.files_changed,
            "pytest_returncode": self.pytest_returncode,
            "pytest_summary": self.pytest_summary,
            "pytest_passed": self.pytest_passed,
        }


def build_repo_map() -> str:
    """A flat listing of existing application/test files, injected into the
    prompt so the agent doesn't burn model turns running find/ls/grep to
    discover structure (docs/adr/0021). Bounded so it can't dominate context.
    """
    areas = {
        "backend/app": "**/*.py",
        "backend/tests": "**/*.py",
        "frontend/src": "**/*.ts*",
    }
    skip = {"__pycache__", "node_modules", "venv", ".venv", ".pytest_cache"}
    blocks: list[str] = []
    for rel, pattern in areas.items():
        base = REPO_ROOT / rel
        if not base.exists():
            continue
        files = [
            str(f.relative_to(REPO_ROOT))
            for f in sorted(base.glob(pattern))
            if f.is_file() and not (skip & set(f.parts))
        ]
        if files:
            shown = files[:250]
            more = f"\n… (+{len(files) - len(shown)} more)" if len(files) > len(shown) else ""
            blocks.append(f"#### {rel}/ ({len(files)} files)\n" + "\n".join(shown) + more)
    if not blocks:
        return "(no application/test code exists yet — likely an early scaffolding ticket)"
    return "\n\n".join(blocks)


def build_prompt(
    issue: dict,
    requirements: str,
    journeys: str,
    epics: str,
    dod: str,
    iteration: int,
    prior_feedback: str,
) -> str:
    protected = ", ".join(target_app.PROTECTED_PATHS)
    repo_map = build_repo_map()
    siblings = ticket_utils.epic_sibling_status(issue)
    sibling_block = (
        f"## Sibling tickets in this epic — what already exists (do NOT recreate)\n"
        f"Some of this epic's work is already merged to `main` and is in the "
        f"repository map above. Build on it; never re-add a model, migration, "
        f"schema, or endpoint a DONE ticket already landed.\n\n{siblings}\n"
        if siblings else ""
    )
    if prior_feedback:
        feedback_block = (
            f"## Feedback from prior iterations — you MUST address this\n"
            f"The previous Test Agent, Review Agent, and/or hard test gate "
            f"rejected this work. Fix the defects below. Do not ignore them "
            f"and do not re-implement from scratch unless the feedback says "
            f"the current approach is wrong.\n\n{prior_feedback}"
        )
    else:
        feedback_block = (
            "## Feedback from prior iterations\n"
            "None — this is the first iteration (or no Test/Review comments yet)."
        )
    return f"""You are the DEV AGENT in an automated engineering harness for the
{PROJECT_NAME} project. "No ticket, no code" is the hard rule here: you
implement EXACTLY what the referenced GitHub Issue's acceptance criteria
describe -- nothing more, nothing speculative.

## Issue #{issue['number']}: {issue['title']}
{issue['body']}

{feedback_block}

## Project requirements (docs/requirements.md)
{requirements}

## Relevant journeys (docs/journeys.md)
{journeys}

## Epics (docs/epics.md)
{epics}

## Repository map — every existing app/test file (so you do NOT need to explore)
{repo_map}

{sibling_block}
## Definition of Done (docs/definition-of-done.md) -- you must satisfy every item before finishing
{dod}

## Working efficiently (do this to avoid wasting time)
- HARD BUDGET: read AT MOST ~8 files, then START WRITING. You have a limited
  number of turns; a run that spends them all reading and writes nothing is a
  FAILED, wasted iteration (this has happened — do not repeat it). Aim to create
  your first file within your first several actions. When in doubt, write code
  now and refine it, rather than reading one more file.
- The repository map above already lists every existing file. Do NOT run
  `find`, `ls`, `tree`, or broad `grep` to discover structure — you have it.
  Only `read_file` the specific files you will edit or directly depend on
  (usually the router/model/schema/test for this ticket's area, plus one
  similar existing file to copy conventions from).
- Create NEW files with `write_file`. To change an EXISTING file, use
  `str_replace` (surgical edit) — do NOT rewrite a whole large file just to fix
  a few lines; that wastes time and risks new errors. Never write files via
  shell heredocs (`cat > file << EOF`) — that causes escaping and syntax errors.
- Validate with the NARROWEST command: `ruff check --fix .` inside `backend/`
  for lint, and run ONLY the test file(s) you added or changed
  (`python -m pytest tests/<area>/test_x.py -q` from `backend/`) — NOT the whole
  suite. The full regression suite + build runs once at the merge gate and in CI;
  re-running all tests after each edit wastes minutes and grows worse as the
  project grows.

## Rules
1. Implement only what this issue's acceptance criteria describe. If you
   notice unrelated problems, mention them in your final summary -- do not
   fix them.
2. Never modify anything under: {protected}. These are planning docs and
   harness tooling, out of scope for any implementation ticket.
3. Write or update automated tests alongside any application code you add
   or change (unit tests under `backend/tests/`, or the frontend
   equivalent). A ticket without tests will fail the harness's hard test
   gate regardless of what you implement.
4. If this issue is infrastructure-only (no application code yet, e.g.
   Docker Compose/CI scaffolding), tests may not apply -- say so explicitly
   in your final summary instead of inventing tests that don't test
   anything real.
5. Follow existing conventions already established in this repo (check
   `backend/` and `frontend/` for prior art before introducing new
   patterns). CRITICAL: do NOT re-create code that already exists — if the
   repository map / sibling tickets show a model, migration, schema, service,
   or endpoint is already present, IMPORT and EXTEND it. Re-adding an existing
   model or migration causes duplicate definitions, conflicts, and review
   failures (this is a common cause of rework).
6. Before finishing, make your change pass the NARROW gate — do NOT run the
   whole suite (the harness gate + CI run the full regression once):
   - Backend: `ruff check --fix .` inside `backend/` (auto-fixes import order (I)
     and unused imports (F401); fix remaining e.g. F841 by hand), then run ONLY
     the tests you added/changed (`python -m pytest tests/<area>/test_x.py -q`)
     and make them green.
   - Frontend: `npm run lint`, and if you added a component test run just that
     spec. The full `npm run build` is part of the merge gate.
   Do NOT finish while lint fails or your own tests fail.
7. This is iteration {iteration} for this issue. If the feedback section
   above is non-empty, treating it as optional is a failure.

## Final message
End your response with a short structured summary: what you implemented,
which files you changed, what tests you added/updated, how you addressed
prior Test/Review feedback (if any), and anything you noticed but
deliberately left out of scope.
"""


def run_dev_agent(issue: dict, model: str, iteration: int) -> tuple[str, str]:
    base_prompt = build_prompt(
        issue,
        read_text(REPO_ROOT / "docs" / "requirements.md"),
        read_text(REPO_ROOT / "docs" / "journeys.md"),
        read_text(REPO_ROOT / "docs" / "epics.md"),
        read_text(REPO_ROOT / "docs" / "definition-of-done.md"),
        iteration,
        ticket_utils.prior_iteration_feedback(issue["number"]),
    )

    status, text, gate_out, wrote_nothing = "unknown", "", "", False
    for attempt in range(1, DEV_BUILD_ATTEMPTS + 1):
        prompt = base_prompt
        if wrote_nothing:
            # The #180/#185 failure mode: the agent spends its whole turn budget
            # READING files and finishes without writing anything. Give it a
            # focused second pass that demands implementation instead of more
            # exploration (docs/adr/0031). Not a hard-fail — if it still writes
            # nothing, run_local's empty-diff flow (Test/Review) decides.
            prompt = base_prompt + (
                f"\n\n## You wrote NO code — in-run attempt {attempt} of {DEV_BUILD_ATTEMPTS}\n"
                f"Your previous attempt spent all its turns READING files and finished without "
                f"creating or editing a single file (`git status` is empty). STOP exploring — you "
                f"already have the repository map and every convention you need above. IMPLEMENT the "
                f"issue NOW: write the actual application and test files with write_file/str_replace "
                f"in your first few turns. A run that only reads and produces no diff is a wasted "
                f"iteration; do not finish until `git status` shows your new/edited files.\n"
            )
        elif gate_out:
            prompt = base_prompt + (
                f"\n\n## Gate STILL FAILING — in-run fix attempt {attempt} of {DEV_BUILD_ATTEMPTS}\n"
                f"Your previous work did NOT pass backend lint + your own tests. Fix ONLY what "
                f"it reports below (do not rewrite passing code, do not restart), then finish:\n"
                f"```\n{gate_out[-3000:]}\n```\n"
            )
        turns = DEV_MAX_TURNS if attempt == 1 else DEV_RETRY_MAX_TURNS
        print(f"--- Dev Agent attempt {attempt}/{DEV_BUILD_ATTEMPTS} for issue #{issue['number']} (model={model}, max_turns={turns}) ---\n")
        status, text = minimax_agent.run_agent(
            "dev-agent", prompt, model, REPO_ROOT, max_turns=turns,
        )
        wrote_nothing = not git_files_changed()
        rc, gate_out = _dev_gate()
        if wrote_nothing:
            print(f"\n[dev-agent] NO code produced on attempt {attempt}; retrying with an "
                  f"implement-now directive.", file=sys.stderr)
            continue
        if rc == 0:
            print(f"\n[dev-agent] gate PASSED on in-run attempt {attempt}.")
            return status, text
        print(f"\n[dev-agent] gate FAILED on in-run attempt {attempt}.", file=sys.stderr)
    print(
        f"[dev-agent] no green diff after {DEV_BUILD_ATTEMPTS} in-run attempts; the empty-diff / "
        f"build gate will route this to needs-rework.", file=sys.stderr,
    )
    return status, text


def git_files_changed() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    return [line[3:].strip() for line in result.stdout.splitlines() if line.strip()]


def _changed_backend_test_files() -> list[str]:
    """New/modified backend test files, as paths relative to the backend dir."""
    bname = target_app.BACKEND_DIR.name
    rel = []
    for f in git_files_changed():  # repo-relative
        if f.startswith(f"{bname}/tests/") and f.endswith(".py") and Path(f).name.startswith("test_"):
            rel.append(f[len(bname) + 1:])  # strip "<backend>/"
    return rel


def run_targeted_tests() -> tuple[int, str]:
    """Run ONLY the backend test files the agent added/changed — not the full
    suite (docs/adr/0031). The full regression runs once at the merge gate + CI.
    rc=0 when there are no changed backend tests."""
    if not target_app.has_backend_tests():
        return 0, "(no backend/tests/ yet -- nothing to run)"
    rel = _changed_backend_test_files()
    if not rel:
        return 0, "(no new/changed backend test files -- full regression deferred to the gate/CI)"
    python_bin = target_app.backend_venv_python()
    result = subprocess.run(
        [python_bin, "-m", "pytest", "-q", *rel],
        cwd=str(target_app.BACKEND_DIR), capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description="Dev Agent: implement a GitHub Issue via MiniMax")
    parser.add_argument("issue_number", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--iteration", type=int, default=1)
    args = parser.parse_args()

    issue = ticket_utils.get_issue(args.issue_number)

    agent_status, final_text = run_dev_agent(issue, args.model, args.iteration)

    print("\n--- Verification: running the tests this change added/modified ---\n")
    returncode, pytest_output = run_targeted_tests()
    print(pytest_output)

    files_changed = git_files_changed()

    report = DevAgentReport(
        issue_number=args.issue_number,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent_run_status=agent_status,
        agent_final_message=final_text[-4000:],
        files_changed=files_changed,
        pytest_returncode=returncode,
        pytest_summary=pytest_output.strip().splitlines()[-1] if pytest_output.strip() else "",
        pytest_passed=(returncode == 0),
    )

    reports_dir = REPO_ROOT / "agents" / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"issue-{args.issue_number}_dev_report_iter{args.iteration}.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2))
    print(f"\nReport written to {report_path}")

    ticket_utils.set_result_label(args.issue_number, "dev", report.pytest_passed)
    details = (
        f"**Files changed**: {', '.join(report.files_changed) or '(none)'}\n\n"
        f"**pytest**: {report.pytest_summary}\n\n"
        f"**Agent summary**:\n{report.agent_final_message[-1500:]}"
    )
    ticket_utils.report_agent_result(
        args.issue_number, "Dev Agent", args.iteration,
        "PASS" if report.pytest_passed else "FAIL", details,
    )

    sys.exit(0 if report.pytest_passed else 1)


if __name__ == "__main__":
    main()
