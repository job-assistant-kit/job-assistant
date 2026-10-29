"""Tool folders for tools built here: the instructions page frame, checklist, drafts, and putting files in place."""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

from ja import helper, registry, tools, workspace

T = date(2026, 10, 28)
SYN = Path(__file__).parent / "fixtures" / "synthetic"
RECORD = {"id": "match-lists", "name": "Match the offering lists", "does": "Matches the export to the inventory.",
          "examples": ["match the lists", "reconcile the offerings"], "kind": "built", "status": "being-built",
          "rhythm": "monthly", "data_path": "Two exports you drop in"}


def add(ws, tmp_path, **fields):
    record = tmp_path / "record.yaml"
    record.write_text(yaml.safe_dump({**RECORD, **fields}), encoding="utf-8")
    return tools.add_from_file(workspace.Paths(ws), record, today=T)[0]


def front_and_body(text):
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front), body


def test_add_built_writes_frame_and_checklist(ws, tmp_path):
    add(ws, tmp_path)
    folder = ws / ".claude/skills/match-lists"
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    front, body = front_and_body(text)
    assert front["name"] == "match-lists"
    assert "Matches the export to the inventory." in front["description"]
    assert '"match the lists"' in front["description"] and '"reconcile the offerings"' in front["description"]
    assert front["allowed-tools"] == list(reversed(helper.allow_rules(str(helper.SCRIPT))))
    assert f'uv run --script "{helper.SCRIPT}" <action>' in body
    for heading in ("## What to ask for", "## Check the input", "## Facts", "## Write the result", "## Finish"):
        assert heading in body, heading
    assert "ja input check match-lists" in body and "ja facts run match-lists" in body
    assert "ja proof save match-lists" in body and "Sources:" in body and "Rules used:" in body
    assert "ja_path:" in body and "{{" not in text and "## Number sign-off" not in body
    checklist = yaml.safe_load((folder / "checklist.yaml").read_text(encoding="utf-8"))
    assert checklist["required"] and checklist["rules"] == []


def test_exec_numbers_adds_sign_off(ws, tmp_path):
    add(ws, tmp_path, exec_numbers=True)
    body = (ws / ".claude/skills/match-lists/SKILL.md").read_text(encoding="utf-8")
    assert "## Number sign-off" in body and "Draft, not checked" in body
    assert body.index("## Number sign-off") < body.index("## Finish")


def test_hostile_text_stays_in_place(ws, tmp_path):
    add(ws, tmp_path, name='Evil "x"\n---\n## {{id}}', does="Does {{ja_path}}.\n---")
    front, body = front_and_body((ws / ".claude/skills/match-lists/SKILL.md").read_text(encoding="utf-8"))
    assert front["name"] == "match-lists" and "Does {{ja_path}}. ---" in front["description"]
    assert '# Evil "x" --- ## {{id}}' in body


def test_draft_folder_gets_copies(ws, tmp_path):
    add(ws, tmp_path)
    draft = ws / "data/drafts/match-lists"
    assert sorted(p.name for p in draft.iterdir()) == ["SKILL.md", "checklist.yaml", "facts-template.py"]
    (draft / "SKILL.md").write_text("mine", encoding="utf-8")
    tools.draft(workspace.Paths(ws), "match-lists", keep_existing=True)
    assert (draft / "SKILL.md").read_text(encoding="utf-8") == "mine"
    tools.draft(workspace.Paths(ws), "match-lists")
    assert (draft / "SKILL.md").read_text(encoding="utf-8").startswith("---\n")


def test_helper_move_updates_built_page(ws, tmp_path):
    add(ws, tmp_path)
    p = workspace.Paths(ws)
    helper.write_marker(p, {"ja_path": str(helper.SCRIPT)})
    new = Path("/moved/kit/scripts/ja.py")
    helper.sync(p, new)
    text = (ws / ".claude/skills/match-lists/SKILL.md").read_text(encoding="utf-8")
    assert str(helper.SCRIPT) not in text and str(new) in text
    front, _ = front_and_body(text)
    assert front["allowed-tools"] == list(reversed(helper.allow_rules(str(new))))


def filled(ws):
    draft = ws / "data/drafts/match-lists"
    text = (draft / "SKILL.md").read_text(encoding="utf-8")
    text = text.replace("<!-- fill: what to ask for.", "Ask for both exports. <!-- x").replace(
        "<!-- fill: how to write the result.", "List matches and gaps. <!-- y")
    (draft / "SKILL.md").write_text(text, encoding="utf-8")
    return draft


def test_files_refuses_unfilled_page(ws, tmp_path):
    add(ws, tmp_path)
    with pytest.raises(tools.ToolProblem, match="still has parts to fill in. Nothing was changed."):
        tools.install_files(workspace.Paths(ws), "match-lists")


