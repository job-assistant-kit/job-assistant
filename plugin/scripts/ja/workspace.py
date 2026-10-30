"""Find the assistant folder and name its standard paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_VAR = "JA_WORKSPACE"
MARKER = Path("assistant") / ".job-assistant"
DEFAULT_NAME = "My Job Assistant"

NOT_FOUND_MESSAGE = (
    "I could not find your assistant folder. Open your assistant folder in Claude (in the desktop app: "
    "Code, then Open folder), or use its shortcut."
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
    def knowledge(self) -> Path:
        return self.assistant_dir / "knowledge.md"

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
    def tasks(self) -> Path:
        """Work done without a tool, one short line each."""
        return self.data_dir / "records" / "tasks.jsonl"

    @property
    def ledger(self) -> Path:
        return self.data_dir / "ledger.jsonl"

    @property
    def proofs_dir(self) -> Path:
        return self.data_dir / "proofs"

    @property
    def drafts_dir(self) -> Path:
        """Working copies of a tool's files while it is built or changed."""
        return self.data_dir / "drafts"

    @property
    def last_dir(self) -> Path:
        """The most recent facts run for each tool."""
        return self.data_dir / "last"

    @property
    def building_dir(self) -> Path:
        """Start times of builds in progress."""
        return self.data_dir / "records" / "building"

    @property
    def parts_dir(self) -> Path:
        return self.root / "parts"

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def dashboard(self) -> Path:
        return self.root / "dashboard" / "index.html"

    @property
    def old_backup_guide(self) -> Path:
        return self.root / "RUNBOOK.md"

    @property
    def settings(self) -> Path:
        return self.root / ".claude" / "settings.json"

    @property
    def claude_md(self) -> Path:
        return self.root / "CLAUDE.md"


OLD_GUIDE_HEADING = "# How to run "
OLD_GUIDE_ENDING = "'s tools when they are away"


def remove_old_backup_guide(paths: "Paths") -> None:
    """Earlier versions wrote RUNBOOK.md, a backup guide. Remove it once, and only when the kit wrote it."""
    guide = paths.old_backup_guide
    try:
        first = guide.read_text(encoding="utf-8").split("\n", 1)[0]
    except (OSError, UnicodeDecodeError):
        return
    if first.startswith(OLD_GUIDE_HEADING) and first.endswith(OLD_GUIDE_ENDING):
        try:
            guide.unlink()
        except OSError:
            pass
