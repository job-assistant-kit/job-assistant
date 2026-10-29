import json
import subprocess
import sys
from pathlib import Path

JA = Path(__file__).parents[1] / "scripts" / "ja.py"
TODAY = ("--today", "2026-10-28")
NOT_FOUND = ("I could not find your assistant folder. Open the assistant from its shortcut, "
             "or run this inside your assistant folder.")


def run(*a, cwd=None):
    return subprocess.run([sys.executable, str(JA), *a], capture_output=True, text=True, cwd=cwd)


def out(r):
    return r.stdout + r.stderr


def make(tmp_path, write_tool=None, **tool):
    root = tmp_path / "assistant-home"
    r = run("init", str(root))
    assert r.returncode == 0, out(r)
    if write_tool is not None:
        write_tool(root, **tool)
    return root


def test_init_creates_layout(tmp_path):
    root = tmp_path / "new"
    r = run("init", str(root), "--name", "David's assistant")
    assert r.returncode == 0, out(r)
    for d in (".claude/skills", "archive", "parts", "inbox", "data/records", "data/proofs", "assistant"):
        assert (root / d).is_dir(), d
    assert (root / "assistant/sources.yaml").read_text().strip() == "[]"
    assert (root / "assistant/profile.yaml").read_text().strip() == "rules: []"
    lines = (root / ".gitignore").read_text().splitlines()
    for entry in ("inbox/", "data/", "dashboard/"):
        assert entry in lines
    claude = (root / "CLAUDE.md").read_text()
    assert "<!-- tool-index:start -->" in claude and "<!-- tool-index:end -->" in claude
    assert "David's assistant" in claude
    assert not (root / "gitignore").exists()


def test_init_into_existing_empty_dir(tmp_path):
    root = tmp_path / "empty"; root.mkdir()
    assert run("init", str(root)).returncode == 0
    assert (root / "assistant").is_dir()


def test_init_refuses_non_empty(tmp_path):
    root = tmp_path / "full"; root.mkdir(); (root / "notes.txt").write_text("x")
    r = run("init", str(root))
    assert r.returncode == 1 and "That folder is not empty" in out(r)
    assert not (root / "assistant").exists()


def test_tools_empty(tmp_path):
    root = make(tmp_path)
    r = run("tools", *TODAY, cwd=root)
    assert r.returncode == 0 and "No tools yet." in r.stdout


def test_check_fail_then_needs_update(tmp_path, write_tool):
    root = make(tmp_path, write_tool)
    r = run("check", "t1", "--result", "fail", "--detail", "Column Stage is missing", *TODAY, cwd=root)
    assert r.returncode == 0, out(r)
    r = run("tools", *TODAY, cwd=root)
    assert "Needs update" in r.stdout and "Last check failed: Column Stage is missing" in r.stdout
    import yaml
    check = yaml.safe_load((root / ".claude/skills/t1/tool.yaml").read_text())["last_check"]
    assert check == {"date": "2026-10-28", "result": "fail", "detail": "Column Stage is missing"}


def test_check_unknown_tool(tmp_path):
    root = make(tmp_path)
    r = run("check", "nope", "--result", "pass", *TODAY, cwd=root)
    assert r.returncode == 1 and "There is no tool called nope." in out(r)


def test_record_runs_counted(tmp_path, write_tool):
    root = make(tmp_path, write_tool)
    for _ in range(2):
        assert run("record", "run", "t1", *TODAY, cwd=root).returncode == 0
    r = run("tools", "--json", *TODAY, cwd=root)
    assert r.returncode == 0 and '"runs": 2' in r.stdout
    data = json.loads(r.stdout)
    assert data["tools"][0]["id"] == "t1" and data["tools"][0]["label"] == "Working"


def test_record_build(tmp_path, write_tool):
    root = make(tmp_path, write_tool)
    r = run("record", "build", "--tool", "t1", "--recipe", "reconcile", "--questions", "3",
            "--corrections", "1", "--minutes", "25", *TODAY, cwd=root)
    assert r.returncode == 0, out(r)
    line = json.loads((root / "data/records/builds.jsonl").read_text().splitlines()[0])
    assert line["minutes"] == 25 and line["recipe"] == "reconcile"


