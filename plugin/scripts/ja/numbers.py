"""Number sign-off: the note shown before a number is sent, and approval into the ledger.

The note puts the facts the person needs in one fixed form: the number, how it compares
with the last published one, whether the method document can be read, how many rows were
left out, and the label "Draft, not checked". The number waits in a pending list until the
person approves it.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from ja import ledger, registry, sources
from ja.records import append_line, read_lines, stamp
from ja.workspace import Paths

DRAFT = "Draft, not checked"
APPROVED = "Saved. Next time I will compare against this number."


class NumberProblem(ValueError):
    """A sign-off step cannot be done. The message is plain."""


def pending_file(paths: Paths) -> Path:
    return paths.data_dir / "numbers" / "pending.jsonl"


def _short(day: str, today: date) -> str:
    d = date.fromisoformat(day)
    text = f"{d:%b} {d.day}"
    return text if d.year == today.year else f"{text}, {d.year}"


def method_line(src: sources.Source, today: date) -> tuple[str, bool]:
    """How the method document can be read, as one plain line, and whether it can be relied on."""
    head = f"Method: {src.name}"
    if src.access == "connector":
        return f"{head}, read live through a connector.", True
    if src.in_future(today):
        return f"{head}. The export date of your copy is in the future. Check the date.", False
    age = src.age_days(today)
    if src.kind == "fixed":
        when = f" from {_short(src.exported, today)}" if src.exported else ""
        return f"{head}. Your copy{when} is a fixed document.", True
    fresh = "Get a fresh copy before relying on the method check."
    if age is None:
        return f"{head}. Your copy has no export date. {fresh}", False
    if src.is_stale(today):
        days = "1 day" if age == 1 else f"{age} days"
        return f"{head}. Your copy is {days} old, past its {src.fresh_days}-day limit. {fresh}", False
    return f"{head}. Your copy from {_short(src.exported, today)} is within its {src.fresh_days}-day limit.", True


def counts_line(excluded: int | None, total: int | None) -> str | None:
    if excluded is None:
        return None
    verb = "was" if excluded == 1 else "were"
    return f"{excluded} of {total} rows {verb} left out."


def _num(value: ledger.Number) -> str:
    return ledger._num(value)


def _data_source(tool: registry.Tool, by_id: dict[str, sources.Source], method_id: str) -> str:
    names = [by_id[s].name if s in by_id else s for s in tool.sources if s != method_id]
    return "; ".join(names) or tool.name


def _read_pending(paths: Paths) -> list[dict[str, Any]]:
    return read_lines(pending_file(paths))


def _write_pending(paths: Paths, items: list[dict[str, Any]]) -> None:
    target = pending_file(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".jsonl.tmp")
    tmp.write_text("", encoding="utf-8")
    for item in items:
        append_line(tmp, item)
    os.replace(tmp, target)


def note(paths: Paths, *, metric: str, value: ledger.Number, unit: str, period: str, tool_id: str,
         method_source: str, excluded: int | None, total: int | None, today: date,
         ts: str | None = None) -> tuple[list[str], dict[str, Any]]:
    """The sign-off note lines and the pending entry, which is saved."""
    if (excluded is None) != (total is None):
        raise NumberProblem("Give both the number of rows left out and the total.")
    if excluded is not None and excluded > total:
        raise NumberProblem("That is more rows left out than there are in total. Check the counts.")
    try:
        tool = registry.find(paths, tool_id)
    except (registry.ToolNotFound, registry.InvalidTool):
        raise NumberProblem(f"There is no tool called {tool_id}.") from None
    by_id, _ = sources.load(paths)
    src = by_id.get(method_source)
    if src is None:
        raise NumberProblem(f"The method document {method_source} is not on your sources list. Add it first.")
    metric = ledger.known_name(paths, metric)
    period = " ".join(period.split())
    try:
        comparison = ledger.compare(paths, metric, value, unit, period=period)
    except ledger.UnitMismatch as exc:
        raise NumberProblem(str(exc)) from None
    unit_text = f" {unit}" if unit else ""
    method, reachable = method_line(src, today)
    lines = [f"{metric}: {_num(value)}{unit_text} for {period}, from {tool.name}."]
    already = ledger.approved(paths, metric, period)
    if already is not None:
        lines.append(ledger.approved_text(already))
    lines.append(ledger.describe(comparison))
    if (warn := ledger.warning(comparison)):
        lines.append(warn)
    lines.append(method)
    if (counted := counts_line(excluded, total)):
        lines.append(counted)
    lines.append(DRAFT)
    entry = {"metric": metric, "period": period, "value": value, "unit": unit, "tool": tool.id,
             "source": _data_source(tool, by_id, src.id), "method_source": src.id, "method_name": src.name,
             "method_reachable": reachable, "excluded": excluded, "total": total,
             "noted_on": today.isoformat(), "ts": ts or stamp(today)}
    kept = [p for p in _read_pending(paths) if not _same(p, metric, period)]
    _write_pending(paths, [*kept, entry])
    return lines, {**entry, "comparison": comparison, "already_approved": already}


def _same(item: dict[str, Any], metric: str, period: str) -> bool:
    return ledger.key(item.get("metric")) == ledger.key(metric) and ledger.key(item.get("period")) == ledger.key(period)


def approve(paths: Paths, *, metric: str, period: str, method_notes: str | None, today: date,
            replace: bool = False) -> dict[str, Any]:
    """Move the waiting number into the ledger with today's date.

    A metric and period already in the ledger is replaced only with replace=True.
    """
    items = _read_pending(paths)
    found = [p for p in items if _same(p, metric, period)]
    if not found:
        raise NumberProblem(f"There is no number for {metric}, {period} waiting for your OK.")
    entry = found[-1]
    given = " ".join((method_notes or "").split())
    notes = [given or f"Method: {entry.get('method_name') or entry.get('method_source')}."]
    counted = counts_line(entry.get("excluded"), entry.get("total"))
    if counted and counted not in given:
        notes.append(counted)
    try:
        ledger.add(paths, metric=entry["metric"], period=entry["period"], value=entry["value"],
                   unit=entry.get("unit", ""), source=entry.get("source", ""), method_notes=" ".join(notes),
                   approved_on=today.isoformat(), tool=entry.get("tool", ""), replace=replace)
    except ledger.AlreadyApproved as exc:
        raise NumberProblem(str(exc)) from None
    except (KeyError, ValueError, TypeError, AttributeError):
        raise NumberProblem("The waiting number could not be read. Run the sign-off note again.") from None
    _write_pending(paths, [p for p in items if p not in found])
    return entry
