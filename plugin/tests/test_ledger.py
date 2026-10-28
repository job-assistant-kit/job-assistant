from ja import ledger, workspace

def test_ledger_compare(ws):
    p = workspace.Paths(ws)
    assert ledger.compare(p, "ttm-days", 94) == {"previous": None}
    ledger.add(p, metric="ttm-days", period="2026-Q2", value=112, unit="days", source="metrics-latest.json",
               method_notes="Rows without awareness date excluded", approved_on="2026-07-10", tool="ttm")
    c = ledger.compare(p, "ttm-days", 94)
    assert c["previous"] == 112 and c["period"] == "2026-Q2" and c["change"] == -18
    assert round(c["percent"], 1) == -16.1

def test_ledger_latest_by_approved_date(ws):
    p = workspace.Paths(ws)
    for per, val, d in [("2026-Q1", 120, "2026-04-10"), ("2026-Q2", 112, "2026-07-10")]:
        ledger.add(p, metric="ttm-days", period=per, value=val, unit="days", source="s", method_notes="m", approved_on=d, tool="ttm")
    assert ledger.compare(p, "ttm-days", 100)["previous"] == 112


# Extra coverage beyond the plan contract.

def test_latest_ignores_line_order(ws):
    p = workspace.Paths(ws)
    for per, val, d in [("2026-Q2", 112, "2026-07-10"), ("2026-Q1", 120, "2026-04-10")]:
        ledger.add(p, metric="ttm-days", period=per, value=val, unit="days", source="s", method_notes="m", approved_on=d, tool="ttm")
    assert ledger.compare(p, "ttm-days", 100)["previous"] == 112

def test_other_metric_ignored(ws):
    p = workspace.Paths(ws)
    ledger.add(p, metric="other", period="2026-Q2", value=5, unit="n", source="s", method_notes="m", approved_on="2026-07-10", tool="x")
    assert ledger.compare(p, "ttm-days", 1) == {"previous": None}

def test_previous_zero_has_no_percent(ws):
    p = workspace.Paths(ws)
    ledger.add(p, metric="m", period="P", value=0, unit="n", source="s", method_notes="m", approved_on="2026-07-10", tool="x")
    c = ledger.compare(p, "m", 3)
    assert c["change"] == 3 and c["percent"] is None

def test_bad_date_rejected(ws):
    import pytest
    with pytest.raises(ValueError):
        ledger.add(workspace.Paths(ws), metric="m", period="P", value=1, unit="n", source="s",
                   method_notes="m", approved_on="July", tool="x")

def test_corrupt_ledger_line_skipped(ws):
    p = workspace.Paths(ws)
    p.ledger.write_text("garbage\n")
    ledger.add(p, metric="m", period="P", value=2, unit="n", source="s", method_notes="m", approved_on="2026-07-10", tool="x")
    assert ledger.compare(p, "m", 3)["previous"] == 2

def test_describe_plain():
    assert ledger.describe({"previous": None}) == "No published value yet."
    c = {"previous": 112, "period": "2026-Q2", "unit": "days", "change": -18, "percent": -16.07}
    assert ledger.describe(c) == "Last published: 112 days for 2026-Q2. Change: -18 (-16.1%)."
    c = {"previous": 10, "period": "P", "unit": "offerings", "change": 2.5, "percent": 25.0}
    assert ledger.describe(c) == "Last published: 10 offerings for P. Change: +2.5 (+25.0%)."

def test_nan_and_infinity_rejected(ws):
    import pytest
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            ledger.add(workspace.Paths(ws), metric="m", period="P", value=bad, unit="n", source="s",
                       method_notes="m", approved_on="2026-07-10", tool="x")

def test_percent_uses_absolute_previous(ws):
    p = workspace.Paths(ws)
    ledger.add(p, metric="m", period="P", value=-10, unit="n", source="s", method_notes="m",
               approved_on="2026-07-10", tool="x")
    c = ledger.compare(p, "m", -5)
    assert c["change"] == 5 and c["percent"] == 50.0

def test_parse_number():
    import pytest
    assert ledger.parse_number("94") == 94 and isinstance(ledger.parse_number("94"), int)
    assert ledger.parse_number("12.5") == 12.5
    assert ledger.parse_number("9007199254740993") == 9007199254740993
    for bad in ("nan", "inf", "-Infinity", "ninety", ""):
        with pytest.raises(ValueError):
            ledger.parse_number(bad)
