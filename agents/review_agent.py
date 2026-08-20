#!/usr/bin/env python3
"""Review Agent -- reviews the Dev Agent's actual code changes for a
GitHub Issue from five senior perspectives in a single pass: Security
Analyst, Software Architect, Senior Developer, UX Architect (API design
ergonomics), and Test Engineer (quality of the Dev Agent's own tests).

Diffs the current branch against `main` (the whole repo, minus paths the
Dev Agent is never allowed to touch -- see target_app.PROTECTED_PATHS).

Usage:
    export CURSOR_API_KEY=cursor_...
    python agents/review_agent.py <issue_number> --iteration 1 [--base origin/main]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions

import github_ticket_utils as ticket_utils
import llm_env
import sdk_run
import target_app

llm_env.configure_minimax_env()

REPO_ROOT = target_app.REPO_ROOT
# Stronger verify tier. With MINIMAX_API_KEY set, defaults to MiniMax-M3;
# otherwise grok-4.6 (docs/adr/0014, docs/adr/0017).
DEFAULT_MODEL = os.environ.get("REVIEW_AGENT_MODEL", "grok-4.6")

PERSPECTIVES = [
    "Security Analyst",
    "Software Architect",
    "Senior Developer",
    "UX Architect",
    "Test Engineer",
]


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else f"[missing: {path}]"


def get_diff(base_ref: str) -> str:
    """Diff of the current branch against base_ref, excluding paths the Dev
    Agent is never allowed to touch, plus untracked new files."""
    exclude_pathspecs = [f":(exclude){p}" for p in target_app.PROTECTED_PATHS]
    tracked_diff = subprocess.run(
        ["git", "diff", base_ref, "--", ".", *exclude_pathspecs],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    ).stdout

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    ).stdout.splitlines()

    untracked_blocks = []
    for rel_path in untracked:
        rel_path = rel_path.strip()
        if not rel_path or any(rel_path.startswith(p) for p in target_app.PROTECTED_PATHS):
            continue
        full_path = REPO_ROOT / rel_path
        try:
            content = full_path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        untracked_blocks.append(f"--- /dev/null\n+++ {rel_path} (new file)\n{content}")

    parts = []
    if tracked_diff.strip():
        parts.append(tracked_diff)
    if untracked_blocks:
        parts.append("\n\n".join(untracked_blocks))
    return "\n\n".join(parts) if parts else f"(no changes detected vs {base_ref})"


def build_prompt(issue: dict, requirements: str, dod: str, diff: str, iteration: int) -> str:
    perspectives_list = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(PERSPECTIVES))
    return f"""You are the REVIEW AGENT in an automated engineering harness. You
review the Dev Agent's actual code changes for a GitHub Issue, wearing
FIVE distinct senior reviewer hats in a single pass:

{perspectives_list}

For each perspective, actually reason from that role's priorities:
- Security Analyst: injection, auth/authz gaps (this is a multi-tenant app
  -- check tenant/branch scoping on every query), secrets handling, input
  validation, unsafe deserialization, dependency risk.
- Software Architect: layering, coupling, separation of concerns,
  consistency with existing patterns in this codebase, multi-tenancy
  correctness, scalability of the approach.
- Senior Developer: readability, naming, error handling, duplication,
  correctness edge cases, adherence to the issue's exact scope (no
  unrelated changes, nothing touched outside backend/frontend app code).
- UX Architect (for backend endpoints, "UX" = API design ergonomics):
  status codes, error message clarity and consistency, response shape
  consistency, predictability for API consumers. For frontend changes:
  actual user experience and accessibility.
- Test Engineer: are the tests the Dev Agent added/modified meaningful?
  Do they cover the issue's boundary/edge cases, including
  tenant/role-scoping cases? Are they deterministic and properly isolated?

## Issue #{issue['number']} under review: {issue['title']}
{issue['body']}

## Project requirements (docs/requirements.md)
{requirements}

## Definition of Done (docs/definition-of-done.md) -- your Test Engineer and
Senior Developer perspectives must explicitly check the diff against this,
not just general code-quality instinct:
{dod}

## Code diff to review (current branch vs main)
```diff
{diff}
```

You MAY also read the full files under `backend/` and `frontend/` for
context beyond the diff hunks shown above.

This is review iteration {iteration} for this issue.

