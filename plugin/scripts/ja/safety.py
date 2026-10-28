"""Refuse facts steps and code parts that reach other systems or run programs.

A tool's facts step runs on the person's computer without asking, so it may only read
the files it is given and print results. This is a check of the code as written, not a
sandbox: it catches the ordinary ways to open a connection or start a program.
"""

from __future__ import annotations

import ast
from pathlib import Path

REFUSED = "This step tries to reach other systems or run programs, which tools here are not allowed to do."

BANNED_MODULES = frozenset({
    "socket", "http", "urllib", "requests", "httpx", "smtplib", "ftplib", "subprocess",
    "urllib3", "aiohttp", "ssl", "imaplib", "poplib", "telnetlib", "xmlrpc", "webbrowser", "pty",
})
BANNED_OS = ("system", "popen", "exec", "spawn", "posix_spawn", "fork")


def _banned_module(name: str | None) -> bool:
    return bool(name) and name.split(".")[0] in BANNED_MODULES


def _banned_os(name: str) -> bool:
    return any(name == b or name.startswith(b) for b in BANNED_OS)


def _literal(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _refused(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(_banned_module(a.name) for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            if _banned_module(node.module):
                return True
            if node.module == "os" and any(_banned_os(a.name) for a in node.names):
                return True
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os" \
                and _banned_os(node.attr):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            args = [_literal(a) for a in node.args]
            if name in ("__import__", "import_module") and any(_banned_module(a) for a in args if a):
                return True
            if name == "getattr" and len(args) >= 2 and args[1] and _banned_os(args[1]):
                return True
    return False


def problem(path: Path) -> str | None:
    """A plain sentence when the code is not allowed or cannot be read, else None."""
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return f"I could not read {Path(path).name}."
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"{Path(path).name} has a mistake on line {exc.lineno} and cannot run."
    return REFUSED if _refused(tree) else None
