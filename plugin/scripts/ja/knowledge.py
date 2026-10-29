"""Facts the person teaches, kept in assistant/knowledge.md, each with its source and date."""

from __future__ import annotations

import os
import re
from datetime import date

from ja import render
from ja.workspace import Paths

HEADING = "# What I have been taught\n\n"
ENTRY = re.compile(r"^- (.+) \(Source: .*\)$")


class KnowledgeProblem(ValueError):
    """A knowledge change cannot be made. The message is plain."""


def _clean(text: str) -> str:
    return render.one_line(render.no_comments(text)).rstrip(".").strip()


def _read(paths: Paths) -> str:
    try:
        return paths.knowledge.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write(paths: Paths, text: str) -> None:
    paths.knowledge.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.knowledge.with_suffix(".md.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, paths.knowledge)


def add(paths: Paths, fact: str, source: str, today: date) -> str:
    """Append one entry. A source is required; 'per <name>, <date>' counts as one."""
    fact, source = _clean(fact), _clean(source)
    if not fact:
        raise KnowledgeProblem("Say the fact in a few words.")
    if not source:
        raise KnowledgeProblem("Every fact needs a source, such as a document name or \"per <name>, <date>\".")
    line = f"- {fact} (Source: {source}. Added {today.isoformat()}.)"
    text = _read(paths) or HEADING
    if not text.endswith("\n"):
        text += "\n"
    _write(paths, text + line + "\n")
    return line


def entries(paths: Paths) -> list[str]:
    """Each entry without its leading dash."""
    return [line[2:] for line in _read(paths).splitlines() if ENTRY.match(line)]


def forget(paths: Paths, match: str) -> list[str]:
    """Remove the one entry whose fact contains the words. Returns the matching facts.

    Nothing is removed when no entry or more than one entry matches.
    """
    wanted = " ".join(match.lower().split())
    if not wanted:
        raise KnowledgeProblem("Say which fact to forget.")
    lines = _read(paths).splitlines(keepends=True)
    hits = [n for n, line in enumerate(lines)
            if (m := ENTRY.match(line.rstrip("\r\n"))) and wanted in " ".join(m.group(1).lower().split())]
    facts = [ENTRY.match(lines[n].rstrip("\r\n")).group(1) for n in hits]
    if len(hits) == 1:
        del lines[hits[0]]
        _write(paths, "".join(lines))
    return facts