## Final report format
End your response with a fenced ```json block with EXACTLY this shape
(empty list for "findings" if there are none):
{{
  "status": "PASS" or "FAIL",
  "issue_number": {issue['number']},
  "iteration": {iteration},
  "findings": [
    {{
      "perspective": "Security Analyst" | "Software Architect" | "Senior Developer" | "UX Architect" | "Test Engineer",
      "severity": "HIGH" or "MEDIUM" or "LOW",
      "issue": "what is wrong",
      "location": "file/function or diff hunk it refers to",
      "recommendation": "concrete fix"
    }}
  ],
  "summary": "one paragraph overall verdict"
}}

Overall "status" is FAIL if there is any HIGH severity finding from any
perspective, otherwise PASS (MEDIUM/LOW findings should still be listed but
don't block).
"""


def run_review_agent(issue: dict, model: str, diff: str, iteration: int) -> tuple[str, str]:
    prompt = build_prompt(
        issue,
        read_text(REPO_ROOT / "docs" / "requirements.md"),
        read_text(REPO_ROOT / "docs" / "definition-of-done.md"),
        diff,
        iteration,
    )

    print(f"--- Review Agent starting for issue #{issue['number']} (model={model}) ---\n")

    try:
        with Agent.create(
            model=model,
            api_key=llm_env.cursor_api_key(),
            local=LocalAgentOptions(cwd=str(REPO_ROOT), auto_review=False),
        ) as agent:
            run = agent.send(prompt)
            print(f"[review-agent] agent_id={agent.agent_id} run_id={run.id}")
            final_text_parts: list[str] = []
            for message in run.messages():
                if message.type == "assistant":
                    for block in message.message.content:
                        if getattr(block, "type", None) == "text":
                            sys.stdout.write(block.text)
                            sys.stdout.flush()
                            final_text_parts.append(block.text)
            result = run.wait()
            return sdk_run.finish_run("review-agent", result, "".join(final_text_parts))
    except CursorAgentError as err:
        print(f"[review-agent] STARTUP FAILURE: {err}", file=sys.stderr)
        return "startup_error", str(err)


def extract_json_report(final_text: str) -> dict | None:
    if "```json" not in final_text:
        return None
    try:
        block = final_text.split("```json", 1)[1].split("```", 1)[0]
        return json.loads(block)
    except (IndexError, json.JSONDecodeError):
        return None


def print_human_report(report: dict):
    print("\n" + "=" * 60)
    print("REVIEW AGENT REPORT")
    print("=" * 60)
    print(f"Status: {report.get('status', 'UNKNOWN')}")
    print(f"Issue: #{report.get('issue_number')}  Iteration: {report.get('iteration')}")
    for f in report.get("findings", []):
        print(f"\n--- Finding ({f.get('perspective')}) ---")
        print(f"Severity:       {f.get('severity')}")
        print(f"Issue:          {f.get('issue')}")
        print(f"Location:       {f.get('location')}")
        print(f"Recommendation: {f.get('recommendation')}")
    print(f"\nSummary: {report.get('summary')}")
    print("=" * 60)


def format_findings_markdown(findings: list[dict]) -> str:
    if not findings:
        return "No findings."
    parts = []
    for f in findings:
        parts.append(
            f"**[{f.get('perspective')}] {f.get('severity')}**: {f.get('issue')}\n"
            f"- Location: {f.get('location')}\n"
            f"- Recommendation: {f.get('recommendation')}"
        )
    return "\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Review Agent: 5-perspective code review via Cursor SDK")
    parser.add_argument("issue_number", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--base", default="origin/main", help="git ref to diff against")
    args = parser.parse_args()

    issue = ticket_utils.get_issue(args.issue_number)
    diff = get_diff(args.base)
    agent_status, final_text = run_review_agent(issue, args.model, diff, args.iteration)

    structured = extract_json_report(final_text) or {
        "status": "UNKNOWN",
        "issue_number": args.issue_number,
        "iteration": args.iteration,
        "findings": [],
        "summary": (
            f"Could not parse structured report. agent_run_status={agent_status}. "
            f"Raw output: {final_text[:1500]}"
        ),
    }

    print_human_report(structured)

    passed = structured.get("status") == "PASS"
    ticket_utils.set_result_label(args.issue_number, "review", passed)
    details = (
        f"**Summary**: {structured.get('summary')}\n\n"
        f"**Findings**: {len(structured.get('findings', []))}\n\n"
        f"{format_findings_markdown(structured.get('findings', []))}"
    )
    ticket_utils.report_agent_result(
        args.issue_number, "Review Agent", args.iteration, structured.get("status", "UNKNOWN"), details,
    )

    reports_dir = REPO_ROOT / "agents" / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"issue-{args.issue_number}_review_report_iter{args.iteration}.json"
    report_path.write_text(json.dumps({"agent_run_status": agent_status, **structured}, indent=2))
    print(f"\nReport written to {report_path}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
