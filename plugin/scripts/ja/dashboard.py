"""Build the tools page (dashboard/index.html) from records. No JavaScript."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ja import profile, records, registry, sources, status, workspace
from ja.workspace import Paths

TEMPLATES = Path(__file__).resolve().parent / "templates"

RHYTHM_WORDS = {
    "on-demand": "When you need it",
    "daily": "Runs daily",
    "weekly": "Runs weekly",
    "monthly": "Runs monthly",
    "quarterly": "Runs quarterly",
}

WAITING = "Waiting for your OK on the method."
NOT_CHECKED = "Not checked yet. Confirm it works on a real example."

PILL_CLASS = {
    "working": "ok",
    "draft-not-checked": "warn",
    "needs-update": "warn",
    "being-built": "build",
    "paused": "off",
    "retired": "off",
}


@dataclass
class Card:
    name: str
    label: str
    pill: str
    does: str
    say: str
    rhythm: str
    uses: str
    last_used: str
    last_check: str
    data_path: str
    manual_steps: list[str]
    rules: list[str]
    improvements: list[dict[str, str]]


@dataclass
class Attention:
    name: str
    reasons: list[str]
    say: str


@dataclass
class Learned:
    text: str
    reason: str
    scope: str


@dataclass
class View:
    title: str
    updated: str
    working: int
    needs_ok: int
    uses_quarter: int
    estimate_hours: str | None
    attention: list[Attention] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    learned: list[Learned] = field(default_factory=list)
    ideas: list[str] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    source_problems: list[str] = field(default_factory=list)
    rule_problems: list[str] = field(default_factory=list)


def quarter_start(today: date) -> date:
    return date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)


def quarter_end(today: date) -> date:
    start = quarter_start(today)
    if start.month == 10:
        return date(start.year, 12, 31)
    return date(start.year, start.month + 3, 1) - timedelta(days=1)


def short_date(iso: str, today: date) -> str:
    d = date.fromisoformat(iso)
    if d == today:
        return "today"
    text = f"{d:%b} {d.day}"
    return text if d.year == today.year else f"{text}, {d.year}"


def _times(n: int) -> str:
    return "Not used yet" if n == 0 else f"Used {n} time" + ("" if n == 1 else "s")


def _check_text(check: dict[str, str] | None, today: date, effective: str) -> str:
    if not check:
        return "Not checked yet"
    word = "passed" if check.get("result") == "pass" else "failed"
    text = f"Last check {word} {short_date(check['date'], today)}"
    if effective == "draft-not-checked" and check.get("result") == "pass":
        return f"{text}. {WAITING}"
    return text


def build_view(paths: Paths, today: date, ideas: list[str] | None = None,
               now: datetime | None = None) -> View:
    now = now or datetime.now()
    tools, tool_problems = registry.load_all(paths)
    archived, archive_problems = registry.load_archive(paths)
    by_id, source_problems = sources.load(paths)
    rules, rule_problems = profile.load(paths)
    rule_text = {r.id: r.text for r in rules}
    names = {t.id: t.name for t in tools}
    since, until = quarter_start(today), quarter_end(today)

    working = needs_ok = uses_quarter = 0
    minutes_total = 0
    has_estimate = False
    attention: list[Attention] = []
    cards: list[Card] = []
    retired: list[str] = [t.name for t in archived]

    for t in tools:
        eff = status.effective_status(t, by_id, today)
        if eff == "retired":
            retired.append(t.name)
            continue
        runs_q = records.count_runs(paths, t.id, since=since, until=until)
        uses_quarter += runs_q
        if t.your_minutes_by_hand is not None:
            has_estimate = True
            minutes_total += t.your_minutes_by_hand * runs_q
        if eff == "working":
            working += 1
        if eff == "needs-update":
            needs_ok += 1
            attention.append(Attention(t.name, status.reasons(t, by_id, today), f"update {t.name}"))
        elif eff == "draft-not-checked":
            needs_ok += 1
            why = _check_text(t.last_check, today, eff) if status.check_passed(t) else NOT_CHECKED
            attention.append(Attention(t.name, [why], f"check {t.name}"))
        last = records.last_run(paths, t.id)
        cards.append(Card(
            name=t.name,
            label=status.label(eff),
            pill=PILL_CLASS.get(eff, "off"),
            does=t.does,
            say=t.examples[0],
            rhythm=RHYTHM_WORDS.get(t.rhythm, t.rhythm),
            uses=_times(records.count_runs(paths, t.id)),
            last_used=f"Last used {short_date(last, today)}" if last else "",
            last_check=_check_text(t.last_check, today, eff),
            data_path=t.data_path,
            manual_steps=list(t.manual_steps),
            rules=[rule_text.get(r, r) for r in t.rules],
            improvements=[
                {"date": short_date(i["date"], today), "change": i["change"], "reason": i.get("reason", "")}
                for i in t.improvements
            ],
        ))

    learned = [
        Learned(
            text=r.text,
            reason=r.reason,
            scope="Used everywhere" if r.everywhere
            else "Used by " + ", ".join(names.get(s, s) for s in r.scope),
        )
        for r in rules
    ]

    return View(
        title=workspace.assistant_name(paths),
        updated=f"{today:%b} {today.day}, {today.year}, {now.hour % 12 or 12}:{now:%M %p}",
        working=working,
        needs_ok=needs_ok,
        uses_quarter=uses_quarter,
        estimate_hours=f"{minutes_total / 60:.1f} hrs" if has_estimate else None,
        attention=attention,
        cards=cards,
        learned=learned,
        ideas=list(ideas or []),
        retired=retired,
        problems=tool_problems + archive_problems,
        source_problems=source_problems,
        rule_problems=rule_problems,
    )


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True,
                       trim_blocks=True, lstrip_blocks=True)


def render(paths: Paths, today: date, ideas: list[str] | None = None,
           now: datetime | None = None) -> str:
    view = build_view(paths, today, ideas=ideas, now=now)
    return _env().get_template("dashboard.html.j2").render(v=view)


def write(paths: Paths, today: date, ideas: list[str] | None = None,
          now: datetime | None = None) -> Path:
    out = paths.dashboard
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".html.tmp")
    tmp.write_text(render(paths, today, ideas=ideas, now=now), encoding="utf-8")
    os.replace(tmp, out)
    return out
