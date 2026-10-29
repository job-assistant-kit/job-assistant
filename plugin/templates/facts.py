#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Facts step for one tool.

Reads the input files named on the command line and prints one JSON object:
    {"facts": [{"id", "label", "value", "unit", "source", "notes"}],
     "counts": {name: whole number}, "problems": [plain sentences]}

Use the standard library only. When an input is an Excel file, add "openpyxl" to the
dependencies above. This step must not reach other systems or start programs; the
assistant refuses to run a step that tries.

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


def main(paths: list[Path]) -> dict:
    facts: list[dict] = []
    counts: dict[str, int] = {}
    problems: list[str] = []
    # Replace this example with the facts this tool needs.
    for n, path in enumerate(paths, start=1):
        if path.suffix.lower() == ".csv":
            rows = read_csv(path)
            facts.append(fact(f"rows-{n}", f"Rows in {path.name}", len(rows), "rows", path.name))
            counts[f"rows_{n}"] = len(rows)
        else:
            problems.append(f"I do not know how to read {path.name} yet.")
    return {"facts": facts, "counts": counts, "problems": problems}


if __name__ == "__main__":
    print(json.dumps(main([Path(a) for a in sys.argv[1:]]), ensure_ascii=False))
