import json

from ja import ledger, workspace

def test_ledger_compare(ws):
    p = workspace.Paths(ws)
    assert ledger.compare(p, "ttm-days", 94, "days") == {"previous": None}
    ledger.add(p, metric="ttm-days", period="2026-Q2", value=112, unit="days", source="metrics-latest.json",
               method_notes="Rows without awareness date excluded", approved_on="2026-07-10", tool="ttm")
    c = ledger.compare(p, "ttm-days", 94, "days")
    assert c["previous"] == 112 and c["period"] == "2026-Q2" and c["change"] == -18
    assert round(c["percent"], 1) == -16.1

def test_ledger_latest_by_approved_date(ws):
    p = workspace.Paths(ws)
    for per, val, d in [("2026-Q1", 120, "2026-04-10"), ("2026-Q2", 112, "2026-07-10")]:
        ledger.add(p, metric="ttm-days", period=per, value=val, unit="days", source="s", method_notes="m", approved_on=d, tool="ttm")
    assert ledger.compare(p, "ttm-days", 100, "days")["previous"] == 112


# Extra coverage beyond the plan contract.

def test_latest_ignores_line_order(ws):
    p = workspace.Paths(ws)
    for per, val, d in [("2026-Q2", 112, "2026-07-10"), ("2026-Q1", 120, "2026-04-10")]:
        ledger.add(p, metric="ttm-days", period=per, value=val, unit="days", source="s", method_notes="m", approved_on=d, tool="ttm")
    assert ledger.compare(p, "ttm-days", 100, "days")["previous"] == 112

def test_other_metric_ignored(ws):
    p = workspace.Paths(ws)
    ledger.add(p, metric="other", period="2026-Q2", value=5, unit="n", source="s", method_notes="m", approved_on="2026-07-10", tool="x")
    assert ledger.compare(p, "ttm-days", 1, "days") == {"previous": None}

def test_previous_zero_has_no_percent(ws):
    p = workspace.Paths(ws)
    ledger.add(p, metric="m", period="P", value=0, unit="n", source="s", method_notes="m", approved_on="2026-07-10", tool="x")
    c = ledger.compare(p, "m", 3, "n")
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
    assert ledger.compare(p, "m", 3, "n")["previous"] == 2

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
    c = ledger.compare(p, "m", -5, "n")
    assert c["change"] == 5 and c["percent"] == 50.0

def test_parse_number():
    import pytest
    assert ledger.parse_number("94") == 94 and isinstance(ledger.parse_number("94"), int)
    assert ledger.parse_number("12.5") == 12.5
    assert ledger.parse_number("9007199254740993") == 9007199254740993
    for bad in ("nan", "inf", "-Infinity", "ninety", ""):
        with pytest.raises(ValueError):
            ledger.parse_number(bad)

def test_big_change_warning(ws, cli):
    p = workspace.Paths(ws)
    ledger.add(p, metric="ttm-days", period="2026-Q2", value=81, unit="days", source="s", method_notes="m",
               approved_on="2026-07-10", tool="ttm")
    assert ledger.BIG_CHANGE_PERCENT == 15
    assert ledger.compare(p, "ttm-days", 94, "days")["big_change"] is True
    assert ledger.compare(p, "ttm-days", 90, "days")["big_change"] is False
    assert ledger.compare(p, "ttm-days", 68, "days")["big_change"] is True
    r = cli("--workspace", str(ws), "ledger", "compare", "--metric", "ttm-days", "--value", "94", "--unit", "days")
    assert r.stdout.splitlines() == ["Last published: 81 days for 2026-Q2. Change: +13 (+16.0%).",
                                     "This is a big change. Check the method before sending."]
    r = cli("--workspace", str(ws), "ledger", "compare", "--metric", "ttm-days", "--value", "90", "--unit", "days")
    assert "big change" not in r.stdout

def test_change_from_zero_is_big():
    assert ledger.warning({"previous": 0, "change": 3, "percent": None}) == ledger.BIG_CHANGE
    assert ledger.warning({"previous": 0, "change": 0, "percent": None}) is None
    assert ledger.warning({"previous": None}) is None


def test_compare_refuses_another_unit(ws, cli):
    import pytest
    p = workspace.Paths(ws)
    ledger.add(p, metric="ttm-days", period="2026-Q2", value=81, unit="days", source="s", method_notes="m",
               approved_on="2026-07-10", tool="ttm")
    with pytest.raises(ledger.UnitMismatch) as exc:
        ledger.compare(p, "ttm-days", 94, "%")
    assert str(exc.value) == ("The last published number is in days and this one is in %. "
                              "I cannot compare them. Check which unit is right.")
    assert ledger.compare(p, "ttm-days", 94, " Days ")["previous"] == 81
    r = cli("--workspace", str(ws), "ledger", "compare", "--metric", "ttm-days", "--value", "94", "--unit", "%")
    assert r.returncode == 1
    assert r.stderr.strip() == ("The last published number is in days and this one is in %. "
                                "I cannot compare them. Check which unit is right.")
    assert r.stdout == ""


