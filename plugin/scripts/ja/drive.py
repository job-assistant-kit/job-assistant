"""Saving accepted results into one private drafts folder in Google Drive.

The assistant may create files in Drive only with the Drive connector's create action, and
only inside the drafts folder the person chose. Three things hold that line:

- The settings file blocks the create action whenever saving is off.
- A check runs before every create action (hook_drive_gate.py, using decide() below). It
  lets through only the drafts folder itself, while it is being made, and new files inside
  it. If the check cannot run, Claude Code blocks the action.
- Every other Drive write action (update, share, copy, trash) stays blocked.

The choice lives in .claude/drive-drafts.json. Claude Code asks before the assistant edits
files under .claude, so only the helper changes it.

This module uses the standard library only, so the check can run without extra packages.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from typing import Any

from ja import settings
from ja.workspace import Paths, assistant_name

CREATE = "mcp__claude_ai_Google_Drive__create_file"
FOLDER_MIME = "application/vnd.google-apps.folder"
_ID = re.compile(r"^[A-Za-z0-9_-]{10,200}$")
_LINK = re.compile(r"/folders/([A-Za-z0-9_-]{10,200})")
STATES = ("off", "creating", "on")

OFF_REASON = "Saving to Drive is turned off for this assistant. Keep the draft in the assistant folder."
CREATING_REASON = "Only the drafts folder can be created in Drive right now."
ON_REASON = "Drafts can only be saved as new files inside the drafts folder in Drive."
BROKEN_REASON = "The Drive drafts setting could not be read, so saving to Drive is blocked."


class DriveProblem(ValueError):
    """The setting cannot be read or the request cannot be used. The message is plain."""


def config_path(paths: Paths) -> Any:
    return paths.root / ".claude" / "drive-drafts.json"


def load(paths: Paths) -> dict[str, Any]:
    path = config_path(paths)
    if not path.is_file():
        return {"state": "off"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise DriveProblem(BROKEN_REASON) from None
    if not isinstance(data, dict) or data.get("state") not in STATES:
        raise DriveProblem(BROKEN_REASON)
    if data["state"] == "creating" and not isinstance(data.get("title"), str):
        raise DriveProblem(BROKEN_REASON)
    if data["state"] == "on" and not (isinstance(data.get("folder_id"), str) and _ID.match(data["folder_id"])
                                      and isinstance(data.get("private"), bool)):
        raise DriveProblem(BROKEN_REASON)
    return data


def _save(paths: Paths, data: dict[str, Any]) -> None:
    path = config_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def kept_open(paths: Paths) -> set[str]:
    """Action names the setup steps must not block, because saving to Drive is on."""
    try:
        state = load(paths)["state"]
    except DriveProblem:
        return set()
    return {CREATE} if state in ("creating", "on") else set()


def folder_id_from(value: str) -> str:
    """A folder id from the id itself or a Drive folder link."""
    value = value.strip()
    match = _LINK.search(value)
    if match:
        return match.group(1)
    if _ID.match(value):
        return value
    raise DriveProblem("That does not look like a Drive folder link. Open the folder in Drive and copy the "
                       "link from the address bar.")


def start(paths: Paths, title: str | None = None) -> str:
    """Get ready to create the drafts folder. Returns the folder's title."""
    title = (title or f"{assistant_name(paths)} drafts").strip()
    if not title:
        raise DriveProblem("The folder name cannot be empty.")
    _save(paths, {"state": "creating", "title": title})
    settings.set_blocked(paths, CREATE, False)
    return title


def set_folder(paths: Paths, folder: str, private: bool, today: date, link: str | None = None) -> dict[str, Any]:
    folder_id = folder_id_from(folder)
    data = {"state": "on", "folder_id": folder_id, "private": private, "checked": today.isoformat(),
            "link": link or f"https://drive.google.com/drive/folders/{folder_id}"}
    _save(paths, data)
    settings.set_blocked(paths, CREATE, False)
    return data


def off(paths: Paths) -> None:
    settings.set_blocked(paths, CREATE, True)
    _save(paths, {"state": "off"})


def target(paths: Paths, tool_name: str, confidential: bool, now: datetime) -> tuple[bool, str, dict[str, str]]:
    """Whether to save this tool's accepted result to Drive, why, and where."""
    data = load(paths)
    if data["state"] != "on":
        return False, "Saving to Drive is off. The result stays in the assistant folder.", {}
    if confidential and not data["private"]:
        return False, ("Not saved to Drive: this tool's results are confidential and the drafts folder is "
                       "shared with other people. The result stays in the assistant folder."), {}
    title = f"{tool_name} draft {now.strftime('%Y-%m-%d %H:%M')}"
    return True, "Save a copy to the drafts folder in Drive.", {"folder": data["folder_id"], "title": title,
                                                               "link": data.get("link", "")}


def _content_given(tool_input: dict[str, Any]) -> bool:
    return any(tool_input.get(k) for k in ("textContent", "base64Content", "content"))


def decide(paths: Paths, tool_input: dict[str, Any]) -> tuple[bool, str]:
    """The check before each Drive create action: (allowed, reason)."""
    try:
        data = load(paths)
    except DriveProblem as exc:
        return False, str(exc)
    if not isinstance(tool_input, dict):
        return False, OFF_REASON if data["state"] == "off" else ON_REASON
    mime = tool_input.get("contentMimeType") or tool_input.get("mimeType")
    parent = tool_input.get("parentId")
    if data["state"] == "creating":
        ok = (mime == FOLDER_MIME and not parent and tool_input.get("title") == data["title"]
              and tool_input.get("inheritedPermissionsDisabled") is True and not _content_given(tool_input))
        return ok, "Creating the drafts folder." if ok else CREATING_REASON
    if data["state"] == "on":
        ok = parent == data["folder_id"] and mime != FOLDER_MIME and bool(str(tool_input.get("title") or "").strip())
        return ok, "Saving a new draft in the drafts folder." if ok else ON_REASON
    return False, OFF_REASON
