#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6",
#     "jinja2>=3.1",
#     "openpyxl>=3.1",
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
    rp = rsub.add_parser("task", parents=[common], help="record work done without a tool")
    rp.add_argument("--words", required=True, metavar="TEXT")
    rp.set_defaults(func=commands.cmd_record_task)
    rp = rsub.add_parser("build", parents=[common], help="record a finished build")
    rp.add_argument("--tool", required=True)
    rp.add_argument("--recipe", default=None)
    rp.add_argument("--questions", type=whole, required=True)
    rp.add_argument("--corrections", type=whole, required=True)
    rp.add_argument("--minutes", type=whole, default=None)
    rp.set_defaults(func=commands.cmd_record_build)

    p = sub.add_parser("build", parents=[common], help="time a tool build")
    bsub = p.add_subparsers(dest="action", metavar="action", required=True)
    bp = bsub.add_parser("start", parents=[common], help="note when building a tool started")
    bp.add_argument("--id", required=True, metavar="ID")
    bp.set_defaults(func=commands.cmd_build_start)
    bp = bsub.add_parser("unfinished", parents=[common], help="list builds that were started and not finished")
    bp.add_argument("--json", action="store_true", help="output for code")
    bp.set_defaults(func=commands.cmd_build_unfinished)

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
    lp.add_argument("--replace", action="store_true", help="replace the number already saved for this period")
    lp.set_defaults(func=commands.cmd_ledger_add)
    lp = lsub.add_parser("compare", parents=[common], help="compare with the last published value")
    lp.add_argument("--metric", required=True)
    lp.add_argument("--value", type=number, required=True)
    lp.add_argument("--unit", required=True)
    lp.add_argument("--json", action="store_true", help="output for code")
    lp.set_defaults(func=commands.cmd_ledger_compare)
    lp = lsub.add_parser("metrics", parents=[common], help="list the metrics already published")
    lp.add_argument("--json", action="store_true", help="output for code")
    lp.set_defaults(func=commands.cmd_ledger_metrics)

    p = sub.add_parser("numbers", parents=[common], help="sign-off for numbers that go to leaders")
    nsub = p.add_subparsers(dest="action", metavar="action", required=True)
    np_ = nsub.add_parser("note", parents=[common], help="write the sign-off note and hold the number")
    np_.add_argument("--metric", required=True)
    np_.add_argument("--value", type=number, required=True)
    np_.add_argument("--unit", required=True)
    np_.add_argument("--period", required=True)
    np_.add_argument("--tool", required=True)
    np_.add_argument("--method-source", dest="method_source", required=True, metavar="SOURCE-ID")
    np_.add_argument("--excluded", type=whole, default=None, metavar="N")
    np_.add_argument("--total", type=whole, default=None, metavar="N")
    np_.add_argument("--json", action="store_true", help="output for code")
    np_.set_defaults(func=commands.cmd_numbers_note)
    np_ = nsub.add_parser("approve", parents=[common], help="save an approved number in the ledger")
    np_.add_argument("--metric", required=True)
    np_.add_argument("--period", required=True)
    np_.add_argument("--method-notes", dest="method_notes", default=None, metavar="TEXT")
    np_.add_argument("--replace", action="store_true", help="replace the number already saved for this period")
    np_.set_defaults(func=commands.cmd_numbers_approve)

    p = sub.add_parser("check", parents=[common], help="record the result of a tool check")
    p.add_argument("tool", metavar="TOOL")
    p.add_argument("--result", choices=["pass", "fail"], required=True)
    p.add_argument("--detail", default="")
    p.set_defaults(func=commands.cmd_check)

    p = sub.add_parser("role", parents=[common], help="the role description in the assistant notes")
    rsub = p.add_subparsers(dest="action", metavar="action", required=True)
    rp = rsub.add_parser("set", parents=[common], help="replace the role description with a file's text")
    rp.add_argument("--file", required=True, metavar="PATH")
    rp.set_defaults(func=commands.cmd_role_set)

    p = sub.add_parser("settings", parents=[common], help="write protection for connector actions")
    ssub = p.add_subparsers(dest="action", metavar="action", required=True)
    sp = ssub.add_parser("deny", parents=[common], help="block connector actions by name")
    sp.add_argument("names", nargs="+", metavar="NAME")
    sp.set_defaults(func=commands.cmd_settings_deny)
    sp = ssub.add_parser("show", parents=[common], help="list blocked and allowed actions")
    sp.set_defaults(func=commands.cmd_settings_show)

    p = sub.add_parser("sources", parents=[common], help="the list of documents and data the tools use")
    ssub = p.add_subparsers(dest="action", metavar="action", required=True)
    sp = ssub.add_parser("add", parents=[common], help="add a source")
    sp.add_argument("--id", required=True)
    sp.add_argument("--name", required=True)
    sp.add_argument("--kind", required=True, choices=["living", "fixed"])
    sp.add_argument("--where", required=True, metavar="TEXT")
    sp.add_argument("--access", required=True, choices=["connector", "file"])
    sp.add_argument("--version", default=None)
    sp.add_argument("--exported", default=None, metavar="YYYY-MM-DD")
    sp.add_argument("--fresh-days", dest="fresh_days", type=whole, default=None, metavar="N")
    sp.set_defaults(func=commands.cmd_sources_add)
    sp = ssub.add_parser("exported", parents=[common], help="record the date of a fresh copy")
    sp.add_argument("id", metavar="ID")
    sp.add_argument("date", metavar="YYYY-MM-DD")
    sp.set_defaults(func=commands.cmd_sources_exported)
    sp = ssub.add_parser("changed", parents=[common], help="note that a source changed since its tools were checked")
    sp.add_argument("id", metavar="ID")
    sp.set_defaults(func=commands.cmd_sources_changed)
    sp = ssub.add_parser("checked", parents=[common], help="note that the tools using a changed source were checked")
    sp.add_argument("id", metavar="ID")
    sp.set_defaults(func=commands.cmd_sources_checked)
    sp = ssub.add_parser("list", parents=[common], help="list sources")
    sp.add_argument("--json", action="store_true", help="output for code")
    sp.set_defaults(func=commands.cmd_sources_list)

    p = sub.add_parser("tool", parents=[common], help="add or change a tool record")
    tsub = p.add_subparsers(dest="action", metavar="action", required=True)
    tp = tsub.add_parser("add", parents=[common], help="add a tool from a record file")
    tp.add_argument("--from", dest="file", required=True, metavar="FILE")
    tp.set_defaults(func=commands.cmd_tool_add)
    tp = tsub.add_parser("draft", parents=[common], help="copy a tool's files to its draft folder for changes")
    tp.add_argument("tool", metavar="ID")
    tp.set_defaults(func=commands.cmd_tool_draft)
    tp = tsub.add_parser("files", parents=[common], help="check a tool's changed files and put them in place")
    tp.add_argument("tool", metavar="ID")
    tp.add_argument("--from", dest="source", default=None, metavar="DIR")
    tp.set_defaults(func=commands.cmd_tool_files)
    tp = tsub.add_parser("improve", parents=[common], help="note an improvement")
    tp.add_argument("tool", metavar="ID")
    tp.add_argument("--change", required=True, metavar="TEXT")
    tp.add_argument("--reason", required=True, metavar="TEXT")
    tp.set_defaults(func=commands.cmd_tool_improve)
    tp = tsub.add_parser("status", parents=[common], help="set the declared status")
    tp.add_argument("tool", metavar="ID")
    tp.add_argument("status", metavar="STATUS")
    tp.set_defaults(func=commands.cmd_tool_status)
    tp = tsub.add_parser("retire", parents=[common], help="move a tool to the archive")
    tp.add_argument("tool", metavar="ID")
    tp.set_defaults(func=commands.cmd_tool_retire)
    tp = tsub.add_parser("restore", parents=[common], help="bring a tool back from the archive")
    tp.add_argument("tool", metavar="ID")
    tp.set_defaults(func=commands.cmd_tool_restore)

    p = sub.add_parser("input", parents=[common], help="check the files given to a tool")
    isub = p.add_subparsers(dest="action", metavar="action", required=True)
    ip = isub.add_parser("check", parents=[common], help="check that the files fit what the tool expects")
    ip.add_argument("tool", metavar="TOOL")
    ip.add_argument("files", nargs="+", metavar="FILE")
    ip.set_defaults(func=commands.cmd_input_check)

    p = sub.add_parser("facts", parents=[common], help="a tool's facts step")
    fsub = p.add_subparsers(dest="action", metavar="action", required=True)
    fp = fsub.add_parser("run", parents=[common], help="run the facts step on the files")
    fp.add_argument("tool", metavar="TOOL")
    fp.add_argument("files", nargs="+", metavar="FILE")
    fp.add_argument("--json", action="store_true", help="output for code")
    fp.set_defaults(func=commands.cmd_facts_run)

    p = sub.add_parser("proof", parents=[common], help="saved examples a tool is checked against")
    psub = p.add_subparsers(dest="action", metavar="action", required=True)
    pp = psub.add_parser("save", parents=[common], help="save an accepted result as an example")
    pp.add_argument("tool", metavar="TOOL")
    pp.add_argument("--input", dest="inputs", nargs="+", required=True, metavar="FILE")
    pp.add_argument("--output", required=True, metavar="FILE")
    pp.set_defaults(func=commands.cmd_proof_save)
    pp = psub.add_parser("run", parents=[common], help="check the tool against its saved examples")
    pp.add_argument("tool", metavar="TOOL")
    pp.add_argument("--case", type=whole, default=None, metavar="N")
    pp.set_defaults(func=commands.cmd_proof_run)
    pp = psub.add_parser("list", parents=[common], help="list the saved examples")
    pp.add_argument("tool", metavar="TOOL")
    pp.set_defaults(func=commands.cmd_proof_list)

    p = sub.add_parser("part", parents=[common], help="add a shared part")
    psub = p.add_subparsers(dest="action", metavar="action", required=True)
    pp = psub.add_parser("add", parents=[common], help="add a part from a record file")
    pp.add_argument("--from", dest="file", required=True, metavar="FILE")
    pp.set_defaults(func=commands.cmd_part_add)

    p = sub.add_parser("parts", parents=[common], help="list shared parts")
    p.add_argument("--json", action="store_true", help="output for code")
    p.set_defaults(func=commands.cmd_parts)

    p = sub.add_parser("search", parents=[common], help="find tools and parts by words")
    p.add_argument("words", nargs="+", metavar="WORD")
    p.add_argument("--json", action="store_true", help="output for code")
    p.set_defaults(func=commands.cmd_search)

    p = sub.add_parser("rules", parents=[common], help="rules learned from the person's corrections")
    rsub = p.add_subparsers(dest="action", metavar="action", required=True)
    rp = rsub.add_parser("add", parents=[common], help="add a learned rule")
    rp.add_argument("--id", required=True, metavar="ID")
    rp.add_argument("--text", required=True, metavar="TEXT")
    rp.add_argument("--reason", required=True, metavar="TEXT")
    rp.add_argument("--scope", required=True, metavar="TOOL")
    rp.add_argument("--pending", action="store_true", help="wait for a check before using it")
    rp.set_defaults(func=commands.cmd_rules_add)
    rp = rsub.add_parser("for", parents=[common], help="the rules a tool must follow")
    rp.add_argument("tool", metavar="TOOL")
    rp.add_argument("--json", action="store_true", help="output for code")
    rp.set_defaults(func=commands.cmd_rules_for)
    rp = rsub.add_parser("confirm", parents=[common], help="start using a rule after its check")
    rp.add_argument("id", metavar="ID")
    rp.set_defaults(func=commands.cmd_rules_confirm)
    rp = rsub.add_parser("hold", parents=[common], help="keep a rule out of use")
    rp.add_argument("id", metavar="ID")
    rp.add_argument("--reason", required=True, metavar="TEXT")
    rp.set_defaults(func=commands.cmd_rules_hold)
    rp = rsub.add_parser("forget", parents=[common], help="remove a rule")
    rp.add_argument("id", metavar="ID")
    rp.set_defaults(func=commands.cmd_rules_forget)
    rp = rsub.add_parser("promote", parents=[common], help="use a rule for every tool")
    rp.add_argument("id", metavar="ID")
    rp.set_defaults(func=commands.cmd_rules_promote)
    rp = rsub.add_parser("list", parents=[common], help="list the learned rules")
    rp.add_argument("--json", action="store_true", help="output for code")
    rp.set_defaults(func=commands.cmd_rules_list)
    rp = rsub.add_parser("similar", parents=[common], help="find rules like this one")
    rp.add_argument("words", nargs="+", metavar="WORD")
    rp.add_argument("--json", action="store_true", help="output for code")
    rp.set_defaults(func=commands.cmd_rules_similar)

    p = sub.add_parser("knowledge", parents=[common], help="facts the person taught, with sources")
    ksub = p.add_subparsers(dest="action", metavar="action", required=True)
    kp = ksub.add_parser("add", parents=[common], help="save a fact with its source")
    kp.add_argument("--fact", required=True, metavar="TEXT")
    kp.add_argument("--source", required=True, metavar="TEXT")
    kp.set_defaults(func=commands.cmd_knowledge_add)
    kp = ksub.add_parser("list", parents=[common], help="list what was taught")
    kp.set_defaults(func=commands.cmd_knowledge_list)
    kp = ksub.add_parser("forget", parents=[common], help="remove a fact")
    kp.add_argument("words", nargs="+", metavar="TEXT")
    kp.set_defaults(func=commands.cmd_knowledge_forget)

    p = sub.add_parser("upkeep", parents=[common], help="what needs the person's attention")
    p.add_argument("--write", action="store_true", help="also save the items for the tools page")
    p.add_argument("--json", action="store_true", help="output for code")
    p.set_defaults(func=commands.cmd_upkeep)

    p = sub.add_parser("inbox", parents=[common], help="files dropped in the inbox")
    isub = p.add_subparsers(dest="action", metavar="action", required=True)
    ip = isub.add_parser("clean", parents=[common], help="list inbox files more than 30 days old, or delete them")
    ip.add_argument("--yes", action="store_true", help="delete them (without it, only list them)")
    ip.set_defaults(func=commands.cmd_inbox_clean)

    p = sub.add_parser("runbook", parents=[common], help="write the backup person's guide")
    p.set_defaults(func=commands.cmd_runbook)

    p = sub.add_parser("launcher", parents=[common], help="add a shortcut that opens the assistant")
    p.add_argument("--yes", action="store_true", help="write the files (without it, only show them)")
    p.add_argument("--bin-dir", dest="bin_dir", default=None, metavar="D")
    p.add_argument("--apps-dir", dest="apps_dir", default=None, metavar="D")
    p.add_argument("--desktop-dir", dest="desktop_dir", default=None, metavar="D")
    p.set_defaults(func=commands.cmd_launcher)

    p = sub.add_parser("env", parents=[common], help="check which needed programs are installed")
    p.add_argument("--json", action="store_true", help="output for code")
    p.set_defaults(func=commands.cmd_env)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for name in ("workspace", "today"):
        if not hasattr(args, name):
            setattr(args, name, None)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
