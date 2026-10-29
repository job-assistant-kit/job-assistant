"""Input checks for a tool: the files it expects (input.yaml) and whether the given files fit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TYPES = ("csv", "xlsx", "json", "md", "txt", "pdf", "png")


class SpecProblem(ValueError):
    """The tool's input checks cannot be used. The message is plain."""


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
        out.append(Expected(name=name, types=list(types), required_columns=[c.strip() for c in columns],
                            min_rows=rows))
    return out
