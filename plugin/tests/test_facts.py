"""Running a tool's facts step and checking what it prints."""

import json
import shutil
from pathlib import Path

import pytest

from ja import facts, workspace

SYN = Path(__file__).parent / "fixtures" / "synthetic"
RECONCILE = Path(__file__).parent / "fixtures" / "facts" / "reconcile.py"
FILES = [str(SYN / "servicenow-export.csv"), str(SYN / "inventory.csv")]


@pytest.fixture
def tool(ws, write_tool):
    write_tool(ws, id="match", name="Match the lists")
    shutil.copyfile(RECONCILE, ws / ".claude/skills/match/facts.py")
    return ws


def step(ws, code):
    (ws / ".claude/skills/match/facts.py").write_text(code, encoding="utf-8")


def test_run_prints_facts_and_keeps_them(tool, cli):
    r = cli("--workspace", str(tool), "facts", "run", "match", *FILES)
    assert r.returncode == 0, r.text
    assert "Rows in the export: 40 rows (source: servicenow-export.csv)" in r.stdout
    assert "Offerings not in the inventory: 2 offerings" in r.stdout
    assert "Rows with no governance date: 6 rows" in r.stdout
    assert "Counts:\n  blank_governance: 6" in r.stdout
    saved = json.loads((tool / "data/last/match.json").read_text(encoding="utf-8"))
    assert [f["id"] for f in saved["facts"]] == ["export-rows", "unmatched", "blank-governance"]
    inputs = json.loads((tool / "data/last/match.inputs.json").read_text(encoding="utf-8"))
    assert [i["name"] for i in inputs] == ["servicenow-export.csv", "inventory.csv"]


def test_json_output(tool, cli):
    r = cli("--workspace", str(tool), "facts", "run", "match", *FILES, "--json")
    assert json.loads(r.stdout)["counts"] == {"blank_governance": 6}


def test_crash_is_plain_and_records_nothing(tool, cli):
    step(tool, "raise ValueError('the Stage column is empty')\n")
    r = cli("--workspace", str(tool), "facts", "run", "match", *FILES)
    assert r.returncode == 1
    assert "The facts step for Match the lists failed: ValueError: the Stage column is empty" in r.stderr
    assert not (tool / "data/last/match.json").exists()


@pytest.mark.parametrize("output, reason", [
    ("print('hello')", "it did not print results"),
    ("print('{\"facts\": 3}')", "there is no list of facts"),
    ("import json; print(json.dumps({'facts': [{'id': 'a', 'label': 'A', 'value': 1}, "
     "{'id': 'a', 'label': 'B', 'value': 2}]}))", "two facts have the id a"),
    ("import json; print(json.dumps({'facts': [{'id': 'a', 'label': 'A'}]}))", "the fact A has no usable value"),
    ("print('{\"facts\": [{\"id\": \"a\", \"label\": \"A\", \"value\": NaN}]}')", "no usable value"),
    ("import json; print(json.dumps({'facts': [], 'counts': {'x': 1.5}}))", "counts must be whole numbers"),
])
def test_invalid_output(tool, cli, output, reason):
    step(tool, output + "\n")
    r = cli("--workspace", str(tool), "facts", "run", "match", *FILES)
    assert r.returncode == 1 and reason in r.stderr, r.text
    assert "gave results I could not use" in r.stderr


def test_refuses_network_and_programs(tool, cli):
    step(tool, "import urllib.request\nprint('{}')\n")
    r = cli("--workspace", str(tool), "facts", "run", "match", *FILES)
    assert r.returncode == 1 and "tries to reach other systems or run programs" in r.stderr


def test_time_limit(tool):
    step(tool, "import time\ntime.sleep(30)\n")
    with pytest.raises(facts.FactsProblem, match="took too long"):
        facts.run(workspace.Paths(tool), "match", "Match the lists", [Path(f) for f in FILES], timeout=3)


def test_no_step(ws, write_tool, cli):
    write_tool(ws, id="plain")
    r = cli("--workspace", str(ws), "facts", "run", "plain", str(SYN / "faq.md"))
    assert r.returncode == 0 and "This tool has no facts step." in r.stdout


