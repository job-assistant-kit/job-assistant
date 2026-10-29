"""Append-only run and build records (JSON lines). Unreadable lines are skipped."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ja.workspace import Paths

RUN_EVENTS = ("run", "accepted", "corrected")


def now_ts() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def stamp(day: date | None) -> str:
    """A timestamp for a record: the given day at the current time of day, or now."""
    now = datetime.now().replace(microsecond=0)
    return (now if day is None else datetime.combine(day, now.time())).isoformat()


def _ends_without_newline(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    with path.open("rb") as fh:
        fh.seek(-1, 2)
        return fh.read(1) != b"\n"


def append_line(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lead = "\n" if _ends_without_newline(path) else ""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(lead + json.dumps(entry, ensure_ascii=False) + "\n")


def read_lines(path: Path) -> list[dict[str, Any]]:
    """Every readable JSON object line in the file; anything else is skipped."""
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _ts_date(ts: Any) -> date | None:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts).date()
    except ValueError:
        return None


def add_run(paths: Paths, tool: str, event: str, ts: str | None = None) -> None:
    if event not in RUN_EVENTS:
        raise ValueError(f"event must be one of {', '.join(RUN_EVENTS)}")
    append_line(paths.runs, {"ts": ts or now_ts(), "tool": tool, "event": event})


def runs(paths: Paths, tool: str | None = None, event: str | None = None) -> list[dict[str, Any]]:
    """Run records with a readable time, optionally for one tool and one event."""
    out = []
    for r in read_lines(paths.runs):
        if _ts_date(r.get("ts")) is None or r.get("event") not in RUN_EVENTS:
            continue
        if tool is not None and r.get("tool") != tool:
            continue
        if event is not None and r.get("event") != event:
            continue
        out.append(r)
    return out


def count_runs(paths: Paths, tool: str, since: date | None = None, until: date | None = None) -> int:
    """How many times the tool ran (event 'run' only), optionally between two dates (both included)."""
    count = 0
    for r in runs(paths, tool, "run"):
        day = _ts_date(r["ts"]) or date.min
        if (since is None or day >= since) and (until is None or day <= until):
            count += 1
    return count


def last_run(paths: Paths, tool: str) -> str | None:
    """Date (YYYY-MM-DD) of the latest run of the tool, or None."""
    dates = [d for r in runs(paths, tool, "run") if (d := _ts_date(r["ts"])) is not None]
    return max(dates).isoformat() if dates else None


def add_task(paths: Paths, words: str, ts: str | None = None) -> None:
    """Note work done without a tool, so repeated work can be spotted later."""
    words = " ".join(words.split())
    if not words:
        raise ValueError("Say what the task was in a few words.")
    append_line(paths.tasks, {"ts": ts or now_ts(), "event": "task", "words": words})


def tasks(paths: Paths) -> list[dict[str, Any]]:
    return [t for t in read_lines(paths.tasks) if t.get("event") == "task" and _ts_date(t.get("ts"))]


def add_build(paths: Paths, *, tool: str, recipe: str | None, questions: int, corrections: int,
              minutes: int, ts: str | None = None) -> None:
    for name, value in (("questions", questions), ("corrections", corrections), ("minutes", minutes)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a whole number")
    append_line(paths.builds, {
        "ts": ts or now_ts(), "tool": tool, "recipe": recipe,
        "questions": questions, "corrections": corrections, "minutes": minutes,
    })


def builds(paths: Paths) -> list[dict[str, Any]]:
    return read_lines(paths.builds)


def _building_file(paths: Paths, tool: str) -> Path:
    return paths.building_dir / f"{tool}.json"


def start_build(paths: Paths, tool: str, ts: str | None = None) -> Path:
    """Note when building a tool started, so the build record can say how long it took."""
    target = _building_file(paths, tool)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"tool": tool, "started": ts or now_ts()}) + "\n", encoding="utf-8")
    return target


def build_minutes(paths: Paths, tool: str, now: datetime | None = None) -> int | None:
    """Whole minutes since the build started (at least 1), or None when no start was noted."""
    try:
        data = json.loads(_building_file(paths, tool).read_text(encoding="utf-8"))
        started = datetime.fromisoformat(data["started"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    seconds = ((now or datetime.now()) - started).total_seconds()
    return max(1, round(seconds / 60))


def end_build(paths: Paths, tool: str) -> None:
    try:
        _building_file(paths, tool).unlink()
    except FileNotFoundError:
        pass


def unfinished_builds(paths: Paths) -> list[dict[str, str]]:
    """Builds that were started and have no build record since, oldest first."""
    if not paths.building_dir.is_dir():
        return []
    recorded: dict[str, list[datetime]] = {}
    for b in builds(paths):
        try:
            recorded.setdefault(str(b.get("tool")), []).append(datetime.fromisoformat(b["ts"]))
        except (KeyError, TypeError, ValueError):
            continue
    out = []
    for f in sorted(paths.building_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            started = datetime.fromisoformat(data["started"])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        tool = f.stem
        if any(ts >= started for ts in recorded.get(tool, [])):
            continue
        out.append({"tool": tool, "started": started.isoformat()})
    return sorted(out, key=lambda b: b["started"])
