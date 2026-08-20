#!/usr/bin/env python3
"""Test Agent -- independently black-box verifies a GitHub Issue's
acceptance criteria against a LIVE running instance of the real backend.
Deliberately does NOT read `backend/tests/` (the Dev Agent's own tests)
and does NOT read the implementation before designing tests -- test design
comes ONLY from requirements/journeys/epics and the issue. Implementation
code may only be consulted afterward, to root-cause an observed failure.

If the target ticket is infrastructure-only and `backend/app/main.py`
doesn't exist yet, there is nothing to black-box test over HTTP -- this
agent detects that and reports PASS-by-inapplicability rather than
failing, deferring entirely to the Review Agent and the hard test gate for
that kind of ticket.

Usage:
    export CURSOR_API_KEY=cursor_...
    python agents/test_agent.py <issue_number> --iteration 1
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import closing
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
DEFAULT_MODEL = os.environ.get("TEST_AGENT_MODEL", "grok-4.6")


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else f"[missing: {path}]"


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerHandle:
    """Boots the real backend with uvicorn against an isolated scratch DB
    (see target_app.DATABASE_OVERRIDE_ENV_VAR), tearing it down afterward
    regardless of outcome."""

    def __init__(self, port: int):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "ServerHandle":
        import os
        python_bin = target_app.backend_venv_python()
        env = {**os.environ, target_app.DATABASE_OVERRIDE_ENV_VAR: f"sqlite:///./qa_run_{self.port}.db"}
        self.proc = subprocess.Popen(
            [python_bin, "-m", "uvicorn", target_app.BACKEND_APP_MODULE,
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(target_app.BACKEND_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
        )
        self._wait_healthy()
        return self

    def _wait_healthy(self, timeout: float = 20.0):
        import urllib.request
        deadline = time.time() + timeout
        last_err = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base_url}{target_app.BACKEND_HEALTH_PATH}", timeout=1) as resp:
                    if resp.status == 200:
                        return
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(0.3)
        raise RuntimeError(f"Server did not become healthy in time: {last_err}")

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        scratch = target_app.BACKEND_DIR / f"qa_run_{self.port}.db"
        if scratch.exists():
            scratch.unlink()


def build_prompt(issue: dict, requirements: str, journeys: str, epics: str, base_url: str, iteration: int) -> str:
    return f"""You are the TEST AGENT in an automated engineering harness -- an
INDEPENDENT QA engineer, deliberately isolated from the developer's work.

STRICT RULES:
1. Do NOT open, read, or rely on `backend/tests/` (the developer's own
   unit tests) at any point. Your test design must come ONLY from the
   requirements/journeys/epics and this issue's acceptance criteria.
2. Do NOT read the application source code (`backend/app/`) BEFORE writing
   and running your tests. You may read it AFTER observing a failure,
   purely to determine root cause for your report.
3. Test the system as a black box over real HTTP, against the already-
   running server at: {base_url}
4. Do NOT modify anything under `backend/app/`. You may create new files
   under `qa/` for your black-box test scripts.

## Issue #{issue['number']}: {issue['title']}
{issue['body']}

## Project requirements (docs/requirements.md)
{requirements}

## Relevant journeys (docs/journeys.md)
{journeys}

## Epics (docs/epics.md)
{epics}

## Your process
1. From the issue's acceptance criteria, enumerate concrete test cases,
   including boundary values and negative cases it implies even if not
   spelled out explicitly.
2. Write a black-box test script under `qa/` using the `requests` library
   against base URL `{base_url}`. Each test should be a separate
   function/case so failures are individually attributable.
3. Execute it and capture actual results.
4. For every failing case, determine root cause (you may now read
   `backend/app/` to investigate) and assign a severity: HIGH (violates a
   stated acceptance criterion / security or data-integrity risk), MEDIUM
   (edge case not handled cleanly), or LOW (cosmetic/wording).
5. This is iteration {iteration} of testing this issue.

