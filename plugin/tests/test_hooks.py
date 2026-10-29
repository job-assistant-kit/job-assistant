"""The two hooks: silent, fast, and never a failure for the session or the tool call."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN = Path(__file__).parents[1]
SCRIPTS = PLUGIN / "scripts"
START = SCRIPTS / "hook_session_start.py"
RECORD = SCRIPTS / "hook_record_run.py"


def run_hook(script, payload, cwd, env=None):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    began = time.monotonic()
    done = subprocess.run([sys.executable, str(script)], input=text, capture_output=True, text=True, cwd=cwd,
                          env={**os.environ, **(env or {})}, timeout=30)
    return done, time.monotonic() - began


def start_input(cwd):
    return {"session_id": "abc", "transcript_path": "/tmp/t.jsonl", "cwd": str(cwd),
            "hook_event_name": "SessionStart", "source": "startup", "model": "claude-opus-5"}


def skill_input(cwd, skill):
    return {"session_id": "abc", "transcript_path": "/tmp/t.jsonl", "cwd": str(cwd), "permission_mode": "default",
            "hook_event_name": "PostToolUse", "tool_name": "Skill", "tool_input": {"skill": skill},
            "tool_response": {"success": True, "commandName": skill}, "tool_use_id": "toolu_1"}


def runs(ws):
    f = ws / "data/records/runs.jsonl"
    return [json.loads(line) for line in f.read_text().splitlines()] if f.exists() else []


def test_session_start_refreshes_the_page_and_notes(ws, write_tool):
    write_tool(ws, id="m", name="Monthly digest", rhythm="monthly")
    done, took = run_hook(START, start_input(ws), cwd=ws)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""
    assert took < 5
    assert (ws / "dashboard/index.html").is_file()
    saved = json.loads((ws / "data/upkeep.json").read_text())
    assert isinstance(saved["items"], list)
    assert "ja_path: " in (ws / "assistant/.job-assistant").read_text()


def test_session_start_from_a_subfolder(ws):
    (ws / "inbox").mkdir()
    done, _ = run_hook(START, start_input(ws / "inbox"), cwd=ws / "inbox")
    assert done.returncode == 0 and done.stdout == ""
    assert (ws / "data/upkeep.json").is_file()


def test_session_start_outside_an_assistant_folder(tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    done, _ = run_hook(START, start_input(other), cwd=other)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""
    assert list(other.iterdir()) == []


def test_session_start_ignores_the_workspace_setting_outside_the_folder(ws, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    done, _ = run_hook(START, start_input(other), cwd=other, env={"JA_WORKSPACE": str(ws)})
    assert done.returncode == 0 and not (ws / "data/upkeep.json").exists()


@pytest.mark.parametrize("payload", ["", "not json", "[1, 2]", '{"cwd": 5}', '{"cwd": "/no/such/folder"}'])
def test_session_start_bad_input_is_silent(ws, payload):
    done, _ = run_hook(START, payload, cwd=ws)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""


def test_session_start_survives_broken_files(ws, write_tool):
    write_tool(ws, id="m", name="Monthly digest")
    (ws / "assistant/sources.yaml").write_text("{{{ not a list")
    (ws / "data/records/runs.jsonl").write_text("garbage\n")
    (ws / "dashboard").mkdir()
    (ws / "dashboard/index.html").mkdir()  # cannot be replaced by a file
    done, _ = run_hook(START, start_input(ws), cwd=ws)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""


def test_record_run_for_a_workspace_tool(ws, write_tool):
    write_tool(ws, id="match-lists", name="Match the lists")
    done, took = run_hook(RECORD, skill_input(ws, "match-lists"), cwd=ws)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""
    assert took < 5
    assert [(r["tool"], r["event"]) for r in runs(ws)] == [("match-lists", "run")]


def test_record_run_from_a_subfolder_with_a_slash(ws, write_tool):
    write_tool(ws, id="match-lists", name="Match the lists")
    (ws / "inbox").mkdir()
    run_hook(RECORD, skill_input(ws / "inbox", "/match-lists"), cwd=ws / "inbox")
    assert len(runs(ws)) == 1


@pytest.mark.parametrize("skill", ["job-assistant:learn", "learn", "Match-Lists", "../x", "", None, 7])
def test_record_run_skips_what_is_not_a_tool(ws, write_tool, skill):
    write_tool(ws, id="match-lists", name="Match the lists")
    (ws / ".claude/skills/learn").mkdir()
    (ws / ".claude/skills/learn/SKILL.md").write_text("---\nname: learn\n---\n")
    done, _ = run_hook(RECORD, skill_input(ws, skill), cwd=ws)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""
    assert runs(ws) == []


def test_record_run_skips_other_tools_and_other_folders(ws, write_tool, tmp_path):
    write_tool(ws, id="match-lists", name="Match the lists")
    other = {**skill_input(ws, "match-lists"), "tool_name": "Bash"}
    run_hook(RECORD, other, cwd=ws)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    run_hook(RECORD, skill_input(elsewhere, "match-lists"), cwd=elsewhere)
    assert runs(ws) == [] and list(elsewhere.iterdir()) == []


@pytest.mark.parametrize("payload", ["", "{", "[]", '{"tool_name": "Skill", "tool_input": "x"}',
                                     '{"tool_name": "Skill", "tool_input": {"skill": "t1"}, "cwd": 3}'])
def test_record_run_bad_input_is_silent(ws, write_tool, payload):
    write_tool(ws, id="t1")
    done, _ = run_hook(RECORD, payload, cwd=ws)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""


def test_record_run_survives_an_unwritable_records_folder(ws, write_tool):
    write_tool(ws, id="t1")
    shutil.rmtree(ws / "data/records")
    (ws / "data/records").write_text("a file where the folder should be")
    done, _ = run_hook(RECORD, skill_input(ws, "t1"), cwd=ws)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""


def hook_commands():
    config = json.loads((PLUGIN / "hooks/hooks.json").read_text(encoding="utf-8"))
    return config, {event: [h for group in groups for h in group["hooks"]] for event, groups in config["hooks"].items()}


def test_hooks_file_shape():
    config, by_event = hook_commands()
    assert set(by_event) == {"SessionStart", "PostToolUse"}
    assert [g.get("matcher") for g in config["hooks"]["PostToolUse"]] == ["Skill"]
    names = {"SessionStart": "hook_session_start.py", "PostToolUse": "hook_record_run.py"}
    for event, hooks in by_event.items():
        assert len(hooks) == 1
        hook = hooks[0]
        assert hook["type"] == "command" and hook["timeout"] <= 5
        command = hook["command"]
        assert f'"${{CLAUDE_PLUGIN_ROOT}}/scripts/{names[event]}"' in command
        assert (SCRIPTS / names[event]).is_file()
        assert command.endswith(">/dev/null 2>&1 || true")


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_hook_commands_run_as_written(ws, write_tool):
    """Run each command line from the hooks file the way Claude Code does, through the shell."""
    write_tool(ws, id="t1")
    _, by_event = hook_commands()
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN), "CLAUDE_PROJECT_DIR": str(ws)}
    for event, payload in (("SessionStart", start_input(ws)), ("PostToolUse", skill_input(ws, "t1"))):
        command = by_event[event][0]["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN))
        done = subprocess.run(["sh", "-c", command], input=json.dumps(payload), capture_output=True, text=True,
                              cwd=ws, env=env, timeout=120)
        assert done.returncode == 0 and done.stdout == "" and done.stderr == "", event
    assert (ws / "data/upkeep.json").is_file() and len(runs(ws)) == 1
