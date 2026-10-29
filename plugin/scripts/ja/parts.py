"""The parts library: pieces that several tools can share, and word search over tools and parts.

A part lives in parts/<id>/ with a record (part.yaml). Code parts (readers, steps, checks,
outputs) are one Python file, part.py, that facts steps load. Writer parts are written
instructions, part.md.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ja import registry, render, safety, status
from ja.workspace import Paths

RECORD_NAME = "part.yaml"
KINDS = ("reader", "step", "check", "writer", "output")
ID_PATTERN = registry.ID_PATTERN
CODE_NAME = "part.py"
TEXT_NAME = "part.md"
STOP_WORDS = frozenset(
    "a an and are as at be by can do does every for from get i in into is it its me my of on or our "
    "please so that the their them then this to up us we what when with you your".split())


class PartProblem(ValueError):
    """A part cannot be added or read. The message is plain."""


@dataclass
class Part:
    id: str
    name: str
    does: str
    kind: str
    file: str | None = None
    used_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "does": self.does, "kind": self.kind, "file": self.file,
                "used_by": self.used_by}


def _from_dict(data: Any, folder: str | None = None) -> Part:
    if not isinstance(data, dict):
        raise PartProblem("The part record must hold named fields.")
    pid = data.get("id")
    if not isinstance(pid, str) or not ID_PATTERN.match(pid):
        raise PartProblem("The part id must use only lowercase letters, numbers, and hyphens.")
    if folder is not None and pid != folder:
        raise PartProblem(f"{folder}: the part id must match its folder name.")
    for key in ("name", "does"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise PartProblem(f"{pid}: the part needs a {key}.")
    if data.get("kind") not in KINDS:
        raise PartProblem(f"{pid}: the kind must be one of {', '.join(KINDS)}.")
    file = data.get("file")
    if file is not None and (not isinstance(file, str) or not file.strip()):
        raise PartProblem(f"{pid}: the file must be a file name or empty.")
    used = data.get("used_by") or []
    if not isinstance(used, list) or not all(isinstance(u, str) for u in used):
        raise PartProblem(f"{pid}: used_by must be a list of tool ids.")
    return Part(id=pid, name=data["name"].strip(), does=data["does"].strip(), kind=data["kind"], file=file,
                used_by=list(used))


def _save(paths: Paths, part: Part) -> None:
    target = paths.parts_dir / part.id / RECORD_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(part.to_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, target)


def load(paths: Paths, part_id: str) -> Part:
    record = paths.parts_dir / part_id / RECORD_NAME
    if not ID_PATTERN.match(part_id) or not record.is_file():
        raise PartProblem(f"There is no part called {part_id}.")
    try:
        data = yaml.safe_load(record.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        raise PartProblem(f"{part_id}: the part record could not be read.") from None
    return _from_dict(data, folder=part_id)


def load_all(paths: Paths) -> tuple[list[Part], list[str]]:
    found: list[Part] = []
    problems: list[str] = []
    if not paths.parts_dir.is_dir():
        return found, problems
    for folder in sorted(p for p in paths.parts_dir.iterdir() if p.is_dir()):
        if not (folder / RECORD_NAME).is_file():
            continue
        try:
            found.append(load(paths, folder.name))
        except PartProblem as exc:
            problems.append(str(exc))
    return found, problems


def add_from_file(paths: Paths, file: Path) -> tuple[Part, list[Path]]:
    """Add a part from a record file. Its code or text file sits next to the record.

    Returns the part and the source files used, so the caller can tidy them away.
    """
    file = Path(file).expanduser()
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        raise PartProblem(f"I could not read {file.name}. Check that the file exists.") from None
    except yaml.YAMLError:
        raise PartProblem(f"The part record in {file.name} could not be read.") from None
    part = _from_dict(data)
    part.used_by = []
    if (paths.parts_dir / part.id).exists():
        raise PartProblem(f"There is already a part called {part.id}.")
    used = [file]
    source = None
    if part.file:
        source = file.parent / part.file
        if not source.is_file():
            raise PartProblem(f"I could not find {part.file} next to the part record.")
        suffix = source.suffix.lower()
        if suffix == ".py":
            refused = safety.problem(source)
            if refused:
                raise PartProblem(refused)
            part.file = CODE_NAME
        elif suffix == ".md":
            part.file = TEXT_NAME
        else:
            raise PartProblem("A part's file must be Python code (.py) or written instructions (.md).")
        used.append(source)
    folder = paths.parts_dir / part.id
    folder.mkdir(parents=True)
    try:
        if source is not None:
            shutil.copyfile(source, folder / part.file)
        _save(paths, part)
    except OSError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return part, used


def check_ids(paths: Paths, ids: Any) -> list[str]:
    """The part ids a tool record names, each checked to exist."""
    if ids is None:
        return []
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise PartProblem("parts must be a list of part ids.")
    for pid in ids:
        load(paths, pid)
    return ids


def mark_used(paths: Paths, part_ids: list[str], tool_id: str) -> None:
    for pid in part_ids:
        part = load(paths, pid)
        if tool_id not in part.used_by:
            part.used_by.append(tool_id)
            _save(paths, part)


def words(text: str) -> set[str]:
    """Lowercase words without common short words, with a plain plural s removed."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP_WORDS or len(w) < 2:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


@dataclass
class Hit:
    kind: str  # "tool" or "part"
    id: str
    name: str
    score: int
    matched: list[str]
    line: str


def search(paths: Paths, query: str, today: Any, limit: int = 5) -> list[Hit]:
    from ja import sources

    wanted = words(query)
    hits: list[Hit] = []
    by_id, _ = sources.load(paths)
    active, _ = registry.load_all(paths)
    retired, _ = registry.load_archive(paths)
    for tool in [*active, *retired]:
        have = words(" ".join([tool.name, tool.does, *tool.examples, tool.recipe or ""]))
        matched = sorted(wanted & have)
        if not matched:
            continue
        label = status.label(status.effective_status(tool, by_id, today))
        example = render.one_line(tool.examples[0])
        hits.append(Hit("tool", tool.id, tool.name, len(matched), matched,
                        f'Tool: {tool.name} ({label}). {render.one_line(tool.does)} Say "{example}". '
                        f"Matches: {', '.join(matched)}."))
    found, _ = load_all(paths)
    for part in found:
        matched = sorted(wanted & words(" ".join([part.name, part.does, part.kind])))
        if not matched:
            continue
        hits.append(Hit("part", part.id, part.name, len(matched), matched,
                        f"Part: {part.name} ({part.kind}, id {part.id}). {render.one_line(part.does)} "
                        f"Matches: {', '.join(matched)}."))
    hits.sort(key=lambda h: (-h.score, h.kind != "tool", h.name.lower()))
    return hits[:limit]