## Final report format
End your response with a fenced ```json block with EXACTLY this shape
(use an empty list for "failures" if status is PASS):
{{
  "status": "PASS" or "FAIL",
  "issue_number": {issue['number']},
  "iteration": {iteration},
  "failures": [
    {{
      "test": "short_test_name",
      "expected": "what should have happened",
      "actual": "what actually happened",
      "root_cause": "your diagnosis",
      "severity": "HIGH" or "MEDIUM" or "LOW",
      "evidence": "concrete evidence, e.g. request/response",
      "recommendation": "what the Dev Agent should do to fix it"
    }}
  ],
  "summary": "one paragraph overview of what you tested and found"
}}
"""


def run_test_agent(issue: dict, model: str, base_url: str, iteration: int) -> tuple[str, str]:
    prompt = build_prompt(
        issue,
        read_text(REPO_ROOT / "docs" / "requirements.md"),
        read_text(REPO_ROOT / "docs" / "journeys.md"),
        read_text(REPO_ROOT / "docs" / "epics.md"),
        base_url,
        iteration,
    )

    print(f"--- Test Agent starting for issue #{issue['number']} against {base_url} (model={model}) ---\n")

    try:
        with Agent.create(
            model=model,
            api_key=llm_env.cursor_api_key(),
            local=LocalAgentOptions(cwd=str(REPO_ROOT), auto_review=False),
        ) as agent:
            run = agent.send(prompt)
            print(f"[test-agent] agent_id={agent.agent_id} run_id={run.id}")
            final_text_parts: list[str] = []
            for message in run.messages():
                if message.type == "assistant":
                    for block in message.message.content:
                        if getattr(block, "type", None) == "text":
                            sys.stdout.write(block.text)
                            sys.stdout.flush()
                            final_text_parts.append(block.text)
            result = run.wait()
            return sdk_run.finish_run("test-agent", result, "".join(final_text_parts))
    except CursorAgentError as err:
        print(f"[test-agent] STARTUP FAILURE: {err}", file=sys.stderr)
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
    print("TEST AGENT REPORT")
    print("=" * 60)
    print(f"Status: {report.get('status', 'UNKNOWN')}")
    print(f"Issue: #{report.get('issue_number')}  Iteration: {report.get('iteration')}")
    for f in report.get("failures", []):
        print("\n--- Defect ---")
        print(f"Test:           {f.get('test')}")
        print(f"Expected:       {f.get('expected')}")
        print(f"Actual:         {f.get('actual')}")
        print(f"Root cause:     {f.get('root_cause')}")
        print(f"Severity:       {f.get('severity')}")
        print(f"Evidence:       {f.get('evidence')}")
        print(f"Recommendation: {f.get('recommendation')}")
    print(f"\nSummary: {report.get('summary')}")
    print("=" * 60)


def format_failures_markdown(failures: list[dict]) -> str:
    if not failures:
        return "No defects found."
    parts = []
    for f in failures:
        parts.append(
            f"**{f.get('test')}** (severity: {f.get('severity')})\n"
            f"- Expected: {f.get('expected')}\n"
            f"- Actual: {f.get('actual')}\n"
            f"- Root cause: {f.get('root_cause')}\n"
            f"- Evidence: {f.get('evidence')}\n"
            f"- Recommendation: {f.get('recommendation')}"
        )
    return "\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Test Agent: independently verify a GitHub Issue via Cursor SDK")
    parser.add_argument("issue_number", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--iteration", type=int, default=1)
    args = parser.parse_args()

    issue = ticket_utils.get_issue(args.issue_number)

    if not target_app.has_app():
        structured = {
            "status": "PASS",
            "issue_number": args.issue_number,
            "iteration": args.iteration,
            "failures": [],
            "summary": (
                "No live application (backend/app/main.py) exists yet -- this "
                "appears to be an infrastructure-only ticket with no HTTP "
                "surface to black-box test. Deferring to the Review Agent and "
                "the hard test gate for this iteration."
            ),
        }
        print_human_report(structured)
        ticket_utils.set_result_label(args.issue_number, "test", True)
        ticket_utils.report_agent_result(
            args.issue_number, "Test Agent", args.iteration, "PASS (not applicable)",
            structured["summary"],
        )
        sys.exit(0)

    (target_app.REPO_ROOT / "qa").mkdir(exist_ok=True)
    port = find_free_port()

    with ServerHandle(port) as server:
        agent_status, final_text = run_test_agent(issue, args.model, server.base_url, args.iteration)

    structured = extract_json_report(final_text) or {
        "status": "UNKNOWN",
        "issue_number": args.issue_number,
        "iteration": args.iteration,
        "failures": [],
        "summary": (
            f"Could not parse structured report. agent_run_status={agent_status}. "
            f"Raw output: {final_text[:1500]}"
        ),
    }

    print_human_report(structured)

    passed = structured.get("status") == "PASS"
    ticket_utils.set_result_label(args.issue_number, "test", passed)
    details = (
        f"**Summary**: {structured.get('summary')}\n\n"
        f"**Failures found**: {len(structured.get('failures', []))}\n\n"
        f"{format_failures_markdown(structured.get('failures', []))}"
    )
    ticket_utils.report_agent_result(
        args.issue_number, "Test Agent", args.iteration, structured.get("status", "UNKNOWN"), details,
    )

    reports_dir = REPO_ROOT / "agents" / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"issue-{args.issue_number}_test_report_iter{args.iteration}.json"
    report_path.write_text(json.dumps({"agent_run_status": agent_status, **structured}, indent=2))
    print(f"\nReport written to {report_path}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
