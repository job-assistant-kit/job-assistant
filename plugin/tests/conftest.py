"""Shared fixtures: a temporary assistant folder and a helper that writes tool records."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

CLAUDE_MD = "# Assistant\n\n<!-- tool-index:start -->\n<!-- tool-index:end -->\n"

TOOL_DEFAULTS: dict[str, Any] = {
    "id": "t1",
    "name": "Tool one",
    "does": "Does one thing.",
    "examples": ["do one"],
    "kind": "built",
    "status": "working",
    "rhythm": "on-demand",
    "data_path": "Files you drop in",
    "created": "2026-10-01",
}


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    for d in ("assistant", ".claude/skills", "data/records"):
        (root / d).mkdir(parents=True)
    (root / "CLAUDE.md").write_text(CLAUDE_MD)
    (root / "assistant" / "sources.yaml").write_text("[]\n")
    (root / "assistant" / "profile.yaml").write_text("rules: []\n")
    return root


def _write_tool(ws: Path, folder: str = ".claude/skills", **fields: Any) -> Path:
    data = dict(TOOL_DEFAULTS)
    data.update(fields)
    path = ws / folder / str(data["id"]) / "tool.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


@pytest.fixture
def write_tool() -> Callable[..., Path]:
    return _write_tool
