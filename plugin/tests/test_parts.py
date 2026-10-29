"""The parts library and search over tools and parts."""

from datetime import date

import pytest
import yaml

from ja import parts, registry, tools, workspace

T = date(2026, 10, 28)


def part_file(tmp_path, code="def key(name):\n    return ' '.join(name.split()).lower()\n", **fields):
    record = {"id": "name-match", "name": "Name matcher", "does": "Matches names ignoring case and spaces.",
              "kind": "step", "file": "names.py", **fields}
    (tmp_path / "names.py").write_text(code, encoding="utf-8")
    (tmp_path / "part.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
    return tmp_path / "part.yaml"


def test_add_code_part(ws, cli, tmp_path):
    r = cli("--workspace", str(ws), "part", "add", "--from", str(part_file(tmp_path)))
    assert r.returncode == 0 and "Added the part Name matcher." in r.stdout
    folder = ws / "parts/name-match"
    assert (folder / "part.py").is_file()
    record = yaml.safe_load((folder / "part.yaml").read_text(encoding="utf-8"))
    assert record == {"id": "name-match", "name": "Name matcher", "does": "Matches names ignoring case and spaces.",
                      "kind": "step", "file": "part.py", "used_by": []}
    r = cli("--workspace", str(ws), "part", "add", "--from", str(part_file(tmp_path)))
    assert r.returncode == 1 and "already a part called name-match" in r.stderr


def test_add_writer_part(ws, tmp_path):
    (tmp_path / "w.md").write_text("Write a short summary first.\n", encoding="utf-8")
    (tmp_path / "part.yaml").write_text(yaml.safe_dump(
        {"id": "summary-first", "name": "Summary first", "does": "Opens with a two line summary.", "kind": "writer",
         "file": "w.md"}), encoding="utf-8")
    part, used = parts.add_from_file(workspace.Paths(ws), tmp_path / "part.yaml")
    assert part.file == "part.md" and (ws / "parts/summary-first/part.md").is_file() and len(used) == 2


@pytest.mark.parametrize("code", ["import socket\n", "import os\nos.system('ls')\n", "from subprocess import run\n"])
def test_code_part_may_not_reach_out(ws, cli, tmp_path, code):
    r = cli("--workspace", str(ws), "part", "add", "--from", str(part_file(tmp_path, code=code)))
    assert r.returncode == 1 and "tries to reach other systems or run programs" in r.stderr
    assert not (ws / "parts/name-match").exists()


@pytest.mark.parametrize("fields, message", [
    ({"kind": "gadget"}, "kind must be one of"),
    ({"id": "Bad Id"}, "lowercase letters"),
    ({"file": "missing.py"}, "could not find missing.py"),
    ({"name": ""}, "needs a name"),
])
def test_bad_parts(ws, tmp_path, fields, message):
    with pytest.raises(parts.PartProblem, match=message):
        parts.add_from_file(workspace.Paths(ws), part_file(tmp_path, **fields))


def test_inbox_files_tidied(ws, cli):
    inbox = ws / "inbox"
    inbox.mkdir()
    part_file(inbox)
    assert cli("--workspace", str(ws), "part", "add", "--from", str(inbox / "part.yaml")).returncode == 0
    assert list(inbox.iterdir()) == []


def test_tool_add_records_parts(ws, cli, tmp_path):
    p = workspace.Paths(ws)
    parts.add_from_file(p, part_file(tmp_path))
    record = {"id": "match", "name": "Match lists", "does": "Matches two lists.", "examples": ["match these"],
              "kind": "built", "status": "being-built", "rhythm": "monthly", "data_path": "Two exports",
              "parts": ["name-match"]}
    (tmp_path / "tool.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
    tools.add_from_file(p, tmp_path / "tool.yaml", today=T)
    assert parts.load(p, "name-match").used_by == ["match"]
    assert registry.find(p, "match").extra["parts"] == ["name-match"]
    r = cli("--workspace", str(ws), "parts")
    assert "Name matcher (step, id name-match): Matches names ignoring case and spaces. Used by: Match lists." in r.stdout
    record.update(id="other", parts=["nope"])
    (tmp_path / "tool.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(tools.ToolProblem, match="There is no part called nope."):
        tools.add_from_file(p, tmp_path / "tool.yaml", today=T)
    assert not (ws / ".claude/skills/other").exists()


def test_search_ranks_tools_and_parts(ws, write_tool, cli, tmp_path):
    p = workspace.Paths(ws)
    write_tool(ws, id="reconcile", name="Reconcile offering lists", does="Matches the export to the inventory.",
               examples=["reconcile the offerings"], recipe="reconcile-two-lists")
    write_tool(ws, id="brief", name="Check a brief", does="Lists gaps in a launch brief.", examples=["check this brief"])
    write_tool(ws, folder="archive", id="old-match", name="Old inventory matcher", status="retired",
               does="Matched inventory rows.", examples=["old match"])
    parts.add_from_file(p, part_file(tmp_path))
    r = cli("--workspace", str(ws), "search", "reconcile", "the", "inventory", "offerings", "names")
    lines = r.stdout.splitlines()
    assert lines[0].startswith("Tool: Reconcile offering lists (Working).") and "Matches: inventory, offering, reconcile." in lines[0]
    assert any(l.startswith("Tool: Old inventory matcher (Retired).") for l in lines)
    assert any(l.startswith("Part: Name matcher (step, id name-match).") for l in lines)
    assert not any("Check a brief" in l for l in lines)
    r = cli("--workspace", str(ws), "search", "weather", "forecast")
    assert "Nothing similar yet." in r.stdout


def test_search_top_five(ws, write_tool, cli):
    for n in range(8):
        write_tool(ws, id=f"t{n}", name=f"Report {n}", does="Builds a report.", examples=["report"])
    assert len(cli("--workspace", str(ws), "search", "report").stdout.splitlines()) == 5


def test_words():
    assert parts.words("The offerings, Reports and class") == {"offering", "report", "class"}
