"""GitHub-Issues-backed replacement for the old file-based ticket_utils.py
(see harness-demo/adr/0005 and docs/adr/0009). A GitHub Issue IS the ticket:
its body is the ticket description/acceptance criteria, its labels carry
the harness's state machine, and agent reports are posted as comments so
the full history is visible on the issue itself.

Requires the `gh` CLI, authenticated, with repo write access. Reads/writes
via subprocess rather than a REST client library to avoid adding a new
dependency beyond what's already used across this project.

Label vocabulary:
  agent:ready-for-dev       -- trigger label; Dev Agent should run
  agent:iteration-N         -- which iteration is currently in flight (only one present at a time)
  agent:dev-pass / agent:dev-fail
  agent:test-pass / agent:test-fail
  agent:review-pass / agent:review-fail
  agent:ready-to-merge      -- hard gate + test + review all passed this iteration
  agent:needs-rework        -- something failed; re-add agent:ready-for-dev to retry
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

ITERATION_LABEL_RE = re.compile(r"^agent:iteration-(\d+)$")


class GitHubCliError(RuntimeError):
    pass


def _run(args: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(
        args, input=input_text, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise GitHubCliError(f"`{' '.join(args)}` failed: {result.stderr.strip()}")
    return result.stdout


def get_issue(issue_number: int) -> dict:
    out = _run([
        "gh", "issue", "view", str(issue_number),
        "--json", "number,title,body,labels,state,url",
    ])
    data = json.loads(out)
    data["label_names"] = [l["name"] for l in data.get("labels", [])]
    return data


def add_label(issue_number: int, label: str) -> None:
    _run(["gh", "issue", "edit", str(issue_number), "--add-label", label])


def remove_label(issue_number: int, label: str) -> None:
    try:
        _run(["gh", "issue", "edit", str(issue_number), "--remove-label", label])
    except GitHubCliError:
        pass  # label may not have been present; not an error for our purposes


def post_comment(issue_number: int, body: str) -> None:
    _run(["gh", "issue", "comment", str(issue_number), "--body-file", "-"], input_text=body)


def get_current_iteration(issue: dict) -> int:
    for name in issue["label_names"]:
        m = ITERATION_LABEL_RE.match(name)
        if m:
            return int(m.group(1))
    return 0


def start_new_iteration(issue_number: int, current_iteration: int) -> int:
    """Removes the old agent:iteration-N label (if any) and adds the next
    one. Returns the new iteration number."""
    if current_iteration > 0:
        remove_label(issue_number, f"agent:iteration-{current_iteration}")
    new_iteration = current_iteration + 1
    add_label(issue_number, f"agent:iteration-{new_iteration}")
    return new_iteration


def set_result_label(issue_number: int, prefix: str, passed: bool) -> None:
    """prefix is one of 'dev', 'test', 'review'."""
    passed_label, failed_label = f"agent:{prefix}-pass", f"agent:{prefix}-fail"
    if passed:
        add_label(issue_number, passed_label)
        remove_label(issue_number, failed_label)
    else:
        add_label(issue_number, failed_label)
        remove_label(issue_number, passed_label)


def report_agent_result(issue_number: int, agent_name: str, iteration: int, result: str, details_markdown: str) -> None:
    """Posts one comment per agent run. Mirrors the old
    ticket_utils.append_log_entry, but as a GitHub comment instead of a
    markdown file section."""
    body = (
        f"### {agent_name} \u2014 iteration {iteration}\n"
        f"**Result**: {result}\n\n"
        f"{details_markdown.strip()}\n"
    )
    post_comment(issue_number, body)


def finalize_iteration(
    issue_number: int,
    iteration: int,
    hard_gate_passed: bool,
    test_passed: bool,
    review_passed: bool,
) -> str:
    """Called once per workflow run, after Dev + hard gate + Test + Review
    have all run. Sets the final label state and returns it. Does NOT close
    the issue directly -- the PR (opened separately, with "Closes #N" in its
    body) closes the issue when a human merges it, per docs/adr/0009's
    "PR-based, human-merges" default."""
    all_green = hard_gate_passed and test_passed and review_passed
    remove_label(issue_number, "agent:ready-for-dev")  # consumed; re-add to retry
    if all_green:
        add_label(issue_number, "agent:ready-to-merge")
        remove_label(issue_number, "agent:needs-rework")
        status = "ready-to-merge"
    else:
        add_label(issue_number, "agent:needs-rework")
        remove_label(issue_number, "agent:ready-to-merge")
        status = "needs-rework"

    overall = (
        "\u2705 ready to merge"
        if all_green
        else "\u274c needs rework \u2014 re-add `agent:ready-for-dev` after addressing the comments above to retry"
    )
    summary = (
        f"## Harness iteration {iteration} summary\n\n"
        f"| Gate | Result |\n|---|---|\n"
        f"| Hard test-existence/coverage gate | {'PASS' if hard_gate_passed else 'FAIL'} |\n"
        f"| Test Agent (independent black-box) | {'PASS' if test_passed else 'FAIL'} |\n"
        f"| Review Agent (5-perspective) | {'PASS' if review_passed else 'FAIL'} |\n\n"
        f"**Overall**: {overall}"
    )
    post_comment(issue_number, summary)
    return status


if __name__ == "__main__":
    # Small manual smoke test: `python github_ticket_utils.py <issue_number>`
    n = int(sys.argv[1])
    print(json.dumps(get_issue(n), indent=2))
