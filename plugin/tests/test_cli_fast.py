"""Command line behavior, run in this process for speed."""

import json

import pytest
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
        r = cli("ledger", "compare", "--metric", "m", "--value", bad, "--unit", "n", *TODAY, cwd=ws)
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


def test_init_bad_name(tmp_path, cli):
    r = cli("init", str(tmp_path / "x"), "--name", "<>")
    assert r.returncode == 1 and "name" in r.stderr and not (tmp_path / "x").exists()


def test_init_cannot_create(tmp_path, cli):
    (tmp_path / "f").write_text("x", encoding="utf-8")
    r = cli("init", str(tmp_path / "f" / "x"))
    assert r.returncode == 1 and r.stderr.startswith("I could not create the folder at ")
    assert "Traceback" not in r.text


def test_dashboard_title_uses_assistant_name(ws, cli):
    (ws / "CLAUDE.md").write_text("# Sam's Assistant\n<!-- tool-index:start -->\n<!-- tool-index:end -->\n",
                                  encoding="utf-8")
    assert cli("dashboard", *TODAY, cwd=ws).returncode == 0
    html = (ws / "dashboard/index.html").read_text(encoding="utf-8")
    assert "<title>Sam&#39;s Assistant</title>" in html and "<h1>Sam&#39;s Assistant</h1>" in html


def test_index_reports_invalid_tools(ws, write_tool, cli):
    write_tool(ws, id="bad", status="great")
    r = cli("index", *TODAY, cwd=ws)
    assert r.returncode == 0
    assert "up to date" not in r.stdout
    assert "Tools with problems:" in r.stdout and "bad: status must be one of" in r.stdout


def test_index_up_to_date_when_clean(ws, write_tool, cli):
    write_tool(ws, id="a")
    r = cli("index", *TODAY, cwd=ws)
    assert r.stdout.strip() == "The list of tools in your assistant notes is up to date."


def test_role_set_cli(tmp_path, cli):
    root = tmp_path / "ws"
    assert cli("init", str(root)).returncode == 0
    card = tmp_path / "role.md"
    card.write_text("Sam reviews offerings.\n", encoding="utf-8")
    r = cli("role", "set", "--file", str(card), cwd=root)
    assert r.returncode == 0, r.text
    assert "Sam reviews offerings." in (root / "CLAUDE.md").read_text(encoding="utf-8")
    card.write_text("x" * 1700, encoding="utf-8")
    r = cli("role", "set", "--file", str(card), cwd=root)
    assert r.returncode == 1
    assert r.stderr.strip() == "The role description is too long. Keep it under about 250 words."
    r = cli("role", "set", "--file", str(tmp_path / "missing.md"), cwd=root)
    assert r.returncode == 1 and "could not read" in r.stderr


def test_settings_cli(ws, cli):
    r = cli("settings", "deny", "mcp__x__send", "mcp__x__post", cwd=ws)
    assert r.returncode == 0 and r.stdout.strip() == "Blocked: 2 new write actions."
    r = cli("settings", "deny", "mcp__x__send", cwd=ws)
    assert r.stdout.strip() == "Blocked: 0 new write actions."
    r = cli("settings", "deny", "mcp__x__send", "mcp__x__share", cwd=ws)
    assert r.stdout.strip() == "Blocked: 1 new write action."
    r = cli("settings", "deny", "post_message", cwd=ws)
    assert r.returncode == 1 and "post_message" in r.stderr
    r = cli("settings", "show", cwd=ws)
    assert r.returncode == 0 and "mcp__x__send" in r.stdout and "mcp__x__post" in r.stdout


def test_sources_cli(ws, write_tool, cli):
    write_tool(ws, id="a", name="Answer", sources=["faq"])
    r = cli("sources", "add", "--id", "faq", "--name", "OLM FAQ", "--kind", "living", "--where", "Shared drive",
            "--access", "file", "--exported", "2026-10-01", *TODAY, cwd=ws)
    assert r.returncode == 0, r.text
    assert "Answer (Needs update)" in (ws / "CLAUDE.md").read_text(encoding="utf-8")
    r = cli("sources", "add", "--id", "faq", "--name", "X", "--kind", "living", "--where", "x",
            "--access", "file", *TODAY, cwd=ws)
    assert r.returncode == 1 and r.stderr.strip() == "There is already a source called faq."
    r = cli("sources", "add", "--id", "q", "--name", "X", "--kind", "soft", "--where", "x", "--access", "file", cwd=ws)
    assert r.returncode == 1 and "usage:" not in r.text
    assert cli("sources", "exported", "faq", "2026-10-27", *TODAY, cwd=ws).returncode == 0
    assert "Answer (Working)" in (ws / "CLAUDE.md").read_text(encoding="utf-8")
    r = cli("sources", "list", *TODAY, cwd=ws)
    assert "OLM FAQ" in r.stdout and "1 day old" in r.stdout
    data = json.loads(cli("sources", "list", "--json", *TODAY, cwd=ws).stdout)
    assert data[0]["id"] == "faq" and data[0]["age_days"] == 1


