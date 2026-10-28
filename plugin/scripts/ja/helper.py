"""Keep the helper's current location recorded in the assistant folder.

The tools in the assistant folder call the helper by its full path, because they are
not part of the installed kit and cannot look it up. An update to the kit moves the
helper, so every run checks the recorded path and, when it changed, rewrites the
marker file, the allow rules in the local settings, and the tool pages that name it.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ja.workspace import MARKER, Paths

SCRIPT = Path(__file__).resolve().parents[1] / "ja.py"
MARKER_NOTE = "# This file marks this folder as a job assistant folder. Please keep it."
_LINE = re.compile(r"^([a-z_]+): (.*)$")
_ANY_HELPER = re.compile(r"/[^\"'\n ]*/scripts/ja\.py")


def read_marker(paths: Paths) -> dict[str, str]:
    try:
        text = (paths.root / MARKER).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    return {m.group(1): m.group(2).strip() for line in text.splitlines() if (m := _LINE.match(line))}


def write_marker(paths: Paths, values: dict[str, str]) -> None:
    target = paths.root / MARKER
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [MARKER_NOTE] + [f"{k}: {' '.join(str(v).split())}" for k, v in values.items()]
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def allow_rules(script: str) -> list[str]:
    """The two forms of the allow rule for one helper path, unquoted and quoted."""
    return [f"Bash(uv run --script {script} *)", f'Bash(uv run --script "{script}" *)']


def _local_settings(paths: Paths) -> Path:
    return paths.root / ".claude" / "settings.local.json"


def _update_rules(paths: Paths, old: str | None, new: str) -> None:
    target = _local_settings(paths)
    data: dict[str, Any] = {}
    if target.is_file():
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        return
    allow = perms.setdefault("allow", [])
    if not isinstance(allow, list):
        return
    stale = set(allow_rules(old)) if old else set()
    kept = [r for r in allow if r not in stale]
    perms["allow"] = kept + [r for r in allow_rules(new) if r not in kept]
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _update_pages(paths: Paths, old: str | None, new: str) -> None:
    for base in (paths.skills_dir, paths.archive_dir):
        if not base.is_dir():
            continue
        for page in base.glob("*/SKILL.md"):
            text = page.read_text(encoding="utf-8")
            fixed = text.replace(old, new) if old and old in text else _ANY_HELPER.sub(lambda _: new, text)
            if fixed != text:
                page.write_text(fixed, encoding="utf-8")


def sync(paths: Paths, script: Path = SCRIPT) -> bool:
    """Record the helper's current path. Returns True when something changed. Never raises."""
    new = str(script)
    values = read_marker(paths)
    old = values.get("ja_path")
    if old == new:
        return False
    for step in (lambda: _update_rules(paths, old, new), lambda: _update_pages(paths, old, new)):
        try:
            step()
        except (OSError, UnicodeDecodeError, ValueError):
            pass
    try:
        write_marker(paths, {**values, "ja_path": new})
    except OSError:
        return False
    return True
