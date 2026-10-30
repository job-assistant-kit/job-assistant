"""A shortcut that opens Claude Code in the assistant folder.

Writes outside the assistant folder, so the default is a preview that writes nothing.
Files carry a marker line; a file without it was not made here and is never replaced.
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
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


NO_CLAUDE = "I could not find Claude on this computer, so I cannot make a shortcut yet."
OTHER_SHORTCUT = {"Linux": "The menu shortcut works now.", "Darwin": "The desktop shortcut works now."}


def _script(root: Path, claude: str) -> str:
    return f"#!/bin/sh\n{MARKER}\ncd {shlex.quote(str(root))} || exit 1\nexec {shlex.quote(claude)} \"$@\"\n"


def _desktop_string(text: str) -> str:
    """Escape a value of type string in a desktop entry: backslash, newline, tab, return, leading space."""
    out = text.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return "\\s" + out[1:] if out.startswith(" ") else out


def _desktop_exec(program: str) -> str:
    """One quoted program path for the Exec key: the quoting rule first, then string escaping and %."""
    quoted = program.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return _desktop_string(f'"{quoted}"').replace("%", "%%")


def _desktop(name: str, root: Path, script: Path) -> str:
    return (
        "[Desktop Entry]\n"
        f"{MARKER}\n"
        "Type=Application\n"
        f"Name={_desktop_string(' '.join(name.split()))}\n"
        "Comment=Open your job assistant\n"
        f"Exec={_desktop_exec(str(script))}\n"
        f"Path={_desktop_string(str(root))}\n"
        "Icon=utilities-terminal\n"
        "Terminal=true\n"
        "Categories=Office;\n"
    )


def plan(paths: Paths, *, system: str | None = None, bin_dir: Path | None = None,
         apps_dir: Path | None = None, desktop_dir: Path | None = None, claude: str | None = None) -> list[Item]:
    system = system or platform.system()
    claude = claude or shutil.which("claude")
    if not claude:
        raise LauncherProblem(NO_CLAUDE)
    home = Path.home()
    bin_dir = Path(bin_dir or home / ".local" / "bin").expanduser()
    root = paths.root.resolve()
    script = bin_dir / COMMAND
    items = [Item(script, _script(root, claude), "a command that opens the assistant")]
    if system == "Linux":
        apps = Path(apps_dir or home / ".local" / "share" / "applications").expanduser()
        items.append(Item(apps / f"{COMMAND}.desktop", _desktop(workspace.assistant_name(paths), root, script),
                          "a menu shortcut"))
    elif system == "Darwin":
        desk = Path(desktop_dir or home / "Desktop").expanduser()
        items.append(Item(desk / "Job Assistant.command", _script(root, claude), "a desktop shortcut"))
    return items


def _ours(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


IN_PLACE = "The shortcut is already in place and opens this assistant folder."


def in_place(items: list[Item]) -> bool:
    """Every shortcut file exists with exactly the content this folder would write."""
    try:
        return all(item.path.read_text(encoding="utf-8") == item.content for item in items)
    except (OSError, UnicodeDecodeError):
        return False


def preview(items: list[Item]) -> str:
    if in_place(items):
        return IN_PLACE
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
    system = str(options.pop("system", None) or platform.system())
    items = plan(paths, system=system, **options)  # type: ignore[arg-type]
    if not yes:
        return preview(items)
    write(items)
    done = ["Your shortcut is ready:"] + [f"  {item.path}" for item in items]
    bin_dir = str(items[0].path.parent)
    if bin_dir not in os.environ.get("PATH", "").split(os.pathsep):
        note = f"Note: {bin_dir} is not on the search path yet, so typing {COMMAND} may not work until it is added."
        if system in OTHER_SHORTCUT:
            note += " " + OTHER_SHORTCUT[system]
        done.append(note)
    return "\n".join(done)
