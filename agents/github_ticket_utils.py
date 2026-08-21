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
  agent:gate-pass / agent:gate-fail
  agent:test-pass / agent:test-fail
  agent:review-pass / agent:review-fail
  agent:ready-to-merge      -- hard gate + test + review all passed this iteration
  agent:needs-rework        -- something failed; harness auto-retries
                               until MAX_ITERATIONS (docs/adr/0015)
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


def get_issue_comments(issue_number: int) -> list[dict]:
    out = _run([
        "gh", "issue", "view", str(issue_number),
        "--comments", "--json", "comments",
    ])
    return json.loads(out).get("comments") or []


def prior_iteration_feedback(issue_number: int, limit_chars: int = 12000) -> str:
    """Test/Review/harness comments the Dev Agent must address on retry.

    Truncates to `limit_chars` from the end so the newest feedback is kept
    if the thread is long (docs/adr/0015).
    """
    parts: list[str] = []
    for comment in get_issue_comments(issue_number):
        body = (comment.get("body") or "").strip()
        if not body:
            continue
        if not (
            body.startswith("### Test Agent")
            or body.startswith("### Review Agent")
            or body.startswith("## Harness iteration")
        ):
            continue
        created = comment.get("createdAt") or ""
        parts.append(f"--- {created} ---\n{body}")
    if not parts:
        return ""
    blob = "\n\n".join(parts)
    if len(blob) > limit_chars:
        blob = blob[-limit_chars:]
    return blob


def epic_sibling_status(issue: dict) -> str:
    """Sibling tickets in the same epic and whether each is already merged, so
    the Dev Agent doesn't re-implement models/migrations a prior ticket already
    landed on main (docs/adr/0025; the #169 "re-added StageHistory" failure)."""
    body = issue.get("body") or ""
    m = re.search(r"[Pp]art of #(\d+)", body)
    if not m:
        return ""
    epic = m.group(1)
    try:
        items = json.loads(_run([
            "gh", "issue", "list", "--state", "all", "--limit", "300",
            "--json", "number,title,state,body",
        ]))
    except (GitHubCliError, json.JSONDecodeError):
        return ""
    pat = re.compile(rf"[Pp]art of #{epic}(?!\d)")
    sibs = [
        it for it in items
        if it.get("number") != issue.get("number") and pat.search(it.get("body") or "")
    ]
    if not sibs:
        return ""
    lines = []
    for it in sorted(sibs, key=lambda x: x["number"]):
        if it.get("state") == "CLOSED":
            mark = "DONE — already merged to main; do NOT re-create its code, build on it"
        else:
            mark = "still in progress — its code is NOT on main yet"
        lines.append(f"- #{it['number']} {it['title']} — {mark}")
    return "\n".join(lines)


def start_new_iteration(issue_number: int, current_iteration: int) -> int:
    """Removes the old agent:iteration-N label (if any) and adds the next
    one. Returns the new iteration number."""
    if current_iteration > 0:
        remove_label(issue_number, f"agent:iteration-{current_iteration}")
    new_iteration = current_iteration + 1
    add_label(issue_number, f"agent:iteration-{new_iteration}")
    # Consumed: this iteration is now in flight. Finalize will re-add
    # needs-rework if the gates fail again (docs/adr/0015).
    remove_label(issue_number, "agent:needs-rework")
    remove_label(issue_number, "agent:ready-to-merge")
    # Drop prior-iteration gate/test/review results so "label present"
    # means *this* iteration finished that stage (docs/adr/0016).
    for prefix in ("dev", "gate", "test", "review"):
        remove_label(issue_number, f"agent:{prefix}-pass")
        remove_label(issue_number, f"agent:{prefix}-fail")
    return new_iteration


def set_result_label(issue_number: int, prefix: str, passed: bool) -> None:
    """prefix is one of 'dev', 'test', 'review', 'gate'."""
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


def result_from_labels(label_names: list[str], prefix: str) -> bool | None:
    """True/False if this iteration recorded a result for `prefix`, else None."""
    names = set(label_names)
    if f"agent:{prefix}-pass" in names:
        return True
    if f"agent:{prefix}-fail" in names:
        return False
    return None


def try_finalize_iteration(issue_number: int, iteration: int) -> str:
    """Join point for parallel Test + Review (docs/adr/0016).

    Returns one of: waiting, already-finalized, stale, ready-to-merge,
    needs-rework.
    """
    issue = get_issue(issue_number)
    labels = issue["label_names"]
    current = get_current_iteration(issue)
    if current != iteration:
        print(f"stale: issue is on iteration {current}, finalize asked for {iteration}")
        return "stale"
    if "agent:ready-to-merge" in labels or "agent:needs-rework" in labels:
        print("already-finalized")
        return "already-finalized"
    gate = result_from_labels(labels, "gate")
    test = result_from_labels(labels, "test")
    review = result_from_labels(labels, "review")
    missing = [
        name
        for name, value in (("gate", gate), ("test", test), ("review", review))
        if value is None
    ]
    if missing:
        print(f"waiting on: {', '.join(missing)}")
        return "waiting"
    return finalize_iteration(
        issue_number,
        iteration,
        hard_gate_passed=bool(gate),
        test_passed=bool(test),
        review_passed=bool(review),
    )


def require_dev_completed(issue_number: int, iteration: int) -> None:
    """Test/Review may only run on an issue Dev Agent just finished.

    Raises SystemExit if this is the wrong iteration or Dev never
    recorded a result (docs/adr/0016). The picker never starts Test or
    Review; only the Dev workflow dispatches them, for that same issue.
    """
    issue = get_issue(issue_number)
    current = get_current_iteration(issue)
    if current != iteration:
        raise SystemExit(
            f"Refuse Test/Review: issue #{issue_number} is on iteration "
            f"{current}, dispatch asked for {iteration}."
        )
    if result_from_labels(issue["label_names"], "dev") is None:
        raise SystemExit(
            f"Refuse Test/Review: Dev Agent has not recorded a result for "
            f"issue #{issue_number} iteration {iteration}. These agents "
            f"do not pick tickets from the backlog."
        )
    print(
        f"Context OK: issue #{issue_number} iteration {iteration} "
        f"has a Dev Agent result; proceeding."
    )


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
        else "\u274c needs rework \u2014 the harness will auto-retry this issue "
        "with the Test/Review feedback above (docs/adr/0015), until MAX_ITERATIONS"
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
