"""Published-numbers ledger: every approved exec-bound number, and comparison with the last one."""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any

from ja.records import append_line, read_lines
from ja.registry import is_date
from ja.workspace import Paths

Number = int | float

BIG_CHANGE_PERCENT = 15
BIG_CHANGE = "This is a big change. Check the method before sending."


def _tidy(value: Number) -> Number:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


NOT_A_NUMBER = "The value must be a number, like 94 or 12.5."
_DECIMAL = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")


def parse_number(text: str) -> Number:
    """Whole numbers stay exact integers; decimals become floats. NaN and infinity are refused."""
    text = text.strip().replace(",", "")
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text)
    if not _DECIMAL.fullmatch(text):
        raise ValueError(NOT_A_NUMBER)
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(NOT_A_NUMBER)
    return value


def _check_number(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(NOT_A_NUMBER)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(NOT_A_NUMBER)


def key(text: Any) -> str:
    """How names are matched: case does not count, and spaces are trimmed."""
    return " ".join(str(text or "").split()).casefold()


class AlreadyApproved(ValueError):
    """A number for this metric and period is already in the ledger. The message is plain."""


def approved_text(e: dict[str, Any]) -> str:
    return f"{e.get('period')} was already approved on {e['approved_on']} as {_num(e['value'])}."


def known_name(paths: Paths, metric: str) -> str:
    """The name already used in the ledger for this metric, or the given name trimmed."""
    found = latest(paths, metric)
    return str(found["metric"]) if found else " ".join(metric.split())


def _replace(paths: Paths, metric: str, period: str, entry: dict[str, Any]) -> None:
    """Rewrite the ledger in one step: the rows for this metric and period become the new entry.

    Other lines, readable or not, stay as they are.
    """
    kept = []
    for line in paths.ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            item = None
        if isinstance(item, dict) and key(item.get("metric")) == key(metric) and key(item.get("period")) == key(period):
            continue
        kept.append(line)
    kept.append(json.dumps(entry, ensure_ascii=False))
    tmp = paths.ledger.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    os.replace(tmp, paths.ledger)


def add(paths: Paths, *, metric: str, period: str, value: Number, unit: str, source: str,
        method_notes: str, approved_on: str, tool: str, replace: bool = False) -> None:
    """Save an approved number. A metric and period already approved is replaced only with replace=True."""
    _check_number(value)
    if not is_date(approved_on):
        raise ValueError("approved_on must be a date like 2026-10-28")
    metric = known_name(paths, metric)
    entry = {"metric": metric, "period": " ".join(period.split()), "value": _tidy(value), "unit": unit,
             "source": source, "method_notes": method_notes, "approved_on": approved_on, "tool": tool}
    before = approved(paths, metric, period)
    if before is None:
        append_line(paths.ledger, entry)
    elif replace:
        _replace(paths, metric, period, entry)
    else:
        raise AlreadyApproved(f"{approved_text(before)} I will only replace it if you say so.")


def entries(paths: Paths, metric: str | None = None) -> list[dict[str, Any]]:
    out = []
    for e in read_lines(paths.ledger):
        v = e.get("value")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not is_date(e.get("approved_on")):
            continue
        if isinstance(v, float) and not math.isfinite(v):
            continue
        if metric is not None and key(e.get("metric")) != key(metric):
            continue
        out.append(e)
    return out


def _last(rows: list[tuple[int, dict[str, Any]]]) -> dict[str, Any] | None:
    """The entry with the latest approval date; on a tie, the one written last."""
    if not rows:
        return None
    return max(rows, key=lambda r: (r[1]["approved_on"], r[0]))[1]


def approved(paths: Paths, metric: str, period: str) -> dict[str, Any] | None:
    """The latest ledger entry for this metric and period, if it was already approved."""
    return _last([(i, e) for i, e in enumerate(entries(paths, metric)) if key(e.get("period")) == key(period)])


def latest(paths: Paths, metric: str, period: str | None = None) -> dict[str, Any] | None:
    """The latest published entry for the metric.

    With a period, entries for that period are left out. When the period was already
    approved, only entries approved before its first approval count, so a period noted
    again is compared with an earlier period.
    """
    rows = list(enumerate(entries(paths, metric)))
    if period is not None:
        same = [(e["approved_on"], i) for i, e in rows if key(e.get("period")) == key(period)]
        rows = [(i, e) for i, e in rows if key(e.get("period")) != key(period)]
        if same:
            first = min(same)
            rows = [(i, e) for i, e in rows if (e["approved_on"], i) < first]
    return _last(rows)


def metrics(paths: Paths) -> list[dict[str, Any]]:
    """Each published metric once, with its unit and its latest period, sorted by name."""
    names: dict[str, str] = {}
    for e in entries(paths):
        names.setdefault(key(e.get("metric")), str(e.get("metric")))
    out = []
    for name in names.values():
        last = latest(paths, name)
        out.append({"metric": str(last["metric"]), "unit": str(last.get("unit") or ""),
                    "period": str(last.get("period") or ""), "approved_on": last["approved_on"]})
    return sorted(out, key=lambda m: key(m["metric"]))


def metric_line(m: dict[str, Any]) -> str:
    unit = f"in {m['unit']}" if m["unit"].strip() else "no unit"
    return f"{m['metric']}, {unit}. Last published for {m['period']}, approved on {m['approved_on']}."


class UnitMismatch(ValueError):
    """The new number is in another unit than the last published one. The message is plain."""


def _unit_words(unit: str) -> str:
    if not unit.strip():
        return "has no unit"
    return f"is in {unit.strip()}"


def check_unit(prev: dict[str, Any], unit: str) -> None:
    """Refuse a comparison across units. Case and spaces around the unit do not count."""
    before = str(prev.get("unit") or "")
    if before.strip().casefold() == (unit or "").strip().casefold():
        return
    raise UnitMismatch(f"The last published number {_unit_words(before)} and this one "
                       f"{_unit_words(unit or '')}. I cannot compare them. Check which unit is right.")


def compare(paths: Paths, metric: str, value: Number, unit: str, period: str | None = None) -> dict[str, Any]:
    """Compare with the last published number. With a period, see latest() for which one counts."""
    _check_number(value)
    prev = latest(paths, metric, period)
    if prev is None:
        return {"previous": None}
    check_unit(prev, unit)
    value = _tidy(value)
    previous = prev["value"]
    change = _tidy(round(value - previous, 10))
    percent = None if previous == 0 else change / abs(previous) * 100
    big = change != 0 if percent is None else abs(percent) > BIG_CHANGE_PERCENT
    return {
        "previous": previous, "period": prev.get("period"), "unit": prev.get("unit", ""),
        "approved_on": prev["approved_on"], "change": change, "percent": percent, "big_change": big,
    }


def warning(c: dict[str, Any]) -> str | None:
    """The big-change warning when the change is over the limit (or any change from zero), else None."""
    if c.get("previous") is None:
        return None
    if c.get("percent") is None:
        return BIG_CHANGE if c.get("change") else None
    return BIG_CHANGE if abs(c["percent"]) > BIG_CHANGE_PERCENT else None


def _num(n: Number) -> str:
    n = _tidy(n)
    return f"{n:,}" if isinstance(n, int) else f"{n:,.10g}"


def describe(c: dict[str, Any]) -> str:
    """One plain sentence for a comparison result."""
    if c.get("previous") is None:
        return "No published value yet."
    unit = f" {c['unit']}" if c.get("unit") else ""
    sign = "+" if c["change"] > 0 else ""
    text = f"Last published: {_num(c['previous'])}{unit} for {c['period']}. Change: {sign}{_num(c['change'])}"
    if c.get("percent") is None:
        return text + "."
    psign = "+" if c["percent"] > 0 else ""
    return text + f" ({psign}{c['percent']:.1f}%)."
