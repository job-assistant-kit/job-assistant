"""Saved examples (proof cases) for a tool, and checks that rerun them.

A saved example holds the input files, the result the person accepted, and, for a tool
with a facts step, the facts from that run. A check reruns the facts step on the saved
inputs and compares the facts exactly. The written result is judged against the tool's
checklist by the building or learning steps, which record the outcome.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ja import facts
from ja.registry import Tool, is_date
from ja.workspace import Paths

CASE = re.compile(r"^case-(\d+)$")
REWRITE = "Now write the result again for this example and confirm each item above."
DAMAGED_DETAILS = "This saved example is damaged: its list of input files cannot be read."
FACTS_MISSING = "This saved example is damaged: its facts are missing."
FACTS_UNREADABLE = "This saved example is damaged: its facts cannot be read."
RESULT_MISSING = "This saved example is missing its result."


class ProofProblem(Exception):
    """An example cannot be saved or checked. The message is plain."""


@dataclass
class Case:
    number: int
    folder: Path
    saved: str
    inputs: list[Path]
    received: dict[str, str] = field(default_factory=dict)
    problem: str | None = None

    @property
    def output(self) -> Path:
        return self.folder / "output.md"

    @property
    def facts_file(self) -> Path:
        return self.folder / "facts.json"


@dataclass
class Outcome:
    case: Case
    compared: bool
    differences: list[str] = field(default_factory=list)
    note: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.differences or self.problems)


def tool_dir(paths: Paths, tool_id: str) -> Path:
    return paths.proofs_dir / tool_id


def cases(paths: Paths, tool_id: str) -> list[Case]:
    base = tool_dir(paths, tool_id)
    out: list[Case] = []
    if not base.is_dir():
        return out
    for folder in base.iterdir():
        m = CASE.match(folder.name)
        if not m or not folder.is_dir():
            continue
        meta = _meta(folder)
        if meta is None:
            # The saved order is part of the example; never guess it from the folder.
            out.append(Case(number=int(m.group(1)), folder=folder, saved="unknown", inputs=[],
                            problem=DAMAGED_DETAILS))
            continue
        got = meta.get("received") if isinstance(meta.get("received"), dict) else {}
        got = {str(k): v for k, v in got.items() if is_date(v)}
        out.append(Case(number=int(m.group(1)), folder=folder, saved=str(meta.get("saved", "unknown")),
                        inputs=[folder / "inputs" / n for n in meta["inputs"]], received=got))
    return sorted(out, key=lambda c: c.number)


def _meta(folder: Path) -> dict[str, Any] | None:
    """The example's details, or None when they cannot be read or do not list the input files."""
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict):
        return None
    names = meta.get("inputs")
    if not isinstance(names, list) or not all(isinstance(n, str) and n and Path(n).name == n for n in names):
        return None
    return meta


def _ordered_like_last_run(paths: Paths, tool_id: str, files: list[Path]) -> list[Path]:
    """The files in the order the latest facts run used. Raises when that run used other files."""
    out, inputs = facts.last_paths(paths, tool_id)
    if not out.is_file() or not inputs.is_file():
        raise ProofProblem("Run the facts step on this example first, so its facts can be saved with it.")
    try:
        used = json.loads(inputs.read_text(encoding="utf-8"))
        hashes = [u["sha256"] for u in used]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        raise ProofProblem("Run the facts step on this example again, so its facts can be saved with it.") from None
    given = {f["sha256"]: Path(p) for f, p in zip(facts.fingerprint(files), files)}
    if sorted(hashes) != sorted(given) or len(given) != len(files):
        raise ProofProblem("The last facts run used different files. Run the facts step on these files first.")
    return [given[h] for h in hashes]


def _last_roles(paths: Paths, tool_id: str) -> list[str] | None:
    """The input name each file had in the latest facts run, in the same order, or None."""
    try:
        used = json.loads(facts.last_paths(paths, tool_id)[1].read_text(encoding="utf-8"))
        roles = [u.get("role") for u in used]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError):
        return None
    return roles if roles and all(isinstance(r, str) and r for r in roles) else None


