"""Add and change tool records. Every change keeps the record valid under the registry rules."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ja import registry
from ja.registry import RECORD_NAME, Tool
from ja.status import check_passed
from ja.workspace import Paths

ADOPTED_TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "adopted-skill.md"
ADOPTED_REQUIRED = ("lives_at", "how_to_run")
NOT_RECORDED = "Not recorded yet. Ask the person."
SETTABLE = ("working", "draft-not-checked", "being-built", "paused")


class ToolProblem(ValueError):
    """A tool change cannot be made. The message is plain."""


def _read_record(file: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(Path(file).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        raise ToolProblem(f"I could not read {file}. Check that the file exists.") from None
    except yaml.YAMLError:
        raise ToolProblem(f"The tool record in {file} could not be read.") from None
    if not isinstance(data, dict):
        raise ToolProblem(f"The tool record in {file} must hold named fields.")
    return data


def _exists(paths: Paths, tool_id: str) -> bool:
    return (paths.skills_dir / tool_id).exists() or (paths.archive_dir / tool_id).exists()


def _text(value: Any) -> str:
    if value is None or (isinstance(value, (str, list)) and not value):
        return NOT_RECORDED
    if isinstance(value, list):
        return "\n".join(f"- {' '.join(str(v).split())}" for v in value)
    return str(value).strip()


def adopted_skill(tool: Tool) -> str:
    """The instructions page for an inherited tool, filled from its record."""
    examples = "; ".join(f'"{e}"' for e in tool.examples)
    description = f"{' '.join(tool.does.split())} Use when the person says things like {examples}."
    values = {
        "skill_name": tool.id,
        "description": json.dumps(description[:1000], ensure_ascii=False),
        "name": tool.name,
        "does": tool.does,
        "lives_at": _text(tool.extra.get("lives_at")),
        "how_to_run": _text(tool.extra.get("how_to_run")),
        "inputs": _text(tool.extra.get("inputs")),
        "outputs": _text(tool.extra.get("outputs")),
        "last_good_run": _text(tool.extra.get("last_good_run")),
    }
    text = ADOPTED_TEMPLATE.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def add_from_file(paths: Paths, file: Path, today: date) -> Tool:
    data = registry._normalize_dates(_read_record(file))
    data.setdefault("created", today.isoformat())
    tool_id = data.get("id")
    try:
        tool = Tool.from_dict(data, folder=tool_id if isinstance(tool_id, str) else None)
    except registry.InvalidTool as exc:
        raise ToolProblem(str(exc)) from None
    if tool.kind == "adopted":
        for key in ADOPTED_REQUIRED:
            if not isinstance(tool.extra.get(key), str) or not tool.extra[key].strip():
                raise ToolProblem(f"{tool.id}: {key} is missing")
    if _exists(paths, tool.id):
        raise ToolProblem(f"There is already a tool called {tool.id}.")
    folder = paths.skills_dir / tool.id
    folder.mkdir(parents=True)
    tool.path = folder / RECORD_NAME
    registry.save(paths, tool)
    if tool.kind == "adopted":
        (folder / "SKILL.md").write_text(adopted_skill(tool), encoding="utf-8")
    return tool


def _find(paths: Paths, tool_id: str) -> Tool:
    try:
        return registry.find(paths, tool_id)
    except registry.ToolNotFound:
        raise ToolProblem(f"There is no tool called {tool_id}.") from None
    except registry.InvalidTool as exc:
        raise ToolProblem(f"I could not read this tool's record: {exc}") from None


def improve(paths: Paths, tool_id: str, change: str, reason: str, today: date) -> Tool:
    if not change.strip():
        raise ToolProblem("Describe the change in a few words.")
    tool = _find(paths, tool_id)
    tool.improvements.append({"date": today.isoformat(), "change": change.strip(), "reason": reason.strip()})
    registry.save(paths, tool)
    return tool


def set_status(paths: Paths, tool_id: str, new: str) -> Tool:
    if new == "needs-update":
        raise ToolProblem("That status is worked out from checks and cannot be set by hand.")
    if new == "retired":
        raise ToolProblem("Retiring moves the tool to the archive. Use the retire step instead.")
    if new not in SETTABLE:
        raise ToolProblem("The status must be one of " + ", ".join(SETTABLE) + ".")
    tool = _find(paths, tool_id)
    tool.status = new
    registry.save(paths, tool)
    return tool


def _move(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dest)


def retire(paths: Paths, tool_id: str) -> Tool:
    tool = _find(paths, tool_id)
    target = paths.archive_dir / tool_id
    if target.exists():
        raise ToolProblem(f"The archive already has a tool called {tool_id}. Restore or remove that one first.")
    _move(paths.skills_dir / tool_id, target)
    tool.path = target / RECORD_NAME
    tool.status = "retired"
    registry.save(paths, tool)
    return tool


def restore(paths: Paths, tool_id: str) -> Tool:
    record = paths.archive_dir / tool_id / RECORD_NAME
    if not registry.ID_PATTERN.match(tool_id) or not record.is_file():
        raise ToolProblem(f"There is no retired tool called {tool_id}.")
    target = paths.skills_dir / tool_id
    if target.exists():
        raise ToolProblem(f"There is already an active tool called {tool_id}.")
    try:
        tool = registry.load_file(record)
    except registry.InvalidTool as exc:
        raise ToolProblem(f"I could not read this tool's record: {exc}") from None
    _move(paths.archive_dir / tool_id, target)
    tool.path = target / RECORD_NAME
    tool.status = "working" if check_passed(tool) else "draft-not-checked"
    registry.save(paths, tool)
    return tool
