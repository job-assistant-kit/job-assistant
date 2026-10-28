"""Small helpers for rewriting a marked block inside a text file."""

from __future__ import annotations

import os
from pathlib import Path


def read_raw(path: Path) -> str:
    """Text with its line endings untouched."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_raw(path: Path, text: str) -> None:
    """Write atomically, keeping the line endings in text as they are."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)


def line_ending(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def find_block(text: str, start: str, end: str) -> tuple[int, int] | None:
    """Positions of the start marker and the end marker after it, or None."""
    i = text.find(start)
    j = text.find(end, i + len(start)) if i != -1 else -1
    return None if i == -1 or j == -1 else (i, j)


def replace_block(text: str, start: str, end: str, lines: list[str]) -> str | None:
    """Text with the lines between the markers replaced, in the file's line endings. None if markers are missing."""
    found = find_block(text, start, end)
    if found is None:
        return None
    i, j = found
    eol = line_ending(text)
    return text[: i + len(start)] + eol + eol.join(lines) + eol + text[j:]
