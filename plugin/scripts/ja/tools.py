"""Add and change tool records. Every change keeps the record valid under the registry rules."""

from __future__ import annotations

import os
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ja import helper, registry, render, safety
from ja.registry import RECORD_NAME, Tool
from ja.status import check_passed
from ja.workspace import Paths

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
ADOPTED_TEMPLATE = TEMPLATES / "adopted-skill.md"
BUILT_TEMPLATE = TEMPLATES / "built-skill.md"
CHECKLIST_TEMPLATE = TEMPLATES / "checklist.yaml"
FACTS_TEMPLATE = TEMPLATES / "facts.py"
SKILL_NAME = "SKILL.md"
CHECKLIST_NAME = "checklist.yaml"
INPUTS_NAME = "input.yaml"
FACTS_NAME = "facts.py"
FACTS_EXAMPLE = "facts-template.py"
WORKING_FILES = (SKILL_NAME, CHECKLIST_NAME, INPUTS_NAME, FACTS_NAME)
FILL_MARK = "<!-- fill:"
FILE_WORDS = {SKILL_NAME: "instructions page", CHECKLIST_NAME: "checklist", INPUTS_NAME: "input checks",
              FACTS_NAME: "facts step"}
NUMBER_SIGNOFF = (
    "\n## Number sign-off\n\n"
    "The numbers from this tool go to leaders or published pages. Label every number \"Draft, not checked\" "
    "until the person approves it through number sign-off. Never call a number checked yourself.\n\n"
    "For each such number, follow the check-number steps: give them the metric, value, unit, period, this tool "
    "(<id>), and the counts of rows left out and in total from the facts step.\n"
)
ADOPTED_REQUIRED = ("lives_at", "how_to_run")
NOT_RECORDED = "Not recorded yet. Ask the person."
SETTABLE = ("working", "draft-not-checked", "being-built", "paused")


class ToolProblem(ValueError):
    """A tool change cannot be made. The message is plain."""


