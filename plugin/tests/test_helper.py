"""Keeping the helper's location current in the assistant folder."""

import json
from pathlib import Path

from ja import helper, init, workspace

OLD = "/old/place/scripts/ja.py"
NEW = Path("/new/place/scripts/ja.py")


def built_page(path: str) -> str:
    return ("---\nname: t1\nallowed-tools:\n"
            f"  - 'Bash(uv run --script \"{path}\" *)'\n---\n\n"
            f'Run `uv run --script "{path}" input check t1 <files>`.\n')


def test_marker_values_round_trip(ws):
    p = workspace.Paths(ws)
    helper.write_marker(p, {"ja_path": "/a b/ja.py"})
    text = (ws / "assistant/.job-assistant").read_text(encoding="utf-8")
    assert text.startswith("# ") and "ja_path: /a b/ja.py" in text
    assert helper.read_marker(p) == {"ja_path": "/a b/ja.py"}
    assert workspace.is_root(ws)


def test_sync_writes_marker_rules_and_pages(ws):
    p = workspace.Paths(ws)
    helper.write_marker(p, {"ja_path": OLD})
    page = ws / ".claude/skills/t1/SKILL.md"
    page.parent.mkdir(parents=True)
    page.write_text(built_page(OLD), encoding="utf-8")
    local = ws / ".claude/settings.local.json"
    local.write_text(json.dumps({"permissions": {"allow": helper.allow_rules(OLD) + ["Bash(ls)"]}}), encoding="utf-8")
    assert helper.sync(p, NEW) is True
    assert helper.read_marker(p)["ja_path"] == str(NEW)
    assert page.read_text(encoding="utf-8") == built_page(str(NEW))
    allow = json.loads(local.read_text(encoding="utf-8"))["permissions"]["allow"]
    assert allow == ["Bash(ls)", *helper.allow_rules(str(NEW))]
    assert helper.sync(p, NEW) is False


def test_sync_without_known_old_path(ws):
    p = workspace.Paths(ws)
    page = ws / "archive/t2/SKILL.md"
    page.parent.mkdir(parents=True)
    page.write_text(built_page(OLD), encoding="utf-8")
    helper.sync(p, NEW)
    assert page.read_text(encoding="utf-8") == built_page(str(NEW))
    allow = json.loads((ws / ".claude/settings.local.json").read_text(encoding="utf-8"))["permissions"]["allow"]
    assert allow == helper.allow_rules(str(NEW))


def test_sync_never_fails(ws):
    p = workspace.Paths(ws)
    (ws / ".claude/settings.local.json").write_text("{broken", encoding="utf-8")
    helper.sync(p, NEW)
    assert helper.read_marker(p)["ja_path"] == str(NEW)
    assert (ws / ".claude/settings.local.json").read_text(encoding="utf-8") == "{broken"


def test_init_records_helper(tmp_path):
    root = init.create(tmp_path / "ws").root
    p = workspace.Paths(root)
    assert helper.read_marker(p)["ja_path"] == str(helper.SCRIPT)
    local = json.loads((root / ".claude/settings.local.json").read_text(encoding="utf-8"))
    assert local["permissions"]["allow"] == helper.allow_rules(str(helper.SCRIPT))
    assert ".claude/settings.local.json" in (root / ".gitignore").read_text(encoding="utf-8")


def test_any_command_keeps_helper_current(ws, cli):
    helper.write_marker(workspace.Paths(ws), {"ja_path": OLD})
    assert cli("tools", cwd=ws).returncode == 0
    assert helper.read_marker(workspace.Paths(ws))["ja_path"] == str(helper.SCRIPT)


def test_sync_leaves_odd_settings_alone(ws):
    local = ws / ".claude/settings.local.json"
    for odd in ('{"permissions": []}', '{"permissions": {"allow": "x"}}', "[]"):
        local.write_text(odd, encoding="utf-8")
        helper.write_marker(workspace.Paths(ws), {"ja_path": OLD})
        helper.sync(workspace.Paths(ws), NEW)
        assert local.read_text(encoding="utf-8") == odd
