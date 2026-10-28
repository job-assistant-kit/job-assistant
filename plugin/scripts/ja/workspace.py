"""Find the assistant folder and name its standard paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_VAR = "JA_WORKSPACE"

NOT_FOUND_MESSAGE = (
    "I could not find your assistant folder. Open the assistant from its shortcut, "
    "or run this inside your assistant folder."
)


class NoWorkspace(Exception):
    """No assistant folder was found."""

    def __init__(self, message: str = NOT_FOUND_MESSAGE) -> None:
        super().__init__(message)


def is_root(path: Path) -> bool:
    return (path / "assistant").is_dir()


def find_root(start: Path) -> Path:
    """Nearest ancestor of start (start included) with an assistant/ folder, else JA_WORKSPACE."""
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if is_root(candidate):
            return candidate
    env = os.environ.get(ENV_VAR)
    if env and is_root(Path(env).expanduser().resolve()):
        return Path(env).expanduser().resolve()
    raise NoWorkspace()


def resolve(explicit: str | None, start: Path) -> Path:
    """Use the explicit path when given, otherwise search from start."""
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not is_root(root):
            raise NoWorkspace()
        return root
    return find_root(start)


@dataclass(frozen=True)
class Paths:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def skills_dir(self) -> Path:
        return self.root / ".claude" / "skills"

    @property
    def archive_dir(self) -> Path:
        return self.root / "archive"

    @property
    def assistant_dir(self) -> Path:
        return self.root / "assistant"

    @property
    def profile(self) -> Path:
        return self.assistant_dir / "profile.yaml"

    @property
    def sources(self) -> Path:
        return self.assistant_dir / "sources.yaml"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def runs(self) -> Path:
        return self.data_dir / "records" / "runs.jsonl"

    @property
    def builds(self) -> Path:
        return self.data_dir / "records" / "builds.jsonl"

    @property
    def ledger(self) -> Path:
        return self.data_dir / "ledger.jsonl"

    @property
    def proofs_dir(self) -> Path:
        return self.data_dir / "proofs"

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def dashboard(self) -> Path:
        return self.root / "dashboard" / "index.html"

    @property
    def claude_md(self) -> Path:
        return self.root / "CLAUDE.md"
