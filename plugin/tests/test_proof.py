"""Saved examples and the checks that rerun them."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from ja import proof, registry, workspace

SYN = Path(__file__).parent / "fixtures" / "synthetic"
RECONCILE = Path(__file__).parent / "fixtures" / "facts" / "reconcile.py"
TTM = ("import json, sys\n"
       "days = int(open(sys.argv[1]).read().split()[0])\n"
       "print(json.dumps({'facts': [{'id': 'ttm', 'label': 'TTM median days', 'value': days},"
       " {'id': 'n', 'label': 'Offerings counted', 'value': 12, 'unit': 'offerings'}]}))\n")


@pytest.fixture
def tool(ws, write_tool):
    write_tool(ws, id="match", name="Match the lists", status="working", last_check=None)
    shutil.copyfile(RECONCILE, ws / ".claude/skills/match/facts.py")
    (ws / ".claude/skills/match/checklist.yaml").write_text(
        yaml.safe_dump({"required": ["Lists every unmatched offering.", "Counts the blank rows."], "rules": []}),
        encoding="utf-8")
    (ws / "inbox").mkdir()
    (ws / "inbox/result.md").write_text("Two offerings are not in the inventory.\n", encoding="utf-8")
    return ws


def inputs(tmp_path):
    out = []
    for name in ("servicenow-export.csv", "inventory.csv"):
        shutil.copyfile(SYN / name, tmp_path / name)
        out.append(str(tmp_path / name))
    return out


def save(cli, ws, files, output="inbox/result.md"):
    return cli("--workspace", str(ws), "proof", "save", "match", "--input", *files, "--output", str(ws / output))


def test_save_needs_a_facts_run_on_the_same_files(tool, cli, tmp_path):
    files = inputs(tmp_path)
    r = save(cli, tool, files)
    assert r.returncode == 1 and "Run the facts step on this example first" in r.stderr
    cli("--workspace", str(tool), "facts", "run", "match", *files)
    other = tmp_path / "other.csv"
    other.write_text("Offering,Owner\nX,Y\n", encoding="utf-8")
    r = save(cli, tool, [files[0], str(other)])
    assert r.returncode == 1 and "used different files" in r.stderr


def test_save_numbers_cases_and_keeps_order(tool, cli, tmp_path):
    files = inputs(tmp_path)
    assert cli("--workspace", str(tool), "facts", "run", "match", *files).returncode == 0
    r = save(cli, tool, list(reversed(files)))
    assert r.returncode == 0 and "Saved example 1 for Match the lists." in r.stdout
    case = tool / "data/proofs/match/case-1"
    assert sorted(p.name for p in case.iterdir()) == ["facts.json", "inputs", "meta.json", "output.md"]
    meta = json.loads((case / "meta.json").read_text(encoding="utf-8"))
    assert meta["inputs"] == ["servicenow-export.csv", "inventory.csv"] and meta["saved"]
    assert "Saved example 2" in save(cli, tool, files).stdout
    r = cli("--workspace", str(tool), "proof", "list", "match")
    assert "Example 1, saved" in r.stdout and "Example 2, saved" in r.stdout and "2 input files" in r.stdout


def test_run_passes_and_prints_checklist(tool, cli, tmp_path):
    files = inputs(tmp_path)
    cli("--workspace", str(tool), "facts", "run", "match", *files)
    save(cli, tool, files)
    r = cli("--workspace", str(tool), "proof", "run", "match")
    assert r.returncode == 0, r.text
    assert "The facts match the saved example." in r.stdout
    assert "- Lists every unmatched offering." in r.stdout and "- Counts the blank rows." in r.stdout
    assert str(tool / "data/proofs/match/case-1/output.md") in r.stdout
    assert proof.REWRITE in r.stdout
    assert registry.find(workspace.Paths(tool), "match").last_check is None


def test_changed_value_fails_and_records(ws, write_tool, cli, tmp_path):
    write_tool(ws, id="ttm", name="TTM report", last_check=None)
    (ws / ".claude/skills/ttm/facts.py").write_text(TTM, encoding="utf-8")
    data = tmp_path / "days.txt"
    data.write_text("101\n", encoding="utf-8")
    (tmp_path / "out.md").write_text("Median 101 days.\n", encoding="utf-8")
    cli("--workspace", str(ws), "facts", "run", "ttm", str(data))
    assert cli("--workspace", str(ws), "proof", "save", "ttm", "--input", str(data),
               "--output", str(tmp_path / "out.md")).returncode == 0
    (ws / "data/proofs/ttm/case-1/inputs/days.txt").write_text("94\n", encoding="utf-8")
    r = cli("--workspace", str(ws), "--today", "2026-10-28", "proof", "run", "ttm")
    assert r.returncode == 1
    assert "TTM median days: was 101, now 94" in r.stdout and proof.REWRITE in r.stdout
    check = registry.find(workspace.Paths(ws), "ttm").last_check
    assert check == {"date": "2026-10-28", "result": "fail", "detail": "Example 1: TTM median days: was 101, now 94"}


def test_compare_sentences():
    old = [{"id": "a", "label": "A", "value": 1, "unit": "days"}, {"id": "b", "label": "B", "value": True, "unit": ""}]
    new = [{"id": "a", "label": "A", "value": 1, "unit": "weeks"}, {"id": "b", "label": "B", "value": 1, "unit": ""},
           {"id": "c", "label": "C", "value": "x", "unit": ""}]
    assert proof.compare(old, new) == ["A: was 1 days, now 1 weeks", "B: was yes, now 1", "C: new fact, now x"]
    assert proof.compare(old, old[:1]) == ["B: was yes, now no longer found"]
    assert proof.compare([{"id": "a", "label": "A", "value": 1, "source": "x", "notes": "y"}],
                         [{"id": "a", "label": "A", "value": 1.0, "source": "z", "notes": ""}]) == []


def test_missing_case_and_no_cases(tool, cli, tmp_path):
    r = cli("--workspace", str(tool), "proof", "run", "match")
    assert r.returncode == 1 and "no saved examples for Match the lists yet" in r.stderr
    assert "There are no saved examples for Match the lists yet." in cli(
        "--workspace", str(tool), "proof", "list", "match").stdout
    files = inputs(tmp_path)
    cli("--workspace", str(tool), "facts", "run", "match", *files)
    save(cli, tool, files)
    r = cli("--workspace", str(tool), "proof", "run", "match", "--case", "3")
    assert r.returncode == 1 and "There is no example 3 for Match the lists." in r.stderr


def test_tool_without_facts_gets_no_verdict(ws, write_tool, cli, tmp_path):
    write_tool(ws, id="faq", name="Answer from the FAQ", last_check=None)
    (tmp_path / "answer.md").write_text("Answer.\n", encoding="utf-8")
    r = cli("--workspace", str(ws), "proof", "save", "faq", "--input", str(SYN / "slack-questions.txt"),
            "--output", str(tmp_path / "answer.md"))
    assert r.returncode == 0 and not (ws / "data/proofs/faq/case-1/facts.json").exists()
    r = cli("--workspace", str(ws), "proof", "run", "faq")
    assert r.returncode == 0 and "no facts step, so only the written result can be checked" in r.stdout
    assert "(This tool has no checklist items yet.)" in r.stdout
    assert registry.find(workspace.Paths(ws), "faq").last_check is None


def test_crash_on_rerun_fails(tool, cli, tmp_path):
    files = inputs(tmp_path)
    cli("--workspace", str(tool), "facts", "run", "match", *files)
    save(cli, tool, files)
    (tool / ".claude/skills/match/facts.py").write_text("raise SystemExit('broken')\n", encoding="utf-8")
    r = cli("--workspace", str(tool), "proof", "run", "match")
    assert r.returncode == 1 and "failed: broken" in r.stdout


def test_save_refuses_duplicate_names_and_missing_files(ws, write_tool, cli, tmp_path):
    write_tool(ws, id="faq", last_check=None)
    (tmp_path / "a").mkdir()
    (tmp_path / "a/q.txt").write_text("1", encoding="utf-8")
    (tmp_path / "q.txt").write_text("2", encoding="utf-8")
    r = cli("--workspace", str(ws), "proof", "save", "faq", "--input", str(tmp_path / "q.txt"),
            str(tmp_path / "a/q.txt"), "--output", str(tmp_path / "q.txt"))
    assert r.returncode == 1 and "same name" in r.stderr
    r = cli("--workspace", str(ws), "proof", "save", "faq", "--input", str(tmp_path / "gone.txt"),
            "--output", str(tmp_path / "q.txt"))
    assert r.returncode == 1 and "I could not find the file gone.txt." in r.stderr
