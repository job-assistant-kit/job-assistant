"""Write protection for the assistant folder (.claude/settings.json).

Claude Code enforces permissions.deny: a denied connector action cannot run, whatever
the conversation says. The setup steps list the connector actions that write, post,
share, or delete, and pass their names here.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from ja.workspace import Paths

NAME = re.compile(r"^mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_-]+$")


class SettingsProblem(ValueError):
    """The settings file or the names cannot be used. The message is plain."""


def load(paths: Paths) -> dict[str, Any]:
    if not paths.settings.is_file():
        return {}
    try:
        data = json.loads(paths.settings.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise SettingsProblem("The assistant settings file could not be read, so I did not change it.") from None
    if not isinstance(data, dict):
        raise SettingsProblem("The assistant settings file is not in the expected shape, so I did not change it.")
    return data


def _list(perms: dict[str, Any], key: str) -> list[str]:
    value = perms.get(key, [])
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise SettingsProblem("The assistant settings file is not in the expected shape, so I did not change it.")
    return value


def deny(paths: Paths, names: list[str]) -> int:
    """Add connector action names to the deny list. Returns how many were new."""
    bad = [n for n in names if not NAME.match(n)]
    if bad or not names:
        shown = ", ".join(repr(n) for n in bad) or "nothing"
        raise SettingsProblem(f"I can only block connector actions, and these are not: {shown}. Nothing was changed.")
    data = load(paths)
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        raise SettingsProblem("The assistant settings file is not in the expected shape, so I did not change it.")
    current = _list(perms, "deny")
    added = 0
    for name in names:
        if name not in current:
            current.append(name)
            added += 1
    perms["deny"] = current
    _write(paths, data)
    return added


def _write(paths: Paths, data: dict[str, Any]) -> None:
    paths.settings.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.settings.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, paths.settings)


def set_blocked(paths: Paths, name: str, blocked: bool) -> None:
    """Add one connector action to the deny list, or take it off."""
    if not NAME.match(name):
        raise SettingsProblem(f"I can only block connector actions, and this is not: {name!r}. Nothing was changed.")
    data = load(paths)
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        raise SettingsProblem("The assistant settings file is not in the expected shape, so I did not change it.")
    current = [n for n in _list(perms, "deny") if n != name]
    if blocked:
        current.append(name)
    perms["deny"] = current
    _write(paths, data)


def show(paths: Paths) -> tuple[list[str], list[str]]:
    """(blocked actions, actions allowed without asking)."""
    perms = load(paths).get("permissions", {})
    if not isinstance(perms, dict):
        return [], []
    return _list(perms, "deny"), _list(perms, "allow")
