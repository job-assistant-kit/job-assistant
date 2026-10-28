from ja import records, ledger, workspace

def test_runs_append_and_count(ws):
    p = workspace.Paths(ws)
    records.add_run(p, "t1", "run", ts="2026-10-01T10:00:00")
    records.add_run(p, "t1", "accepted", ts="2026-10-02T10:00:00")
    records.add_run(p, "t2", "run", ts="2026-10-03T10:00:00")
    assert records.count_runs(p, "t1") == 1          # only event == run
    assert records.last_run(p, "t1") == "2026-10-01"

def test_bad_event_rejected(ws):
    import pytest
    with pytest.raises(ValueError):
        records.add_run(workspace.Paths(ws), "t1", "liked")

def test_builds(ws):
    p = workspace.Paths(ws)
    records.add_build(p, tool="t1", recipe="reconcile", questions=3, corrections=1, minutes=25, ts="2026-10-01T10:00:00")
    assert records.builds(p)[0]["minutes"] == 25

def test_corrupt_line_skipped(ws):
    p = workspace.Paths(ws)
    p.runs.parent.mkdir(parents=True, exist_ok=True)
    p.runs.write_text('{"ts":"2026-10-01T00:00:00","tool":"t1","event":"run"}\nnot json\n')
    assert records.count_runs(p, "t1") == 1


# Extra coverage beyond the plan contract.

def test_no_records_yet(ws):
    p = workspace.Paths(ws)
    assert records.count_runs(p, "t1") == 0 and records.last_run(p, "t1") is None and records.builds(p) == []

def test_count_runs_since(ws):
    from datetime import date
    p = workspace.Paths(ws)
    records.add_run(p, "t1", "run", ts="2026-09-30T10:00:00")
    records.add_run(p, "t1", "run", ts="2026-10-01T10:00:00")
    assert records.count_runs(p, "t1", since=date(2026, 10, 1)) == 1

def test_last_run_uses_latest_time(ws):
    p = workspace.Paths(ws)
    records.add_run(p, "t1", "run", ts="2026-10-05T10:00:00")
    records.add_run(p, "t1", "run", ts="2026-10-02T10:00:00")
    assert records.last_run(p, "t1") == "2026-10-05"

def test_default_timestamp_written(ws):
    p = workspace.Paths(ws)
    records.add_run(p, "t1", "run")
    assert records.count_runs(p, "t1") == 1 and records.last_run(p, "t1") is not None

def test_bad_build_numbers_rejected(ws):
    import pytest
    with pytest.raises(ValueError):
        records.add_build(workspace.Paths(ws), tool="t1", recipe=None, questions=-1, corrections=0, minutes=5)

def test_append_adds_missing_newline_runs(ws):
    p = workspace.Paths(ws)
    p.runs.parent.mkdir(parents=True, exist_ok=True)
    p.runs.write_text('{"ts":"2026-10-01T00:00:00","tool":"t1","event":"run"}', encoding="utf-8")
    records.add_run(p, "t1", "run", ts="2026-10-02T00:00:00")
    assert records.count_runs(p, "t1") == 2
    assert p.runs.read_text(encoding="utf-8").count("\n") == 2

def test_append_adds_missing_newline_ledger(ws):
    p = workspace.Paths(ws)
    p.ledger.parent.mkdir(parents=True, exist_ok=True)
    p.ledger.write_text('{"metric":"m","period":"P","value":1,"unit":"n","source":"s","method_notes":"m",'
                        '"approved_on":"2026-07-01","tool":"x"}', encoding="utf-8")
    ledger.add(p, metric="m", period="Q", value=2, unit="n", source="s", method_notes="m",
               approved_on="2026-07-10", tool="x")
    assert len(ledger.entries(p, "m")) == 2

def test_count_runs_until(ws):
    from datetime import date
    p = workspace.Paths(ws)
    records.add_run(p, "t1", "run", ts="2026-12-31T10:00:00")
    records.add_run(p, "t1", "run", ts="2027-01-01T10:00:00")
    assert records.count_runs(p, "t1", since=date(2026, 10, 1), until=date(2026, 12, 31)) == 1
