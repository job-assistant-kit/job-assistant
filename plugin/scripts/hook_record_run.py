#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6",
#     "jinja2>=3.1",
#     "openpyxl>=3.1",
# ]
# ///
"""After-tool hook on the Skill tool: when the page used is one of this folder's tools, record a run.

The tools in an assistant folder live in .claude/skills/<id>/ with a tool.yaml record, and
their page name is the id. Pages from the kit itself are named "job-assistant:<name>" and are
not tools, so they are never recorded. Prints nothing and always exits 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def work(data: dict) -> None:
    from ja import hooks, records, registry
    from ja.workspace import Paths

    if data.get("tool_name") != "Skill":
        return
    tool_input = data.get("tool_input")
    name = tool_input.get("skill") if isinstance(tool_input, dict) else None
    if not isinstance(name, str):
        return
    name = name.strip().lstrip("/")
    if not registry.ID_PATTERN.match(name):
        return
    root = hooks.folder_root(data)
    if root is None:
        return
    paths = Paths(root)
    if not (paths.skills_dir / name / registry.RECORD_NAME).is_file():
        return
    records.add_run(paths, name, "run")


if __name__ == "__main__":
    try:
        from ja import hooks as _hooks
    except BaseException:  # noqa: BLE001  never fail the tool call
        sys.exit(0)
    sys.exit(_hooks.run_quietly(work))
