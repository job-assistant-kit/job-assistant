"""Adding and changing tool records."""

import json
from datetime import date

import pytest
import yaml

from ja import registry, tools, workspace

T = date(2026, 10, 28)

BUILT = {"id": "brief-check", "name": "Check a brief", "does": "Lists gaps in a launch brief.",
         "examples": ["check this brief"], "kind": "built", "status": "draft-not-checked",
         "rhythm": "on-demand", "data_path": "Files you drop in"}

ADOPTED = {"id": "metrics", "name": "Metrics pipeline", "does": "Builds the monthly metrics file.",
           "examples": ["run the metrics"], "kind": "adopted", "status": "draft-not-checked",
           "rhythm": "monthly", "data_path": "A shared sheet",
           "lives_at": "A shared folder called Metrics", "how_to_run": "Open the sheet and click Refresh.",
           "inputs": ["The offerings export"], "outputs": "One row per offering with a date for each stage.",
           "last_good_run": "2026-09-30"}


def write(tmp_path, data, suffix=".yaml"):
    f = tmp_path / f"record{suffix}"
    f.write_text(json.dumps(data) if suffix == ".json" else yaml.safe_dump(data), encoding="utf-8")
    return f


def test_add_built(ws, tmp_path):
    p = workspace.Paths(ws)
    t, _ = tools.add_from_file(p, write(tmp_path, BUILT), today=T)
    assert t.id == "brief-check" and t.created == "2026-10-28"
    assert (ws / ".claude/skills/brief-check/tool.yaml").is_file()
    assert (ws / ".claude/skills/brief-check/SKILL.md").is_file()


def test_add_from_json(ws, tmp_path):
    tools.add_from_file(workspace.Paths(ws), write(tmp_path, BUILT, ".json"), today=T)
    assert registry.find(workspace.Paths(ws), "brief-check").name == "Check a brief"


def test_add_adopted_writes_skill(ws, tmp_path):
    p = workspace.Paths(ws)
    tools.add_from_file(p, write(tmp_path, ADOPTED), today=T)
    text = (ws / ".claude/skills/metrics/SKILL.md").read_text(encoding="utf-8")
    front = yaml.safe_load(text.split("---")[1])
    assert front["name"] == "metrics" and "Builds the monthly metrics file." in front["description"]
    assert "run the metrics" in front["description"]
    for part in ("A shared folder called Metrics", "Open the sheet and click Refresh.", "- The offerings export",
                 "One row per offering", "2026-09-30", "If it breaks, use the fix-tool steps"):
        assert part in text, part
    assert "{{" not in text
    assert registry.find(p, "metrics").extra["lives_at"] == "A shared folder called Metrics"


def test_adopted_needs_where_and_how(ws, tmp_path):
    data = dict(ADOPTED)
    del data["how_to_run"]
    with pytest.raises(tools.ToolProblem) as err:
        tools.add_from_file(workspace.Paths(ws), write(tmp_path, data), today=T)
    assert str(err.value) == "metrics: how_to_run is missing"


