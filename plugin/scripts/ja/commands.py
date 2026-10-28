"""Command functions called by ja.py. Each takes parsed args and returns an exit code.

Everything printed here is read by a business user or relayed to one, so messages
are plain sentences. Output for code is only produced with --json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from ja import index, init, ledger, records, registry, sources, status, workspace
from ja.registry import is_date
from ja.workspace import Paths


class Stop(Exception):
    """End the command with a plain message and exit code 1."""


def _say(text: str) -> None:
    print(text)


def _fail(text: str) -> int:
    print(text, file=sys.stderr)
    return 1


def _today(args: argparse.Namespace) -> date:
    value = getattr(args, "today", None)
    if value is None:
        return date.today()
    if not is_date(value):
        raise Stop("The date must look like 2026-10-28.")
    return date.fromisoformat(value)


def _paths(args: argparse.Namespace) -> Paths:
    try:
        return Paths(workspace.resolve(getattr(args, "workspace", None), Path.cwd()))
    except workspace.NoWorkspace as exc:
        raise Stop(str(exc)) from None


def _tool_exists(paths: Paths, tool_id: str) -> None:
    if not registry.ID_PATTERN.match(tool_id) or not (paths.skills_dir / tool_id / registry.RECORD_NAME).is_file():
        raise Stop(f"There is no tool called {tool_id}.")


def _guard(func):
    """Turn Stop into a plain message and exit code 1."""
    def wrapper(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except Stop as exc:
            return _fail(str(exc))
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _stamp(args: argparse.Namespace) -> str:
    """Record time: the --today date (when given) at the current time of day."""
    return records.stamp(_today(args) if getattr(args, "today", None) else None)


@_guard
def cmd_init(args: argparse.Namespace) -> int:
    try:
        created = init.create(Path(args.path), name=args.name)
    except (init.NotEmpty, init.BadName, init.CannotCreate) as exc:
        raise Stop(str(exc)) from None
    _say(f"Your assistant folder is ready at {created.root}.")
    if created.note:
        _say(created.note)
    return 0


@_guard
def cmd_tools(args: argparse.Namespace) -> int:
    paths = _paths(args)
    today = _today(args)
    tools, problems = registry.load_all(paths)
    by_id, source_problems = sources.load(paths)
    rows = []
    for t in tools:
        eff = status.effective_status(t, by_id, today)
        if eff == "retired":
            continue
        rows.append({
            "id": t.id, "name": t.name, "status": eff, "label": status.label(eff),
            "example": t.examples[0], "runs": records.count_runs(paths, t.id),
            "last_run": records.last_run(paths, t.id), "reasons": status.reasons(t, by_id, today),
        })
    if args.json:
        print(json.dumps({"tools": rows, "problems": problems, "source_problems": source_problems},
                         indent=2, ensure_ascii=False))
        return 0
    if not rows and not problems:
        _say(index.EMPTY)
    for row in rows:
        _say(f'{row["name"]} ({row["label"]}). Say "{row["example"]}".')
        for reason in row["reasons"]:
            _say(f"  Why: {reason}")
    _say_problems("Tools with problems:", problems, gap=bool(rows))
    _say_problems("Sources with problems:", source_problems, gap=bool(rows or problems))
    return 0


def _say_problems(heading: str, problems: list[str], gap: bool = True) -> None:
    if not problems:
        return
    if gap:
        _say("")
    _say(heading)
    for p in problems:
        _say(f"  {p}")


@_guard
def cmd_index(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        problems = index.rewrite(paths, today=_today(args))
    except index.MarkersMissing as exc:
        raise Stop(str(exc)) from None
    if problems:
        _say("I updated the list of tools in your assistant notes, "
             "but left out tools whose records have a mistake.")
        _say_problems("Tools with problems:", problems)
    else:
        _say("The list of tools in your assistant notes is up to date.")
    return 0


def _open_in_browser(target: Path) -> bool:
    opener = shutil.which("xdg-open") or shutil.which("open")
    if not opener:
        return False
    try:
        subprocess.Popen([opener, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        return False
    return True


@_guard
def cmd_dashboard(args: argparse.Namespace) -> int:
    from ja import dashboard  # loaded here so other commands start faster

    paths = _paths(args)
    out = dashboard.write(paths, today=_today(args))
    _say(f"Your tools page is ready: {out}")
    if args.open and not _open_in_browser(out):
        _say("I could not open a browser. Open the page above yourself.")
    return 0


@_guard
def cmd_record_run(args: argparse.Namespace) -> int:
    paths = _paths(args)
    _tool_exists(paths, args.tool)
    records.add_run(paths, args.tool, args.event, ts=_stamp(args))
    return 0


@_guard
def cmd_record_build(args: argparse.Namespace) -> int:
    paths = _paths(args)
    _tool_exists(paths, args.tool)
    try:
        records.add_build(paths, tool=args.tool, recipe=args.recipe, questions=args.questions,
                          corrections=args.corrections, minutes=args.minutes, ts=_stamp(args))
    except ValueError as exc:
        raise Stop(f"I could not save the build record: {exc}.") from None
    return 0


@_guard
def cmd_ledger_add(args: argparse.Namespace) -> int:
    paths = _paths(args)
    approved = args.date or _today(args).isoformat()
    if not is_date(approved):
        raise Stop("The date must look like 2026-10-28.")
    try:
        ledger.add(paths, metric=args.metric, period=args.period, value=args.value, unit=args.unit,
                   source=args.source, method_notes=args.method_notes, approved_on=approved, tool=args.tool)
    except ValueError as exc:
        raise Stop(str(exc)) from None
    _say(f"Saved {args.value} {args.unit} for {args.period} as the published {args.metric} number.")
    return 0


@_guard
def cmd_ledger_compare(args: argparse.Namespace) -> int:
    paths = _paths(args)
    result = ledger.compare(paths, args.metric, args.value)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _say(ledger.describe(result))
    return 0


@_guard
def cmd_check(args: argparse.Namespace) -> int:
    paths = _paths(args)
    today = _today(args)
    try:
        tool = registry.find(paths, args.tool)
    except registry.ToolNotFound:
        raise Stop(f"There is no tool called {args.tool}.") from None
    except registry.InvalidTool as exc:
        raise Stop(f"I could not read this tool's record: {exc}") from None
    tool.last_check = {"date": today.isoformat(), "result": args.result, "detail": args.detail or ""}
    registry.save(paths, tool)
    word = "passed" if args.result == "pass" else "failed"
    _say(f"Saved: the check of {tool.name} {word} today.")
    return 0