def _read_record(file: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(Path(file).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        raise ToolProblem(f"I could not read {file}. Check that the file exists.") from None
    except yaml.YAMLError:
        raise ToolProblem(f"The tool record in {file} could not be read.") from None
    if not isinstance(data, dict):
        raise ToolProblem(f"The tool record in {file} must hold named fields.")
    return data


def _exists(paths: Paths, tool_id: str) -> bool:
    return (paths.skills_dir / tool_id).exists() or (paths.archive_dir / tool_id).exists()


def _text(value: Any) -> str:
    """One line of text, or one line per list item. Never empty."""
    if value is None or (isinstance(value, (str, list)) and not value):
        return NOT_RECORDED
    if isinstance(value, list):
        return "\n".join(f"- {render.one_line(v)}" for v in value)
    return render.one_line(value) or NOT_RECORDED


def description_for(tool: Tool) -> str:
    examples = "; ".join(f'"{render.one_line(e)}"' for e in tool.examples)
    text = f"{render.one_line(tool.does)} Use when the person says things like {examples}, or asks for the same thing in other words."
    return text[:1000]


def adopted_skill(tool: Tool) -> str:
    """The instructions page for an inherited tool, filled from its record."""
    values = {
        "skill_name": render.yaml_scalar(tool.id),
        "description": render.yaml_scalar(description_for(tool)),
        "name": render.one_line(tool.name),
        "does": render.one_line(tool.does),
        "lives_at": _text(tool.extra.get("lives_at")),
        "how_to_run": _text(tool.extra.get("how_to_run")),
        "inputs": _text(tool.extra.get("inputs")),
        "outputs": _text(tool.extra.get("outputs")),
        "last_good_run": _text(tool.extra.get("last_good_run")),
    }
    return render.fill(ADOPTED_TEMPLATE.read_text(encoding="utf-8"), values)


def built_skill(tool: Tool, script: Path | str = helper.SCRIPT) -> str:
    """The instructions page frame for a tool built here, with the helper's full path."""
    rules = helper.allow_rules(str(script))
    values = {
        "skill_name": render.yaml_scalar(tool.id),
        "description": render.yaml_scalar(description_for(tool)),
        "allow_quoted": render.yaml_scalar(rules[1]),
        "allow_plain": render.yaml_scalar(rules[0]),
        "name": render.one_line(tool.name),
        "does": render.one_line(tool.does),
        "id": tool.id,
        "ja_path": str(script),
        "number_signoff": NUMBER_SIGNOFF.replace("<id>", tool.id) if tool.exec_numbers else "",
    }
    return render.fill(BUILT_TEMPLATE.read_text(encoding="utf-8"), values)


NEW_STATUSES = ("being-built", "draft-not-checked")
DROPPED_CHECK = "I left out the check result in the record. A new tool gets checked on a real example first."
STARTS_AS_DRAFT = "It starts as Draft, not checked until a check on a real example passes."


def _new_tool_status(data: dict[str, Any]) -> list[str]:
    """New tools never start as checked. Adjusts data in place; returns plain notes."""
    notes: list[str] = []
    declared = data.get("status")
    if declared == "retired":
        raise ToolProblem("A new tool cannot start as retired.")
    if declared == "needs-update":
        raise ToolProblem("That status is worked out from checks and cannot be set by hand.")
    if data.get("last_check") is not None:
        data["last_check"] = None
        notes.append(DROPPED_CHECK)
    if declared in registry.STATUSES and declared not in NEW_STATUSES:
        data["status"] = "draft-not-checked"
        if declared == "working":
            notes.append(STARTS_AS_DRAFT)
    return notes


def add_from_file(paths: Paths, file: Path, today: date) -> tuple[Tool, list[str]]:
    """Add a tool from a record file. Returns the tool and plain notes about what was adjusted."""
    data = registry._normalize_dates(_read_record(file))
    data.setdefault("created", today.isoformat())
    notes = _new_tool_status(data)
    tool_id = data.get("id")
    try:
        tool = Tool.from_dict(data, folder=tool_id if isinstance(tool_id, str) else None)
    except registry.InvalidTool as exc:
        raise ToolProblem(str(exc)) from None
    if tool.kind == "adopted":
        for key in ADOPTED_REQUIRED:
            if not isinstance(tool.extra.get(key), str) or not tool.extra[key].strip():
                raise ToolProblem(f"{tool.id}: {key} is missing")
    if _exists(paths, tool.id):
        raise ToolProblem(f"There is already a tool called {tool.id}.")
    from ja import parts

    try:
        used_parts = parts.check_ids(paths, tool.extra.get("parts"))
    except parts.PartProblem as exc:
        raise ToolProblem(str(exc)) from None
    folder = paths.skills_dir / tool.id
    folder.mkdir(parents=True)
    tool.path = folder / RECORD_NAME
    registry.save(paths, tool)
    parts.mark_used(paths, used_parts, tool.id)
    if tool.kind == "adopted":
        (folder / SKILL_NAME).write_text(adopted_skill(tool), encoding="utf-8")
    else:
        (folder / SKILL_NAME).write_text(built_skill(tool), encoding="utf-8")
        shutil.copyfile(CHECKLIST_TEMPLATE, folder / CHECKLIST_NAME)
        draft(paths, tool.id, keep_existing=True)
    return tool, notes


def draft_dir(paths: Paths, tool_id: str) -> Path:
    return paths.drafts_dir / tool_id


def draft(paths: Paths, tool_id: str, keep_existing: bool = False) -> Path:
    """Copy a tool's working files into its draft folder, where the steps may edit them.

    The tool folder itself sits in a place the assistant may not write to without asking,
    so changes are made in the draft folder and put in place with install_files.
    With keep_existing, files already in the draft folder are left as they are.
    """
    folder = paths.skills_dir / tool_id
    if not registry.ID_PATTERN.match(tool_id) or not (folder / RECORD_NAME).is_file():
        raise ToolProblem(f"There is no tool called {tool_id}.")
    target = draft_dir(paths, tool_id)
    if target.exists() and not keep_existing:
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for name in WORKING_FILES:
        if (folder / name).is_file() and not (target / name).exists():
            shutil.copyfile(folder / name, target / name)
    if not (folder / FACTS_NAME).is_file() and not (target / FACTS_NAME).exists():
        shutil.copyfile(FACTS_TEMPLATE, target / FACTS_EXAMPLE)
    return target


def _skill_problem(tool_id: str, text: str) -> str | None:
    if not text.startswith("---\n") or text.count("---\n") < 2:
        return "The instructions page must start with its name and description between two --- lines."
    try:
        front = yaml.safe_load(text.split("---\n", 2)[1])
    except yaml.YAMLError:
        return "The top of the instructions page could not be read."
    if not isinstance(front, dict) or front.get("name") != tool_id:
        return f"The instructions page must be named {tool_id}."
    desc = front.get("description")
    if not isinstance(desc, str) or not desc.strip() or len(desc) >= 1024:
        return "The instructions page needs a description of one to a few sentences."
    if FILL_MARK in text:
        return "The instructions page still has parts to fill in."
    return None


def _checklist_problem(text: str) -> str | None:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return "The checklist could not be read."
    if not isinstance(data, dict):
        return "The checklist must have a list of required items."
    required = data.get("required")
    if not isinstance(required, list) or not required or \
            not all(isinstance(x, str) and x.strip() for x in required):
        return "The checklist must list at least one required item, each as a plain sentence."
    rules = data.get("rules", [])
    if rules is not None and not (isinstance(rules, list) and all(isinstance(x, str) for x in rules)):
        return "The checklist rules must be a list of short names."
    return None


def _inputs_problem(text: str) -> str | None:
    from ja import inputs

    try:
        inputs.parse_spec(yaml.safe_load(text))
    except yaml.YAMLError:
        return "The input checks could not be read."
    except inputs.SpecProblem as exc:
        return str(exc)
    return None


def _file_problem(tool_id: str, name: str, source: Path) -> str | None:
    if name == FACTS_NAME:
        return safety.problem(source)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return f"I could not read the {FILE_WORDS[name]}."
    if name == SKILL_NAME:
        return _skill_problem(tool_id, text)
    if name == CHECKLIST_NAME:
        return _checklist_problem(text)
    return _inputs_problem(text)


def install_files(paths: Paths, tool_id: str, source: Path | None = None) -> tuple[Tool, list[str], bool]:
    """Check the working files in the draft folder and put them in the tool folder.

    Returns the tool, the plain names of the files put in place, and whether anything changed.
    Nothing is copied unless every file passes its check. A change clears the last check,
    because the tool has to be checked again on its saved examples.
    """
    tool = find(paths, tool_id)
    source = Path(source) if source else draft_dir(paths, tool_id)
    found = [n for n in WORKING_FILES if (source / n).is_file()]
    if not found:
        raise ToolProblem(f"There are no working files for {tool.name} to put in place.")
    for name in found:
        problem = _file_problem(tool.id, name, source / name)
        if problem:
            raise ToolProblem(f"{problem} Nothing was changed.")
    folder = paths.skills_dir / tool.id
    changed = False
    for name in found:
        new = (source / name).read_bytes()
        old = (folder / name).read_bytes() if (folder / name).is_file() else None
        if new != old:
            tmp = folder / (name + ".tmp")
            tmp.write_bytes(new)
            os.replace(tmp, folder / name)
            changed = True
    if changed and tool.last_check is not None:
        tool.last_check = None
        registry.save(paths, tool)
    return tool, [FILE_WORDS[n] for n in found], changed


def find(paths: Paths, tool_id: str) -> Tool:
    try:
        return registry.find(paths, tool_id)
    except registry.ToolNotFound:
        raise ToolProblem(f"There is no tool called {tool_id}.") from None
    except registry.InvalidTool as exc:
        raise ToolProblem(f"I could not read this tool's record: {exc}") from None


def improve(paths: Paths, tool_id: str, change: str, reason: str, today: date) -> Tool:
    if not change.strip():
        raise ToolProblem("Describe the change in a few words.")
    tool = find(paths, tool_id)
    tool.improvements.append({"date": today.isoformat(), "change": change.strip(), "reason": reason.strip()})
    registry.save(paths, tool)
    return tool


def set_status(paths: Paths, tool_id: str, new: str) -> Tool:
    if new == "needs-update":
        raise ToolProblem("That status is worked out from checks and cannot be set by hand.")
    if new == "retired":
        raise ToolProblem("Retiring moves the tool to the archive. Use the retire step instead.")
    if new not in SETTABLE:
        raise ToolProblem("The status must be one of " + ", ".join(SETTABLE) + ".")
    tool = find(paths, tool_id)
    tool.status = new
    registry.save(paths, tool)
    return tool


def _move(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dest)


def retire(paths: Paths, tool_id: str) -> Tool:
    tool = find(paths, tool_id)
    target = paths.archive_dir / tool_id
    if target.exists():
        raise ToolProblem(f"The archive already has a tool called {tool_id}. Restore or remove that one first.")
    _move(paths.skills_dir / tool_id, target)
    tool.path = target / RECORD_NAME
    tool.status = "retired"
    registry.save(paths, tool)
    return tool


def restore(paths: Paths, tool_id: str) -> Tool:
    record = paths.archive_dir / tool_id / RECORD_NAME
    if not registry.ID_PATTERN.match(tool_id) or not record.is_file():
        raise ToolProblem(f"There is no retired tool called {tool_id}.")
    target = paths.skills_dir / tool_id
    if target.exists():
        raise ToolProblem(f"There is already an active tool called {tool_id}.")
    try:
        tool = registry.load_file(record)
    except registry.InvalidTool as exc:
        raise ToolProblem(f"I could not read this tool's record: {exc}") from None
    _move(paths.archive_dir / tool_id, target)
    tool.path = target / RECORD_NAME
    tool.status = "working" if check_passed(tool) else "draft-not-checked"
    registry.save(paths, tool)
    return tool
