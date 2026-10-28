"""Write the always-loaded tool index between the markers in CLAUDE.md."""

from __future__ import annotations

from datetime import date

from ja import files, registry, sources, status
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


def collect(paths: Paths, today: date) -> tuple[list[str], list[str]]:
    """One line per active tool (not retired), using the computed status, plus tool problems."""
    tools, problems = registry.load_all(paths)
    by_id, _ = sources.load(paths)
    out = []
    for t in tools:
        eff = status.effective_status(t, by_id, today)
        if eff != "retired":
            out.append(line_for(t, eff))
    return out or [EMPTY], problems


def lines(paths: Paths, today: date) -> list[str]:
    return collect(paths, today)[0]


def rewrite(paths: Paths, today: date) -> list[str]:
    """Rewrite the block between the markers. Returns the tools left out because their records are broken."""
    text = files.read_raw(paths.claude_md) if paths.claude_md.is_file() else ""
    if files.find_block(text, START, END) is None:
        raise MarkersMissing()
    found, problems = collect(paths, today)
    files.write_raw(paths.claude_md, files.replace_block(text, START, END, found))
    return problems
