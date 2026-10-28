"""RUNBOOK.md: how a backup person runs each tool while its owner is away."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ja import files, registry, sources, status, workspace
from ja.registry import Tool
from ja.sources import Source
from ja.workspace import Paths

CONFIDENTIAL = "Contains confidential data. Ask before sharing results."


def _one_line(text: object) -> str:
    return " ".join(str(text).split())


def _check(tool: Tool) -> str:
    check = tool.last_check
    if not check:
        return "Not checked yet"
    word = "Passed" if check.get("result") == "pass" else "Failed"
    detail = _one_line(check.get("detail") or "")
    return f"{word} on {check['date']}" + (f": {detail}" if detail else "")


def _source_names(tool: Tool, by_id: dict[str, Source]) -> str:
    names = []
    for sid in tool.sources:
        src = by_id.get(sid)
        names.append(f"{src.name} ({_one_line(src.where)})" if src else f"{sid} (not on the sources list)")
    return "; ".join(names) if names else _one_line(tool.data_path)


def _section(tool: Tool, by_id: dict[str, Source], today: date) -> list[str]:
    eff = status.effective_status(tool, by_id, today)
    out = [f"## {_one_line(tool.name)}", ""]
    if tool.confidential:
        out += [f"**{CONFIDENTIAL}**", ""]
    out.append(f"- What it does: {_one_line(tool.does)}")
    out.append("- To start it, say: " + " or ".join(f'"{_one_line(e)}"' for e in tool.examples))
    out.append(f"- Status: {status.label(eff)}")
    out.append(f"- What to drop in: {_one_line(tool.data_path)}")
    if tool.manual_steps:
        out.append("- Steps to do first:")
        out += [f"  {n}. {_one_line(step)}" for n, step in enumerate(tool.manual_steps, 1)]
    out.append(f"- Where the data comes from: {_source_names(tool, by_id)}")
    out.append(f"- How often: {status.RHYTHM_WORDS.get(tool.rhythm, tool.rhythm)}")
    out.append(f"- Last check: {_check(tool)}")
    if tool.kind == "adopted":
        out.append(f"- Where it lives: {_one_line(tool.extra.get('lives_at') or 'Not recorded yet')}")
        out.append(f"- How to run it: {_one_line(tool.extra.get('how_to_run') or 'Not recorded yet')}")
    out.append("")
    return out


def render(paths: Paths, today: date) -> str:
    name = workspace.assistant_name(paths)
    tools, _ = registry.load_all(paths)
    by_id, _ = sources.load(paths)
    active = [t for t in tools if status.effective_status(t, by_id, today) != "retired"]
    lines = [
        f"# How to run {name}'s tools when they are away",
        "",
        "This guide is for a backup person. Open the assistant from its shortcut, then say the words "
        "shown for a tool. The assistant keeps this page up to date when a tool changes.",
        "",
    ]
    if not active:
        lines += ["No tools yet.", ""]
    for tool in active:
        lines += _section(tool, by_id, today)
    return "\n".join(lines).rstrip("\n") + "\n"


def write(paths: Paths, today: date) -> Path:
    files.write_raw(paths.runbook, render(paths, today))
    return paths.runbook
