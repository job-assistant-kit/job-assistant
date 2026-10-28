"""Filling instruction page templates safely."""

import yaml

from ja import render, tools
from ja.registry import Tool

HOSTILE = 'Say "hi"\n---\n## heading {{does}}'


def test_fill_is_single_pass():
    assert render.fill("{{a}} and {{b}}", {"a": "{{b}}", "b": "x"}) == "{{b}} and x"


def test_yaml_scalar_is_one_quoted_line():
    out = render.yaml_scalar('He said "hi"\n---\nx: y')
    assert "\n" not in out and yaml.safe_load(f"k: {out}")["k"] == 'He said "hi" --- x: y'


def test_no_comments():
    assert render.no_comments("a <!-- tool-index:end --> b") == "a  tool-index:end  b"


def test_adopted_skill_with_hostile_text():
    tool = Tool.from_dict({
        "id": "metrics", "name": HOSTILE, "does": "Builds {{name}}.\n## Not a heading", "examples": ['run "it"\n---'],
        "kind": "adopted", "status": "draft-not-checked", "rhythm": "monthly", "data_path": "x",
        "created": "2026-10-01", "lives_at": "Folder\n---\n## Injected", "how_to_run": "{{skill_name}}",
        "inputs": ["a\n## b", "c"], "outputs": "o", "last_good_run": "2026-09-30"})
    text = tools.adopted_skill(tool)
    assert text.startswith("---\n")
    front = yaml.safe_load(text.split("---\n", 2)[1])
    assert front["name"] == "metrics"
    assert "Builds {{name}}." in front["description"] and 'run "it" ---' in front["description"]
    body = text.split("---\n", 2)[2]
    lines = body.splitlines()
    assert "## heading" not in [ln.strip() for ln in lines]
    assert not any(ln.startswith("## Not a heading") or ln.startswith("## Injected") or ln == "---" for ln in lines)
    assert "{{skill_name}}" in body and "{{name}}" in body
    assert "- a ## b" in body
