"""Write the always-loaded tool index between the markers in CLAUDE.md."""

from __future__ import annotations

import os
from datetime import date

from ja import registry, sources, status
from ja.registry import Tool
from ja.workspace import Paths

START = "<!-- tool-index:start -->"
END = "<!-- tool-index:end -->"
EMPTY = "No tools yet."


class MarkersMissing(Exception):
    """CLAUDE.md does not have both tool index markers, in order."""

    def __init__(self) -> None:
        super().__init__(
            "Your assistant notes are missing the tool list markers. "
            f"Add the lines {START} and {END} to CLAUDE.md, then try again."
        )


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _sentence(text: str) -> str:
    text = _one_line(text)
    return text if text.endswith((".", "!", "?")) else text + "."


def line_for(tool: Tool, effective: str) -> str:
    example = _one_line(tool.examples[0])
    return f'- {_one_line(tool.name)} ({status.label(effective)}): {_sentence(tool.does)} Say: "{example}".'


def lines(paths: Paths, today: date) -> list[str]:
    """One line per active tool (not retired), using the computed status."""
    tools, _ = registry.load_all(paths)
    by_id, _ = sources.load(paths)
    out = []
    for t in tools:
        eff = status.effective_status(t, by_id, today)
        if eff != "retired":
            out.append(line_for(t, eff))
    return out or [EMPTY]


def rewrite(paths: Paths, today: date) -> None:
    text = paths.claude_md.read_text(encoding="utf-8") if paths.claude_md.is_file() else ""
    start = text.find(START)
    end = text.find(END, start + len(START)) if start != -1 else -1
    if start == -1 or end == -1:
        raise MarkersMissing()
    block = "\n" + "\n".join(lines(paths, today)) + "\n"
    new = text[: start + len(START)] + block + text[end:]
    tmp = paths.claude_md.with_suffix(".md.tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, paths.claude_md)
