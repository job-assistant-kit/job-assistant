"""Command functions called by ja.py. Each takes parsed args and returns an exit code."""

from __future__ import annotations

import argparse
import sys


def _not_ready(args: argparse.Namespace) -> int:
    print("This command is not ready yet.", file=sys.stderr)
    return 2


cmd_init = _not_ready
cmd_tools = _not_ready
cmd_index = _not_ready
cmd_dashboard = _not_ready
cmd_record_run = _not_ready
cmd_record_build = _not_ready
cmd_ledger_add = _not_ready
cmd_ledger_compare = _not_ready
cmd_check = _not_ready
