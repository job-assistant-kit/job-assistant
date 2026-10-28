"""A shortcut that opens Claude Code in the assistant folder.

Writes outside the assistant folder, so the default is a preview that writes nothing.
Files carry a marker line; a file without it was not made here and is never replaced.
"""

from __future__ import annotations

import os
import platform
import shlex
from dataclasses import dataclass
from pathlib import Path

from ja import workspace
from ja.workspace import Paths

MARKER = "# Created by job-assistant. Opens the assistant in its folder."
COMMAND = "job-assistant"


class LauncherProblem(Exception):
    """The shortcut cannot be written. The message is plain."""


@dataclass
class Item:
    path: Path
    content: str
    what: str


def _script(root: Path) -> str:
    return f"#!/bin/sh\n{MARKER}\ncd {shlex.quote(str(root))} || exit 1\nexec claude \"$@\"\n"


def _desktop_quote(text: str) -> str:
    """Quote one argument for the Exec key of a .desktop file."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return f'"{escaped}"'.replace("%", "%%")


def _desktop(name: str, root: Path, script: Path) -> str:
    return (
        "[Desktop Entry]\n"
        f"{MARKER}\n"
        "Type=Application\n"
        f"Name={' '.join(name.split())}\n"
        "Comment=Open your job assistant\n"
        f"Exec={_desktop_quote(str(script))}\n"
        f"Path={root}\n"
        "Icon=utilities-terminal\n"
        "Terminal=true\n"
        "Categories=Office;\n"
    )


def plan(paths: Paths, *, system: str | None = None, bin_dir: Path | None = None,
         apps_dir: Path | None = None, desktop_dir: Path | None = None) -> list[Item]:
    system = system or platform.system()
    home = Path.home()
    bin_dir = Path(bin_dir or home / ".local" / "bin").expanduser()
    root = paths.root.resolve()
    script = bin_dir / COMMAND
    items = [Item(script, _script(root), "a command that opens the assistant")]
    if system == "Linux":
        apps = Path(apps_dir or home / ".local" / "share" / "applications").expanduser()
        items.append(Item(apps / f"{COMMAND}.desktop", _desktop(workspace.assistant_name(paths), root, script),
                          "a menu shortcut"))
    elif system == "Darwin":
        desk = Path(desktop_dir or home / "Desktop").expanduser()
        items.append(Item(desk / "Job Assistant.command", _script(root), "a desktop shortcut"))
    return items


def _ours(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def preview(items: list[Item]) -> str:
    lines = ["I can add a shortcut that opens your assistant. Nothing has been written yet.",
             "These files would be written:", ""]
    for item in items:
        lines.append(f"{item.path} ({item.what}):")
        lines += [f"    {line}" for line in item.content.splitlines()]
        lines.append("")
    lines.append("Run again with --yes to write them.")
    return "\n".join(lines)


def write(items: list[Item]) -> None:
    for item in items:
        if item.path.exists() and not _ours(item.path):
            raise LauncherProblem(f"There is already a file at {item.path} that I did not create. "
                                  "I left it alone and wrote nothing. Move that file, then try again.")
    for item in items:
        try:
            item.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = item.path.with_name(item.path.name + ".tmp")
            tmp.write_text(item.content, encoding="utf-8")
            tmp.chmod(0o755)
            os.replace(tmp, item.path)
        except OSError:
            raise LauncherProblem(f"I could not write the shortcut at {item.path}.") from None


def run(paths: Paths, *, yes: bool, **options: object) -> str:
    items = plan(paths, **options)  # type: ignore[arg-type]
    if not yes:
        return preview(items)
    write(items)
    done = ["Your shortcut is ready:"] + [f"  {item.path}" for item in items]
    bin_dir = str(items[0].path.parent)
    if bin_dir not in os.environ.get("PATH", "").split(os.pathsep):
        done.append(f"Note: {bin_dir} is not on the search path yet, so typing {COMMAND} may not work "
                    "until it is added. The other shortcut works now.")
    return "\n".join(done)