def test_record_unknown_tool(tmp_path):
    root = make(tmp_path)
    r = run("record", "run", "ghost", *TODAY, cwd=root)
    assert r.returncode == 1 and "There is no tool called ghost." in out(r)


def test_ledger_add_and_compare(tmp_path):
    root = make(tmp_path)
    r = run("ledger", "compare", "--metric", "ttm-days", "--value", "94", *TODAY, cwd=root)
    assert r.returncode == 0 and "No published value yet" in r.stdout
    r = run("ledger", "add", "--metric", "ttm-days", "--period", "2026-Q2", "--value", "112", "--unit", "days",
            "--source", "metrics-latest.json", "--method-notes", "Rows without awareness date excluded",
            "--tool", "ttm", "--date", "2026-07-10", *TODAY, cwd=root)
    assert r.returncode == 0, out(r)
    r = run("ledger", "compare", "--metric", "ttm-days", "--value", "94", *TODAY, cwd=root)
    assert r.stdout.strip().splitlines() == [
        "Last published: 112 days for 2026-Q2. Change: -18 (-16.1%).",
        "This is a big change. Check the method before sending.",
    ]
    r = run("ledger", "compare", "--metric", "ttm-days", "--value", "94", "--json", *TODAY, cwd=root)
    assert json.loads(r.stdout)["previous"] == 112


def test_ledger_add_defaults_to_today(tmp_path):
    root = make(tmp_path)
    run("ledger", "add", "--metric", "m", "--period", "P", "--value", "1", "--unit", "n", "--source", "s",
        "--method-notes", "m", "--tool", "t", *TODAY, cwd=root)
    line = json.loads((root / "data/ledger.jsonl").read_text())
    assert line["approved_on"] == "2026-10-28" and line["value"] == 1


def test_index_and_dashboard_write_files(tmp_path, write_tool):
    root = make(tmp_path, write_tool, name="Check a brief")
    r = run("index", *TODAY, cwd=root)
    assert r.returncode == 0, out(r)
    assert '- Check a brief (Working): Does one thing. Say: "do one".' in (root / "CLAUDE.md").read_text()
    r = run("dashboard", *TODAY, cwd=root)
    assert r.returncode == 0, out(r)
    assert "Check a brief" in (root / "dashboard/index.html").read_text()


def test_index_missing_markers(tmp_path):
    root = make(tmp_path)
    (root / "CLAUDE.md").write_text("no markers\n")
    r = run("index", *TODAY, cwd=root)
    assert r.returncode == 1 and "markers" in out(r)


def test_workspace_flag_and_subfolder(tmp_path, write_tool):
    root = make(tmp_path, write_tool)
    assert "Tool one" in run("tools", "--workspace", str(root), *TODAY, cwd=tmp_path).stdout
    assert "Tool one" in run("--workspace", str(root), "tools", *TODAY, cwd=tmp_path).stdout
    assert "Tool one" in run("tools", *TODAY, cwd=root / "inbox").stdout


def test_tools_lists_problems(tmp_path, write_tool):
    root = make(tmp_path, write_tool, id="bad", status="great")
    r = run("tools", *TODAY, cwd=root)
    assert r.returncode == 0
    assert "Tools with problems" in r.stdout and "bad: status must be one of" in r.stdout
    assert "Traceback" not in out(r)


def test_bad_today(tmp_path):
    root = make(tmp_path)
    r = run("tools", "--today", "soon", cwd=root)
    assert r.returncode == 1 and "Traceback" not in out(r)


def test_outside_workspace(tmp_path):
    for args in (("tools",), ("index",), ("dashboard",), ("record", "run", "t1"), ("check", "t1", "--result", "pass"),
                 ("ledger", "compare", "--metric", "m", "--value", "1")):
        r = run(*args, *TODAY, cwd=tmp_path)
        assert r.returncode == 1, args
        assert NOT_FOUND in out(r), args
