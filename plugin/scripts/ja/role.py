"""The role card block in CLAUDE.md, written by the setup steps."""

from __future__ import annotations

from ja import files, index
from ja.workspace import Paths

START = "<!-- role:start -->"
END = "<!-- role:end -->"
MAX_CHARS = 1600


class RoleProblem(ValueError):
    """The role text or the notes page cannot be used. The message is plain."""


def set_role(paths: Paths, text: str) -> None:
    body = text.strip()
    if not body:
        raise RoleProblem("The role description is empty. Write a few sentences about the job first.")
    if len(body) > MAX_CHARS:
        raise RoleProblem("The role description is too long. Keep it under about 250 words.")
    if any(marker in body for marker in (START, END, index.START, index.END)):
        raise RoleProblem("The role description contains a marker line from the notes page. Remove it and try again.")
    current = files.read_raw(paths.claude_md) if paths.claude_md.is_file() else ""
    new = files.replace_block(current, START, END, body.splitlines())
    if new is None:
        raise RoleProblem(
            "Your assistant notes are missing the role markers. "
            f"Add the lines {START} and {END} to CLAUDE.md, then try again."
        )
    files.write_raw(paths.claude_md, new)
