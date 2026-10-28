"""Creating an assistant folder, and finding it again."""

import errno
import re
from pathlib import Path

import pytest

from ja import init, workspace


def test_marker_written(tmp_path):
    root = init.create(tmp_path / "a").root
    assert (root / "assistant" / ".job-assistant").is_file()
    assert workspace.find_root(root / "inbox") == root


def test_assistant_folder_without_marker_ignored(tmp_path):
    (tmp_path / "assistant").mkdir()
    with pytest.raises(workspace.NoWorkspace):
        workspace.find_root(tmp_path)
    with pytest.raises(workspace.NoWorkspace):
        workspace.resolve(str(tmp_path), tmp_path)


def test_env_comes_before_ancestors(ws, tmp_path, monkeypatch):
    other = init.create(tmp_path / "other").root
    monkeypatch.setenv("JA_WORKSPACE", str(other))
    assert workspace.resolve(None, ws / "assistant") == other
    assert workspace.resolve(str(ws), ws) == ws


def test_bad_env_falls_back_to_ancestors(ws, tmp_path, monkeypatch):
    monkeypatch.setenv("JA_WORKSPACE", str(tmp_path / "nowhere"))
    assert workspace.resolve(None, ws / "assistant") == ws


def test_bad_parent_path(tmp_path):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(init.CannotCreate) as err:
        init.create(blocker / "ws")
    assert str(err.value) == (f"I could not create the folder at {blocker / 'ws'}: "
                              "part of that path is a file, not a folder.")


def test_copy_failure_leaves_nothing(tmp_path, monkeypatch):
    def broken(*a, **k):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(init.shutil, "copyfile", broken)
    target = tmp_path / "parent" / "ws"
    with pytest.raises(init.CannotCreate) as err:
        init.create(target)
    assert str(err.value).endswith(": the disk is full.")
    assert not target.exists()
    assert not (tmp_path / "parent").exists()
    assert list(tmp_path.iterdir()) == []


def test_copy_failure_keeps_existing_empty_folder(tmp_path, monkeypatch):
    target = tmp_path / "ws"
    target.mkdir()
    monkeypatch.setattr(init.shutil, "copyfile", lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(init.CannotCreate):
        init.create(target)
    assert target.is_dir() and list(target.iterdir()) == []
    assert [p.name for p in tmp_path.iterdir()] == ["ws"]


@pytest.mark.parametrize("raw, clean", [
    ("David's assistant", "David's assistant"),
    ("  <b>Ops</b>\nhelper ", "bOps/b helper"),
])
def test_clean_name(raw, clean):
    assert init.clean_name(raw) == clean


@pytest.mark.parametrize("raw", ["", "  ", "<>", "\n"])
def test_empty_name_refused(raw):
    with pytest.raises(init.BadName):
        init.clean_name(raw)


def test_default_name(tmp_path):
    root = init.create(tmp_path / "a").root
    assert (root / "CLAUDE.md").read_text(encoding="utf-8").startswith("# My Job Assistant\n")


def test_assistant_name_from_heading(ws):
    p = workspace.Paths(ws)
    (ws / "CLAUDE.md").write_text("intro\n# David's Assistant\n\n# Later\n", encoding="utf-8")
    assert workspace.assistant_name(p) == "David's Assistant"
    (ws / "CLAUDE.md").write_text("no heading\n", encoding="utf-8")
    assert workspace.assistant_name(p) == "My Job Assistant"
    (ws / "CLAUDE.md").unlink()
    assert workspace.assistant_name(p) == "My Job Assistant"


def test_every_text_read_and_write_names_utf8():
    scripts = Path(__file__).parents[1] / "scripts"
    bad = []
    for path in scripts.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\.(read_text|write_text)\(", line) and "encoding=" not in line:
                bad.append(f"{path.name}:{n}")
            if re.search(r"\bopen\([^)]*\"[rwa]\+?\"", line) and "encoding=" not in line:
                bad.append(f"{path.name}:{n}")
    assert bad == []
