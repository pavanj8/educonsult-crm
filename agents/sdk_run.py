"""Shared helpers for Cursor SDK local runs.

`Cursor.models.list()` returns IDs the account can *see*; the local
runtime only actually executes a subset of those. Passing an ID that is
listed but not locally executable returns `result.status == "error"` in
a few seconds with empty assistant text and an empty `result.result` —
easy to misread as a Test/Review failure. See docs/adr/0014.
"""
from __future__ import annotations

import sys


def finish_run(prefix: str, result: object, streamed_text: str) -> tuple[str, str]:
    """Log wait() details and return (status, text) for the caller to parse.

    On a silent local-runtime rejection, the returned text is a diagnostic
    string so the GitHub issue comment is not just "UNKNOWN / 0 failures".
    """
    status = getattr(result, "status", "unknown")
    extra = getattr(result, "result", "") or ""
    duration = getattr(result, "duration_ms", "?")
    print(f"\n\n--- {prefix} run finished: status={status} duration_ms={duration} ---")
    if extra:
        print(f"[{prefix}] run.result={extra}")
    if status == "error" and not streamed_text:
        hint = (
            f"Local SDK run failed with status=error and no assistant output "
            f"(duration_ms={duration}). This usually means the chosen model "
            f"is listed for the account but is not executable on the local "
            f"runtime (docs/adr/0014). run.result={extra!r}"
        )
        print(f"[{prefix}] {hint}", file=sys.stderr)
        return "error", hint
    return status, streamed_text or extra