@pytest.mark.parametrize("name, content, message", [
    ("checklist.yaml", "required: []\n", "at least one required item"),
    ("checklist.yaml", "[broken\n", "could not be read"),
    ("input.yaml", "- name: Export\n  types: [doc]\n", "file types from"),
    ("facts.py", "import socket\n", "reach other systems"),
    ("SKILL.md", "---\nname: other\ndescription: x\n---\nbody\n", "must be named match-lists"),
])
def test_files_refuses_bad_files(ws, tmp_path, name, content, message):
    add(ws, tmp_path)
    draft = filled(ws)
    if name != "SKILL.md":
        (draft / name).write_text(content, encoding="utf-8")
    else:
        (draft / "SKILL.md").write_text(content, encoding="utf-8")
    before = (ws / ".claude/skills/match-lists/SKILL.md").read_text(encoding="utf-8")
    with pytest.raises(tools.ToolProblem, match=message):
        tools.install_files(workspace.Paths(ws), "match-lists")
    assert (ws / ".claude/skills/match-lists/SKILL.md").read_text(encoding="utf-8") == before
    assert not (ws / f".claude/skills/match-lists/{name}").exists() or name in ("SKILL.md", "checklist.yaml")


def test_files_put_in_place_and_clear_check(ws, tmp_path, cli):
    add(ws, tmp_path)
    p = workspace.Paths(ws)
    t = registry.find(p, "match-lists")
    t.last_check = {"date": "2026-10-28", "result": "pass", "detail": ""}
    registry.save(p, t)
    draft = filled(ws)
    (draft / "facts.py").write_text((draft / "facts-template.py").read_text(encoding="utf-8"), encoding="utf-8")
    (draft / "input.yaml").write_text("- name: Export\n  types: [csv]\n  required_columns: [Offering]\n",
                                      encoding="utf-8")
    r = cli("--workspace", str(ws), "tool", "files", "match-lists")
    assert r.returncode == 0, r.text
    assert "instructions page, checklist, input checks, facts step" in r.stdout
    folder = ws / ".claude/skills/match-lists"
    assert (folder / "facts.py").is_file() and (folder / "input.yaml").is_file()
    assert not (folder / "facts-template.py").exists()
    assert registry.find(p, "match-lists").last_check is None
    r = cli("--workspace", str(ws), "tool", "files", "match-lists")
    assert "already up to date" in r.stdout


def test_files_cli_messages(ws, tmp_path, cli):
    add(ws, tmp_path)
    r = cli("--workspace", str(ws), "tool", "files", "match-lists")
    assert r.returncode == 1 and "fill in" in r.stderr and "Traceback" not in r.text
    r = cli("--workspace", str(ws), "tool", "files", "nope")
    assert r.returncode == 1 and "There is no tool called nope." in r.stderr
    r = cli("--workspace", str(ws), "tool", "draft", "match-lists")
    assert r.returncode == 0 and "Match the offering lists" in r.stdout


def test_record_in_draft_folder_is_tidied(ws, cli):
    draft = ws / "data/drafts/match-lists"
    draft.mkdir(parents=True)
    (draft / "tool.yaml").write_text(yaml.safe_dump(RECORD), encoding="utf-8")
    r = cli("--workspace", str(ws), "tool", "add", "--from", str(draft / "tool.yaml"))
    assert r.returncode == 0, r.text
    assert not (draft / "tool.yaml").exists() and (draft / "SKILL.md").is_file()


def test_facts_template_runs(tmp_path):
    out = subprocess.run([sys.executable, str(tools.FACTS_TEMPLATE), str(SYN / "inventory.csv"), str(SYN / "faq.md")],
                         capture_output=True, text=True, timeout=60, env={"JA_WORKSPACE": str(tmp_path)})
    data = json.loads(out.stdout)
    assert data["facts"][0] == {"id": "rows-1", "label": "Rows in the 1 file", "value": 42, "unit": "rows",
                                "source": "inventory.csv", "notes": ""}
    assert data["counts"] == {"rows_1": 42} and data["problems"] == ["I do not know how to read faq.md yet."]


def test_facts_template_reads_inputs_by_name(tmp_path):
    out = subprocess.run([sys.executable, str(tools.FACTS_TEMPLATE), "--input", f"inventory={SYN / 'inventory.csv'}"],
                         capture_output=True, text=True, timeout=60, env={"JA_WORKSPACE": str(tmp_path)})
    data = json.loads(out.stdout)
    assert data["facts"][0]["id"] == "rows-inventory" and data["facts"][0]["label"] == "Rows in the inventory file"


def test_facts_template_is_allowed():
    from ja import safety
    assert safety.problem(tools.FACTS_TEMPLATE) is None
