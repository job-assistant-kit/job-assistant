"""Read learned rules from the profile (assistant/profile.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from ja.registry import _normalize_dates, is_date
from ja.workspace import Paths


@dataclass
class Rule:
    id: str
    text: str
    reason: str
    scope: str | list[str]
    added: str

    @property
    def everywhere(self) -> bool:
        return self.scope == "everywhere"


def _first_problem(d: dict[str, Any]) -> str | None:
    for name in ("id", "text", "reason"):
        if not isinstance(d.get(name), str) or not d[name].strip():
            return f"{name} is missing"
    scope = d.get("scope")
    if scope != "everywhere" and not (isinstance(scope, list) and all(isinstance(x, str) for x in scope)):
        return "scope must be everywhere or a list of tools"
    if not is_date(d.get("added")):
        return "added must be a date like 2026-10-28"
    return None


def load(paths: Paths) -> tuple[list[Rule], list[str]]:
    """Valid rules in file order, plus plain problem lines."""
    if not paths.profile.is_file():
        return [], []
    try:
        raw = yaml.safe_load(paths.profile.read_text())
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        return [], ["profile: the list of learned rules could not be read"]
    if raw is None:
        return [], []
    if not isinstance(raw, dict):
        return [], ["profile: the profile must hold a list of rules"]
    items = raw.get("rules") or []
    if not isinstance(items, list):
        return [], ["profile: rules must be a list"]
    rules: list[Rule] = []
    problems: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            problems.append("?: each rule must hold named fields")
            continue
        item = _normalize_dates(item)
        problem = _first_problem(item)
        if problem:
            problems.append(f"{item.get('id') or '?'}: {problem}")
            continue
        rules.append(Rule(id=item["id"], text=item["text"], reason=item["reason"],
                          scope=item["scope"], added=item["added"]))
    return rules, problems
