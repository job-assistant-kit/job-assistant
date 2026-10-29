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


MONTHS = inputs.parse_spec([
    {"name": "this month", "types": ["csv"], "required_columns": ["Offering", "Stage"]},
    {"name": "last month", "types": ["csv"], "required_columns": ["Offering", "Stage"]},
])


def two_months(tmp_path):
    a, b = tmp_path / "october.csv", tmp_path / "september.csv"
    a.write_text("Offering,Stage\nA,Intake\nB,Review\n", encoding="utf-8")
    b.write_text("Offering,Stage\nA,Intake\n", encoding="utf-8")
    return a, b


def test_assign_matches_by_columns_in_list_order():
    spec = inputs.parse_spec(SPEC)
    got = inputs.assign(spec, [SYN / "inventory.csv", SYN / "servicenow-export.csv"])
    assert got == [("offering export", SYN / "servicenow-export.csv"), ("inventory", SYN / "inventory.csv")]


def test_assign_refuses_a_file_two_inputs_could_take(tmp_path):
    a, b = two_months(tmp_path)
    with pytest.raises(inputs.MatchProblem) as err:
        inputs.assign(MONTHS, [a, b])
    assert str(err.value) == ("The file october.csv could be the this month file or the last month file. "
                              "Say which file is which.")


def test_assign_uses_names_given_for_same_shape_files(tmp_path):
    a, b = two_months(tmp_path)
    got = inputs.assign(MONTHS, [], named=[("Last Month", a), ("this month", b)])
    assert got == [("this month", b), ("last month", a)]
    got = inputs.assign(MONTHS, [a], named=[("last month", b)])
    assert got == [("this month", a), ("last month", b)]


def test_assign_refuses_a_file_that_fits_no_input(tmp_path):
    with pytest.raises(inputs.MatchProblem) as err:
        inputs.assign(inputs.parse_spec(SPEC), [SYN / "faq.md", SYN / "inventory.csv"])
    assert str(err.value) == ("The file faq.md does not fit any input this tool takes: offering export, inventory.")


def test_assign_refuses_two_files_for_one_input(tmp_path):
    spec = inputs.parse_spec(SPEC)
    copy = tmp_path / "inventory-2.csv"
    shutil.copyfile(SYN / "inventory.csv", copy)
    with pytest.raises(inputs.MatchProblem) as err:
        inputs.assign(spec, [SYN / "inventory.csv", copy])
    assert str(err.value) == ("The files inventory.csv and inventory-2.csv both look like the inventory file. "
                              "Say which file is which.")


@pytest.mark.parametrize("files, named, message", [
    (["inventory.csv"], [], "I still need the offering export file (CSV or Excel)."),
    ([], [("stock list", "inventory.csv")], "This tool has no input called stock list. Its inputs are: "
                                            "offering export, inventory."),
    ([], [("inventory", "inventory.csv"), ("Inventory", "inventory.csv")], "The inventory file was given twice."),
    ([], [("offering export", "inventory.csv")], "The file inventory.csv is missing the column Stage, so it "
                                                 "cannot be the offering export file."),
    ([], [("inventory", "faq.md")], "The file faq.md is not a CSV or Excel file, so it cannot be the "
                                    "inventory file."),
    (["gone.csv"], [], "I could not find the file gone.csv."),
])
def test_assign_problems(files, named, message):
    spec = inputs.parse_spec(SPEC)
    with pytest.raises(inputs.MatchProblem) as err:
        inputs.assign(spec, [SYN / f for f in files], named=[(n, SYN / f) for n, f in named])
    assert str(err.value) == message


@pytest.mark.parametrize("spec, message", [
    ([{"name": "a=b", "types": ["csv"]}], "cannot contain an equals sign"),
    ([{"name": "inventory", "types": ["csv"]}, {"name": "Inventory ", "types": ["csv"]}], "two expected files named"),
])
def test_input_names_must_be_usable(spec, message):
    with pytest.raises(inputs.SpecProblem, match=message):
        inputs.parse_spec(spec)
