from datetime import date
from ja import sources, status
from ja.registry import Tool

def src(**k):
    base = dict(id="faq", name="OLM FAQ", kind="living", where="x", access="file",
                version=None, exported="2026-10-21", fresh_days=7, changed=False)
    # 2026-10-21 is 7 days before T, the last day a 7-day copy counts as fresh.
    base.update(k); return sources.Source(**base)

T = date(2026, 10, 28)

def tool(**k):
    base = dict(id="t1", name="T", does="d.", examples=["x"], kind="built", status="working",
                rhythm="on-demand", data_path="Files you drop in", created="2026-10-01", sources=["faq"])
    base.update(k); return Tool.from_dict(base)

PASSED = {"date": "2026-10-27", "result": "pass", "detail": ""}

def test_fresh_source_working():
    assert status.effective_status(tool(last_check=PASSED), {"faq": src()}, T) == "working"

def test_stale_living_file_source():
    s = {"faq": src(exported="2026-10-10")}
    assert status.effective_status(tool(), s, T) == "needs-update"
    assert status.reasons(tool(), s, T) == ["Your copy of OLM FAQ is 18 days old"]

def test_connector_source_never_stale():
    assert status.effective_status(tool(last_check=PASSED), {"faq": src(access="connector", exported=None)}, T) == "working"

def test_fixed_source_never_stale():
    assert status.effective_status(tool(last_check=PASSED), {"faq": src(kind="fixed", exported="2025-01-01")}, T) == "working"

def test_changed_source():
    s = {"faq": src(changed=True)}
    assert status.reasons(tool(), s, T) == ["OLM FAQ changed since this tool was checked"]

def test_failed_check_beats_draft():
    t = tool(status="draft-not-checked", last_check={"date": "2026-10-27", "result": "fail", "detail": "Column Stage is missing"})
    assert status.effective_status(t, {"faq": src()}, T) == "needs-update"
    assert status.reasons(t, {"faq": src()}, T) == ["Last check failed: Column Stage is missing"]

def test_paused_wins():
    assert status.effective_status(tool(status="paused", sources=["faq"]), {"faq": src(changed=True)}, T) == "paused"

def test_unknown_source():
    assert status.reasons(tool(sources=["nope"]), {}, T) == ["Uses a source that is not on your sources list"]

def test_labels():
    assert status.LABELS["draft-not-checked"] == "Draft, not checked"


# Extra coverage beyond the plan contract.

def test_unknown_source_status():
    assert status.effective_status(tool(sources=["nope"]), {}, T) == "needs-update"

def test_exactly_at_limit_is_fresh():
    assert status.effective_status(tool(last_check=PASSED), {"faq": src(exported="2026-10-21")}, T) == "working"

def test_living_file_without_export_date_is_stale():
    s = {"faq": src(exported=None)}
    assert status.effective_status(tool(), s, T) == "needs-update"
    assert status.reasons(tool(), s, T) == ["I do not know how old your copy of OLM FAQ is"]

def test_working_tool_has_no_reasons():
    assert status.reasons(tool(), {"faq": src()}, T) == []

def test_draft_stays_draft_when_fresh():
    assert status.effective_status(tool(status="draft-not-checked"), {"faq": src()}, T) == "draft-not-checked"

def test_failed_check_without_detail():
    t = tool(last_check={"date": "2026-10-27", "result": "fail", "detail": ""})
    assert status.reasons(t, {"faq": src()}, T) == ["Last check failed"]

def test_label_for_every_status():
    for s in ("working", "draft-not-checked", "needs-update", "being-built", "paused", "retired"):
        assert status.label(s) == status.LABELS[s]

def test_load_sources(ws):
    from ja import workspace
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Drive\n  access: file\n  exported: 2026-10-20\n"
        "- id: bad\n  name: Bad\n  kind: soft\n  where: x\n  access: file\n"
    )
    by_id, problems = sources.load(workspace.Paths(ws))
    assert list(by_id) == ["faq"] and by_id["faq"].exported == "2026-10-20" and by_id["faq"].fresh_days == 7
    assert problems == ["bad: kind must be living or fixed"]

def test_load_sources_missing_file(ws):
    from ja import workspace
    (ws / "assistant/sources.yaml").unlink()
    assert sources.load(workspace.Paths(ws)) == ({}, [])


# Status rule 4: Working only after a passed check.

def test_working_without_check_is_draft():
    assert status.effective_status(tool(), {"faq": src()}, T) == "draft-not-checked"
    assert status.reasons(tool(), {"faq": src()}, T) == []

def test_draft_with_passed_check_stays_draft():
    t = tool(status="draft-not-checked", last_check=PASSED)
    assert status.effective_status(t, {"faq": src()}, T) == "draft-not-checked"

def test_working_with_passed_check_is_working():
    assert status.effective_status(tool(last_check=PASSED), {"faq": src()}, T) == "working"
