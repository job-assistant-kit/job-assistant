#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6",
#     "jinja2>=3.1",
#     "openpyxl>=3.1",
# ]
# ///
"""Session start hook: in an assistant folder, refresh the helper's path, the upkeep notes, and the tools page.

Prints nothing, so nothing is added to the conversation, and always exits 0.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def work(data: dict) -> None:
    from ja import dashboard, helper, hooks, upkeep
    from ja.workspace import Paths

    root = hooks.folder_root(data)
    if root is None:
        return
    paths = Paths(root)
    helper.sync(paths)
    today = date.today()
    try:
        upkeep.write(paths, upkeep.items(paths, today), today)
    finally:
        dashboard.write(paths, today)


if __name__ == "__main__":
    try:
        from ja import hooks as _hooks
    except BaseException:  # noqa: BLE001  never fail the session
        sys.exit(0)
    sys.exit(_hooks.run_quietly(work))
