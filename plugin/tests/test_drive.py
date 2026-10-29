"""Saving accepted results to one drafts folder in Drive, and the check before each Drive create."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from ja import drive, init, settings, workspace

PLUGIN = Path(__file__).parents[1]
JA = PLUGIN / "scripts" / "ja.py"
GATE = PLUGIN / "scripts" / "hook_drive_gate.py"
FOLDER = "1AbCdEfGhIjKlMnOp"
TODAY = date(2026, 10, 29)
NOW = datetime(2026, 10, 29, 14, 5)


@pytest.fixture
def p(tmp_path: Path) -> workspace.Paths:
    return workspace.Paths(init.create(tmp_path / "ws", name="Sam's Assistant").root)


def denied(p: workspace.Paths) -> list[str]:
    return settings.show(p)[0]


def folder_request(**over):
    req = {"title": "Sam's Assistant drafts", "contentMimeType": drive.FOLDER_MIME,
           "inheritedPermissionsDisabled": True}
    req.update(over)
    return {k: v for k, v in req.items() if v is not None}


def test_off_by_default_and_create_blocked(p):
    assert drive.load(p) == {"state": "off"}
    assert drive.CREATE in denied(p)
    assert drive.decide(p, {"title": "x", "parentId": FOLDER}) == (False, drive.OFF_REASON)
    assert drive.target(p, "Tool", False, NOW)[0] is False


def test_start_unblocks_create_and_allows_only_the_folder(p):
    assert drive.start(p) == "Sam's Assistant drafts"
    assert drive.CREATE not in denied(p)
    assert drive.CREATE not in settings.show(p)[1]  # never on the allow list: the check decides
    assert drive.decide(p, folder_request())[0] is True
    for bad in (folder_request(title="Other"), folder_request(parentId="0Bxyzxyzxyz1"),
                folder_request(inheritedPermissionsDisabled=False), folder_request(inheritedPermissionsDisabled=None),
                folder_request(contentMimeType="text/plain"), folder_request(textContent="hi")):
        assert drive.decide(p, bad) == (False, drive.CREATING_REASON), bad


def test_set_from_link_or_id(p):
    data = drive.set_folder(p, f"https://drive.google.com/drive/folders/{FOLDER}?usp=sharing", True, TODAY)
    assert data["folder_id"] == FOLDER and data["checked"] == "2026-10-29"
    assert data["link"] == f"https://drive.google.com/drive/folders/{FOLDER}"
    assert drive.set_folder(p, FOLDER, False, TODAY)["private"] is False
    assert drive.CREATE not in denied(p)
    with pytest.raises(drive.DriveProblem):
        drive.set_folder(p, "my drafts", True, TODAY)


def test_on_allows_new_files_in_the_folder_only(p):
    drive.set_folder(p, FOLDER, True, TODAY)
    ok = {"title": "Brief check draft", "parentId": FOLDER, "contentMimeType": "text/markdown", "textContent": "x"}
    assert drive.decide(p, ok)[0] is True
    for bad in ({**ok, "parentId": "0Bxyzxyzxyz1"}, {k: v for k, v in ok.items() if k != "parentId"},
                {**ok, "contentMimeType": drive.FOLDER_MIME}, {**ok, "title": "  "}, "not a dict"):
        assert drive.decide(p, bad) == (False, drive.ON_REASON), bad


def test_off_blocks_again(p):
    drive.set_folder(p, FOLDER, True, TODAY)
    drive.off(p)
    assert denied(p).count(drive.CREATE) == 1
    assert drive.decide(p, {"title": "x", "parentId": FOLDER}) == (False, drive.OFF_REASON)


@pytest.mark.parametrize("text", ["not json", "[]", '{"state": "maybe"}', '{"state": "on", "folder_id": "x"}',
                                  '{"state": "on", "folder_id": "1AbCdEfGhIjKlMnOp"}', '{"state": "creating"}'])
def test_unreadable_setting_blocks(p, text):
    drive.config_path(p).write_text(text, encoding="utf-8")
    assert drive.decide(p, {"title": "x", "parentId": FOLDER}) == (False, drive.BROKEN_REASON)
    assert drive.kept_open(p) == set()


def test_target_titles_and_confidential(p):
    drive.set_folder(p, FOLDER, False, TODAY)
    save, _, where = drive.target(p, "Check a brief", False, NOW)
    assert save and where["folder"] == FOLDER and where["title"] == "Check a brief draft 2026-10-29 14:05"
    save, why, where = drive.target(p, "Check a brief", True, NOW)
    assert not save and "confidential" in why and where == {}
    drive.set_folder(p, FOLDER, True, TODAY)
    assert drive.target(p, "Check a brief", True, NOW)[0] is True


def test_setup_deny_leaves_create_open_while_on(p):
    def ja(*args):
        return subprocess.run([sys.executable, str(JA), "--workspace", str(p.root), *args],
                              capture_output=True, text=True)
    drive.set_folder(p, FOLDER, True, TODAY)
    r = ja("settings", "deny", drive.CREATE, "mcp__x__post")
    assert r.returncode == 0, r.stderr
    assert "Left open" in r.stdout
    assert drive.CREATE not in denied(p) and "mcp__x__post" in denied(p)
    drive.off(p)
    r = ja("settings", "deny", drive.CREATE)
    assert r.returncode == 0 and "Left open" not in r.stdout


def test_status_command(p, write_tool):
    write_tool(p.root, id="brief", name="Check a brief", confidential=True)

    def ja(*args):
        return subprocess.run([sys.executable, str(JA), "--workspace", str(p.root), *args, "--today", "2026-10-29"],
                              capture_output=True, text=True)
    assert ja("drive", "status").stdout.strip() == "Saving to Drive is off."
    assert "off" in ja("drive", "status", "--tool", "brief").stdout
    assert ja("drive", "set", "--folder", FOLDER, "--private", "maybe").returncode == 1
    r = ja("drive", "set", "--folder", FOLDER, "--private", "no")
    assert r.returncode == 0 and "will not be saved there" in r.stdout
    assert "Not saved to Drive" in ja("drive", "status", "--tool", "brief").stdout
    ja("drive", "set", "--folder", FOLDER, "--private", "yes")
    out = ja("drive", "status", "--tool", "brief").stdout
    assert f"parentId: {FOLDER}" in out and "title: Check a brief draft 2026-10-29 " in out
    assert ja("drive", "status", "--tool", "ghost").returncode == 1


def gate(cwd: Path, tool_input: dict, tool_name: str = drive.CREATE) -> subprocess.CompletedProcess:
    data = {"tool_name": tool_name, "cwd": str(cwd), "tool_input": tool_input}
    return subprocess.run([sys.executable, str(GATE)], input=json.dumps(data), capture_output=True, text=True)


def decision(r: subprocess.CompletedProcess) -> str:
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_gate_outside_an_assistant_folder_says_nothing(tmp_path):
    r = gate(tmp_path, {"title": "x"})
    assert r.returncode == 0 and r.stdout == ""


def test_gate_ignores_other_actions(p):
    r = gate(p.root, {"title": "x"}, tool_name="mcp__claude_ai_Google_Drive__search_files")
    assert r.returncode == 0 and r.stdout == ""


def test_gate_decisions(p):
    assert decision(gate(p.root, {"title": "x", "parentId": FOLDER})) == "deny"
    drive.start(p)
    assert decision(gate(p.root / "inbox", folder_request())) == "allow"
    drive.set_folder(p, FOLDER, True, TODAY)
    assert decision(gate(p.root, {"title": "d", "parentId": FOLDER, "contentMimeType": "text/markdown"})) == "allow"
    assert decision(gate(p.root, {"title": "d", "parentId": "0Bxyzxyzxyz1"})) == "deny"
    drive.config_path(p).write_text("{", encoding="utf-8")
    assert decision(gate(p.root, {"title": "d", "parentId": FOLDER})) == "deny"


def test_gate_failure_blocks_the_action():
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    [entry] = [h for h in hooks if h["matcher"] == drive.CREATE]
    [hook] = entry["hooks"]
    assert hook["onFailure"] == "block" and "hook_drive_gate.py" in hook["command"]
    header = GATE.read_text(encoding="utf-8")
    assert "dependencies = []" in header