def test_tool_commands_refresh_index_and_page(ws, tmp_path, write_tool, cli):
    rec = tmp_path / "t.yaml"
    rec.write_text(yaml.safe_dump({"id": "brief", "name": "Check a brief", "does": "Lists gaps.",
                                   "examples": ["check this brief"], "kind": "built", "status": "working",
                                   "rhythm": "on-demand", "data_path": "Files you drop in"}), encoding="utf-8")
    r = cli("tool", "add", "--from", str(rec), *TODAY, cwd=ws)
    assert r.returncode == 0, r.text
    notes = lambda: (ws / "CLAUDE.md").read_text(encoding="utf-8")
    page = lambda: (ws / "dashboard/index.html").read_text(encoding="utf-8")
    assert "Check a brief (Draft, not checked)" in notes() and "Check a brief" in page()
    (ws / "data/proofs/brief/case-1/inputs").mkdir(parents=True)
    (ws / "data/proofs/brief/case-1/meta.json").write_text('{"saved": "2026-10-28", "inputs": []}', encoding="utf-8")
    assert cli("check", "brief", "--result", "pass", *TODAY, cwd=ws).returncode == 0
    assert "Check a brief (Draft, not checked)" in notes()
    assert cli("tool", "status", "brief", "working", *TODAY, cwd=ws).returncode == 0
    assert "Check a brief (Working)" in notes()
    assert cli("tool", "improve", "brief", "--change", "Shorter.", "--reason", "Edits.", *TODAY, cwd=ws).returncode == 0
    assert "Shorter." in page()
    assert cli("tool", "status", "brief", "paused", *TODAY, cwd=ws).returncode == 0
    assert "Check a brief (Paused)" in notes()
    r = cli("tool", "status", "brief", "needs-update", *TODAY, cwd=ws)
    assert r.returncode == 1 and r.stderr.strip() == "That status is worked out from checks and cannot be set by hand."
    assert cli("tool", "retire", "brief", *TODAY, cwd=ws).returncode == 0
    assert "Check a brief" not in notes().split("tool-index:start")[1] and "bring back Check a brief" in page()
    r = cli("tool", "restore", "brief", *TODAY, cwd=ws)
    assert r.returncode == 0 and "Check a brief (Working)" in notes()


def test_old_backup_guide_is_removed_only_when_the_kit_wrote_it(ws, write_tool, cli):
    write_tool(ws, id="a", name="Answer a question")
    guide = ws / "RUNBOOK.md"
    guide.write_text("# How to run Sam's Assistant's tools when they are away\n\nold\n", encoding="utf-8")
    assert cli("tool", "retire", "a", *TODAY, cwd=ws).returncode == 0
    assert not guide.exists()
    guide.write_text("# My own notes\n", encoding="utf-8")
    cli("tool", "restore", "a", *TODAY, cwd=ws)
    assert guide.read_text(encoding="utf-8") == "# My own notes\n"
    assert cli("runbook", *TODAY, cwd=ws).returncode != 0


def test_launcher_cli_preview_and_yes(ws, tmp_path, cli):
    args = ("--bin-dir", str(tmp_path / "b"), "--apps-dir", str(tmp_path / "a"), "--desktop-dir", str(tmp_path / "d"))
    r = cli("launcher", *args, cwd=ws)
    assert r.returncode == 0 and "Nothing has been written yet." in r.stdout
    assert not (tmp_path / "b").exists()
    r = cli("launcher", "--yes", *args, cwd=ws)
    assert r.returncode == 0 and (tmp_path / "b/job-assistant").is_file()


ROLE_MD = "# A\n<!-- role:start -->\nx\n<!-- role:end -->\n<!-- tool-index:start -->\n<!-- tool-index:end -->\n"


