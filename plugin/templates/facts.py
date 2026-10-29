#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Facts step for one tool.

Reads its input files and prints one JSON object:
    {"facts": [{"id", "label", "value", "unit", "source", "notes"}],
     "counts": {name: whole number}, "problems": [plain sentences]}

Use the standard library only. When an input is an Excel file, add "openpyxl" to the
dependencies above. This step must not reach other systems or start programs; the
assistant refuses to run a step that tries.

When the tool lists its inputs (input.yaml), the helper passes each file by its input
name, so main() receives {"<input name>": path}. Read each file by its name, never by its
position. Without an input list, the files arrive as {"1": path, "2": path, ...}.

The step may read only the files it is given and files in the assistant folder. It may not
reach other systems, start programs, or change files: the helper blocks those while it runs.

Shared parts from the assistant folder load with load_part("<part id>").
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("JA_WORKSPACE") or Path(__file__).resolve().parents[3])
PARTS = WORKSPACE / "parts"
sys.path.insert(0, str(PARTS))


def load_part(part_id: str):
    """Load the code part parts/<part_id>/part.py as a module."""
    spec = importlib.util.spec_from_file_location(part_id.replace("-", "_"), PARTS / part_id / "part.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fact(fid: str, label: str, value, unit: str = "", source: str = "", notes: str = "") -> dict:
    return {"id": fid, "label": label, "value": value, "unit": unit, "source": source, "notes": notes}


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def given_inputs(args: list[str]) -> dict[str, Path]:
    """The input files by name: --input "<name>=<path>" pairs, or numbered when unnamed."""
    named: dict[str, Path] = {}
    plain: list[Path] = []
    rest = iter(args)
    for arg in rest:
        if arg == "--input":
            name, _, path = next(rest, "").partition("=")
            named[name] = Path(path)
        else:
            plain.append(Path(arg))
    return named or {str(n): p for n, p in enumerate(plain, start=1)}


def main(files: dict[str, Path]) -> dict:
    facts: list[dict] = []
    counts: dict[str, int] = {}
    problems: list[str] = []
    # Replace this example with the facts this tool needs. Read each input by its name,
    # for example files["inventory"].
    for name, path in files.items():
        key = name.replace(" ", "-")
        if path.suffix.lower() == ".csv":
            rows = read_csv(path)
            facts.append(fact(f"rows-{key}", f"Rows in the {name} file", len(rows), "rows", path.name))
            counts[f"rows_{key}"] = len(rows)
        else:
            problems.append(f"I do not know how to read {path.name} yet.")
    return {"facts": facts, "counts": counts, "problems": problems}


if __name__ == "__main__":
    print(json.dumps(main(given_inputs(sys.argv[1:])), ensure_ascii=False))
