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

from ja import helper, index, init, launcher, ledger, records, registry, role, runbook, settings, sources, status, tools, workspace
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
        paths = Paths(workspace.resolve(getattr(args, "workspace", None), Path.cwd()))
    except workspace.NoWorkspace as exc:
        raise Stop(str(exc)) from None
    helper.sync(paths)
    return paths


def _tool_exists(paths: Paths, tool_id: str) -> None:
    if not registry.ID_PATTERN.match(tool_id) or not (paths.skills_dir / tool_id / registry.RECORD_NAME).is_file():
        raise Stop(f"There is no tool called {tool_id}.")


def _guard(func):
    """Turn Stop and file errors into a plain message and exit code 1."""
    def wrapper(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except Stop as exc:
            return _fail(str(exc))
        except OSError as exc:
            return _fail(f"I could not finish this: {init.plain_reason(exc)}.")
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _stamp(args: argparse.Namespace) -> str:
    """Record time: the --today date (when given) at the current time of day."""
    return records.stamp(_today(args) if getattr(args, "today", None) else None)


def _refresh(paths: Paths, today: date) -> None:
    """After a change: rewrite the tool index, the tools page, and the backup guide. Never fails the change."""
    from ja import dashboard  # loaded here so other commands start faster

    try:
        problems = index.rewrite(paths, today=today)
    except index.MarkersMissing as exc:
        _warn(f"Saved, but I could not update the tool list: {exc}")
    except OSError:
        _warn("Saved, but I could not update the tool list in your assistant notes.")
    else:
        if problems:
            _warn("Some tool records have a mistake and were left out of the tool list. "
                  "Say \"fix my tools\" to look at them.")
    try:
        dashboard.write(paths, today=today)
    except OSError:
        _warn("Saved, but I could not update your tools page.")
    try:
        runbook.write(paths, today=today)
    except OSError:
        _warn("Saved, but I could not update the backup guide.")


def _warn(text: str) -> None:
    print(text, file=sys.stderr)


def _inside(folder: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(folder.resolve())
    except (ValueError, OSError):
        return False
    return True


def _in_inbox(paths: Paths, target: Path) -> bool:
    return _inside(paths.inbox, target)


def _tidy_inbox(paths: Paths, file: Path) -> None:
    """Remove a working file the setup or building steps left in the inbox or a draft folder. Other files stay."""
    target = Path(file).expanduser()
    if target.is_file() and (_in_inbox(paths, target) or _inside(paths.drafts_dir, target)):
        try:
            target.unlink()
        except OSError:
            pass


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
    _refresh(paths, today)
    word = "passed" if args.result == "pass" else "failed"
    _say(f"Saved: the check of {tool.name} {word} today.")
    return 0


@_guard
def cmd_role_set(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        text = Path(args.file).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise Stop(f"I could not read {args.file}. Check that the file exists and is plain text.") from None
    try:
        role.set_role(paths, text)
    except role.RoleProblem as exc:
        raise Stop(str(exc)) from None
    _tidy_inbox(paths, Path(args.file))
    _say("Saved the role description in your assistant notes.")
    return 0


@_guard
def cmd_settings_deny(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        added = settings.deny(paths, args.names)
    except settings.SettingsProblem as exc:
        raise Stop(str(exc)) from None
    _say(f"Blocked: {added} new write action{'' if added == 1 else 's'}.")
    return 0


@_guard
def cmd_settings_show(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        blocked, allowed = settings.show(paths)
    except settings.SettingsProblem as exc:
        raise Stop(str(exc)) from None
    _say(f"Blocked write actions ({len(blocked)}):")
    for name in blocked:
        _say(f"  {name}")
    _say(f"Allowed without asking ({len(allowed)}):")
    for name in allowed:
        _say(f"  {name}")
    return 0


@_guard
def cmd_sources_add(args: argparse.Namespace) -> int:
    paths = _paths(args)
    today = _today(args)
    entry = {"id": args.id, "name": args.name, "kind": args.kind, "where": args.where, "access": args.access,
             "version": args.version, "exported": args.exported, "fresh_days": args.fresh_days}
    try:
        src = sources.add(paths, entry, today=today)
    except sources.SourceProblem as exc:
        raise Stop(str(exc)) from None
    _refresh(paths, today)
    _say(f"Added {src.name} to your sources.")
    return 0


@_guard
def cmd_sources_exported(args: argparse.Namespace) -> int:
    paths = _paths(args)
    today = _today(args)
    try:
        sources.set_exported(paths, args.id, args.date, today=today)
    except sources.SourceProblem as exc:
        raise Stop(str(exc)) from None
    _refresh(paths, today)
    src = sources.load(paths)[0].get(args.id)
    _say(f"Saved: your copy of {src.name if src else args.id} is from {args.date}.")
    return 0


@_guard
def cmd_sources_list(args: argparse.Namespace) -> int:
    paths = _paths(args)
    rows = sources.describe(paths, _today(args))
    _, problems = sources.load(paths)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows and not problems:
        _say("No sources yet.")
    for r in rows:
        _say(f"{r['name']}: {r['reached']}. {r['age']}.")
    _say_problems("Sources with problems:", problems, gap=bool(rows))
    return 0


def _shows_as(paths: Paths, tool: registry.Tool, today: date) -> str:
    by_id, _ = sources.load(paths)
    return status.label(status.effective_status(tool, by_id, today))


def _tool_change(func):
    """Run a tool change, then refresh the tool list and the tools page."""
    @_guard
    def wrapper(args: argparse.Namespace) -> int:
        paths = _paths(args)
        today = _today(args)
        try:
            message = func(args, paths, today)
        except tools.ToolProblem as exc:
            raise Stop(str(exc)) from None
        _refresh(paths, today)
        _say(message)
        return 0
    wrapper.__name__ = func.__name__
    return wrapper


@_tool_change
def cmd_tool_add(args: argparse.Namespace, paths: Paths, today: date) -> str:
    tool, notes = tools.add_from_file(paths, Path(args.file), today=today)
    _tidy_inbox(paths, Path(args.file))
    return "\n".join([f'Added {tool.name} ({_shows_as(paths, tool, today)}). Say "{tool.examples[0]}" to use it.', *notes])


@_tool_change
def cmd_tool_draft(args: argparse.Namespace, paths: Paths, today: date) -> str:
    folder = tools.draft(paths, args.tool)
    name = tools.find(paths, args.tool).name
    return f"Working copies of the files for {name} are in {folder}. Change them there, then put them in place."


@_tool_change
def cmd_tool_files(args: argparse.Namespace, paths: Paths, today: date) -> str:
    source = Path(args.source).expanduser() if args.source else None
    tool, names, changed = tools.install_files(paths, args.tool, source)
    if not changed:
        return f"The files for {tool.name} were already up to date."
    return (f"Saved the {', '.join(names)} for {tool.name}. "
            "Check it on its saved examples before relying on it.")


@_tool_change
def cmd_tool_improve(args: argparse.Namespace, paths: Paths, today: date) -> str:
    tool = tools.improve(paths, args.tool, args.change, args.reason, today=today)
    return f"Saved the change to {tool.name}."


@_tool_change
def cmd_tool_status(args: argparse.Namespace, paths: Paths, today: date) -> str:
    tool = tools.set_status(paths, args.tool, args.status)
    return f"Saved. {tool.name} now shows as {_shows_as(paths, tool, today)}."


@_tool_change
def cmd_tool_retire(args: argparse.Namespace, paths: Paths, today: date) -> str:
    tool = tools.retire(paths, args.tool)
    return f'Retired {tool.name}. Say "bring back {tool.name}" to restore it.'


@_tool_change
def cmd_tool_restore(args: argparse.Namespace, paths: Paths, today: date) -> str:
    tool = tools.restore(paths, args.tool)
    return f"Restored {tool.name}. It shows as {_shows_as(paths, tool, today)}."


@_guard
def cmd_runbook(args: argparse.Namespace) -> int:
    paths = _paths(args)
    out = runbook.write(paths, today=_today(args))
    _say(f"The backup guide is ready: {out}")
    return 0


@_guard
def cmd_launcher(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        text = launcher.run(paths, yes=args.yes, bin_dir=args.bin_dir, apps_dir=args.apps_dir,
                            desktop_dir=args.desktop_dir)
    except launcher.LauncherProblem as exc:
        raise Stop(str(exc)) from None
    _say(text)
    return 0


PROGRAMS = ("git", "python3", "uv", "claude")


@_guard
def cmd_env(args: argparse.Namespace) -> int:
    """Which programs the assistant relies on are installed. Changes nothing."""
    found = {name: shutil.which(name) is not None for name in PROGRAMS}
    if args.json:
        print(json.dumps(found, indent=2))
        return 0
    for name in PROGRAMS:
        _say(f"{name}: {'installed' if found[name] else 'not installed'}")
    return 0
