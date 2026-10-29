"""Shared parts of the two hooks Claude Code runs: at session start and after each tool page is used.

A hook must never get in the person's way. It prints nothing (text printed at session
start would be added to the conversation), it ends with exit code 0 whatever happens,
and it acts only inside an assistant folder.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from ja import workspace


def read_input(stream: Any = None) -> dict[str, Any]:
    """The JSON object Claude Code sends on standard input, or an empty one."""
    stream = stream or sys.stdin
    try:
        if stream.isatty():
            return {}
        data = json.loads(stream.read() or "{}")
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def folder_root(data: dict[str, Any]) -> Path | None:
    """The assistant folder the session works in: the hook's folder or the nearest marked parent.

    JA_WORKSPACE is not used here, so a session in another folder never touches an assistant folder.
    """
    start = data.get("cwd")
    if not isinstance(start, str) or not start:
        start = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        here = Path(start).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    for candidate in (here, *here.parents):
        try:
            if workspace.is_root(candidate):
                return candidate
        except OSError:
            return None
    return None


def run_quietly(work: Callable[[dict[str, Any]], None]) -> int:
    """Run the hook's work with all output swallowed and every error caught. Always returns 0."""
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            work(read_input())
    except BaseException:  # noqa: BLE001  a hook must never fail the session or the tool call
        pass
    return 0
