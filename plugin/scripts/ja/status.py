"""Effective tool status, computed from checks and source freshness. Never stored."""

from __future__ import annotations

from datetime import date

from ja.registry import Tool
from ja.sources import Source

LABELS: dict[str, str] = {
    "working": "Working",
    "draft-not-checked": "Draft, not checked",
    "needs-update": "Needs update",
    "being-built": "Being built",
    "paused": "Paused",
    "retired": "Retired",
}

RHYTHM_WORDS: dict[str, str] = {
    "on-demand": "When you need it",
    "daily": "Runs daily",
    "weekly": "Runs weekly",
    "monthly": "Runs monthly",
    "quarterly": "Runs quarterly",
}

HELD = ("retired", "paused", "being-built")
UNKNOWN_SOURCE = "Uses a source that is not on your sources list"


def label(status: str) -> str:
    return LABELS.get(status, status)


def _problems(tool: Tool, sources_by_id: dict[str, Source], today: date) -> list[str]:
    out: list[str] = []
    check = tool.last_check
    if check and check.get("result") == "fail":
        detail = (check.get("detail") or "").strip()
        out.append(f"Last check failed: {detail}" if detail else "Last check failed")
    for sid in tool.sources:
        src = sources_by_id.get(sid)
        if src is None:
            if UNKNOWN_SOURCE not in out:
                out.append(UNKNOWN_SOURCE)
            continue
        if src.duplicate:
            out.append(f"Your sources list has two entries for {sid}")
            continue
        if src.in_future(today):
            out.append(f"The export date for {src.name} is in the future. Check the date.")
        elif src.is_stale(today):
            age = src.age_days(today)
            if age is None:
                out.append(f"I do not know how old your copy of {src.name} is")
            else:
                out.append(f"Your copy of {src.name} is {age} days old")
        if src.changed:
            out.append(f"{src.name} changed since this tool was checked")
    return out


def check_passed(tool: Tool) -> bool:
    return bool(tool.last_check) and tool.last_check.get("result") == "pass"


def effective_status(tool: Tool, sources_by_id: dict[str, Source], today: date) -> str:
    if tool.status in HELD:
        return tool.status
    if _problems(tool, sources_by_id, today):
        return "needs-update"
    if tool.status == "working" and not check_passed(tool):
        return "draft-not-checked"
    return tool.status


def reasons(tool: Tool, sources_by_id: dict[str, Source], today: date) -> list[str]:
    """Plain sentences explaining a needs-update status; empty for any other status."""
    if tool.status in HELD:
        return []
    return _problems(tool, sources_by_id, today)
