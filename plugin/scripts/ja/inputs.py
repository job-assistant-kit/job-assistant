"""Input checks for a tool: the files it expects (input.yaml) and whether the given files fit."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

TYPES = ("csv", "xlsx", "json", "md", "txt", "pdf", "png")


class SpecProblem(ValueError):
    """The tool's input checks cannot be used. The message is plain."""


class MatchProblem(ValueError):
    """The given files cannot be matched to the tool's inputs. The message is plain."""


@dataclass
class Expected:
    name: str
    types: list[str]
    required_columns: list[str] = field(default_factory=list)
    min_rows: int = 0


def parse_spec(data: Any) -> list[Expected]:
    """Read the list of expected inputs. Raises SpecProblem with a plain message."""
    if not isinstance(data, list) or not data:
        raise SpecProblem("The input checks must list at least one expected file.")
    out: list[Expected] = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise SpecProblem("Each expected file in the input checks needs a name.")
        name = " ".join(item["name"].split())
        types = item.get("types")
        if not isinstance(types, list) or not types or any(t not in TYPES for t in types):
            raise SpecProblem(f"The input check for {name} must list file types from: {', '.join(TYPES)}.")
        columns = item.get("required_columns") or []
        if not isinstance(columns, list) or not all(isinstance(c, str) and c.strip() for c in columns):
            raise SpecProblem(f"The required columns for {name} must be a list of column names.")
        rows = item.get("min_rows", 0)
        if rows is None:
            rows = 0
        if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
            raise SpecProblem(f"The smallest number of rows for {name} must be a whole number.")
        if "=" in name:
            raise SpecProblem(f"The input name {name} cannot contain an equals sign.")
        if any(_key(e.name) == _key(name) for e in out):
            raise SpecProblem(f"The input checks list two expected files named {name}.")
        out.append(Expected(name=name, types=list(types), required_columns=[c.strip() for c in columns],
                            min_rows=rows))
    return out


SPEC_NAME = "input.yaml"
SIGNATURES = {"pdf": b"%PDF", "png": b"\x89PNG\r\n\x1a\n"}


@dataclass
class Seen:
    """What could be read from one given file."""
    path: Path
    kind: str
    columns: list[str] | None = None
    rows: int | None = None
    problem: str | None = None


@dataclass
class Report:
    problems: list[str]
    matched: list[tuple[str, str]]  # (expected input name, file name)
    unused: list[str]


