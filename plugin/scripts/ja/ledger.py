"""Published-numbers ledger: every approved exec-bound number, and comparison with the last one."""

from __future__ import annotations

import math
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


def add(paths: Paths, *, metric: str, period: str, value: Number, unit: str, source: str,
        method_notes: str, approved_on: str, tool: str) -> None:
    _check_number(value)
    if not is_date(approved_on):
        raise ValueError("approved_on must be a date like 2026-10-28")
    append_line(paths.ledger, {
        "metric": metric, "period": period, "value": _tidy(value), "unit": unit,
        "source": source, "method_notes": method_notes, "approved_on": approved_on, "tool": tool,
    })


def entries(paths: Paths, metric: str | None = None) -> list[dict[str, Any]]:
    out = []
    for e in read_lines(paths.ledger):
        v = e.get("value")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not is_date(e.get("approved_on")):
            continue
        if isinstance(v, float) and not math.isfinite(v):
            continue
        if metric is not None and e.get("metric") != metric:
            continue
        out.append(e)
    return out


def latest(paths: Paths, metric: str) -> dict[str, Any] | None:
    """The entry with the latest approval date; on a tie, the one written last."""
    best: dict[str, Any] | None = None
    for e in entries(paths, metric):
        if best is None or e["approved_on"] >= best["approved_on"]:
            best = e
    return best


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


def compare(paths: Paths, metric: str, value: Number, unit: str) -> dict[str, Any]:
    _check_number(value)
    prev = latest(paths, metric)
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
