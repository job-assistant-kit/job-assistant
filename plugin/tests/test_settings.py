"""Write protection settings for the assistant folder."""

import json

import pytest

from ja import init, settings, workspace


def test_template_settings(tmp_path):
    p = workspace.Paths(init.create(tmp_path / "ws").root)
    data = json.loads(p.settings.read_text(encoding="utf-8"))
    deny = data["permissions"]["deny"]
    for name in ("create_file", "update_file", "share_file", "trash_file", "copy_file"):
        assert f"mcp__claude_ai_Google_Drive__{name}" in deny
    assert "mcp__claude_ai_Atlassian__createJiraIssue" in deny
    assert all(n.startswith("mcp__") for n in deny) and len(deny) == len(set(deny))
    assert "Bash(uv run --script *ja.py*)" in data["permissions"]["allow"]
    assert "mcp__claude_ai_Google_Drive__read_file_content" not in deny


def test_deny_adds_and_dedupes(ws):
    p = workspace.Paths(ws)
    assert settings.deny(p, ["mcp__x__send", "mcp__x__post", "mcp__x__send"]) == 2
    assert settings.deny(p, ["mcp__x__send", "mcp__y__delete"]) == 1
    assert settings.load(p)["permissions"]["deny"] == ["mcp__x__send", "mcp__x__post", "mcp__y__delete"]


def test_deny_keeps_other_keys(ws):
    p = workspace.Paths(ws)
    p.settings.parent.mkdir(parents=True, exist_ok=True)
    p.settings.write_text(json.dumps({"model": "x", "permissions": {"allow": ["Bash(ls)"], "deny": ["mcp__a__b"]},
                                      "hooks": {"Stop": []}}), encoding="utf-8")
    settings.deny(p, ["mcp__c__d"])
    data = json.loads(p.settings.read_text(encoding="utf-8"))
    assert data["model"] == "x" and data["hooks"] == {"Stop": []}
    assert data["permissions"]["allow"] == ["Bash(ls)"]
    assert data["permissions"]["deny"] == ["mcp__a__b", "mcp__c__d"]


def test_bad_names_refused(ws):
    p = workspace.Paths(ws)
    for bad in (["Bash(rm *)"], ["mcp__ok__x", "slack_post"], ["mcp__has space"], [""]):
        with pytest.raises(settings.SettingsProblem):
            settings.deny(p, bad)
    assert not p.settings.exists()


def test_missing_file_created(ws):
    p = workspace.Paths(ws)
    assert not p.settings.exists()
    settings.deny(p, ["mcp__x__send"])
    assert json.loads(p.settings.read_text(encoding="utf-8")) == {"permissions": {"deny": ["mcp__x__send"]}}


def test_unreadable_file_not_overwritten(ws):
    p = workspace.Paths(ws)
    p.settings.parent.mkdir(parents=True, exist_ok=True)
    p.settings.write_text("{not json", encoding="utf-8")
    with pytest.raises(settings.SettingsProblem):
        settings.deny(p, ["mcp__x__send"])
    assert p.settings.read_text(encoding="utf-8") == "{not json"
