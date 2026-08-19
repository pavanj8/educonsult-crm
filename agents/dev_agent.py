#!/usr/bin/env python3
"""Dev Agent -- implements a GitHub Issue against the real EduConsult CRM
repo (see docs/adr/0008, docs/adr/0009). Meant to run inside the GitHub
Actions workflow (.github/workflows/agent-harness.yml) on a branch checked
out from `main`, but can also be run manually for debugging.

Usage:
    export CURSOR_API_KEY=cursor_...
    python agents/dev_agent.py <issue_number> --iteration 1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions

import github_ticket_utils as ticket_utils
import sdk_run
import target_app

REPO_ROOT = target_app.REPO_ROOT
# Fast/cheap tier: Dev Agent writes a lot of code across many tickets, and
# composer-2.5 is purpose-built for agentic coding loops (edit -> run ->
# fix). Test/Review intentionally use a stronger model instead -- see
# docs/adr/0013.
DEFAULT_MODEL = "composer-2.5"


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


def build_prompt(issue: dict, requirements: str, journeys: str, epics: str, dod: str, iteration: int) -> str:
    protected = ", ".join(target_app.PROTECTED_PATHS)
    return f"""You are the DEV AGENT in an automated engineering harness for the
EduConsult CRM project. "No ticket, no code" is the hard rule here: you
implement EXACTLY what the referenced GitHub Issue's acceptance criteria
describe -- nothing more, nothing speculative.

## Issue #{issue['number']}: {issue['title']}
{issue['body']}

## Project requirements (docs/requirements.md)
{requirements}

## Relevant journeys (docs/journeys.md)
{journeys}

## Epics (docs/epics.md)
{epics}

## Definition of Done (docs/definition-of-done.md) -- you must satisfy every item before finishing
{dod}

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
   patterns).
6. Run your own tests (e.g. `pytest` inside `backend/`) and iterate until
   they pass, before finishing.
7. This is iteration {iteration} for this issue. If earlier iteration
   comments exist on the issue (Dev/Test/Review feedback), read them via
   `gh issue view {issue['number']} --comments` and address them.

## Final message
End your response with a short structured summary: what you implemented,
which files you changed, what tests you added/updated, and anything you
noticed but deliberately left out of scope.
"""


def run_dev_agent(issue: dict, model: str, iteration: int) -> tuple[str, str]:
    prompt = build_prompt(
        issue,
        read_text(REPO_ROOT / "docs" / "requirements.md"),
        read_text(REPO_ROOT / "docs" / "journeys.md"),
        read_text(REPO_ROOT / "docs" / "epics.md"),
        read_text(REPO_ROOT / "docs" / "definition-of-done.md"),
        iteration,
    )

    print(f"--- Dev Agent starting for issue #{issue['number']} (model={model}) ---\n")

    try:
        with Agent.create(
            model=model,
            local=LocalAgentOptions(cwd=str(REPO_ROOT), auto_review=False),
        ) as agent:
            run = agent.send(prompt)
            print(f"[dev-agent] agent_id={agent.agent_id} run_id={run.id}")
            final_text_parts: list[str] = []
            for message in run.messages():
                if message.type == "assistant":
                    for block in message.message.content:
                        if getattr(block, "type", None) == "text":
                            sys.stdout.write(block.text)
                            sys.stdout.flush()
                            final_text_parts.append(block.text)
            result = run.wait()
            return sdk_run.finish_run("dev-agent", result, "".join(final_text_parts))
    except CursorAgentError as err:
        print(f"[dev-agent] STARTUP FAILURE: {err}", file=sys.stderr)
        return "startup_error", str(err)


def git_files_changed() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    return [line[3:].strip() for line in result.stdout.splitlines() if line.strip()]


def run_pytest_independently() -> tuple[int, str]:
    if not target_app.has_backend_tests():
        return 0, "(no backend/tests/ yet -- nothing to run)"
    python_bin = target_app.backend_venv_python()
    result = subprocess.run(
        [python_bin, "-m", "pytest", "-v"],
        cwd=str(target_app.BACKEND_DIR), capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description="Dev Agent: implement a GitHub Issue via Cursor SDK")
    parser.add_argument("issue_number", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--iteration", type=int, default=1)
    args = parser.parse_args()

    issue = ticket_utils.get_issue(args.issue_number)

    agent_status, final_text = run_dev_agent(issue, args.model, args.iteration)

    print("\n--- Independent verification: running pytest ourselves ---\n")
    returncode, pytest_output = run_pytest_independently()
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
