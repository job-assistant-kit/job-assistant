"""Command line behavior, run in this process for speed."""

import json

import yaml

TODAY = ("--today", "2026-10-28")


def test_tools_only_invalid_prints_problems(ws, write_tool, cli):
    write_tool(ws, id="bad", status="great")
    r = cli("tools", *TODAY, cwd=ws)
    assert r.returncode == 0
    assert "No tools yet." not in r.stdout
    assert "Tools with problems:" in r.stdout and "bad: status must be one of" in r.stdout


def test_tools_source_problems_separate(ws, write_tool, cli):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: soft\n  where: x\n  access: file\n")
    write_tool(ws, id="a")
    r = cli("tools", *TODAY, cwd=ws)
    assert "Sources with problems:" in r.stdout and "faq: kind must be living or fixed" in r.stdout
    assert "Tools with problems" not in r.stdout
    data = json.loads(cli("tools", "--json", *TODAY, cwd=ws).stdout)
    assert data["problems"] == [] and data["source_problems"] == ["faq: kind must be living or fixed"]


def test_record_honors_today(ws, write_tool, cli):
    write_tool(ws, id="t1")
    assert cli("record", "run", "t1", "--today", "2026-09-15", cwd=ws).returncode == 0
    assert cli("record", "build", "--tool", "t1", "--questions", "1", "--corrections", "0", "--minutes", "5",
               "--today", "2026-09-15", cwd=ws).returncode == 0
    run = json.loads((ws / "data/records/runs.jsonl").read_text(encoding="utf-8"))
    build = json.loads((ws / "data/records/builds.jsonl").read_text(encoding="utf-8"))
    assert run["ts"].startswith("2026-09-15T") and build["ts"].startswith("2026-09-15T")


def test_ledger_value_not_a_number(ws, cli):
    for bad in ("nan", "inf", "ninety"):
        r = cli("ledger", "compare", "--metric", "m", "--value", bad, *TODAY, cwd=ws)
        assert r.returncode == 1
        assert r.stderr.strip() == "The value must be a number, like 94 or 12.5."
        assert "usage:" not in r.text


def test_ledger_keeps_big_integers(ws, cli):
    r = cli("ledger", "add", "--metric", "m", "--period", "P", "--value", "9007199254740993", "--unit", "n",
            "--source", "s", "--method-notes", "m", "--tool", "t", *TODAY, cwd=ws)
    assert r.returncode == 0, r.text
    assert json.loads((ws / "data/ledger.jsonl").read_text(encoding="utf-8"))["value"] == 9007199254740993


def test_argument_errors_are_plain(ws, cli):
    cases = [
        (("check", "t1", *TODAY), "Some details are missing: --result."),
        (("check", "t1", "--result", "maybe", *TODAY), "maybe is not one of the choices. Use one of: pass, fail."),
        (("record", "build", "--tool", "t1", "--questions", "x", "--corrections", "0", "--minutes", "1"),
         "The number must be a whole number, like 3."),
        (("tools", "--bogus"), "I did not understand: --bogus."),
    ]
    for args, message in cases:
        r = cli(*args, cwd=ws)
        assert r.returncode == 1, args
        assert r.stderr.strip() == message, r.stderr
        assert "usage:" not in r.text


def test_help_still_works(cli):
    r = cli("--help")
    assert r.returncode == 0 and "init" in r.stdout
