"""Published-numbers ledger: every approved exec-bound number, and comparison with the last one."""

from __future__ import annotations

from typing import Any

from ja.records import append_line, read_lines
from ja.registry import is_date
from ja.workspace import Paths

Number = int | float


def _tidy(value: Number) -> Number:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def add(paths: Paths, *, metric: str, period: str, value: Number, unit: str, source: str,
        method_notes: str, approved_on: str, tool: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("value must be a number")
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


def compare(paths: Paths, metric: str, value: Number) -> dict[str, Any]:
    prev = latest(paths, metric)
    if prev is None:
        return {"previous": None}
    value = _tidy(value)
    previous = prev["value"]
    change = _tidy(round(value - previous, 10))
    percent = None if previous == 0 else change / previous * 100
    return {
        "previous": previous, "period": prev.get("period"), "unit": prev.get("unit", ""),
        "approved_on": prev["approved_on"], "change": change, "percent": percent,
    }


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
