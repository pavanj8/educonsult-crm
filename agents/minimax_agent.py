#!/usr/bin/env python3
"""Direct-MiniMax agent loop -- the harness's execution engine (docs/adr/0019).

Replaces the Cursor SDK local runtime. Drives the agents with a self-contained
tool-calling loop over MiniMax's **Anthropic-compatible** Messages API (via the
`anthropic` client pointed at ANTHROPIC_BASE_URL). Rather than pay for Cursor
inference, ADR-0019 drops the Cursor engine entirely.

The loop gives the model the same capabilities the Cursor local runtime did --
read files, write files, list directories, run shell commands -- all scoped to
a working directory. It runs entirely in-process inside the GitHub Actions job
(never a personal machine); the Test Agent still boots the backend on
127.0.0.1 *inside that runner*.

`CURSOR_API_KEY` is intentionally NOT consumed here, and the cursor-sdk package
is not installed (its presence hijacks HTTP clients onto the Cursor gateway --
docs/adr/0019 follow-up).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import llm_env

# Safety rails. A run that needs more than this many model turns is almost
# certainly stuck; failing closed here surfaces as agent:needs-rework rather
# than burning the token budget indefinitely. Test/Review agents are
# legitimately tool-heavy (write tests, run the full suite, verify), so this
# is generous; a `report_tool` caller also gets a forced final report on the
# last turn instead of dying as max_turns (see run_agent).
MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "140"))
# Anthropic Messages API requires an explicit output cap per call.
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "16384"))
COMMAND_TIMEOUT_SEC = 600
# Keep individual tool results from blowing the context window. Tail-truncate
# so the most recent (usually most relevant) output survives.
MAX_TOOL_OUTPUT_CHARS = 60_000
MAX_FILE_READ_CHARS = 120_000

# Anthropic tool schema: {name, description, input_schema}.
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file, relative to the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the working directory."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a UTF-8 text file (parent dirs are created).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the working directory."},
                "content": {"type": "string", "description": "Full new file contents."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List the entries of a directory relative to the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default '.')."},
            },
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command in the working directory and return its combined "
            "stdout/stderr and exit code. Use this for git, pytest, python, grep, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "timeout": {"type": "integer", "description": f"Seconds (default {COMMAND_TIMEOUT_SEC})."},
            },
            "required": ["command"],
        },
    },
]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"[... {len(text) - limit} chars truncated ...]\n" + text[-limit:]


def _resolve(cwd: Path, rel: str) -> Path:
    """Resolve `rel` under `cwd`, refusing to escape the working directory."""
    target = (cwd / rel).resolve()
    if target != cwd and cwd not in target.parents:
        raise ValueError(f"path escapes the working directory: {rel}")
    return target


def _read_file(cwd: Path, path: str) -> str:
    target = _resolve(cwd, path)
    if not target.exists():
        return f"ERROR: no such file: {path}"
    try:
        return _truncate(target.read_text(), MAX_FILE_READ_CHARS)
    except (UnicodeDecodeError, OSError) as err:
        return f"ERROR: could not read {path}: {err}"


def _write_file(cwd: Path, path: str, content: str) -> str:
    target = _resolve(cwd, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Wrote {len(content)} chars to {path}"


def _list_dir(cwd: Path, path: str) -> str:
    target = _resolve(cwd, path or ".")
    if not target.is_dir():
        return f"ERROR: not a directory: {path}"
    entries = sorted(
        (f"{p.name}/" if p.is_dir() else p.name) for p in target.iterdir()
    )
    return "\n".join(entries) or "(empty directory)"


def _run_command(cwd: Path, command: str, timeout: int) -> str:
    try:
        proc = subprocess.run(
            command, shell=True, cwd=str(cwd),
            capture_output=True, text=True, timeout=timeout or COMMAND_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout or COMMAND_TIMEOUT_SEC}s: {command}"
    body = _truncate(proc.stdout + proc.stderr, MAX_TOOL_OUTPUT_CHARS)
    return f"exit_code={proc.returncode}\n{body}"


def _dispatch(name: str, args: dict, cwd: Path) -> str:
    try:
        if name == "read_file":
            return _read_file(cwd, args["path"])
        if name == "write_file":
            return _write_file(cwd, args["path"], args.get("content", ""))
        if name == "list_dir":
            return _list_dir(cwd, args.get("path", "."))
        if name == "run_command":
            return _run_command(cwd, args["command"], int(args.get("timeout", COMMAND_TIMEOUT_SEC)))
        return f"ERROR: unknown tool: {name}"
    except KeyError as err:
        return f"ERROR: missing required argument {err}"
    except Exception as err:  # noqa: BLE001 -- surface any tool failure to the model
        return f"ERROR: {name} failed: {err}"


def run_agent(
    prefix: str,
    prompt: str,
    model: str,
    cwd: str | os.PathLike[str],
    *,
    max_turns: int = MAX_TURNS,
    report_tool: dict | None = None,
) -> tuple[str, str]:
    """Drive a MiniMax (Anthropic Messages API) tool-calling agent to completion.

    Returns ``(status, text)`` where ``status`` is one of ``completed``,
    ``error``, or ``max_turns`` and ``text`` is the concatenated assistant
    prose. On a hard failure ``text`` is a diagnostic string so the GitHub
    issue comment is never a bare "UNKNOWN".

    ``report_tool`` (Test/Review agents): an Anthropic tool schema the model
    MUST call to deliver its final structured report. When it does, the tool's
    input is captured and appended to the returned text as a ```json block (so
    the callers' existing parsers work unchanged), and the run ends. This
    replaces the fragile "emit a ```json block in free text" contract, which
    silently produced ``UNKNOWN`` when the model ran out of turns or formatted
    loosely. On the last allowed turn the report tool is *forced* (tool_choice)
    so the run yields a real report instead of dying as ``max_turns``.
    """
    cwd = Path(cwd).resolve()
    try:
        client = llm_env.minimax_client()
    except Exception as err:  # noqa: BLE001 -- missing token / client init
        print(f"[{prefix}] STARTUP FAILURE: {err}", file=sys.stderr)
        return "error", str(err)

    report_name = report_tool["name"] if report_tool else None
    all_tools = TOOLS + ([report_tool] if report_tool else [])

    messages: list[dict] = [{"role": "user", "content": prompt}]
    final_text_parts: list[str] = []

    def _emit_report(payload: dict) -> tuple[str, str]:
        """Append the captured report as a ```json block and finish."""
        final_text_parts.append("\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n")
        print(f"\n\n--- {prefix} finished: submitted structured report ---")
        return "completed", "".join(final_text_parts)

    for turn in range(1, max_turns + 1):
        # On the final allowed turn, force the report tool so we get a real
        # report rather than dying as max_turns (report-tool callers only).
        force_report = report_tool is not None and turn == max_turns
        create_kwargs: dict = {
            "model": model, "max_tokens": MAX_TOKENS, "messages": messages,
            "tools": [report_tool] if force_report else all_tools,
        }
        if force_report:
            create_kwargs["tool_choice"] = {"type": "tool", "name": report_name}
        try:
            resp = client.messages.create(**create_kwargs)
        except Exception as err:  # noqa: BLE001 -- auth/model/rate-limit failures
            if force_report and "tool_choice" in create_kwargs:
                # Some backends may reject forced tool_choice; retry once softly.
                create_kwargs.pop("tool_choice", None)
                try:
                    resp = client.messages.create(**create_kwargs)
                except Exception as err2:  # noqa: BLE001
                    err = err2
                else:
                    err = None
            if err is not None:
                hint = (
                    f"MiniMax (Anthropic API) call failed on turn {turn} (model={model!r}): "
                    f"{err}. If this is an invalid-model or auth/quota error, verify the "
                    f"model ID, ANTHROPIC_AUTH_TOKEN, and Token Plan balance (docs/adr/0019)."
                )
                print(f"[{prefix}] {hint}", file=sys.stderr)
                return "error", hint

        assistant_blocks: list[dict] = []
        tool_uses: list = []
        for block in resp.content:
            if block.type == "text":
                sys.stdout.write(block.text)
                sys.stdout.flush()
                final_text_parts.append(block.text)
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_blocks.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )
                tool_uses.append(block)
        messages.append({"role": "assistant", "content": assistant_blocks})

        # The model delivered its final report -> capture and finish.
        for tu in tool_uses:
            if tu.name == report_name:
                return _emit_report(tu.input if isinstance(tu.input, dict) else {})

        if resp.stop_reason != "tool_use":
            print(f"\n\n--- {prefix} finished: stop_reason={resp.stop_reason} turns={turn} ---")
            return "completed", "".join(final_text_parts)

        tool_results: list[dict] = []
        for tu in tool_uses:
            args = tu.input if isinstance(tu.input, dict) else {}
            print(f"\n[{prefix}] tool: {tu.name}({json.dumps(args)[:200]})")
            result = _dispatch(tu.name, args, cwd)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": tu.id, "content": result}
            )
        messages.append({"role": "user", "content": tool_results})

    hint = (
        f"Agent exceeded {max_turns} turns without producing a final message "
        f"(docs/adr/0019 safety rail)."
    )
    print(f"[{prefix}] {hint}", file=sys.stderr)
    return "max_turns", "".join(final_text_parts) or hint
