"""Small behaviors from the second review round."""

from datetime import date

import yaml

from ja import records, registry, render, upkeep, workspace


def test_id_with_a_trailing_newline_is_refused():
    assert registry.ID_PATTERN.match("tool\n") is None and registry.ID_PATTERN.match("tool")


def test_parts_is_kept_for_the_assistant(ws, write_tool):
    write_tool(ws, id="parts")
    tools, problems = registry.load_all(workspace.Paths(ws))
    assert tools == [] and problems == ["parts: id parts is kept for the assistant's own use"]


def test_user_text_cannot_open_a_fill_in_note():
    assert "<!--" not in render.one_line("Counts <!-- fill: rows --> here")


def test_a_failed_check_is_not_a_finished_step(ws, write_tool):
    p = workspace.Paths(ws)
    write_tool(ws, id="digest", name="Weekly digest", status="being-built",
               last_check={"date": "2026-10-28", "result": "fail", "detail": "Wrong column"})
    building = p.data_dir / "records" / "building"
    building.mkdir(parents=True, exist_ok=True)
    (building / "digest.json").write_text('{"started": "2026-10-28T09:00:00"}', encoding="utf-8")
    rows = upkeep.unfinished(p, date(2026, 10, 28))
    assert rows and rows[0]["done"]["check"] is False


def test_rules_for_says_when_rules_cannot_be_read(ws, write_tool, cli):
    write_tool(ws, id="t1")
    (ws / "assistant/profile.yaml").write_text("rules: [unclosed\n", encoding="utf-8")
    r = cli("--workspace", str(ws), "rules", "for", "t1")
    assert r.returncode == 0 and "could not be read" in r.stdout