def test_missing_file(tool, cli, tmp_path):
    r = cli("--workspace", str(tool), "facts", "run", "match", str(tmp_path / "gone.csv"))
    assert r.returncode == 1 and "I could not find the file gone.csv." in r.stderr


def test_step_sees_the_workspace(tool, cli):
    step(tool, "import json, os\nprint(json.dumps({'facts': [{'id': 'w', 'label': 'Where', "
               "'value': os.environ['JA_WORKSPACE']}]}))\n")
    r = cli("--workspace", str(tool), "facts", "run", "match", *FILES)
    assert f"Where: {tool.resolve()}" in r.stdout


def _set_mtime(path, day):
    import os
    from datetime import datetime
    stamp = datetime.fromisoformat(day + "T10:00:00").timestamp()
    os.utime(path, (stamp, stamp))


def test_run_prints_when_each_file_was_received(tool, cli, tmp_path):
    files = []
    for name, day in (("servicenow-export.csv", "2026-10-27"), ("inventory.csv", "2026-10-20")):
        shutil.copyfile(SYN / name, tmp_path / name)
        _set_mtime(tmp_path / name, day)
        files.append(str(tmp_path / name))
    r = cli("--workspace", str(tool), "facts", "run", "match", *files)
    assert r.returncode == 0, r.text
    assert ("Received (saved on this computer): servicenow-export.csv on Oct 27, 2026; "
            "inventory.csv on Oct 20, 2026.") in r.stdout
    assert 'Export date: unknown unless the person says it.' in r.stdout
    inputs = json.loads((tool / "data/last/match.inputs.json").read_text(encoding="utf-8"))
    assert [i["received"] for i in inputs] == ["2026-10-27", "2026-10-20"]
    data = json.loads(cli("--workspace", str(tool), "facts", "run", "match", *files, "--json").stdout)
    assert data["received"] == {"servicenow-export.csv": "2026-10-27", "inventory.csv": "2026-10-20"}
    assert "received" not in json.loads((tool / "data/last/match.json").read_text(encoding="utf-8"))


def _running(marker: str) -> bool:
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit():
            try:
                if marker in (proc / "cmdline").read_bytes().decode(errors="ignore"):
                    return True
            except OSError:
                pass
    return False


def test_time_limit_stops_the_whole_step(tool):
    marker = "ja-sleep-marker-7f3a"
    step(tool, f"# {marker}\nimport time\ntime.sleep(60)\n")
    target = tool / ".claude/skills/match/facts.py"
    with pytest.raises(facts.FactsProblem, match="took too long"):
        facts.run(workspace.Paths(tool), "match", "Match the lists", [Path(f) for f in FILES], timeout=3)
    assert not _running(str(target))


def test_blocked_action_gets_a_plain_message(tool):
    step(tool, "import importlib\nm = importlib.import_module('sub' + 'process')\nm.run(['id'])\n")
    with pytest.raises(facts.FactsProblem) as err:
        facts.run(workspace.Paths(tool), "match", "Match the lists", [Path(f) for f in FILES])
    assert str(err.value) == ("The facts step for Match the lists tried to run a program, "
                              "which tools here are not allowed to do.")


def test_extra_software_is_refused(tool):
    step(tool, "# /// script\n# dependencies = [\"requests>=2\", \"openpyxl\"]\n# ///\nprint('{}')\n")
    with pytest.raises(facts.FactsProblem, match=r"extra software \(requests\)"):
        facts.run(workspace.Paths(tool), "match", "Match the lists", [Path(f) for f in FILES])


def test_approved_library_is_available(tool):
    step(tool, "# /// script\n# dependencies = [\"openpyxl\"]\n# ///\nimport json, openpyxl\n"
               "print(json.dumps({'facts': [], 'counts': {}, 'problems': []}))\n")
    result = facts.run(workspace.Paths(tool), "match", "Match the lists", [Path(f) for f in FILES])
    assert result.facts == []
