"""Load the sources list and decide which copies are stale."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yaml

from ja.registry import ID_PATTERN, _normalize_dates, is_date
from ja.workspace import Paths

KINDS = ("living", "fixed")
ACCESS = ("connector", "file")
DEFAULT_FRESH_DAYS = 7


@dataclass
class Source:
    id: str
    name: str
    kind: str
    where: str
    access: str
    version: str | None = None
    exported: str | None = None
    fresh_days: int = DEFAULT_FRESH_DAYS
    changed: bool = False
    # Set by load() when the id appears more than once. Never saved.
    duplicate: bool = field(default=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "where": self.where,
            "access": self.access, "version": self.version, "exported": self.exported,
            "fresh_days": self.fresh_days, "changed": self.changed,
        }

    def in_future(self, today: date) -> bool:
        age = self.age_days(today)
        return age is not None and age < 0

    def age_days(self, today: date) -> int | None:
        if self.exported is None:
            return None
        return (today - date.fromisoformat(self.exported)).days

    def is_stale(self, today: date) -> bool:
        """A living source read from a file copy is stale once the copy passes its freshness limit.

        An export date in the future is a mistake, so it always counts as stale.
        """
        if self.in_future(today):
            return True
        if self.access != "file" or self.kind != "living":
            return False
        age = self.age_days(today)
        return age is None or age > self.fresh_days


def _first_problem(d: dict[str, Any]) -> str | None:
    for name in ("id", "name", "kind", "where", "access"):
        if not isinstance(d.get(name), str) or not d[name].strip():
            return f"{name} is missing"
    if d["kind"] not in KINDS:
        return "kind must be living or fixed"
    if d["access"] not in ACCESS:
        return "access must be connector or file"
    if d.get("version") is not None and not isinstance(d["version"], (str, int, float)):
        return "version must be text or empty"
    if d.get("exported") is not None and not is_date(d["exported"]):
        return "exported must be a date like 2026-10-28"
    fresh = d.get("fresh_days", DEFAULT_FRESH_DAYS)
    if isinstance(fresh, bool) or not isinstance(fresh, int) or fresh < 0:
        return "fresh_days must be a whole number"
    if not isinstance(d.get("changed", False), bool):
        return "changed must be true or false"
    return None


def from_dict(d: dict[str, Any]) -> Source:
    """Build a Source. Raises ValueError with '<id>: <field> <problem>'."""
    if not isinstance(d, dict):
        raise ValueError("?: each source must hold named fields")
    d = _normalize_dates(d)
    problem = _first_problem(d)
    if problem:
        raise ValueError(f"{d.get('id') or '?'}: {problem}")
    version = d.get("version")
    return Source(
        id=d["id"], name=d["name"], kind=d["kind"], where=d["where"], access=d["access"],
        version=None if version is None else str(version),
        exported=d.get("exported"),
        fresh_days=d.get("fresh_days", DEFAULT_FRESH_DAYS),
        changed=d.get("changed", False),
    )


def load(paths: Paths) -> tuple[dict[str, Source], list[str]]:
    """Sources by id, plus plain problem lines for entries that break the contract."""
    if not paths.sources.is_file():
        return {}, []
    try:
        raw = yaml.safe_load(paths.sources.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        return {}, ["sources: the sources list could not be read"]
    if raw is None:
        return {}, []
    if not isinstance(raw, list):
        return {}, ["sources: the sources list must be a list"]
    by_id: dict[str, Source] = {}
    problems: list[str] = []
    for entry in raw:
        try:
            s = from_dict(entry)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if s.id in by_id:
            if not by_id[s.id].duplicate:
                by_id[s.id].duplicate = True
                problems.append(f"{s.id}: id is used by more than one entry")
            continue
        by_id[s.id] = s
    return by_id, problems


def save(paths: Paths, items: list[Source]) -> None:
    paths.sources.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.sources.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump([s.to_dict() for s in items], sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, paths.sources)


class SourceProblem(ValueError):
    """A sources change cannot be made. The message is plain."""


def _read_raw(paths: Paths) -> list[Any]:
    """The sources file as written, so entries this version cannot read are kept."""
    if not paths.sources.is_file():
        return []
    try:
        raw = yaml.safe_load(paths.sources.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        raise SourceProblem("Your sources list could not be read, so I did not change it.") from None
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SourceProblem("Your sources list is not a list, so I did not change it.")
    return raw


def _write_raw(paths: Paths, items: list[Any]) -> None:
    items = sorted(items, key=lambda e: str(e.get("id", "")) if isinstance(e, dict) else "")
    paths.sources.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.sources.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(items, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, paths.sources)


def _plain(problem: str) -> str:
    """'<id>: <field> <problem>' as a sentence."""
    text = problem.split(": ", 1)[-1]
    return "The source " + text + "."


def _check_date(value: str, today: date) -> None:
    if not is_date(value):
        raise SourceProblem("The export date must look like 2026-10-28.")
    if date.fromisoformat(value) > today:
        raise SourceProblem("The export date is in the future. Use the date the copy was saved.")


def add(paths: Paths, entry: dict[str, Any], today: date) -> Source:
    """Add one source. Refuses a duplicate id and invalid values."""
    entry = {k: v for k, v in entry.items() if v is not None}
    sid = entry.get("id")
    if not isinstance(sid, str) or not ID_PATTERN.match(sid):
        raise SourceProblem("The source id must use only lowercase letters, numbers, and hyphens.")
    if entry.get("exported") is not None:
        _check_date(entry["exported"], today)
    try:
        src = from_dict(entry)
    except ValueError as exc:
        raise SourceProblem(_plain(str(exc))) from None
    items = _read_raw(paths)
    if any(isinstance(e, dict) and e.get("id") == sid for e in items):
        raise SourceProblem(f"There is already a source called {sid}.")
    items.append(src.to_dict())
    _write_raw(paths, items)
    return src


def set_exported(paths: Paths, sid: str, when: str, today: date) -> None:
    """Record the date of a fresh copy."""
    _check_date(when, today)
    items = _read_raw(paths)
    found = [e for e in items if isinstance(e, dict) and e.get("id") == sid]
    if not found:
        raise SourceProblem(f"There is no source called {sid}.")
    for e in found:
        e["exported"] = when
    _write_raw(paths, items)


def _short(d: date, today: date) -> str:
    text = f"{d:%b} {d.day}"
    return text if d.year == today.year else f"{text}, {d.year}"


def _days(n: int) -> str:
    return f"{n} day old" if n == 1 else f"{n} days old"


def describe(paths: Paths, today: date) -> list[dict[str, Any]]:
    """One plain row per readable source: how it is reached and how old the copy is."""
    by_id, _ = load(paths)
    rows = []
    for s in sorted(by_id.values(), key=lambda x: x.id):
        age = s.age_days(today)
        if s.access == "connector":
            reached, text = "read live through a connector", "live"
        else:
            reached = "a copy you drop in"
            if age is None:
                text = "No export date yet"
            elif age < 0:
                text = "The export date is in the future. Check the date"
            else:
                text = f"Copy from {_short(date.fromisoformat(s.exported), today)}, {_days(age)}"
                if s.is_stale(today):
                    text += f", past its {s.fresh_days}-day limit"
        rows.append({**s.to_dict(), "reached": reached, "age": text, "age_days": age,
                     "stale": s.is_stale(today)})
    return rows


def set_changed(paths: Paths, sid: str, changed: bool) -> dict[str, Any]:
    """Mark a source as changed since its tools were checked, or clear the mark. Returns the entry."""
    items = _read_raw(paths)
    found = [e for e in items if isinstance(e, dict) and e.get("id") == sid]
    if not found:
        raise SourceProblem(f"There is no source called {sid}.")
    for e in found:
        e["changed"] = changed
    _write_raw(paths, items)
    return {**found[0], "name": found[0].get("name") or sid}
