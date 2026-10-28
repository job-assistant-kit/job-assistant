"""The shortcut that opens the assistant in its folder."""

import os
import shutil
import subprocess

import pytest

from ja import launcher, workspace


def dirs(tmp_path):
    return dict(bin_dir=tmp_path / "bin", apps_dir=tmp_path / "apps", desktop_dir=tmp_path / "Desktop")


def test_linux_plan(ws, tmp_path):
    items = launcher.plan(workspace.Paths(ws), system="Linux", **dirs(tmp_path))
    assert [i.path for i in items] == [tmp_path / "bin/job-assistant", tmp_path / "apps/job-assistant.desktop"]
    script, desktop = items[0].content, items[1].content
    assert script.startswith("#!/bin/sh\n") and launcher.MARKER in script
    assert f"cd {ws}" in script or f"cd '{ws}'" in script
    assert "exec claude" in script
    assert "Terminal=true" in desktop and launcher.MARKER in desktop
    assert str(tmp_path / "bin/job-assistant") in desktop


def test_mac_plan(ws, tmp_path):
    items = launcher.plan(workspace.Paths(ws), system="Darwin", **dirs(tmp_path))
    assert [i.path for i in items] == [tmp_path / "bin/job-assistant", tmp_path / "Desktop/Job Assistant.command"]


def test_preview_writes_nothing(ws, tmp_path):
    text = launcher.run(workspace.Paths(ws), yes=False, system="Linux", **dirs(tmp_path))
    assert str(tmp_path / "bin/job-assistant") in text and "exec claude" in text
    assert not (tmp_path / "bin").exists() and not (tmp_path / "apps").exists()


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
    items = launcher.plan(workspace.Paths(root), system="Linux", **dirs(tmp_path))
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "claude").write_text("#!/bin/sh\npwd\n", encoding="utf-8")
    (fake / "claude").chmod(0o755)
    script = tmp_path / "launch.sh"
    script.write_text(items[0].content, encoding="utf-8")
    out = subprocess.run(["sh", str(script)], capture_output=True, text=True,
                         env={**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"})
    assert out.stdout.strip() == str(root)