def test_compare_names_a_missing_unit(ws):
    import pytest
    p = workspace.Paths(ws)
    ledger.add(p, metric="m", period="P", value=1, unit="", source="s", method_notes="m",
               approved_on="2026-07-10", tool="x")
    with pytest.raises(ledger.UnitMismatch, match="The last published number has no unit and this one is in days."):
        ledger.compare(p, "m", 2, "days")
    assert ledger.compare(p, "m", 2, "")["previous"] == 1


def _add(p, metric, period, value, day, unit="days"):
    ledger.add(p, metric=metric, period=period, value=value, unit=unit, source="s", method_notes="m",
               approved_on=day, tool="ttm")


def test_metric_names_ignore_case_and_spaces(ws):
    p = workspace.Paths(ws)
    _add(p, "ttm-days", "2026-Q2", 81, "2026-07-10")
    assert ledger.compare(p, "  TTM-Days ", 94, "days")["previous"] == 81
    _add(p, " TTM-DAYS", "2026-Q3", 94, "2026-10-10")
    assert [e["metric"] for e in ledger.entries(p, "ttm-days")] == ["ttm-days", "ttm-days"]


def test_metrics_lists_published_names(ws, cli):
    p = workspace.Paths(ws)
    r = cli("--workspace", str(ws), "ledger", "metrics")
    assert r.returncode == 0 and r.stdout.strip() == "No numbers have been published yet."
    _add(p, "ttm-days", "2026-Q2", 81, "2026-07-10")
    _add(p, "ttm-days", "2026-Q3", 94, "2026-10-10")
    _add(p, "on-time", "2026-Q3", 92.5, "2026-10-11", unit="%")
    r = cli("--workspace", str(ws), "ledger", "metrics")
    assert r.stdout.splitlines() == [
        "on-time, in %. Last published for 2026-Q3, approved on 2026-10-11.",
        "ttm-days, in days. Last published for 2026-Q3, approved on 2026-10-10.",
    ]
    data = json.loads(cli("--workspace", str(ws), "ledger", "metrics", "--json").stdout)
    assert data == [
        {"metric": "on-time", "unit": "%", "period": "2026-Q3", "approved_on": "2026-10-11"},
        {"metric": "ttm-days", "unit": "days", "period": "2026-Q3", "approved_on": "2026-10-10"},
    ]


def test_same_period_needs_replace(ws, cli):
    import pytest
    p = workspace.Paths(ws)
    _add(p, "ttm-days", "2026-Q2", 81, "2026-07-10")
    with pytest.raises(ledger.AlreadyApproved) as exc:
        _add(p, "TTM-days", "2026-Q2", 85, "2026-07-12")
    assert str(exc.value).startswith("2026-Q2 was already approved on 2026-07-10 as 81.")
    r = cli("--workspace", str(ws), "ledger", "add", "--metric", "ttm-days", "--period", "2026-Q2", "--value", "85",
            "--unit", "days", "--source", "s", "--method-notes", "m", "--tool", "ttm", "--date", "2026-07-12")
    assert r.returncode == 1 and "2026-Q2 was already approved on 2026-07-10 as 81." in r.stderr
    assert [e["value"] for e in ledger.entries(p, "ttm-days")] == [81]
    r = cli("--workspace", str(ws), "ledger", "add", "--metric", "ttm-days", "--period", "2026-Q2", "--value", "85",
            "--unit", "days", "--source", "s", "--method-notes", "m", "--tool", "ttm", "--date", "2026-07-12",
            "--replace")
    assert r.returncode == 0, r.text
    assert [(e["period"], e["value"]) for e in ledger.entries(p, "ttm-days")] == [("2026-Q2", 85)]


def test_replace_keeps_other_lines(ws):
    p = workspace.Paths(ws)
    _add(p, "ttm-days", "2026-Q1", 90, "2026-04-10")
    p.ledger.write_text(p.ledger.read_text() + "garbage\n")
    _add(p, "ttm-days", "2026-Q2", 81, "2026-07-10")
    ledger.add(p, metric="ttm-days", period="2026-Q2", value=85, unit="days", source="s", method_notes="m",
               approved_on="2026-07-12", tool="ttm", replace=True)
    assert "garbage" in p.ledger.read_text()
    assert [(e["period"], e["value"]) for e in ledger.entries(p, "ttm-days")] == [("2026-Q1", 90), ("2026-Q2", 85)]


def test_renoting_a_period_compares_with_an_earlier_one(ws):
    p = workspace.Paths(ws)
    _add(p, "ttm-days", "2026-Q1", 90, "2026-04-10")
    _add(p, "ttm-days", "2026-Q2", 81, "2026-07-10")
    _add(p, "ttm-days", "2026-Q3", 94, "2026-10-10")
    c = ledger.compare(p, "ttm-days", 85, "days", period="2026-Q2")
    assert c["previous"] == 90 and c["period"] == "2026-Q1"
    assert ledger.approved(p, "ttm-days", "2026-q2 ")["value"] == 81
    assert ledger.compare(p, "ttm-days", 85, "days", period="2026-Q4")["period"] == "2026-Q3"
    assert ledger.compare(p, "ttm-days", 85, "days", period="2026-Q1") == {"previous": None}
