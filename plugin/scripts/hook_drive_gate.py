#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check before each Drive create action: in an assistant folder, allow only the drafts folder.

Outside an assistant folder it prints nothing, so the normal permission rules apply.
Inside one it prints an allow or deny decision. If this program fails or times out,
the hook setting blocks the action.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ja import drive, hooks  # noqa: E402
from ja.workspace import Paths  # noqa: E402


def decision(data: dict) -> dict | None:
    if data.get("tool_name") != drive.CREATE:
        return None
    root = hooks.folder_root(data)
    if root is None:
        return None
    try:
        allowed, reason = drive.decide(Paths(root), data.get("tool_input") or {})
    except Exception:  # noqa: BLE001  inside an assistant folder, any doubt blocks the action
        allowed, reason = False, drive.BROKEN_REASON
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "allow" if allowed else "deny",
                                   "permissionDecisionReason": reason}}


if __name__ == "__main__":
    out = decision(hooks.read_input())
    if out is not None:
        print(json.dumps(out))
    sys.exit(0)
