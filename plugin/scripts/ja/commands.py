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
from datetime import date, datetime
from pathlib import Path

from ja import facts, helper, profile, index, inputs, init, launcher, ledger, parts, proof, records, registry, role, runbook, settings, sources, status, tools, workspace
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
    minutes = args.minutes
    if minutes is None:
        minutes = records.build_minutes(paths, args.tool)
        if minutes is None:
            raise Stop("I do not know when this build started. Give the minutes it took.")
    try:
        records.add_build(paths, tool=args.tool, recipe=args.recipe, questions=args.questions,
                          corrections=args.corrections, minutes=minutes, ts=_stamp(args))
    except ValueError as exc:
        raise Stop(f"I could not save the build record: {exc}.") from None
    records.end_build(paths, args.tool)
    _say(f"Saved the build record: {minutes} minute{'' if minutes == 1 else 's'} to a working tool.")
    return 0


@_guard
def cmd_build_start(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if not registry.ID_PATTERN.match(args.id):
        raise Stop("The tool id must use only lowercase letters, numbers, and hyphens.")
    records.start_build(paths, args.id, ts=_stamp(args))
    _say("Noted the start time for this build.")
    return 0


BUILD_STEPS = (("record", "tool record saved", "write the tool record"),
               ("example", "example saved", "run it on their example and save it once they say it looks right"),
               ("check", "check recorded", "record the check"))


def _days_ago(n: int) -> str:
    if n <= 0:
        return "today"
    return "yesterday" if n == 1 else f"{n} days ago"


@_guard
def cmd_build_unfinished(args: argparse.Namespace) -> int:
    """Builds that were started and never recorded, with the steps already done."""
    paths = _paths(args)
    today = _today(args)
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
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        _say("No unfinished builds.")
    for r in rows:
        started = datetime.fromisoformat(r["started"]).date()
        done_words = ", ".join(word for key, word, _ in BUILD_STEPS if r["done"][key]) or "nothing"
        _say(f"{r['name']}: started {started:%b} {started.day}, {_days_ago(r['days_ago'])}. "
             f"Done so far: {done_words}. Next: {r['next']}.")
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


def _record_check(paths: Paths, tool: registry.Tool, result: str, detail: str, today: date) -> None:
    tool.last_check = {"date": today.isoformat(), "result": result, "detail": detail}
    registry.save(paths, tool)
    _refresh(paths, today)


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
    _record_check(paths, tool, args.result, args.detail or "", today)
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


def _tool(paths: Paths, tool_id: str) -> registry.Tool:
    try:
        return tools.find(paths, tool_id)
    except tools.ToolProblem as exc:
        raise Stop(str(exc)) from None


def _files(names: list[str]) -> list[Path]:
    return [Path(n).expanduser() for n in names]


@_guard
def cmd_input_check(args: argparse.Namespace) -> int:
    paths = _paths(args)
    tool = _tool(paths, args.tool)
    try:
        spec = inputs.load_spec(paths.skills_dir / tool.id)
    except inputs.SpecProblem as exc:
        raise Stop(f"{exc} Say \"fix {tool.name}\" to look at it.") from None
    report = inputs.check(spec, _files(args.files))
    if report.problems:
        for problem in report.problems:
            _say(problem)
        if tool.manual_steps:
            _say("")
            _say("To get the right file:")
            for n, step in enumerate(tool.manual_steps, start=1):
                _say(f"{n}. {step}")
        return 1
    if report.matched:
        _say("The files look right: " + "; ".join(f"{f} for {name}" for name, f in report.matched) + ".")
    else:
        _say("The files are there and can be read.")
    for name in report.unused:
        _say(f"I will not use {name} for this tool.")
    return 0


@_guard
def cmd_facts_run(args: argparse.Namespace) -> int:
    paths = _paths(args)
    tool = _tool(paths, args.tool)
    if not facts.has_step(paths, tool.id):
        _say(facts.NO_STEP)
        return 0
    files = _files(args.files)
    missing = [f.name for f in files if not f.is_file()]
    if missing:
        raise Stop(f"I could not find the file {missing[0]}.")
    try:
        result = facts.run(paths, tool.id, tool.name, files)
    except facts.FactsProblem as exc:
        raise Stop(str(exc)) from None
    facts.save_last(paths, tool.id, result, files)
    dates = {f.name: facts.received(f) for f in files}
    if args.json:
        print(json.dumps({**result.data, "received": dates}, indent=2, ensure_ascii=False))
        return 0
    for line in facts.describe(result):
        _say(line)
    _say("")
    for line in facts.received_lines(dates):
        _say(line)
    return 0


@_guard
def cmd_proof_save(args: argparse.Namespace) -> int:
    paths = _paths(args)
    tool = _tool(paths, args.tool)
    try:
        case = proof.save(paths, tool, _files(args.inputs), Path(args.output).expanduser(), today=_today(args))
    except proof.ProofProblem as exc:
        raise Stop(str(exc)) from None
    _say(f"Saved example {case.number} for {tool.name}. Later changes will be checked against it.")
    return 0


@_guard
def cmd_proof_list(args: argparse.Namespace) -> int:
    paths = _paths(args)
    tool = _tool(paths, args.tool)
    found = proof.cases(paths, tool.id)
    if not found:
        _say(f"There are no saved examples for {tool.name} yet.")
    for case in found:
        n = len(case.inputs)
        _say(f"Example {case.number}, saved {case.saved}, {n} input file{'' if n == 1 else 's'}.")
    return 0


@_guard
def cmd_proof_run(args: argparse.Namespace) -> int:
    paths = _paths(args)
    today = _today(args)
    tool = _tool(paths, args.tool)
    found = proof.cases(paths, tool.id)
    if args.case is not None:
        found = [c for c in found if c.number == args.case]
        if not found:
            raise Stop(f"There is no example {args.case} for {tool.name}.")
    if not found:
        raise Stop(f"There are no saved examples for {tool.name} yet, so there is nothing to check against.")
    items = proof.checklist(paths, tool.id)
    outcomes = []
    for case in found:
        outcome = proof.check_case(paths, tool, case)
        outcomes.append(outcome)
        _say(f"Example {case.number} (saved {case.saved}):")
        if outcome.failed:
            _say("  The facts changed:")
            for d in outcome.differences:
                _say(f"  {d}")
        elif outcome.compared:
            _say("  The facts match the saved example.")
        else:
            _say(f"  {outcome.note}")
        _say("  Input files: " + ", ".join(
            f"{p} (received {facts.day_text(case.received[p.name])})" if p.name in case.received else str(p)
            for p in case.inputs))
        _say(f"  Saved result: {case.output}")
        _say("  Checklist:")
        for item in items or ["(This tool has no checklist items yet.)"]:
            _say(f"  - {item}")
        _say(f"  {proof.REWRITE}")
    failed = [o for o in outcomes if o.failed]
    if failed:
        _record_check(paths, tool, "fail", proof.failure_detail(outcomes), today)
        _say("")
        _say(f"Saved: the check of {tool.name} failed because the facts changed.")
        return 1
    return 0


@_guard
def cmd_part_add(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        part, used = parts.add_from_file(paths, Path(args.file))
    except parts.PartProblem as exc:
        raise Stop(str(exc)) from None
    for f in used:
        _tidy_inbox(paths, f)
    _say(f"Added the part {part.name}. New tools can reuse it.")
    return 0


@_guard
def cmd_parts(args: argparse.Namespace) -> int:
    paths = _paths(args)
    found, problems = parts.load_all(paths)
    if args.json:
        print(json.dumps({"parts": [p.to_dict() for p in found], "problems": problems}, indent=2,
                         ensure_ascii=False))
        return 0
    if not found and not problems:
        _say("No parts yet.")
    names = {t.id: t.name for t in registry.load_all(paths)[0]}
    for part in found:
        used = ", ".join(names.get(t, t) for t in part.used_by) or "no tools yet"
        _say(f"{part.name} ({part.kind}, id {part.id}): {part.does} Used by: {used}.")
    _say_problems("Parts with problems:", problems, gap=bool(found))
    return 0


@_guard
def cmd_search(args: argparse.Namespace) -> int:
    paths = _paths(args)
    hits = parts.search(paths, " ".join(args.words), today=_today(args))
    if args.json:
        print(json.dumps([{"kind": h.kind, "id": h.id, "name": h.name, "score": h.score, "matched": h.matched}
                          for h in hits], indent=2, ensure_ascii=False))
        return 0
    if not hits:
        _say("Nothing similar yet. A new tool is needed.")
    for hit in hits:
        _say(hit.line)
    return 0


def _rule_change(func):
    """Run a rule change, then refresh the tool list, the tools page, and the backup guide."""
    @_guard
    def wrapper(args: argparse.Namespace) -> int:
        paths = _paths(args)
        today = _today(args)
        try:
            message = func(args, paths, today)
        except profile.RuleProblem as exc:
            raise Stop(str(exc)) from None
        _refresh(paths, today)
        _say(message)
        return 0
    wrapper.__name__ = func.__name__
    return wrapper


def _tool_names(paths: Paths) -> dict[str, str]:
    active, _ = registry.load_all(paths)
    archived, _ = registry.load_archive(paths)
    return {t.id: t.name for t in [*archived, *active]}


def _scope_words(rule: profile.Rule, names: dict[str, str]) -> str:
    if rule.everywhere:
        return "every tool"
    return ", ".join(names.get(t, t) for t in rule.scope)


@_rule_change
def cmd_rules_add(args: argparse.Namespace, paths: Paths, today: date) -> str:
    rule = profile.add(paths, rule_id=args.id, text=args.text, reason=args.reason, scope=args.scope,
                       pending=args.pending, today=today)
    where = _scope_words(rule, _tool_names(paths))
    if rule.state == "pending":
        return f"Saved the rule for {where}. It is waiting for a check on the saved examples before I use it."
    return f"Saved the rule. From now on I will follow it for {where}."


@_rule_change
def cmd_rules_confirm(args: argparse.Namespace, paths: Paths, today: date) -> str:
    rule = profile.confirm(paths, args.id)
    return f"The rule is now in use for {_scope_words(rule, _tool_names(paths))}: {rule.text}"


@_rule_change
def cmd_rules_hold(args: argparse.Namespace, paths: Paths, today: date) -> str:
    rule = profile.hold(paths, args.id, args.reason)
    if rule.active:
        return (f"Kept the rule for {_scope_words(rule, _tool_names(paths))} only, and not for every tool, "
                f"because {rule.held_reason}: {rule.text}")
    return f"Put the rule on hold, because {rule.held_reason}: {rule.text}"


@_rule_change
def cmd_rules_forget(args: argparse.Namespace, paths: Paths, today: date) -> str:
    return profile.no_longer(profile.forget(paths, args.id))


@_rule_change
def cmd_rules_promote(args: argparse.Namespace, paths: Paths, today: date) -> str:
    rule = profile.promote(paths, args.id)
    return ("The rule will apply to every tool once their saved examples are checked with it. "
            f"Until then it is waiting for a check: {rule.text}")


def _rule_row(rule: profile.Rule, names: dict[str, str]) -> dict:
    return {**rule.to_dict(), "used_by": _scope_words(rule, names)}


@_guard
def cmd_rules_for(args: argparse.Namespace) -> int:
    paths = _paths(args)
    tool = _tool(paths, args.tool)
    found = profile.applying(paths, tool.id)
    if args.json:
        print(json.dumps([{"id": r.id, "text": r.text} for r in found], indent=2, ensure_ascii=False))
        return 0
    if not found:
        _say(f"No learned rules apply to {tool.name}.")
    for r in found:
        _say(f"{r.id}: {r.text}")
    return 0


@_guard
def cmd_rules_list(args: argparse.Namespace) -> int:
    paths = _paths(args)
    rules, problems = profile.load(paths)
    names = _tool_names(paths)
    groups = {state: [r for r in rules if r.state == state] for state in ("active", "pending", "held")}
    if args.json:
        print(json.dumps({**{k: [_rule_row(r, names) for r in v] for k, v in groups.items()},
                          "problems": problems}, indent=2, ensure_ascii=False))
        return 0
    if not rules and not problems:
        _say("No learned rules yet.")
    first = True
    for state, found in groups.items():
        if not found:
            continue
        if not first:
            _say("")
        first = False
        _say(profile.STATE_HEADINGS[state] + ":")
        for r in found:
            why = f" Why: {r.held_reason}" if r.held_reason else ""
            _say(f"  {r.id}: {r.text} ({_scope_words(r, names)}){why}")
    _say_problems("Rules with problems:", problems, gap=bool(rules))
    return 0


@_guard
def cmd_rules_similar(args: argparse.Namespace) -> int:
    paths = _paths(args)
    found = profile.similar(paths, " ".join(args.words))
    names = _tool_names(paths)
    if args.json:
        print(json.dumps([{**_rule_row(r, names), "matched": m} for r, m in found], indent=2, ensure_ascii=False))
        return 0
    if not found:
        _say("No similar rules yet.")
    for r, matched in found:
        _say(f"{r.id} ({_scope_words(r, names)}): {r.text} Shared words: {', '.join(matched)}.")
    return 0


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
