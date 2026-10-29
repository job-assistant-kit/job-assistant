"""Upkeep: what needs the person's attention, worked out from the records only.

Each item is one plain sentence plus the words the person can say to act on it.
Nothing here changes a tool. Retiring, cleaning the inbox, and changing a tool all
need the person's own yes through the assistant's steps.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ja import facts, proof, records, registry, sources, status
from ja.workspace import Paths

QUARTER_NOTICE_DAYS = 14
MONTH_NOTICE_DAYS = 5
WEEK_DAYS = 6
UNUSED_DAYS = 90
TASK_WINDOW_DAYS = 30
TASK_REPEATS = 3
INBOX_DAYS = 30
STABLE_ACCEPTED = 5
SKIP_FILES = (".keep",)

# Lower comes first. Time-bound items lead, proposals come last.
ORDER = ("due", "update", "unfinished", "inbox", "idea", "stable", "retire")
# Items shown under "Ideas" on the tools page; the rest go under "Needs your OK".
IDEA_KINDS = ("idea", "stable")

BUILD_STEPS = (("record", "tool record saved", "write the tool record"),
               ("example", "example saved", "run it on their example and save it once they say it looks right"),
               ("check", "check recorded", "record the check"))


@dataclass
class Item:
    kind: str
    text: str
    say: str
    tool: str | None = None
    name: str = ""

    @property
    def line(self) -> str:
        return f'{self.text} Say "{self.say}".'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def quarter_start(today: date) -> date:
    return date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)


def quarter_end(today: date) -> date:
    start = quarter_start(today)
    if start.month == 10:
        return date(start.year, 12, 31)
    return date(start.year, start.month + 3, 1) - timedelta(days=1)


def month_end(today: date) -> date:
    if today.month == 12:
        return date(today.year, 12, 31)
    return date(today.year, today.month + 1, 1) - timedelta(days=1)


def short_date(d: date, today: date) -> str:
    text = f"{d:%b} {d.day}"
    return text if d.year == today.year else f"{text}, {d.year}"


def _day(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def _last_used(paths: Paths, tool: registry.Tool) -> date | None:
    """The latest run, or the day the tool was made when it never ran."""
    return _day(records.last_run(paths, tool.id)) or _day(tool.created)


def _due(paths: Paths, tool: registry.Tool, today: date) -> Item | None:
    say = tool.examples[0]
    if tool.rhythm == "quarterly":
        end = quarter_end(today)
        if (end - today).days <= QUARTER_NOTICE_DAYS and not records.count_runs(
                paths, tool.id, since=quarter_start(today), until=end):
            return Item("due", f"{tool.name} is due by {short_date(end, today)}, and it has not run this quarter.",
                        say, tool.id, tool.name)
    elif tool.rhythm == "monthly":
        end = month_end(today)
        if (end - today).days <= MONTH_NOTICE_DAYS and not records.count_runs(
                paths, tool.id, since=today.replace(day=1), until=end):
            return Item("due", f"{tool.name} is due by {short_date(end, today)}, and it has not run this month.",
                        say, tool.id, tool.name)
    elif tool.rhythm == "weekly":
        last = _last_used(paths, tool)
        if last is not None and (today - last).days >= WEEK_DAYS:
            ran = records.last_run(paths, tool.id)
            when = f"it last ran {short_date(last, today)}" if ran else "it has not run yet"
            return Item("due", f"{tool.name} runs weekly, and {when}.", say, tool.id, tool.name)
    return None


def _retire(paths: Paths, tool: registry.Tool, today: date) -> Item | None:
    """Offer retiring a tool built here that has not been used for a long time. Never automatic.

    Rhythm tools never get this. Inherited tools do not either: they often run outside
    the assistant, so no record of use is not evidence that they are unused.
    """
    if tool.rhythm != "on-demand" or tool.kind != "built":
        return None
    last = _last_used(paths, tool)
    if last is None or (today - last).days < UNUSED_DAYS:
        return None
    ran = records.last_run(paths, tool.id)
    since = f"since {short_date(last, today)}" if ran else f"since it was made on {short_date(last, today)}"
    return Item("retire", f"You have not used {tool.name} {since}. If you no longer need it, I can retire it.",
                f"retire {tool.name}", tool.id, tool.name)


def _stable(paths: Paths, tool: registry.Tool) -> Item | None:
    if tool.kind != "built" or facts.has_step(paths, tool.id):
        return None
    if len(records.runs(paths, tool.id, "accepted")) < STABLE_ACCEPTED:
        return None
    return Item("stable", f"Want me to make {tool.name} more reliable by moving its counting into a fixed step?",
                f"make {tool.name} more reliable", tool.id, tool.name)


def _days_ago(n: int) -> str:
    if n <= 0:
        return "today"
    return "yesterday" if n == 1 else f"{n} days ago"


def unfinished(paths: Paths, today: date) -> list[dict[str, Any]]:
    """Builds that were started and never recorded, with the steps already done and the next one."""
    rows = []
    for b in records.unfinished_builds(paths):
        tool_id = b["tool"]
        try:
            tool = registry.find(paths, tool_id)
        except (registry.ToolNotFound, registry.InvalidTool):
            tool = None
        done = {"record": tool is not None,
                "example": bool(proof.cases(paths, tool_id)),
                "check": tool is not None and tool.last_check is not None}
        nxt = next((todo for key, _, todo in BUILD_STEPS if not done[key]), "record the build")
        started = datetime.fromisoformat(b["started"]).date()
        rows.append({"tool": tool_id, "name": tool.name if tool else tool_id, "started": b["started"],
                     "days_ago": (today - started).days, "done": done, "next": nxt})
    return rows


def unfinished_line(row: dict[str, Any]) -> str:
    started = datetime.fromisoformat(row["started"]).date()
    done_words = ", ".join(word for key, word, _ in BUILD_STEPS if row["done"][key]) or "nothing"
    return (f"{row['name']}: started {started:%b} {started.day}, {_days_ago(row['days_ago'])}. "
            f"Done so far: {done_words}. Next: {row['next']}.")


def _similar(a: set[str], b: set[str]) -> bool:
    """Two task lines are the same kind of work when they share most of the shorter one's words."""
    shared = a & b
    if not shared:
        return False
    smaller = min(len(a), len(b))
    return (len(shared) >= 2 or smaller == 1) and len(shared) * 2 >= smaller