def save(paths: Paths, tool: Tool, inputs: list[Path], output: Path, today: date) -> Case:
    for f in [*inputs, output]:
        if not Path(f).is_file():
            raise ProofProblem(f"I could not find the file {Path(f).name}.")
    names = [Path(f).name for f in inputs]
    if len(set(names)) != len(names):
        raise ProofProblem("Two of the input files have the same name. Rename one and try again.")
    with_facts = facts.has_step(paths, tool.id)
    ordered = _ordered_like_last_run(paths, tool.id, inputs) if with_facts else list(inputs)
    existing = cases(paths, tool.id)
    number = (existing[-1].number if existing else 0) + 1
    folder = tool_dir(paths, tool.id) / f"case-{number}"
    tmp = folder.with_name(folder.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "inputs").mkdir(parents=True)
    try:
        for f in ordered:
            shutil.copyfile(f, tmp / "inputs" / Path(f).name)
        shutil.copyfile(output, tmp / "output.md")
        if with_facts:
            shutil.copyfile(facts.last_paths(paths, tool.id)[0], tmp / "facts.json")
        meta = {"saved": today.isoformat(), "inputs": [Path(f).name for f in ordered],
                "received": {Path(f).name: facts.received(f) for f in ordered}}
        roles = _last_roles(paths, tool.id) if with_facts else None
        if roles and len(roles) == len(ordered):
            meta["roles"] = {Path(f).name: r for f, r in zip(ordered, roles)}
        (tmp / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        tmp.rename(folder)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return Case(number=number, folder=folder, saved=today.isoformat(),
                inputs=[folder / "inputs" / n for n in meta["inputs"]], received=meta["received"])


def _shown(fact: dict[str, Any]) -> str:
    value = facts.value_text(fact.get("value"))
    return f"{value} {fact['unit']}" if fact.get("unit") else value


def _same(a: Any, b: Any) -> bool:
    """Equal values; true and 1 are different facts."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def compare(saved: list[dict[str, Any]], now: list[dict[str, Any]], saved_counts: dict[str, int] | None = None,
            now_counts: dict[str, int] | None = None) -> list[str]:
    """Plain sentences for every fact whose id, value, or unit differs, then every count that differs.

    Sources and notes are ignored. Counts must match exactly.
    """
    before = {f["id"]: f for f in saved}
    after = {f["id"]: f for f in now}
    out: list[str] = []
    for fid, old in before.items():
        new = after.get(fid)
        if new is None:
            out.append(f"{old['label']}: was {_shown(old)}, now no longer found")
        elif not _same(old.get("value"), new.get("value")) or new.get("unit", "") != old.get("unit", ""):
            out.append(f"{old['label']}: was {_shown(old)}, now {_shown(new)}")
    for fid, new in after.items():
        if fid not in before:
            out.append(f"{new['label']}: new fact, now {_shown(new)}")
    old_counts, new_counts = saved_counts or {}, now_counts or {}
    for name, old in old_counts.items():
        if name not in new_counts:
            out.append(f"The count {name}: was {old}, now no longer given")
        elif not _same(old, new_counts[name]):
            out.append(f"The count {name}: was {old}, now {new_counts[name]}")
    for name, new in new_counts.items():
        if name not in old_counts:
            out.append(f"The count {name}: new, now {new}")
    return out


def _saved_facts(case: Case) -> dict[str, Any] | None:
    try:
        return facts.validate(json.loads(case.facts_file.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None


def check_case(paths: Paths, tool: Tool, case: Case) -> Outcome:
    if case.problem:
        return Outcome(case=case, compared=False, problems=[case.problem])
    with_facts = facts.has_step(paths, tool.id)
    problems = [] if case.output.is_file() else [RESULT_MISSING]
    saved = None
    if with_facts:
        if not case.facts_file.is_file():
            problems.append(FACTS_MISSING)
        elif (saved := _saved_facts(case)) is None:
            problems.append(FACTS_UNREADABLE)
    if problems:
        return Outcome(case=case, compared=False, problems=problems)
    if not with_facts:
        return Outcome(case=case, compared=False, note="This tool has no facts step, so only the written "
                                                       "result can be checked.")
    missing = [p.name for p in case.inputs if not p.is_file()]
    if missing:
        return Outcome(case=case, compared=True, differences=[f"The saved file {missing[0]} is missing"])
    roles = _meta(case.folder) or {}
    roles = roles.get("roles") if isinstance(roles.get("roles"), dict) else None
    if roles and all(p.name in roles for p in case.inputs):
        files, named = [], [(roles[p.name], p) for p in case.inputs]
    else:
        files, named = case.inputs, []
    try:
        result = facts.run(paths, tool.id, tool.name, files, named=named)
    except facts.FactsProblem as exc:
        return Outcome(case=case, compared=True, differences=[str(exc).rstrip(".")])
    return Outcome(case=case, compared=True, differences=compare(saved["facts"], result.facts, saved["counts"],
                                                                 result.data["counts"]))


def checklist(paths: Paths, tool_id: str) -> list[str]:
    try:
        data = yaml.safe_load((paths.skills_dir / tool_id / "checklist.yaml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return []
    required = data.get("required") if isinstance(data, dict) else None
    return [x for x in required if isinstance(x, str)] if isinstance(required, list) else []


def failure_detail(outcomes: list[Outcome]) -> str:
    parts = []
    for o in outcomes:
        if o.failed:
            found = [p.rstrip(".") for p in o.problems] + o.differences
            parts.append(f"Example {o.case.number}: " + "; ".join(found[:3]))
    return ". ".join(parts)
