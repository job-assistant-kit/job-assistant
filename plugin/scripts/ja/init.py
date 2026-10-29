"""Create a new assistant folder from the bundled template.

The folder is built in a temporary sibling and renamed into place at the end, so a
failure part way through leaves nothing behind.
"""

from __future__ import annotations

import errno
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ja import helper
from ja.workspace import DEFAULT_NAME, MARKER, Paths

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "workspace"
NAME_TOKEN = "{{assistant_name}}"

# Stored without the leading dot so the template's ignore rules do not hide the
# template's own placeholder folders in this source tree.
RENAMES = {"gitignore": ".gitignore"}


class NotEmpty(Exception):
    """The target folder already has files in it."""

    def __init__(self) -> None:
        super().__init__("That folder is not empty. Choose a new or empty folder for your assistant.")


class BadName(ValueError):
    """The assistant name is empty after cleaning."""

    def __init__(self) -> None:
        super().__init__("The assistant name cannot be empty. Use a short name, like Sam's Assistant.")


class CannotCreate(Exception):
    """The computer refused to create the folder."""

    def __init__(self, root: Path, exc: OSError) -> None:
        super().__init__(f"I could not create the folder at {root}: {plain_reason(exc)}.")


@dataclass
class Created:
    root: Path
    note: str | None = None


def plain_reason(exc: OSError) -> str:
    if isinstance(exc, PermissionError):
        return "you do not have permission to save there"
    if isinstance(exc, (NotADirectoryError, FileExistsError)):
        return "part of that path is a file, not a folder"
    if isinstance(exc, FileNotFoundError):
        return "part of that path does not exist"
    if exc.errno == errno.ENOSPC:
        return "the disk is full"
    if exc.errno == errno.EROFS:
        return "that place is read-only"
    if exc.errno == errno.ENAMETOOLONG:
        return "the folder name is too long"
    return "the computer would not save files there"


def clean_name(name: str | None) -> str:
    """One line, no angle brackets. None means the default name."""
    if name is None:
        return DEFAULT_NAME
    text = " ".join(name.replace("<", "").replace(">", "").split())
    if not text:
        raise BadName()
    return text


def _first_missing(path: Path) -> Path | None:
    """The highest ancestor of path (path included) that does not exist yet."""
    missing = None
    for candidate in (path, *path.parents):
        if candidate.exists():
            break
        missing = candidate
    return missing


def _fill(folder: Path, name: str) -> None:
    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        dest = folder / rel.parent / RENAMES.get(rel.name, rel.name)
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    claude_md = folder / "CLAUDE.md"
    claude_md.write_text(claude_md.read_text(encoding="utf-8").replace(NAME_TOKEN, name), encoding="utf-8")
    helper.sync(Paths(folder))
    if not (folder / MARKER).is_file():
        raise OSError("could not write the marker file")


NO_GIT = "Saved without version history because git is not installed."
GIT_FAILED = "Saved without version history because git could not set it up here."
FALLBACK_IDENTITY = ("-c", "user.name=Job Assistant", "-c", "user.email=assistant@localhost")


def _git(folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=60)


def _has_identity(folder: Path) -> bool:
    return all(_git(folder, "config", key).stdout.strip() for key in ("user.name", "user.email"))


def start_history(folder: Path) -> str | None:
    """Start version history with one commit of the non-data files. Returns a note when it could not."""
    if shutil.which("git") is None:
        return NO_GIT
    try:
        if _git(folder, "init", "-q", "-b", "main").returncode != 0:
            if _git(folder, "init", "-q").returncode != 0:
                raise OSError("git init failed")
            _git(folder, "symbolic-ref", "HEAD", "refs/heads/main")
        identity = () if _has_identity(folder) else FALLBACK_IDENTITY
        if _git(folder, "add", "-A").returncode != 0:
            raise OSError("git add failed")
        commit = _git(folder, *identity, "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify",
                      "-m", "Set up assistant folder")
        if commit.returncode != 0:
            raise OSError("git commit failed")
    except (OSError, subprocess.SubprocessError):
        shutil.rmtree(folder / ".git", ignore_errors=True)
        return GIT_FAILED
    return None


def _move_into_place(tmp: Path, root: Path) -> None:
    try:
        os.rename(tmp, root)
    except OSError:
        if not (root.is_dir() and not any(root.iterdir())):
            raise
        root.rmdir()
        os.rename(tmp, root)


def create(path: Path, name: str | None = None) -> Created:
    name = clean_name(name)
    root = Path(path).expanduser().resolve()
    try:
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise NotEmpty()
    except OSError as exc:
        raise CannotCreate(root, exc) from None
    made = _first_missing(root.parent)
    tmp: Path | None = None
    try:
        root.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=f".{root.name}.", suffix=".setup", dir=root.parent))
        _fill(tmp, name)
        note = start_history(tmp)
        _move_into_place(tmp, root)
        tmp = None
    except OSError as exc:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        if made is not None:
            shutil.rmtree(made, ignore_errors=True)
        raise CannotCreate(root, exc) from None
    return Created(root=root, note=note)
