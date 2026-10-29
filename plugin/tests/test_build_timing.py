"""Timing a build from its start to the build record."""

import json
from datetime import datetime, timedelta

from ja import records, workspace


def test_start_then_record_computes_minutes(ws, write_tool, cli):
    write_tool(ws, id="match")
    r = cli("--workspace", str(ws), "build", "start", "--id", "match")
    assert r.returncode == 0 and "Noted the start time" in r.stdout
    started = json.loads((ws / "data/records/building/match.json").read_text(encoding="utf-8"))
    assert started["tool"] == "match"
    earlier = (datetime.now() - timedelta(minutes=42, seconds=10)).replace(microsecond=0).isoformat()
    records.start_build(workspace.Paths(ws), "match", ts=earlier)
    r = cli("--workspace", str(ws), "record", "build", "--tool", "match", "--recipe", "reconcile-two-lists",
            "--questions", "2", "--corrections", "1")
    assert r.returncode == 0, r.text
    assert "42 minutes" in r.stdout
    line = json.loads((ws / "data/records/builds.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert line["minutes"] == 42 and line["questions"] == 2 and line["corrections"] == 1
    assert not (ws / "data/records/building/match.json").exists()


def test_given_minutes_win_and_clear_the_start(ws, write_tool, cli):
    write_tool(ws, id="match")
    cli("--workspace", str(ws), "build", "start", "--id", "match")
    r = cli("--workspace", str(ws), "record", "build", "--tool", "match", "--questions", "0", "--corrections", "0",
            "--minutes", "7")
    assert r.returncode == 0 and "7 minutes" in r.stdout
    assert not (ws / "data/records/building/match.json").exists()


def test_without_start_or_minutes(ws, write_tool, cli):
    write_tool(ws, id="match")
    r = cli("--workspace", str(ws), "record", "build", "--tool", "match", "--questions", "0", "--corrections", "0")
    assert r.returncode == 1 and "I do not know when this build started" in r.stderr
    assert not (ws / "data/records/builds.jsonl").exists()


def test_at_least_one_minute_and_bad_file(ws):
    p = workspace.Paths(ws)
    records.start_build(p, "quick")
    assert records.build_minutes(p, "quick") == 1
    (ws / "data/records/building/quick.json").write_text("{broken", encoding="utf-8")
    assert records.build_minutes(p, "quick") is None


def test_start_refuses_bad_id(ws, cli):
    r = cli("--workspace", str(ws), "build", "start", "--id", "Bad Id")
    assert r.returncode == 1 and "lowercase letters" in r.stderr


def test_unfinished_builds_list_steps_done(ws, write_tool, cli):
    p = workspace.Paths(ws)
    records.start_build(p, "half-done", ts="2026-10-27T09:30:00")
    records.start_build(p, "not-begun", ts="2026-10-29T08:00:00")
    write_tool(ws, id="half-done", name="Match the lists", status="being-built", last_check=None)
    (ws / "data/proofs/half-done/case-1").mkdir(parents=True)
    (ws / "data/proofs/half-done/case-1/meta.json").write_text('{"saved": "2026-10-27"}', encoding="utf-8")
    r = cli("--workspace", str(ws), "--today", "2026-10-29", "build", "unfinished")
    assert r.returncode == 0, r.text
    assert ("Match the lists: started Oct 27, 2 days ago. Done so far: tool record saved, example saved. "
            "Next: record the check.") in r.stdout
    assert "not-begun: started Oct 29, today. Done so far: nothing. Next: write the tool record." in r.stdout
    data = json.loads(cli("--workspace", str(ws), "--today", "2026-10-29", "build", "unfinished", "--json").stdout)
    assert [b["tool"] for b in data] == ["half-done", "not-begun"]
    assert data[0]["done"] == {"record": True, "example": True, "check": False}
    assert data[0]["next"] == "record the check" and data[0]["days_ago"] == 2


def test_unfinished_skips_recorded_builds(ws, write_tool, cli):
    write_tool(ws, id="match", status="being-built")
    r = cli("--workspace", str(ws), "build", "unfinished")
    assert r.returncode == 0 and r.stdout.strip() == "No unfinished builds."
    p = workspace.Paths(ws)
    records.start_build(p, "match", ts="2026-10-28T09:00:00")
    records.add_build(p, tool="match", recipe=None, questions=0, corrections=0, minutes=5, ts="2026-10-28T10:00:00")
    assert cli("--workspace", str(ws), "build", "unfinished").stdout.strip() == "No unfinished builds."
    cli("--workspace", str(ws), "--today", "2026-10-28", "build", "start", "--id", "other")
    r = cli("--workspace", str(ws), "--today", "2026-10-29", "build", "unfinished")
    assert "other: started Oct 28, yesterday." in r.stdout
    assert "check recorded" not in r.stdout


def test_unfinished_all_steps_done(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists", status="working")
    (ws / "data/proofs/match/case-1").mkdir(parents=True)
    records.start_build(workspace.Paths(ws), "match", ts="2026-10-28T09:00:00")
    r = cli("--workspace", str(ws), "--today", "2026-10-28", "build", "unfinished")
    assert "Done so far: tool record saved, example saved, check recorded. Next: record the build." in r.stdout
