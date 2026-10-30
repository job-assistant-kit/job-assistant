"""The shortcut that opens the assistant in its folder."""

import os
import shutil
import subprocess

import pytest

from ja import launcher, workspace


CLAUDE = "/opt/claude tools/bin/claude"


def dirs(tmp_path):
    return dict(bin_dir=tmp_path / "bin", apps_dir=tmp_path / "apps", desktop_dir=tmp_path / "Desktop",
                claude=CLAUDE)


def test_linux_plan(ws, tmp_path):
    items = launcher.plan(workspace.Paths(ws), system="Linux", **dirs(tmp_path))
    assert [i.path for i in items] == [tmp_path / "bin/job-assistant", tmp_path / "apps/job-assistant.desktop"]
    script, desktop = items[0].content, items[1].content
    assert script.startswith("#!/bin/sh\n") and launcher.MARKER in script
    assert f"cd {ws}" in script or f"cd '{ws}'" in script
    assert "exec '/opt/claude tools/bin/claude' \"$@\"" in script
    assert "Terminal=true" in desktop and launcher.MARKER in desktop
    assert str(tmp_path / "bin/job-assistant") in desktop


def test_mac_plan(ws, tmp_path):
    items = launcher.plan(workspace.Paths(ws), system="Darwin", **dirs(tmp_path))
    assert [i.path for i in items] == [tmp_path / "bin/job-assistant", tmp_path / "Desktop/Job Assistant.command"]


def test_preview_writes_nothing(ws, tmp_path):
    text = launcher.run(workspace.Paths(ws), yes=False, system="Linux", **dirs(tmp_path))
    assert str(tmp_path / "bin/job-assistant") in text and "exec '/opt/claude tools/bin/claude'" in text
    assert not (tmp_path / "bin").exists() and not (tmp_path / "apps").exists()


def test_preview_says_when_shortcut_is_in_place(ws, tmp_path):
    paths = workspace.Paths(ws)
    assert launcher.IN_PLACE not in launcher.run(paths, yes=False, system="Linux", **dirs(tmp_path))
    launcher.run(paths, yes=True, system="Linux", **dirs(tmp_path))
    assert launcher.run(paths, yes=False, system="Linux", **dirs(tmp_path)) == launcher.IN_PLACE
    (tmp_path / "apps/job-assistant.desktop").unlink()
    assert launcher.IN_PLACE not in launcher.run(paths, yes=False, system="Linux", **dirs(tmp_path))


def test_yes_writes_executable_files(ws, tmp_path):
    launcher.run(workspace.Paths(ws), yes=True, system="Linux", **dirs(tmp_path))
    script = tmp_path / "bin/job-assistant"
    assert os.access(script, os.X_OK) and (tmp_path / "apps/job-assistant.desktop").is_file()
    launcher.run(workspace.Paths(ws), yes=True, system="Linux", **dirs(tmp_path))


def test_refuses_file_it_did_not_create(ws, tmp_path):
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps/job-assistant.desktop").write_text("[Desktop Entry]\nName=Mine\n", encoding="utf-8")
    with pytest.raises(launcher.LauncherProblem) as err:
        launcher.run(workspace.Paths(ws), yes=True, system="Linux", **dirs(tmp_path))
    assert "did not create" in str(err.value)
    assert not (tmp_path / "bin/job-assistant").exists()
    assert (tmp_path / "apps/job-assistant.desktop").read_text(encoding="utf-8") == "[Desktop Entry]\nName=Mine\n"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_script_goes_to_folder_with_odd_name(tmp_path):
    from ja import init
    root = init.create(tmp_path / "it's a $folder").root
    fake = tmp_path / "fake bin"
    fake.mkdir()
    (fake / "claude").write_text("#!/bin/sh\npwd\n", encoding="utf-8")
    (fake / "claude").chmod(0o755)
    items = launcher.plan(workspace.Paths(root), system="Linux", **dict(dirs(tmp_path), claude=str(fake / "claude")))
    script = tmp_path / "launch.sh"
    script.write_text(items[0].content, encoding="utf-8")
    out = subprocess.run(["sh", str(script)], capture_output=True, text=True)
    assert out.stdout.strip() == str(root)


def test_refuses_without_claude(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(launcher.LauncherProblem) as err:
        launcher.plan(workspace.Paths(ws), system="Linux", bin_dir=tmp_path / "bin", apps_dir=tmp_path / "apps")
    assert str(err.value) == "I could not find Claude on this computer, so I cannot make a shortcut yet."


def test_finds_claude_on_path(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)
    items = launcher.plan(workspace.Paths(ws), system="Linux", bin_dir=tmp_path / "bin", apps_dir=tmp_path / "apps")
    assert "exec /usr/local/bin/claude" in items[0].content


def test_desktop_entry_escaping():
    assert launcher._desktop_exec('/a b/c"d$e\\f%g') == '"/a b/c\\\\"d\\\\$e\\\\\\\\f%%g"'
    assert launcher._desktop_string(" lead\\x\nnew") == "\\slead\\\\x\\nnew"


def test_desktop_paths_escaped(tmp_path):
    from ja import init
    root = init.create(tmp_path / "back\\slash folder").root
    items = launcher.plan(workspace.Paths(root), system="Linux", **dirs(tmp_path))
    desktop = items[1].content
    assert f"Path={str(root).replace(chr(92), chr(92) * 2)}" in desktop


@pytest.mark.parametrize("system,words", [("Linux", "The menu shortcut works now."),
                                          ("Darwin", "The desktop shortcut works now.")])
def test_path_note_per_platform(ws, tmp_path, monkeypatch, system, words):
    monkeypatch.setenv("PATH", "/usr/bin")
    text = launcher.run(workspace.Paths(ws), yes=True, system=system, **dirs(tmp_path))
    assert words in text and "is not on the search path yet" in text


def test_path_note_other_platform(ws, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    text = launcher.run(workspace.Paths(ws), yes=True, system="Other", **dirs(tmp_path))
    assert "shortcut works now" not in text and "is not on the search path yet" in text
