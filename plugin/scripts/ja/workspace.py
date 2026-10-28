"""Find the assistant folder and name its standard paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_VAR = "JA_WORKSPACE"
MARKER = Path("assistant") / ".job-assistant"
DEFAULT_NAME = "My Job Assistant"

NOT_FOUND_MESSAGE = (
    "I could not find your assistant folder. Open the assistant from its shortcut, "
    "or run this inside your assistant folder."
)


class NoWorkspace(Exception):
    """No assistant folder was found."""

    def __init__(self, message: str = NOT_FOUND_MESSAGE) -> None:
        super().__init__(message)


def is_root(path: Path) -> bool:
    """An assistant folder has the marker file that init writes. A bare assistant/ folder is not enough."""
    return (path / MARKER).is_file()


def find_root(start: Path) -> Path:
    """JA_WORKSPACE when it names an assistant folder, else the nearest marked ancestor of start."""
    env = os.environ.get(ENV_VAR)
    if env and is_root(Path(env).expanduser().resolve()):
        return Path(env).expanduser().resolve()
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if is_root(candidate):
            return candidate
    raise NoWorkspace()


def assistant_name(paths: "Paths") -> str:
    """The first '# ' heading of CLAUDE.md, or the default name."""
    try:
        text = paths.claude_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return DEFAULT_NAME
    for line in text.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return DEFAULT_NAME


def resolve(explicit: str | None, start: Path) -> Path:
    """Order: the explicit path, then JA_WORKSPACE, then the nearest marked ancestor of start."""
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
