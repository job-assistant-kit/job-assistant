"""Write protection settings for the assistant folder."""

import json

import pytest

from ja import init, settings, workspace


CACHE_RULE = "Bash(uv run --script */plugins/cache/job-assistant/job-assistant/*/scripts/ja.py *)"


def test_template_settings(tmp_path):
    p = workspace.Paths(init.create(tmp_path / "ws").root)
    data = json.loads(p.settings.read_text(encoding="utf-8"))
    perms = data["permissions"]
    deny = perms["deny"]
    assert perms["defaultMode"] == "acceptEdits"
    for name in ("create_file", "update_file", "share_file", "trash_file", "copy_file"):
        assert f"mcp__claude_ai_Google_Drive__{name}" in deny
    for prefix in ("mcp__claude_ai_Atlassian__", "mcp__atlassian-mcp-server__"):
        for name in ("createJiraIssue", "editJiraIssue", "transitionJiraIssue", "addCommentToJiraIssue",
                     "createConfluencePage", "updateConfluencePage"):
            assert prefix + name in deny
    for rule in ("Bash(git push*)", "Bash(clasp push*)", "Bash(clasp deploy*)"):
        assert rule in deny
    assert len(deny) == len(set(deny))
    mcp = [n for n in deny if not n.startswith("Bash(")]
    assert all(settings.NAME.match(n) for n in mcp)
    assert "mcp__claude_ai_Google_Drive__read_file_content" not in deny
    assert not any("slack" in n.lower() or "gmail" in n.lower() for n in deny)
    allow = perms["allow"]
    assert CACHE_RULE in allow
    assert not any("facts.py" in rule for rule in allow)
    assert "Bash(uv run --script *ja.py*)" not in allow


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
    for bad in (["Bash(rm *)"], ["mcp__ok__x", "slack_post"], ["mcp__has space"], [""], ["mcp__nodouble"],
                ["mcp__a__b c"], ["mcp__a__b*"], ["mcp____x"]):
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


def test_deny_accepts_real_connector_names(ws):
    p = workspace.Paths(ws)
    assert settings.deny(p, ["mcp__atlassian-mcp-server__createJiraIssue", "mcp__claude_ai_Google_Drive__share_file"]) == 2
