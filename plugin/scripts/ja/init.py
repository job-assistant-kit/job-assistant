"""Create a new assistant folder from the bundled template."""

from __future__ import annotations

import shutil
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "workspace"
DEFAULT_NAME = "My Work Assistant"
NAME_TOKEN = "{{assistant_name}}"

# Stored without the leading dot so the template's ignore rules do not hide the
# template's own placeholder folders in this source tree.
RENAMES = {"gitignore": ".gitignore"}


class NotEmpty(Exception):
    """The target folder already has files in it."""

    def __init__(self) -> None:
        super().__init__("That folder is not empty. Choose a new or empty folder for your assistant.")


def create(path: Path, name: str | None = None) -> Path:
    root = Path(path).expanduser().resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise NotEmpty()
    root.mkdir(parents=True, exist_ok=True)
    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        dest = root / rel.parent / RENAMES.get(rel.name, rel.name)
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    claude_md = root / "CLAUDE.md"
    claude_md.write_text(claude_md.read_text(encoding="utf-8").replace(NAME_TOKEN, name or DEFAULT_NAME),
                         encoding="utf-8")
    return root
