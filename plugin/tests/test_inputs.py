"""Checking the files given to a tool against what it expects."""

import shutil
from pathlib import Path

import pytest
import yaml

from ja import inputs

SYN = Path(__file__).parent / "fixtures" / "synthetic"
SPEC = [
    {"name": "offering export", "types": ["csv", "xlsx"], "required_columns": ["Offering", "Stage"], "min_rows": 10},
    {"name": "inventory", "types": ["csv", "xlsx"], "required_columns": ["Offering", "Awareness Date"]},
]


@pytest.fixture
def tool(ws, write_tool):
    write_tool(ws, id="match", manual_steps=["Open the offerings report.", "Click Export, then CSV."])
    (ws / ".claude/skills/match/input.yaml").write_text(yaml.safe_dump(SPEC), encoding="utf-8")
    return ws


def test_good_files_in_any_order(tool, cli):
    r = cli("--workspace", str(tool), "input", "check", "match", str(SYN / "inventory.csv"),
            str(SYN / "servicenow-export.csv"))
    assert r.returncode == 0, r.text
    assert "servicenow-export.csv for offering export; inventory.csv for inventory" in r.stdout


def test_missing_column_and_steps(tool, cli, tmp_path):
    bad = tmp_path / "servicenow-export.csv"
    text = (SYN / "servicenow-export.csv").read_text(encoding="utf-8")
    bad.write_text(text.replace("Stage", "Phase", 1), encoding="utf-8")
    r = cli("--workspace", str(tool), "input", "check", "match", str(bad), str(SYN / "inventory.csv"))
    assert r.returncode == 1
    assert "The file servicenow-export.csv is missing the column Stage." in r.stdout
    assert "To get the right file:\n1. Open the offerings report.\n2. Click Export, then CSV." in r.stdout


def test_too_few_rows_and_missing_file(tool, cli, tmp_path):
    short = tmp_path / "export.csv"
    short.write_text("Offering,Stage\nA,1\n", encoding="utf-8")
    r = cli("--workspace", str(tool), "input", "check", "match", str(short))
    assert r.returncode == 1
    assert "The file export.csv has 1 rows, but this needs at least 10." in r.stdout
    assert "I still need the inventory file (CSV or Excel)." in r.stdout
    r = cli("--workspace", str(tool), "input", "check", "match", str(tmp_path / "gone.csv"))
    assert "I could not find the file gone.csv." in r.stdout


def test_columns_match_ignoring_case_and_spaces(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("﻿ offering ,STAGE\nx,y\n", encoding="utf-8")
    spec = inputs.parse_spec([{"name": "a", "types": ["csv"], "required_columns": ["Offering", "Stage"]}])
    assert inputs.check(spec, [f]).problems == []


def test_xlsx_columns(tmp_path):
    import openpyxl
    book = openpyxl.Workbook()
    book.active.append(["Offering", "Owner"])
    book.active.append(["A", "B"])
    book.save(tmp_path / "inv.xlsx")
    spec = inputs.parse_spec([{"name": "inventory", "types": ["xlsx"], "required_columns": ["Offering", "Target GA"]}])
    assert inputs.check(spec, [tmp_path / "inv.xlsx"]).problems == ["The file inv.xlsx is missing the column Target GA."]
    (tmp_path / "broken.xlsx").write_bytes(b"not a workbook")
    assert "could not be read" in inputs.check(spec, [tmp_path / "broken.xlsx"]).problems[0]


@pytest.mark.parametrize("name, content, problem", [
    ("a.json", "{cut", "could not be read"),
    ("a.md", "  \n", "is empty"),
    ("a.png", "plain text", "not a real PNG file"),
])
def test_other_kinds(tmp_path, name, content, problem):
    (tmp_path / name).write_text(content, encoding="utf-8")
    assert problem in inputs.check(None, [tmp_path / name]).problems[0]


def test_without_input_checks_only_existence(ws, write_tool, cli, tmp_path):
    write_tool(ws, id="plain")
    r = cli("--workspace", str(ws), "input", "check", "plain", str(SYN / "faq.md"))
    assert r.returncode == 0 and "can be read" in r.stdout
    r = cli("--workspace", str(ws), "input", "check", "plain", str(tmp_path / "x.md"))
    assert r.returncode == 1


@pytest.mark.parametrize("spec, message", [
    ([], "at least one expected file"),
    ([{"types": ["csv"]}], "needs a name"),
    ([{"name": "a", "types": ["doc"]}], "file types from"),
    ([{"name": "a", "types": ["csv"], "required_columns": "Offering"}], "list of column names"),
    ([{"name": "a", "types": ["csv"], "min_rows": -1}], "whole number"),
])
def test_bad_specs(spec, message):
    with pytest.raises(inputs.SpecProblem, match=message):
        inputs.parse_spec(spec)


def test_broken_spec_is_plain(tool, cli):
    (tool / ".claude/skills/match/input.yaml").write_text("[broken", encoding="utf-8")
    r = cli("--workspace", str(tool), "input", "check", "match", str(SYN / "faq.md"))
    assert r.returncode == 1 and "could not be read" in r.stderr and "Traceback" not in r.text


def test_unknown_tool(ws, cli):
    r = cli("--workspace", str(ws), "input", "check", "nope", "x.csv")
    assert r.returncode == 1 and "There is no tool called nope." in r.stderr