def test_add_refuses_existing_and_invalid(ws, tmp_path, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="brief-check")
    with pytest.raises(tools.ToolProblem) as err:
        tools.add_from_file(p, write(tmp_path, BUILT), today=T)
    assert str(err.value) == "There is already a tool called brief-check."
    with pytest.raises(tools.ToolProblem) as err:
        tools.add_from_file(p, write(tmp_path, dict(BUILT, id="x", status="great")), today=T)
    assert str(err.value).startswith("x: status must be one of")
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: [", encoding="utf-8")
    with pytest.raises(tools.ToolProblem):
        tools.add_from_file(p, bad, today=T)


def test_improve(ws, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="t1")
    tools.improve(p, "t1", "Shorter replies.", "Learned from 3 edits.", today=T)
    assert registry.find(p, "t1").improvements == [
        {"date": "2026-10-28", "change": "Shorter replies.", "reason": "Learned from 3 edits."}]


def test_status(ws, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="t1")
    tools.set_status(p, "t1", "paused")
    assert registry.find(p, "t1").status == "paused"
    with pytest.raises(tools.ToolProblem) as err:
        tools.set_status(p, "t1", "needs-update")
    assert str(err.value) == "That status is worked out from checks and cannot be set by hand."
    for bad in ("retired", "great"):
        with pytest.raises(tools.ToolProblem):
            tools.set_status(p, "t1", bad)
    with pytest.raises(tools.ToolProblem):
        tools.set_status(p, "ghost", "paused")


def test_retire_restore_round_trip(ws, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="t1", status="working")
    (ws / ".claude/skills/t1/SKILL.md").write_text("keep me", encoding="utf-8")
    tools.retire(p, "t1")
    assert not (ws / ".claude/skills/t1").exists()
    assert (ws / "archive/t1/SKILL.md").read_text(encoding="utf-8") == "keep me"
    assert registry.load_archive(p)[0][0].status == "retired"
    restored = tools.restore(p, "t1")
    assert restored.status == "working" and (ws / ".claude/skills/t1/SKILL.md").is_file()
    assert not (ws / "archive/t1").exists()


def test_restore_without_passed_check_is_draft(ws, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="t1", status="retired", folder="archive",
               last_check={"date": "2026-10-01", "result": "fail", "detail": "x"})
    assert tools.restore(p, "t1").status == "draft-not-checked"
    write_tool(ws, id="t2", status="retired", folder="archive", last_check=None)
    assert tools.restore(p, "t2").status == "draft-not-checked"


def test_retire_and_restore_refuse_clashes(ws, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="t1")
    write_tool(ws, id="t1", status="retired", folder="archive")
    with pytest.raises(tools.ToolProblem):
        tools.retire(p, "t1")
    with pytest.raises(tools.ToolProblem):
        tools.restore(p, "t1")
    with pytest.raises(tools.ToolProblem):
        tools.restore(p, "ghost")


def test_add_never_trusts_a_check(ws, tmp_path):
    p = workspace.Paths(ws)
    data = dict(BUILT, status="working", last_check={"date": "2026-10-01", "result": "pass", "detail": ""})
    t, notes = tools.add_from_file(p, write(tmp_path, data), today=T)
    saved = registry.find(p, "brief-check")
    assert saved.status == "draft-not-checked" and saved.last_check is None
    assert t.status == "draft-not-checked"
    assert any("check" in n for n in notes) and any("Draft, not checked" in n for n in notes)


def test_add_keeps_being_built_and_draft(ws, tmp_path):
    p = workspace.Paths(ws)
    t, notes = tools.add_from_file(p, write(tmp_path, dict(BUILT, status="being-built")), today=T)
    assert t.status == "being-built" and notes == []
    t, _ = tools.add_from_file(p, write(tmp_path, dict(BUILT, id="b2", status="paused")), today=T)
    assert t.status == "draft-not-checked"


def test_add_refuses_retired_and_needs_update(ws, tmp_path):
    p = workspace.Paths(ws)
    with pytest.raises(tools.ToolProblem) as err:
        tools.add_from_file(p, write(tmp_path, dict(BUILT, status="retired")), today=T)
    assert str(err.value) == "A new tool cannot start as retired."
    with pytest.raises(tools.ToolProblem) as err:
        tools.add_from_file(p, write(tmp_path, dict(BUILT, status="needs-update")), today=T)
    assert str(err.value) == "That status is worked out from checks and cannot be set by hand."
    assert not (ws / ".claude/skills/brief-check").exists()


def test_restore_with_check_before_change_is_draft(ws, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="t1", status="retired", folder="archive",
               improvements=[{"date": "2026-10-05", "change": "x", "reason": "y"}])
    assert tools.restore(p, "t1").status == "draft-not-checked"
