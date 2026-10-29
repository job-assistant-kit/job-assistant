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
