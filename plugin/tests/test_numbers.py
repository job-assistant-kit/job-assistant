"""Number sign-off: the note before sending, and approval into the ledger."""

import json

import yaml

from ja import ledger, workspace

T = "2026-10-29"


def seed(ws, write_tool, exported="2026-10-27", access="file"):
    write_tool(ws, id="ttm", name="TTM report", exec_numbers=True, sources=["metrics", "ttm-method"])
    (ws / "assistant/sources.yaml").write_text(yaml.safe_dump([
        {"id": "metrics", "name": "Metrics export", "kind": "living", "where": "inbox", "access": "file",
         "exported": "2026-10-28", "fresh_days": 7, "version": None, "changed": False},
        {"id": "ttm-method", "name": "TTM Methodology Explainer", "kind": "living", "where": "Drive",
         "access": access, "exported": exported, "fresh_days": 7, "version": None, "changed": False},
    ]), encoding="utf-8")
    ledger.add(workspace.Paths(ws), metric="ttm-days", period="2026-Q2", value=81, unit="days",
               source="Metrics export", method_notes="Rows without an awareness date left out",
               approved_on="2026-07-10", tool="ttm")


def note(cli, ws, *extra):
    return cli("--workspace", str(ws), "--today", T, "numbers", "note", "--metric", "ttm-days", "--value", "94",
               "--unit", "days", "--period", "2026-Q3", "--tool", "ttm", "--method-source", "ttm-method", *extra)


def pending(ws):
    path = ws / "data/numbers/pending.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_note_has_the_fixed_parts(ws, write_tool, cli):
    seed(ws, write_tool)
    r = note(cli, ws, "--excluded", "6", "--total", "40")
    assert r.returncode == 0, r.text
    assert r.stdout.splitlines() == [
        "ttm-days: 94 days for 2026-Q3, from TTM report.",
        "Last published: 81 days for 2026-Q2. Change: +13 (+16.0%).",
        "This is a big change. Check the method before sending.",
        "Method: TTM Methodology Explainer. Your copy from Oct 27 is within its 7-day limit.",
        "6 of 40 rows were left out.",
        "Draft, not checked",
    ]
    saved = pending(ws)
    assert len(saved) == 1
    assert {k: saved[0][k] for k in ("metric", "period", "value", "unit", "tool", "method_source", "excluded",
                                     "total", "noted_on")} == {
        "metric": "ttm-days", "period": "2026-Q3", "value": 94, "unit": "days", "tool": "ttm",
        "method_source": "ttm-method", "excluded": 6, "total": 40, "noted_on": T}
    assert saved[0]["source"] == "Metrics export"


def test_note_says_when_the_method_copy_is_old(ws, write_tool, cli):
    seed(ws, write_tool, exported="2026-10-10")
    r = note(cli, ws)
    assert ("Method: TTM Methodology Explainer. Your copy is 19 days old, past its 7-day limit. "
            "Get a fresh copy before relying on the method check.") in r.stdout
    assert "rows were left out" not in r.stdout and r.stdout.rstrip().endswith("Draft, not checked")


def test_note_with_a_live_method_and_no_history(ws, write_tool, cli):
    seed(ws, write_tool, access="connector")
    (ws / "data/ledger.jsonl").unlink()
    r = note(cli, ws, "--excluded", "1", "--total", "40")
    assert "No published value yet." in r.stdout and "big change" not in r.stdout
    assert "Method: TTM Methodology Explainer, read live through a connector." in r.stdout
    assert "1 of 40 rows was left out." in r.stdout


def test_note_refuses_bad_details(ws, write_tool, cli):
    seed(ws, write_tool)
    r = note(cli, ws, "--excluded", "6")
    assert r.returncode == 1 and "Give both the number of rows left out and the total." in r.stderr
    r = note(cli, ws, "--excluded", "41", "--total", "40")
    assert r.returncode == 1 and "more rows left out than there are" in r.stderr
    r = cli("--workspace", str(ws), "numbers", "note", "--metric", "m", "--value", "1", "--unit", "u",
            "--period", "P", "--tool", "ttm", "--method-source", "nothing")
    assert r.returncode == 1 and "The method document nothing is not on your sources list." in r.stderr
    r = cli("--workspace", str(ws), "numbers", "note", "--metric", "m", "--value", "1", "--unit", "u",
            "--period", "P", "--tool", "gone", "--method-source", "ttm-method")
    assert r.returncode == 1 and "There is no tool called gone." in r.stderr
    assert pending(ws) == []


def test_a_second_note_replaces_the_first(ws, write_tool, cli):
    seed(ws, write_tool)
    note(cli, ws)
    cli("--workspace", str(ws), "--today", T, "numbers", "note", "--metric", "ttm-days", "--value", "96",
        "--unit", "days", "--period", "2026-Q3", "--tool", "ttm", "--method-source", "ttm-method")
    assert [p["value"] for p in pending(ws)] == [96]


def test_approve_moves_it_into_the_ledger(ws, write_tool, cli):
    seed(ws, write_tool)
    note(cli, ws, "--excluded", "6", "--total", "40")
    r = cli("--workspace", str(ws), "--today", "2026-10-30", "numbers", "approve", "--metric", "ttm-days",
            "--period", "2026-Q3", "--method-notes", "Rows without an awareness date left out, per the explainer.")
    assert r.returncode == 0, r.text
    assert r.stdout.strip() == "Saved. Next time I will compare against this number."
    latest = ledger.latest(workspace.Paths(ws), "ttm-days")
    assert latest == {"metric": "ttm-days", "period": "2026-Q3", "value": 94, "unit": "days",
                      "source": "Metrics export",
                      "method_notes": "Rows without an awareness date left out, per the explainer. "
                                      "6 of 40 rows were left out.",
                      "approved_on": "2026-10-30", "tool": "ttm"}
    assert pending(ws) == []
    r = cli("--workspace", str(ws), "numbers", "approve", "--metric", "ttm-days", "--period", "2026-Q3")
    assert r.returncode == 1 and "There is no number for ttm-days, 2026-Q3 waiting for your OK." in r.stderr


def test_approve_without_notes_names_the_method(ws, write_tool, cli):
    seed(ws, write_tool)
    note(cli, ws)
    cli("--workspace", str(ws), "--today", T, "numbers", "approve", "--metric", "ttm-days", "--period", "2026-Q3")
    assert ledger.latest(workspace.Paths(ws), "ttm-days")["method_notes"] == "Method: TTM Methodology Explainer."
