#!/usr/bin/env python3
"""Direct-MiniMax agent loop -- the harness's execution engine (docs/adr/0019).

Replaces the Cursor SDK local runtime. ADR-0018 established that `cursor_sdk`
validates model IDs against Cursor's own catalog and rejects MiniMax IDs, so
MiniMax inference could not be routed through `Agent.create()`. Rather than pay
for Cursor inference, ADR-0019 drops the Cursor engine entirely and drives the
agents with this self-contained tool-calling loop over MiniMax's
OpenAI-compatible `chat/completions` API.

The loop gives the model the same capabilities the Cursor local runtime did --
read files, write files, list directories, run shell commands -- all scoped to
a working directory. It runs entirely in-process inside the GitHub Actions job
(never a personal machine), exactly like the Cursor SDK did before; the Test
Agent still boots the backend on 127.0.0.1 *inside that runner*.

`CURSOR_API_KEY` is intentionally NOT consumed here. It stays configured in the
workflows/secrets but dormant, mirroring how `MINIMAX_API_KEY` was kept dormant
before this ADR.
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
# than burning the MiniMax token budget indefinitely.
MAX_TURNS = 80
COMMAND_TIMEOUT_SEC = 600
# Keep individual tool results from blowing the context window. Tail-truncate
# so the most recent (usually most relevant) output survives.
MAX_TOOL_OUTPUT_CHARS = 60_000
MAX_FILE_READ_CHARS = 120_000

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file, relative to the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the working directory."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a UTF-8 text file (parent dirs are created).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the working directory."},
                    "content": {"type": "string", "description": "Full new file contents."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the entries of a directory relative to the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default '.')."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the working directory and return its combined "
                "stdout/stderr and exit code. Use this for git, pytest, python, grep, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute."},
                    "timeout": {"type": "integer", "description": f"Seconds (default {COMMAND_TIMEOUT_SEC})."},
                },
                "required": ["command"],
            },
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


def _assistant_dict(msg) -> dict:
    d: dict = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return d


def run_agent(
    prefix: str,
    prompt: str,
    model: str,
    cwd: str | os.PathLike[str],
    *,
    max_turns: int = MAX_TURNS,
) -> tuple[str, str]:
    """Drive a MiniMax tool-calling agent to completion.

    Returns ``(status, text)`` where ``status`` is one of ``completed``,
    ``error``, or ``max_turns`` and ``text`` is the concatenated assistant
    prose (the callers parse a trailing ```json block out of it, same as they
    did with the Cursor SDK output). On a hard failure ``text`` is a diagnostic
    string so the GitHub issue comment is never a bare "UNKNOWN".
    """
    cwd = Path(cwd).resolve()
    try:
        client = llm_env.minimax_client()
    except RuntimeError as err:
        print(f"[{prefix}] STARTUP FAILURE: {err}", file=sys.stderr)
        return "error", str(err)

    messages: list[dict] = [{"role": "user", "content": prompt}]
    final_text_parts: list[str] = []

    for turn in range(1, max_turns + 1):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=TOOLS, temperature=0.2,
            )
        except Exception as err:  # noqa: BLE001 -- network/model-id failures land here
            hint = (
                f"MiniMax API call failed on turn {turn} (model={model!r}): {err}. "
                f"If this is an invalid-model error, verify the ID against your "
                f"MiniMax account catalog (docs/adr/0019)."
            )
            print(f"[{prefix}] {hint}", file=sys.stderr)
            return "error", hint

        msg = resp.choices[0].message
        messages.append(_assistant_dict(msg))
        if msg.content:
            sys.stdout.write(msg.content)
            sys.stdout.flush()
            final_text_parts.append(msg.content)

        tool_calls = msg.tool_calls or []
        if not tool_calls:
            print(f"\n\n--- {prefix} finished: status=completed turns={turn} ---")
            return "completed", "".join(final_text_parts)

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as err:
                result = f"ERROR: could not parse arguments for {tc.function.name}: {err}"
            else:
                print(f"\n[{prefix}] tool: {tc.function.name}({json.dumps(args)[:200]})")
                result = _dispatch(tc.function.name, args, cwd)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    hint = (
        f"Agent exceeded {max_turns} turns without producing a final message "
        f"(docs/adr/0019 safety rail)."
    )
    print(f"[{prefix}] {hint}", file=sys.stderr)
    return "max_turns", "".join(final_text_parts) or hint
