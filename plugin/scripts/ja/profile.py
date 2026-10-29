"""Learned rules in the profile (assistant/profile.yaml): read them, add them, and change their state.

A new rule can wait for a check (pending) before it is used. The learning steps rerun the
tool's saved examples with the rule, then confirm it (active) or put it on hold (held).
Only active rules are ever used. Active rules scoped to tools are also listed in those
tools' records, so a tool folder carries the rules it depends on.

Promoting a rule to every tool adds a waiting copy scoped everywhere; the original stays in
use on its own tools until the copy is confirmed (the copy replaces it) or held (the copy
is removed). So a rule is never out of use while it waits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml

from ja import registry, render
from ja.registry import ID_PATTERN, _normalize_dates, is_date
from ja.workspace import Paths

STATES = ("pending", "active", "held")
STATE_HEADINGS = {"active": "Active", "pending": "Waiting for a check", "held": "On hold"}
EVERYWHERE = "everywhere"


class RuleProblem(ValueError):
    """A rule change cannot be made. The message is plain."""


@dataclass
class Rule:
    id: str
    text: str
    reason: str
    scope: str | list[str]
    added: str
    state: str = "active"
    held_reason: str | None = None
    scope_before: list[str] | None = None
    replaces: str | None = None

    @property
    def everywhere(self) -> bool:
        return self.scope == EVERYWHERE

    @property
    def active(self) -> bool:
        return self.state == "active"

    def applies_to(self, tool_id: str) -> bool:
        """An active rule used everywhere or by this tool."""
        return self.active and (self.everywhere or tool_id in self.scope)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "text": self.text, "reason": self.reason, "scope": self.scope,
                               "added": self.added, "state": self.state, "held_reason": self.held_reason}
        if self.scope_before is not None:
            out["scope_before"] = self.scope_before
        if self.replaces is not None:
            out["replaces"] = self.replaces
        return out


def _is_tool_list(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _first_problem(d: dict[str, Any]) -> str | None:
    for name in ("id", "text", "reason"):
        if not isinstance(d.get(name), str) or not d[name].strip():
            return f"{name} is missing"
    scope = d.get("scope")
    if scope != EVERYWHERE and not _is_tool_list(scope):
        return "scope must be everywhere or a list of tools"
    if not is_date(d.get("added")):
        return "added must be a date like 2026-10-28"
    if d.get("state", "active") not in STATES:
        return "state must be pending, active, or held"
    if d.get("held_reason") is not None and not isinstance(d["held_reason"], str):
        return "held_reason must be text or empty"
    if d.get("scope_before") is not None and not _is_tool_list(d["scope_before"]):
        return "scope_before must be a list of tools"
    if d.get("replaces") is not None and not isinstance(d["replaces"], str):
        return "replaces must be a rule id"
    return None


def _from_dict(item: dict[str, Any]) -> Rule:
    return Rule(id=item["id"], text=item["text"], reason=item["reason"], scope=item["scope"],
                added=item["added"], state=item.get("state") or "active", held_reason=item.get("held_reason"),
                scope_before=item.get("scope_before"), replaces=item.get("replaces"))


def load(paths: Paths) -> tuple[list[Rule], list[str]]:
    """Valid rules in file order, plus plain problem lines. A rule without a state is active."""
    if not paths.profile.is_file():
        return [], []
    try:
        raw = yaml.safe_load(paths.profile.read_text(encoding="utf-8"))
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
        rules.append(_from_dict(item))
    return rules, problems


def _read_raw(paths: Paths) -> dict[str, Any]:
    """The profile as written, so entries and keys this version cannot read are kept."""
    if not paths.profile.is_file():
        return {"rules": []}
    try:
        raw = yaml.safe_load(paths.profile.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        raise RuleProblem("The list of learned rules could not be read, so I did not change it.") from None
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or not isinstance(raw.get("rules") or [], list):
        raise RuleProblem("The list of learned rules is not in the expected form, so I did not change it.")
    raw["rules"] = raw.get("rules") or []
    return raw


def _write_raw(paths: Paths, raw: dict[str, Any]) -> None:
    paths.profile.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.profile.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, paths.profile)


def _known_ids(raw: dict[str, Any]) -> set[str]:
    return {str(e["id"]) for e in raw["rules"] if isinstance(e, dict) and e.get("id") is not None}


def _find(raw: dict[str, Any], rule_id: str) -> tuple[int, Rule]:
    for n, item in enumerate(raw["rules"]):
        if isinstance(item, dict) and item.get("id") == rule_id:
            item = _normalize_dates(item)
            problem = _first_problem(item)
            if problem:
                raise RuleProblem(f"The learned rule {rule_id} has a mistake, so I did not change it.")
            return n, _from_dict(item)
    raise RuleProblem(f"There is no learned rule called {rule_id}.")


def _all_tools(paths: Paths) -> list[registry.Tool]:
    active, _ = registry.load_all(paths)
    archived, _ = registry.load_archive(paths)
    return [*active, *archived]


def sync_tools(paths: Paths, removed: set[str] | None = None) -> None:
    """Make each tool record list exactly the active rules scoped to it.

    Rule ids the profile does not know are left alone, except the ones just removed.
    """
    raw = _read_raw(paths)
    rules, _ = load(paths)
    known = _known_ids(raw) | (removed or set())
    for tool in _all_tools(paths):
        want = [r.id for r in rules if r.active and not r.everywhere and tool.id in r.scope]
        kept = [r for r in tool.rules if r not in known or r in want]
        new = kept + [r for r in want if r not in kept]
        if new != tool.rules:
            tool.rules = new
            registry.save(paths, tool)


def _save(paths: Paths, raw: dict[str, Any], n: int, rule: Rule, removed: set[str] | None = None) -> None:
    raw["rules"][n] = rule.to_dict()
    _write_raw(paths, raw)
    sync_tools(paths, removed)


def add(paths: Paths, *, rule_id: str, text: str, reason: str, scope: str, pending: bool, today: date) -> Rule:
    if not ID_PATTERN.match(rule_id or ""):
        raise RuleProblem("The rule's short name must use only lowercase letters, numbers, and hyphens.")
    text, reason = render.one_line(render.no_comments(text)), render.one_line(render.no_comments(reason))
    if not text:
        raise RuleProblem("Say what the rule is in a few words.")
    if not reason:
        raise RuleProblem("Say why, in the person's words.")
    raw = _read_raw(paths)
    if rule_id in _known_ids(raw):
        raise RuleProblem(f"There is already a learned rule called {rule_id}.")
    if scope != EVERYWHERE:
        try:
            registry.find(paths, scope)
        except (registry.ToolNotFound, registry.InvalidTool):
            raise RuleProblem(f"There is no tool called {scope}. Use a tool's id or everywhere.") from None
    rule = Rule(id=rule_id, text=text, reason=reason, scope=EVERYWHERE if scope == EVERYWHERE else [scope],
                added=today.isoformat(), state="pending" if pending else "active")
    raw["rules"].append(rule.to_dict())
    _write_raw(paths, raw)
    sync_tools(paths)
    return rule


def applying(paths: Paths, tool_id: str) -> list[Rule]:
    """Active rules that apply to the tool: its own first, then the ones used everywhere."""
    rules, _ = load(paths)
    mine = [r for r in rules if r.applies_to(tool_id) and not r.everywhere]
    return mine + [r for r in rules if r.applies_to(tool_id) and r.everywhere]


def _index(raw: dict[str, Any], rule_id: str | None) -> int | None:
    for n, item in enumerate(raw["rules"]):
        if isinstance(item, dict) and item.get("id") == rule_id:
            return n
    return None


def confirm(paths: Paths, rule_id: str) -> Rule:
    """A rule waiting for a check becomes active. A copy made by promote replaces its original."""
    raw = _read_raw(paths)
    n, rule = _find(raw, rule_id)
    if rule.active:
        raise RuleProblem(f"The rule {rule_id} is already in use.")
    if rule.state != "pending":
        raise RuleProblem(f"Only a rule waiting for a check can be put in use. The rule {rule_id} is on hold.")
    original = rule.replaces
    rule.state, rule.held_reason, rule.scope_before, rule.replaces = "active", None, None, None
    raw["rules"][n] = rule.to_dict()
    m = _index(raw, original) if original else None
    if m is not None:
        del raw["rules"][m]
    _write_raw(paths, raw)
    sync_tools(paths, {original} if m is not None else None)
    return rule


def hold(paths: Paths, rule_id: str, reason: str) -> Rule:
    """A rule waiting for a check goes on hold.

    A rule waiting because it was about to be used everywhere goes back to the tools it had,
    stays active there, and keeps the reason it was not used everywhere.
    """
    reason = render.one_line(render.no_comments(reason))
    if not reason:
        raise RuleProblem("Say why the rule is on hold, in a few words.")
    raw = _read_raw(paths)
    n, rule = _find(raw, rule_id)
    if rule.state != "pending":
        raise RuleProblem(f"Only a rule waiting for a check can be put on hold. The rule {rule_id} is "
                          + ("in use." if rule.active else "already on hold."))
    m = _index(raw, rule.replaces) if rule.replaces else None
    if m is not None:
        # A copy waiting to be used everywhere: drop it, and keep the original in use on its tools.
        _, original = _find(raw, rule.replaces)
        original.held_reason = reason
        raw["rules"][m] = original.to_dict()
        del raw["rules"][n]
        _write_raw(paths, raw)
        sync_tools(paths, {rule.id})
        return original
    if rule.scope_before is not None:
        # Promoted by an earlier version, which changed the rule in place.
        rule.scope, rule.scope_before, rule.state = rule.scope_before, None, "active"
    else:
        rule.state, rule.replaces = "held", None
    rule.held_reason = reason
    _save(paths, raw, n, rule)
    return rule


def promote(paths: Paths, rule_id: str) -> Rule:
    """Add a copy of an active tool rule for every tool, waiting for a check on all of them.

    The original stays in use on its own tools until the copy is confirmed or held.
    """
    raw = _read_raw(paths)
    n, rule = _find(raw, rule_id)
    if rule.everywhere:
        raise RuleProblem(f"The rule {rule_id} is already used everywhere.")
    if not rule.active:
        raise RuleProblem(f"The rule {rule_id} is not in use yet. Check it on its own tool first.")
    if any(isinstance(e, dict) and e.get("replaces") == rule_id for e in raw["rules"]):
        raise RuleProblem(f"The rule {rule_id} is already waiting for a check on every tool.")
    known = _known_ids(raw)
    copy_id, k = f"{rule_id}-everywhere", 2
    while copy_id in known:
        copy_id, k = f"{rule_id}-everywhere-{k}", k + 1
    copy = Rule(id=copy_id, text=rule.text, reason=rule.reason, scope=EVERYWHERE, added=rule.added,
                state="pending", replaces=rule_id)
    raw["rules"].insert(n + 1, copy.to_dict())
    _write_raw(paths, raw)
    return copy


def forget(paths: Paths, rule_id: str) -> Rule:
    raw = _read_raw(paths)
    n, rule = _find(raw, rule_id)
    del raw["rules"][n]
    _write_raw(paths, raw)
    sync_tools(paths, removed={rule_id})
    return rule


def no_longer(rule: Rule) -> str:
    """'I will stop applying this rule: <text>.' with the rule's own words."""
    return f"I will stop applying this rule: {rule.text.strip().rstrip('.')}."


def similar(paths: Paths, text: str, limit: int = 3) -> list[tuple[Rule, list[str]]]:
    """Active rules sharing the most words with the text, with the shared words."""
    from ja.parts import words

    wanted = words(text)
    rules, _ = load(paths)
    scored = []
    for r in rules:
        if not r.active:
            continue
        matched = sorted(wanted & words(r.text))
        if matched:
            scored.append((r, matched))
    scored.sort(key=lambda x: -len(x[1]))
    return scored[:limit]