def test_inbox_files_removed_after_use(ws, cli):
    (ws / "CLAUDE.md").write_text(ROLE_MD, encoding="utf-8")
    (ws / "inbox").mkdir(exist_ok=True)
    rec = ws / "inbox/setup-brief.yaml"
    rec.write_text(yaml.safe_dump({"id": "brief", "name": "Check a brief", "does": "Lists gaps.",
                                   "examples": ["check this brief"], "kind": "built", "status": "draft-not-checked",
                                   "rhythm": "on-demand", "data_path": "Files you drop in"}), encoding="utf-8")
    assert cli("tool", "add", "--from", str(rec), *TODAY, cwd=ws).returncode == 0
    assert not rec.exists()
    role_file = ws / "inbox/role.md"
    role_file.write_text("A short role.\n", encoding="utf-8")
    assert cli("role", "set", "--file", "inbox/role.md", cwd=ws).returncode == 0
    assert not role_file.exists()


def test_files_outside_inbox_kept(ws, tmp_path, cli):
    (ws / "CLAUDE.md").write_text(ROLE_MD, encoding="utf-8")
    role_file = tmp_path / "role.md"
    role_file.write_text("A short role.\n", encoding="utf-8")
    assert cli("role", "set", "--file", str(role_file), cwd=ws).returncode == 0
    assert role_file.exists()
    (ws / "inbox").mkdir(exist_ok=True)
    bad = ws / "inbox/bad.yaml"
    bad.write_text("id: [", encoding="utf-8")
    assert cli("tool", "add", "--from", str(bad), cwd=ws).returncode == 1
    assert bad.exists()


def test_env_reports_programs(ws, cli, monkeypatch):
    import shutil
    real = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "uv" else real(name) or "/x/" + name)
    r = cli("env", cwd=ws)
    assert r.returncode == 0
    assert "git: installed" in r.stdout and "uv: not installed" in r.stdout
    data = json.loads(cli("env", "--json", cwd=ws).stdout)
    assert data["uv"] is False and data["claude"] is True


@pytest.mark.parametrize("env, route", [
    ({}, None),
    ({"CLAUDE_CODE_USE_VERTEX": "1"}, "Google Vertex AI"),
    ({"CLAUDE_CODE_USE_BEDROCK": "true"}, "Amazon Bedrock"),
    ({"CLAUDE_CODE_USE_VERTEX": "0"}, None),
    ({"ANTHROPIC_API_KEY": "x"}, "an API key"),
])
def test_env_reports_whether_connectors_can_appear(ws, cli, monkeypatch, env, route):
    for name in ("CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_FOUNDRY",
                 "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    out = cli("env", cwd=ws).stdout
    data = json.loads(cli("env", "--json", cwd=ws).stdout)
    assert data["sign_in_route"] == route and data["claude_ai_connectors"] is (route is None)
    if route:
        assert f"not available. Claude signs in through {route}" in out
    else:
        assert "claude.ai connectors: available" in out


@pytest.mark.parametrize("entry, where, words", [
    ("claude-desktop", "desktop", "the Claude desktop app"),
    ("cli", "terminal", "Claude Code in a terminal"),
    ("claude-vscode", "other", "another Claude Code app"),
    ("", "other", "another Claude Code app"),
])
def test_env_reports_where_claude_runs(ws, cli, monkeypatch, entry, where, words):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", entry)
    assert json.loads(cli("env", "--json", cwd=ws).stdout)["running_in"] == where
    assert f"Running in: {words}." in cli("env", cwd=ws).stdout


def test_file_errors_are_plain(ws, write_tool, cli, monkeypatch):
    from ja import registry
    write_tool(ws, id="t1")

    def refuse(*a, **k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(registry, "save", refuse)
    for args in (("tool", "improve", "t1", "--change", "x", "--reason", "y"), ("check", "t1", "--result", "fail"),
                 ("tool", "status", "t1", "paused")):
        r = cli(*args, *TODAY, cwd=ws)
        assert r.returncode == 1, args
        assert r.stderr.strip() == "I could not finish this: you do not have permission to save there.", args
        assert "Traceback" not in r.text


def test_source_messages_use_names(ws, cli):
    cli("sources", "add", "--id", "faq", "--name", "OLM FAQ", "--kind", "living", "--where", "Drive",
        "--access", "file", "--exported", "2026-10-20", *TODAY, cwd=ws)
    r = cli("sources", "exported", "faq", "2026-10-27", *TODAY, cwd=ws)
    assert r.stdout.strip() == "Saved: your copy of OLM FAQ is from 2026-10-27."
    r = cli("sources", "list", *TODAY, cwd=ws)
    assert r.stdout.startswith("OLM FAQ: a copy you drop in.") and "(faq)" not in r.stdout
