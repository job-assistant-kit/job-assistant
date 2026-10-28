#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6",
#     "jinja2>=3.1",
# ]
# ///
"""Command line entry for the job assistant. Parses arguments and dispatches only."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ja import commands, ledger  # noqa: E402


def plain_error(message: str) -> str:
    """Turn an argparse error into one plain sentence."""
    m = re.match(r"the following arguments are required: (.+)", message)
    if m:
        return f"Some details are missing: {m.group(1)}."
    m = re.match(r"unrecognized arguments: (.+)", message)
    if m:
        return f"I did not understand: {m.group(1)}."
    m = re.match(r"argument ([^:]+): invalid choice: '?([^'(]*?)'? \(choose from (.+)\)", message)
    if m:
        choices = ", ".join(c.strip().strip("'") for c in m.group(3).split(","))
        return f"{m.group(2)} is not one of the choices. Use one of: {choices}."
    m = re.match(r"argument ([^:]+): expected one argument", message)
    if m:
        return f"{m.group(1).split('/')[0]} needs a value."
    m = re.match(r"argument [^:]+: (.+)", message)
    text = m.group(1) if m else message
    return text[0].upper() + text[1:] if text else "I did not understand that."


class PlainParser(argparse.ArgumentParser):
    """Argument errors as one plain sentence and exit code 1, without the usage dump."""

    def error(self, message: str) -> None:  # type: ignore[override]
        print(plain_error(message), file=sys.stderr)
        sys.exit(1)


def number(text: str) -> int | float:
    try:
        return ledger.parse_number(text)
    except ValueError:
        raise argparse.ArgumentTypeError(ledger.NOT_A_NUMBER) from None


def whole(text: str) -> int:
    if not re.fullmatch(r"\d+", text.strip()):
        raise argparse.ArgumentTypeError("The number must be a whole number, like 3.")
    return int(text)


def _common() -> argparse.ArgumentParser:
    """Options accepted before or after the command name."""
    p = PlainParser(add_help=False)
    p.add_argument("--workspace", metavar="PATH", default=argparse.SUPPRESS,
                   help="assistant folder to use")
    p.add_argument("--today", metavar="YYYY-MM-DD", default=argparse.SUPPRESS,
                   help="date to treat as today")
    return p


def build_parser() -> argparse.ArgumentParser:
    common = _common()
    parser = PlainParser(prog="ja", description="Job assistant command line.",
                                     parents=[common])
    sub = parser.add_subparsers(dest="command", metavar="command", required=True)

    p = sub.add_parser("init", parents=[common], help="create a new assistant folder")
    p.add_argument("path", metavar="PATH")
    p.add_argument("--name", default=None, help="name for the assistant folder")
    p.set_defaults(func=commands.cmd_init)

    p = sub.add_parser("tools", parents=[common], help="list active tools")
    p.add_argument("--json", action="store_true", help="output for code")
    p.set_defaults(func=commands.cmd_tools)

    p = sub.add_parser("index", parents=[common], help="rewrite the tool index in CLAUDE.md")
    p.set_defaults(func=commands.cmd_index)

    p = sub.add_parser("dashboard", parents=[common], help="build the tools page")
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    p.set_defaults(func=commands.cmd_dashboard)

    p = sub.add_parser("record", parents=[common], help="record a run or a build")
    rsub = p.add_subparsers(dest="event", metavar="event", required=True)
    for event in ("run", "accepted", "corrected"):
        rp = rsub.add_parser(event, parents=[common], help=f"record a '{event}' event")
        rp.add_argument("tool", metavar="TOOL")
        rp.set_defaults(func=commands.cmd_record_run)
    rp = rsub.add_parser("build", parents=[common], help="record a finished build")
    rp.add_argument("--tool", required=True)
    rp.add_argument("--recipe", default=None)
    rp.add_argument("--questions", type=whole, required=True)
    rp.add_argument("--corrections", type=whole, required=True)
    rp.add_argument("--minutes", type=whole, required=True)
    rp.set_defaults(func=commands.cmd_record_build)

    p = sub.add_parser("ledger", parents=[common], help="published-numbers ledger")
    lsub = p.add_subparsers(dest="action", metavar="action", required=True)
    lp = lsub.add_parser("add", parents=[common], help="add an approved number")
    lp.add_argument("--metric", required=True)
    lp.add_argument("--period", required=True)
    lp.add_argument("--value", type=number, required=True)
    lp.add_argument("--unit", required=True)
    lp.add_argument("--source", required=True)
    lp.add_argument("--method-notes", dest="method_notes", required=True)
    lp.add_argument("--tool", required=True)
    lp.add_argument("--date", default=None, metavar="YYYY-MM-DD")
    lp.set_defaults(func=commands.cmd_ledger_add)
    lp = lsub.add_parser("compare", parents=[common], help="compare with the last published value")
    lp.add_argument("--metric", required=True)
    lp.add_argument("--value", type=number, required=True)
    lp.add_argument("--json", action="store_true", help="output for code")
    lp.set_defaults(func=commands.cmd_ledger_compare)

    p = sub.add_parser("check", parents=[common], help="record the result of a tool check")
    p.add_argument("tool", metavar="TOOL")
    p.add_argument("--result", choices=["pass", "fail"], required=True)
    p.add_argument("--detail", default="")
    p.set_defaults(func=commands.cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for name in ("workspace", "today"):
        if not hasattr(args, name):
            setattr(args, name, None)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
