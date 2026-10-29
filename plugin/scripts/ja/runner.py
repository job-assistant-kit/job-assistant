"""Run a tool's facts step with outside actions blocked.

Usage: python runner.py <workspace> <facts.py> [input files...]

The facts step is code the assistant wrote. Before it runs, this program installs a
Python audit hook. The hook sees every attempt to open a network connection, start a
program, load native code, change a file, or read outside the allowed folders, and
refuses it at the moment it happens, however the code reached it. Hooks cannot be
removed once installed, and the hook refuses any attempt to add another.

This is strong in-process enforcement for code written by the assistant. It is not an
operating system sandbox.

The program has no imports from the rest of the helper, so it can run in a bare
environment. A refused action ends the run with exit code 3 and one line on stderr:
"JA-BLOCKED: <what it tried>".
"""

from __future__ import annotations

import os
import runpy
import sys

BLOCKED_EXIT = 3
MARKER = "JA-BLOCKED: "

REACH = "reach another system"
RUN = "run a program"
NATIVE = "load code from outside Python"
CHANGE = "change a file"
READ = "read a file outside the assistant folder"
GUARD = "turn off its safety checks"

_PREFIXES: list[tuple[str, str]] = [
    ("socket.", REACH), ("http.client.", REACH), ("ftplib.", REACH), ("smtplib.", REACH),
    ("imaplib.", REACH), ("poplib.", REACH), ("nntplib.", REACH), ("telnetlib.", REACH),
    ("urllib.Request", REACH), ("webbrowser.open", REACH),
    ("subprocess.", RUN), ("os.system", RUN), ("os.exec", RUN), ("os.spawn", RUN),
    ("os.posix_spawn", RUN), ("os.fork", RUN), ("os.forkpty", RUN), ("os.startfile", RUN),
    ("pty.spawn", RUN), ("os.kill", RUN), ("os.killpg", RUN), ("signal.pthread_kill", RUN),
    ("ctypes.", NATIVE), ("cpython.remote_debugger_script", NATIVE),
    ("os.remove", CHANGE), ("os.rename", CHANGE), ("os.mkdir", CHANGE), ("os.rmdir", CHANGE),
    ("os.chmod", CHANGE), ("os.chown", CHANGE), ("os.chflags", CHANGE), ("os.link", CHANGE),
    ("os.symlink", CHANGE), ("os.truncate", CHANGE), ("os.utime", CHANGE), ("os.mkfifo", CHANGE),
    ("os.mknod", CHANGE), ("os.setxattr", CHANGE), ("os.removexattr", CHANGE), ("shutil.", CHANGE),
    ("tempfile.mkstemp", CHANGE), ("tempfile.mkdtemp", CHANGE),
    ("sys.addaudithook", GUARD), ("sys.settrace", GUARD), ("sys.setprofile", GUARD),
]

_NATIVE_MODULES = {"ctypes", "_ctypes", "cffi", "_cffi_backend"}
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_READ_ROOTS: tuple[str, ...] = ()
_READ_FILES: frozenset[str] = frozenset()
_blocked: list[str] = []


def _real(path: object) -> str | None:
    if isinstance(path, int):
        return None
    try:
        return os.path.realpath(os.fsdecode(path))
    except (TypeError, ValueError):
        return ""


def _inside(path: str) -> bool:
    if path in _READ_FILES:
        return True
    return any(path == root or path.startswith(root + os.sep) for root in _READ_ROOTS)


def _refuse(what: str) -> None:
    _blocked.append(what)
    raise PermissionError(f"Blocked: this step may not {what}.")


def _hook(event: str, args: tuple) -> None:
    if event == "open":
        path, mode, flags = (tuple(args) + (None, None, None))[:3]
        writes = (set(mode) & set("wax+")) if isinstance(mode, str) else (
            mode is None and isinstance(flags, int) and flags & _WRITE_FLAGS)
        if writes:
            _refuse(CHANGE)
        real = _real(path)
        if real is not None and not _inside(real):
            _refuse(READ)
        return
    if event in ("os.listdir", "os.scandir"):
        real = _real(args[0]) if args and args[0] is not None else _real(".")
        if real is not None and not _inside(real):
            _refuse(READ)
        return
    if event == "import" and args and str(args[0]).split(".")[0] in _NATIVE_MODULES:
        _refuse(NATIVE)
    for prefix, what in _PREFIXES:
        if event.startswith(prefix):
            _refuse(what)


def _roots(workspace: str) -> tuple[str, ...]:
    roots = {workspace, sys.prefix, sys.base_prefix, sys.exec_prefix, "/usr/share/zoneinfo", "/etc/localtime"}
    roots.update(p for p in sys.path if p)
    out = []
    for r in roots:
        real = _real(r)
        if real:
            out.append(real.rstrip(os.sep) or os.sep)
    return tuple(sorted(set(out)))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: runner.py <workspace> <facts.py> [files...]", file=sys.stderr)
        return 2
    global _READ_ROOTS, _READ_FILES
    workspace, script, files = argv[0], argv[1], argv[2:]
    # This file sits next to the helper's own modules (one is named profile), which would
    # shadow standard modules for the step. Take this folder off the import path.
    here = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
    sys.path[:] = [p for p in sys.path if not p or os.path.realpath(p) != here]
    sys.dont_write_bytecode = True
    _READ_ROOTS = _roots(os.path.realpath(workspace))
    _READ_FILES = frozenset(r for r in (_real(f) for f in [script, *files]) if r)
    sys.argv = [script, *files]
    # Load the system's harmless lookup tables now, so libraries that read them on import
    # (openpyxl reads the file type table) do not need wider read access later.
    import mimetypes
    mimetypes.init()
    sys.addaudithook(_hook)
    code = 0
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as exc:
        if isinstance(exc.code, int) or exc.code is None:
            code = exc.code or 0
        else:
            sys.stderr.write(f"{exc.code}\n")
            code = 1
    except BaseException:
        if not _blocked:
            raise
    if _blocked:
        sys.stdout.flush()
        sys.stderr.write(MARKER + _blocked[0] + "\n")
        sys.stderr.flush()
        os._exit(BLOCKED_EXIT)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
