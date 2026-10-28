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
