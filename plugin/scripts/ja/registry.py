"""Load, check, and save tool records (tool.yaml)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from ja.workspace import Paths

RECORD_NAME = "tool.yaml"
ID_PATTERN = re.compile(r"^[a-z0-9-]+$")
KINDS = ("built", "adopted")
STATUSES = ("working", "draft-not-checked", "being-built", "paused", "retired")
RHYTHMS = ("on-demand", "daily", "weekly", "monthly", "quarterly")
CHECK_RESULTS = ("pass", "fail")

FIELDS = (
    "id", "name", "does", "examples", "kind", "recipe", "status", "rhythm", "sources",
    "data_path", "manual_steps", "your_minutes_by_hand", "confidential", "exec_numbers",
    "rules", "improvements", "last_check", "created",
)
REQUIRED = ("id", "name", "does", "examples", "kind", "status", "rhythm", "data_path", "created")


class InvalidTool(ValueError):
    """A tool record breaks the contract. The message is '<id>: <field> <problem>'."""


class ToolNotFound(LookupError):
    """No tool record with that id."""


@dataclass
class Tool:
    id: str
    name: str
    does: str
    examples: list[str]
    kind: str
    status: str
    rhythm: str
    data_path: str
    created: str
    recipe: str | None = None
    sources: list[str] = field(default_factory=list)
    manual_steps: list[str] = field(default_factory=list)
    your_minutes_by_hand: int | None = None
    confidential: bool = False
    exec_numbers: bool = False
    rules: list[str] = field(default_factory=list)
    improvements: list[dict[str, str]] = field(default_factory=list)
    last_check: dict[str, str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], folder: str | None = None, path: Path | None = None) -> "Tool":
        """Build a Tool from raw record data. Raises InvalidTool with a plain message."""
        if not isinstance(data, dict):
            raise InvalidTool(f"{folder or '?'}: tool.yaml must hold named fields")
        data = _normalize_dates(data)
        label = folder or (data.get("id") if isinstance(data.get("id"), str) else None) or "?"
        problem = _first_problem(data, folder)
        if problem:
            raise InvalidTool(f"{label}: {problem}")
        known = {k: data[k] for k in FIELDS if data.get(k) is not None}
        extra = {k: v for k, v in data.items() if k not in FIELDS}
        return cls(**known, extra=extra, path=path)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {k: getattr(self, k) for k in FIELDS}
        out.update(self.extra)
        return out


def _normalize_dates(data: dict[str, Any]) -> dict[str, Any]:
    """YAML reads bare dates as date objects; keep them as ISO text."""
    def fix(v: Any) -> Any:
        if isinstance(v, datetime):
            return v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        return v

    out = {k: fix(v) for k, v in data.items()}
    if isinstance(out.get("last_check"), dict):
        out["last_check"] = {k: fix(v) for k, v in out["last_check"].items()}
    if isinstance(out.get("improvements"), list):
        out["improvements"] = [
            {k: fix(v) for k, v in item.items()} if isinstance(item, dict) else item
            for item in out["improvements"]
        ]
    return out


def is_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def _is_text(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _is_text_list(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _first_problem(d: dict[str, Any], folder: str | None) -> str | None:
    """Return the first contract problem as '<field> <problem>', or None."""
    for name in REQUIRED:
        if name not in d or d[name] is None:
            return f"{name} is missing"
    if not isinstance(d["id"], str) or not ID_PATTERN.match(d["id"]):
        return "id must use only lowercase letters, numbers, and hyphens"
    if folder is not None and d["id"] != folder:
        return "id must match its folder name"
    for name in ("name", "does", "data_path"):
        if not _is_text(d[name]):
            return f"{name} must be text"
    if not _is_text_list(d["examples"]):
        return "examples must be a list of text"
    if not d["examples"]:
        return "examples must list at least one example"
    if d["kind"] not in KINDS:
        return "kind must be built or adopted"
    if d.get("recipe") is not None and not _is_text(d["recipe"]):
        return "recipe must be text or empty"
    if d["status"] not in STATUSES:
        return "status must be one of " + ", ".join(STATUSES)
    if d["rhythm"] not in RHYTHMS:
        return "rhythm must be one of " + ", ".join(RHYTHMS)
    for name in ("sources", "manual_steps", "rules"):
        if d.get(name) is not None and not _is_text_list(d[name]):
            return f"{name} must be a list of text"
    minutes = d.get("your_minutes_by_hand")
    if minutes is not None and (isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0):
        return "your_minutes_by_hand must be a whole number or empty"
    for name in ("confidential", "exec_numbers"):
        if d.get(name) is not None and not isinstance(d[name], bool):
            return f"{name} must be true or false"
    improvements = d.get("improvements")
    if improvements is not None:
        if not isinstance(improvements, list):
            return "improvements must be a list"
        for item in improvements:
            if not (isinstance(item, dict) and is_date(item.get("date"))
                    and _is_text(item.get("change")) and isinstance(item.get("reason"), str)):
                return "improvements each need a date, a change, and a reason"
    check = d.get("last_check")
    if check is not None:
        if not isinstance(check, dict):
            return "last_check must have a date, a result, and a detail"
        if not is_date(check.get("date")):
            return "last_check date must be a date like 2026-10-28"
        if check.get("result") not in CHECK_RESULTS:
            return "last_check result must be pass or fail"
        if not isinstance(check.get("detail", ""), str):
            return "last_check detail must be text"
    if not is_date(d["created"]):
        return "created must be a date like 2026-10-28"
    return None


def load_file(path: Path) -> Tool:
    folder = path.parent.name
    try:
        data = yaml.safe_load(path.read_text())
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        raise InvalidTool(f"{folder}: tool.yaml could not be read") from None
    if data is None:
        raise InvalidTool(f"{folder}: tool.yaml is empty")
    return Tool.from_dict(data, folder=folder, path=path)


def _load_dir(base: Path) -> tuple[list[Tool], list[str]]:
    tools: list[Tool] = []
    problems: list[str] = []
    if not base.is_dir():
        return tools, problems
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        record = folder / RECORD_NAME
        if not record.is_file():
            continue
        try:
            tools.append(load_file(record))
        except InvalidTool as exc:
            problems.append(str(exc))
    return tools, problems


def load_all(paths: Paths) -> tuple[list[Tool], list[str]]:
    """All tool records in the skills folder, valid ones and plain problem lines."""
    return _load_dir(paths.skills_dir)


def load_archive(paths: Paths) -> tuple[list[Tool], list[str]]:
    """Retired tools kept in the archive folder."""
    return _load_dir(paths.archive_dir)


def find(paths: Paths, tool_id: str) -> Tool:
    record = paths.skills_dir / tool_id / RECORD_NAME
    if not ID_PATTERN.match(tool_id) or not record.is_file():
        raise ToolNotFound(tool_id)
    return load_file(record)


def save(paths: Paths, tool: Tool) -> Path:
    """Write the record back, keeping fields this version does not know about."""
    target = tool.path or paths.skills_dir / tool.id / RECORD_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(tool.to_dict(), sort_keys=False, allow_unicode=True))
    os.replace(tmp, target)
    tool.path = target
    return target
