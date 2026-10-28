from ja import registry, workspace
import yaml, pytest

def test_find_root_from_subdir(ws):
    sub = ws / "inbox" / "x"; sub.mkdir(parents=True)
    assert workspace.find_root(sub) == ws

def test_find_root_none(tmp_path):
    with pytest.raises(workspace.NoWorkspace):
        workspace.find_root(tmp_path)

def test_load_valid_tool(ws, write_tool):
    write_tool(ws, id="brief-check", name="Check a brief")
    tools, problems = registry.load_all(workspace.Paths(ws))
    assert [t.id for t in tools] == ["brief-check"] and problems == []

def test_invalid_tool_reported_plainly(ws, write_tool):
    write_tool(ws, id="bad", status="great")
    tools, problems = registry.load_all(workspace.Paths(ws))
    assert tools == []
    assert problems == ["bad: status must be one of working, draft-not-checked, being-built, paused, retired"]

def test_id_must_match_folder(ws, write_tool):
    p = write_tool(ws, id="a")
    data = yaml.safe_load(p.read_text()); data["id"] = "b"; p.write_text(yaml.safe_dump(data))
    _, problems = registry.load_all(workspace.Paths(ws))
    assert problems == ["a: id must match its folder name"]

def test_archived_tools_listed_separately(ws, write_tool):
    write_tool(ws, id="old", status="retired", folder="archive")
    tools, _ = registry.load_all(workspace.Paths(ws))
    archived, _ = registry.load_archive(workspace.Paths(ws))
    assert tools == [] and [t.id for t in archived] == ["old"]

def test_save_roundtrip_keeps_unknown_fields(ws, write_tool):
    p = write_tool(ws, id="t1", extra_field="kept")
    tools, _ = registry.load_all(workspace.Paths(ws))
    registry.save(workspace.Paths(ws), tools[0])
    assert yaml.safe_load(p.read_text())["extra_field"] == "kept"


# Extra coverage beyond the plan contract.

def test_find_root_env_and_explicit(ws, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"; elsewhere.mkdir()
    monkeypatch.setenv("JA_WORKSPACE", str(ws))
    assert workspace.find_root(elsewhere) == ws
    assert workspace.resolve(None, elsewhere) == ws
    monkeypatch.delenv("JA_WORKSPACE")
    assert workspace.resolve(str(ws), elsewhere) == ws

def test_explicit_path_without_assistant_folder(tmp_path):
    with pytest.raises(workspace.NoWorkspace):
        workspace.resolve(str(tmp_path), tmp_path)

def test_paths_contract(ws):
    p = workspace.Paths(ws)
    assert p.skills_dir == ws / ".claude/skills"
    assert p.archive_dir == ws / "archive"
    assert p.profile == ws / "assistant/profile.yaml"
    assert p.sources == ws / "assistant/sources.yaml"
    assert p.runs == ws / "data/records/runs.jsonl"
    assert p.builds == ws / "data/records/builds.jsonl"
    assert p.ledger == ws / "data/ledger.jsonl"
    assert p.proofs_dir == ws / "data/proofs"
    assert p.inbox == ws / "inbox"
    assert p.dashboard == ws / "dashboard/index.html"
    assert p.claude_md == ws / "CLAUDE.md"

def test_missing_required_field(ws, write_tool):
    p = write_tool(ws, id="m")
    data = yaml.safe_load(p.read_text()); del data["does"]; p.write_text(yaml.safe_dump(data))
    _, problems = registry.load_all(workspace.Paths(ws))
    assert problems == ["m: does is missing"]

def test_empty_examples_rejected(ws, write_tool):
    write_tool(ws, id="e", examples=[])
    _, problems = registry.load_all(workspace.Paths(ws))
    assert problems == ["e: examples must list at least one example"]

def test_bad_date_rejected(ws, write_tool):
    write_tool(ws, id="d", created="yesterday")
    _, problems = registry.load_all(workspace.Paths(ws))
    assert problems == ["d: created must be a date like 2026-10-28"]

def test_bad_last_check_rejected(ws, write_tool):
    write_tool(ws, id="c", last_check={"date": "2026-10-01", "result": "ok", "detail": ""})
    _, problems = registry.load_all(workspace.Paths(ws))
    assert problems == ["c: last_check result must be pass or fail"]

def test_unreadable_yaml_reported(ws):
    d = ws / ".claude/skills/broken"; d.mkdir(parents=True)
    (d / "tool.yaml").write_text("id: [unclosed\n")
    tools, problems = registry.load_all(workspace.Paths(ws))
    assert tools == [] and problems == ["broken: tool.yaml could not be read"]

def test_folder_without_record_ignored(ws):
    (ws / ".claude/skills/plain-skill").mkdir(parents=True)
    tools, problems = registry.load_all(workspace.Paths(ws))
    assert tools == [] and problems == []

def test_defaults_applied(ws, write_tool):
    write_tool(ws, id="t1")
    t = registry.load_all(workspace.Paths(ws))[0][0]
    assert t.sources == [] and t.manual_steps == [] and t.rules == [] and t.improvements == []
    assert t.confidential is False and t.exec_numbers is False
    assert t.recipe is None and t.last_check is None and t.your_minutes_by_hand is None

def test_save_roundtrip_values(ws, write_tool):
    write_tool(ws, id="t1", your_minutes_by_hand=30, improvements=[{"date": "2026-10-02", "change": "x", "reason": "y"}])
    p = workspace.Paths(ws)
    t = registry.load_all(p)[0][0]
    t.last_check = {"date": "2026-10-28", "result": "pass", "detail": ""}
    registry.save(p, t)
    again = registry.load_all(p)[0][0]
    assert again.last_check["result"] == "pass" and again.your_minutes_by_hand == 30
    assert again.improvements[0]["change"] == "x"

def test_find_tool(ws, write_tool):
    write_tool(ws, id="t1")
    assert registry.find(workspace.Paths(ws), "t1").id == "t1"
    with pytest.raises(registry.ToolNotFound):
        registry.find(workspace.Paths(ws), "nope")
