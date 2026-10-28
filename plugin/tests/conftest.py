"""Shared fixtures: a temporary assistant folder and a helper that writes tool records."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
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
    "last_check": {"date": "2026-10-01", "result": "pass", "detail": ""},
}


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    for d in ("assistant", ".claude/skills", "data/records"):
        (root / d).mkdir(parents=True)
    (root / "CLAUDE.md").write_text(CLAUDE_MD)
    (root / "assistant" / "sources.yaml").write_text("[]\n")
    (root / "assistant" / "profile.yaml").write_text("rules: []\n")
    (root / "assistant" / ".job-assistant").write_text("marker\n")
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


@pytest.fixture(autouse=True)
def _no_workspace_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JA_WORKSPACE", raising=False)


JA = Path(__file__).parents[1] / "scripts" / "ja.py"


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("ja_cli", JA)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return self.stdout + self.stderr


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Callable[..., Result]:
    """Run the command line in this process (fast). Returns code, stdout, stderr."""
    module = _load_cli()

    def call(*args: str, cwd: Path | None = None) -> Result:
        if cwd is not None:
            monkeypatch.chdir(cwd)
        try:
            code = module.main(list(args))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return call