def load_spec(folder: Path) -> list[Expected] | None:
    """The tool's expected inputs, or None when it has no input checks."""
    spec = folder / SPEC_NAME
    if not spec.is_file():
        return None
    try:
        data = yaml.safe_load(spec.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        raise SpecProblem("This tool's input checks could not be read.") from None
    return parse_spec(data)


def _text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _csv(path: Path) -> tuple[list[str], int]:
    rows = list(csv.reader(io.StringIO(_text(path), newline="")))
    if not rows:
        return [], 0
    data = [r for r in rows[1:] if any(cell.strip() for cell in r)]
    return [c.strip() for c in rows[0]], len(data)


def _xlsx(path: Path) -> tuple[list[str], int]:
    import openpyxl  # loaded only for Excel files

    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = book.worksheets[0]
        rows = [r for r in sheet.iter_rows(values_only=True)]
    finally:
        book.close()
    if not rows:
        return [], 0
    header = ["" if c is None else str(c).strip() for c in rows[0]]
    data = [r for r in rows[1:] if any(c is not None and str(c).strip() for c in r)]
    return header, len(data)


def look(path: Path) -> Seen:
    """Read enough of a file to check it. Never raises."""
    kind = path.suffix.lower().lstrip(".")
    seen = Seen(path=path, kind=kind)
    if not path.is_file():
        seen.problem = f"I could not find the file {path.name}."
        return seen
    try:
        if kind == "csv":
            seen.columns, seen.rows = _csv(path)
        elif kind == "xlsx":
            seen.columns, seen.rows = _xlsx(path)
        elif kind == "json":
            json.loads(_text(path))
        elif kind in ("md", "txt"):
            if not _text(path).strip():
                seen.problem = f"The file {path.name} is empty."
        elif kind in SIGNATURES:
            with path.open("rb") as fh:
                if not fh.read(8).startswith(SIGNATURES[kind]):
                    seen.problem = f"The file {path.name} is not a real {kind.upper()} file."
        else:
            path.open("rb").close()
    except json.JSONDecodeError:
        seen.problem = f"The file {path.name} could not be read. It may be cut short or saved in the wrong format."
    except OSError:
        seen.problem = f"I could not open the file {path.name}."
    except Exception:  # a damaged spreadsheet raises many kinds of errors
        seen.problem = f"The file {path.name} could not be read. It may be damaged or saved in the wrong format."
    return seen


def _key(text: str) -> str:
    return " ".join(text.split()).lower()


def _missing(expected: Expected, seen: Seen) -> list[str]:
    have = {_key(c) for c in seen.columns or []}
    return [c for c in expected.required_columns if _key(c) not in have]


def _kinds(types: list[str]) -> str:
    words = [t.upper() if t in ("csv", "pdf", "png", "json") else {"xlsx": "Excel", "md": "text", "txt": "text"}[t]
             for t in types]
    unique = list(dict.fromkeys(words))
    return unique[0] if len(unique) == 1 else ", ".join(unique[:-1]) + " or " + unique[-1]


def check(spec: list[Expected] | None, files: list[Path]) -> Report:
    """Check the given files against the expected inputs.

    Each expected input takes the unused file of an allowed type that has the most of its
    required columns, so the files may be given in any order.
    """
    seen = [look(Path(f)) for f in files]
    problems = [s.problem for s in seen if s.problem]
    if spec is None:
        return Report(problems=problems, matched=[], unused=[])
    usable = [s for s in seen if not s.problem]
    matched: list[tuple[str, str]] = []
    for expected in spec:
        candidates = [s for s in usable if s.kind in expected.types]
        if not candidates:
            problems.append(f"I still need the {expected.name} file ({_kinds(expected.types)}).")
            continue
        best = min(candidates, key=lambda s: len(_missing(expected, s)))
        usable.remove(best)
        matched.append((expected.name, best.path.name))
        for column in _missing(expected, best):
            problems.append(f"The file {best.path.name} is missing the column {column}.")
        if best.rows is not None and best.rows < expected.min_rows:
            problems.append(f"The file {best.path.name} has {best.rows} rows, but this needs at least "
                            f"{expected.min_rows}.")
    return Report(problems=problems, matched=matched, unused=[s.path.name for s in usable])


def _fits(expected: Expected, seen: Seen) -> bool:
    return seen.kind in expected.types and not _missing(expected, seen)


def assign(spec: list[Expected], files: list[Path], named: list[tuple[str, Path]] | tuple = ()) -> list[tuple[str, Path]]:
    """Match each expected input to one file, in the order of the input list.

    Files given with a name go to that input. Each other file must fit exactly one input
    that is still open (its type and required columns), and each input may take only one
    file. Anything unclear is refused, so a facts step never gets two files swapped.
    Raises MatchProblem with a plain message.
    """
    by_key = {_key(e.name): e for e in spec}
    listed = ", ".join(e.name for e in spec)
    chosen: dict[str, Path] = {}
    for name, path in named:
        expected = by_key.get(_key(name))
        if expected is None:
            raise MatchProblem(f"This tool has no input called {name}. Its inputs are: {listed}.")
        if expected.name in chosen:
            raise MatchProblem(f"The {expected.name} file was given twice.")
        seen = look(Path(path))
        if seen.problem:
            raise MatchProblem(seen.problem)
        if seen.kind not in expected.types:
            raise MatchProblem(f"The file {Path(path).name} is not a {_kinds(expected.types)} file, "
                               f"so it cannot be the {expected.name} file.")
        missing = _missing(expected, seen)
        if missing:
            raise MatchProblem(f"The file {Path(path).name} is missing the column {missing[0]}, "
                               f"so it cannot be the {expected.name} file.")
        chosen[expected.name] = Path(path)
    open_inputs = [e for e in spec if e.name not in chosen]
    seen_files = [look(Path(f)) for f in files]
    for seen in seen_files:
        if seen.problem:
            raise MatchProblem(seen.problem)
    fits = [(seen, [e for e in open_inputs if _fits(e, seen)]) for seen in seen_files]
    for seen, options in fits:
        if not options:
            raise MatchProblem(f"The file {seen.path.name} does not fit any input this tool takes: {listed}.")
        if len(options) > 1:
            raise MatchProblem(f"The file {seen.path.name} could be the {options[0].name} file or the "
                               f"{options[1].name} file. Say which file is which.")
    for expected in open_inputs:
        takers = [seen for seen, options in fits if options[0] is expected]
        if len(takers) > 1:
            raise MatchProblem(f"The files {takers[0].path.name} and {takers[1].path.name} both look like "
                               f"the {expected.name} file. Say which file is which.")
        if takers:
            chosen[expected.name] = takers[0].path
    for expected in spec:
        if expected.name not in chosen:
            raise MatchProblem(f"I still need the {expected.name} file ({_kinds(expected.types)}).")
    return [(e.name, chosen[e.name]) for e in spec]
