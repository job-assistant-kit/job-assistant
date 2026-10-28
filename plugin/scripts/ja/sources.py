"""Load the sources list and decide which copies are stale."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import yaml

from ja.registry import _normalize_dates, is_date
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

    def age_days(self, today: date) -> int | None:
        if self.exported is None:
            return None
        return (today - date.fromisoformat(self.exported)).days

    def is_stale(self, today: date) -> bool:
        """A living source read from a file copy is stale once the copy passes its freshness limit."""
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
        raw = yaml.safe_load(paths.sources.read_text())
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
        by_id[s.id] = s
    return by_id, problems


def save(paths: Paths, items: list[Source]) -> None:
    paths.sources.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.sources.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump([asdict(s) for s in items], sort_keys=False, allow_unicode=True))
    os.replace(tmp, paths.sources)