def ideas(paths: Paths, today: date) -> list[Item]:
    """Hand work done three or more times in the last 30 days, newest wording first."""
    from ja.parts import words

    recent = []
    for t in records.tasks(paths):
        day = datetime.fromisoformat(t["ts"]).date()
        text = t.get("words")
        if isinstance(text, str) and 0 <= (today - day).days < TASK_WINDOW_DAYS:
            recent.append((t["ts"], text, words(text)))
    recent.sort(key=lambda x: x[0], reverse=True)
    used = [False] * len(recent)
    out = []
    for i, (_, text, w) in enumerate(recent):
        if used[i] or not w:
            continue
        group = [j for j in range(i, len(recent)) if not used[j] and _similar(w, recent[j][2])]
        if len(group) < TASK_REPEATS:
            continue
        for j in group:
            used[j] = True
        out.append(Item("idea", f"You did '{text}' {len(group)} times in the last {TASK_WINDOW_DAYS} days.",
                        "automate this"))
    return out


def old_inbox_files(paths: Paths, today: date) -> list[Path]:
    """Files anywhere in the inbox last changed more than 30 days ago. Links and placeholders are skipped."""
    if not paths.inbox.is_dir():
        return []
    out = []
    for f in sorted(paths.inbox.rglob("*")):
        try:
            if f.is_symlink() or not f.is_file() or f.name in SKIP_FILES:
                continue
            changed = date.fromtimestamp(f.stat().st_mtime)
        except OSError:
            continue
        if (today - changed).days > INBOX_DAYS:
            out.append(f)
    return out


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _inbox(paths: Paths, today: date) -> Item | None:
    old = old_inbox_files(paths, today)
    if not old:
        return None
    verb = "is" if len(old) == 1 else "are"
    return Item("inbox", f"{_plural(len(old), 'file')} in your inbox {verb} more than {INBOX_DAYS} days old. "
                         "I delete old files only when you say yes.", "clean my inbox")


def items(paths: Paths, today: date) -> list[Item]:
    """Everything upkeep would mention, most urgent first."""
    tools, _ = registry.load_all(paths)
    by_id, source_problems = sources.load(paths)
    found: list[Item] = []
    for t in sorted(tools, key=lambda x: x.name.lower()):
        if t.status in status.HELD:
            continue
        if (due := _due(paths, t, today)) is not None:
            found.append(due)
        if status.effective_status(t, by_id, today) == "needs-update":
            why = "; ".join(r.rstrip(".") for r in status.reasons(t, by_id, today))
            found.append(Item("update", f"{t.name} needs an update: {why}.", f"update {t.name}", t.id, t.name))
        if (stable := _stable(paths, t)) is not None:
            found.append(stable)
        if (retire := _retire(paths, t, today)) is not None:
            found.append(retire)
    for problem in source_problems:
        found.append(Item("update", f"An entry in your sources list has a mistake ({problem}).", "fix my sources"))
    for row in unfinished(paths, today):
        found.append(Item("unfinished", f"You started {row['name']} on "
                          f"{short_date(datetime.fromisoformat(row['started']).date(), today)} and did not finish it.",
                          f"finish {row['name']}", row["tool"], row["name"]))
    if (inbox := _inbox(paths, today)) is not None:
        found.append(inbox)
    found += ideas(paths, today)
    return sorted(found, key=lambda i: ORDER.index(i.kind))


def watch(paths: Paths) -> list[dict[str, Any]]:
    """Living sources read through a connector, with the tools that use them and their oldest check.

    The upkeep steps compare each one's modified time with that date to spot a change.
    """
    tools, _ = registry.load_all(paths)
    by_id, _ = sources.load(paths)
    out = []
    for s in sorted(by_id.values(), key=lambda x: x.id):
        if s.access != "connector" or s.kind != "living":
            continue
        users = [t for t in tools if s.id in t.sources and t.status != "retired"]
        checks = [t.last_check["date"] for t in users if t.last_check and t.last_check.get("date")]
        out.append({"id": s.id, "name": s.name, "where": s.where, "used_by": sorted(t.name for t in users),
                    "checked": min(checks) if checks else None})
    return out


def write(paths: Paths, found: list[Item], today: date) -> Path:
    target = paths.data_dir / "upkeep.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    text = json.dumps({"date": today.isoformat(), "items": [i.to_dict() for i in found]}, indent=2, ensure_ascii=False)
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def clean_inbox(paths: Paths, today: date) -> int:
    """Delete inbox files more than 30 days old. Returns how many were deleted."""
    count = 0
    for f in old_inbox_files(paths, today):
        try:
            f.unlink()
            count += 1
        except OSError:
            continue
    return count
