"""Learned rules: staging, use, and keeping tool records in step."""

import json

import yaml

from ja import profile, registry, workspace

T = "2026-10-29"


def rules_file(ws):
    return yaml.safe_load((ws / "assistant/profile.yaml").read_text(encoding="utf-8"))["rules"]


def tool_rules(ws, tool_id, folder=".claude/skills"):
    return yaml.safe_load((ws / folder / tool_id / "tool.yaml").read_text(encoding="utf-8")).get("rules") or []


def run(cli, ws, *args):
    return cli("--workspace", str(ws), "--today", T, "rules", *args)


def add(cli, ws, rule_id, text, scope="match", *extra):
    return run(cli, ws, "add", "--id", rule_id, "--text", text, "--reason", "You asked on Oct 29", "--scope", scope,
               *extra)


def test_old_rules_without_state_are_active(ws):
    (ws / "assistant/profile.yaml").write_text(
        "rules:\n- id: short\n  text: Keep replies short.\n  reason: Edits.\n  scope: [a]\n  added: 2026-10-20\n",
        encoding="utf-8")
    rules, problems = profile.load(workspace.Paths(ws))
    assert problems == [] and rules[0].state == "active" and rules[0].held_reason is None


def test_bad_state_is_a_problem(ws):
    (ws / "assistant/profile.yaml").write_text(
        "rules:\n- id: x\n  text: T.\n  reason: R.\n  scope: everywhere\n  added: 2026-10-20\n  state: maybe\n",
        encoding="utf-8")
    assert profile.load(workspace.Paths(ws)) == ([], ["x: state must be pending, active, or held"])


def test_add_active_rule_lists_it_on_the_tool(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    r = add(cli, ws, "unmatched-first", "List unmatched rows first.")
    assert r.returncode == 0, r.text
    assert "Match the lists" in r.stdout
    assert rules_file(ws)[0] == {"id": "unmatched-first", "text": "List unmatched rows first.",
                                 "reason": "You asked on Oct 29", "scope": ["match"], "added": T,
                                 "state": "active", "held_reason": None}
    assert tool_rules(ws, "match") == ["unmatched-first"]
    assert "List unmatched rows first." in (ws / "dashboard/index.html").read_text(encoding="utf-8")


def test_add_refuses_bad_and_duplicate_ids_and_unknown_tools(ws, write_tool, cli):
    write_tool(ws, id="match")
    r = add(cli, ws, "Bad Id", "Text.")
    assert r.returncode == 1 and "lowercase letters" in r.stderr
    assert add(cli, ws, "one", "Text.").returncode == 0
    r = add(cli, ws, "one", "Other text.")
    assert r.returncode == 1 and "There is already a learned rule called one." in r.stderr
    r = add(cli, ws, "two", "Text.", "nothing-here")
    assert r.returncode == 1 and "There is no tool called nothing-here." in r.stderr


def test_pending_rule_is_not_used_until_confirmed(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    r = add(cli, ws, "unmatched-first", "List unmatched rows first.", "match", "--pending")
    assert r.returncode == 0 and "waiting for a check" in r.stdout
    assert rules_file(ws)[0]["state"] == "pending"
    assert tool_rules(ws, "match") == []
    r = run(cli, ws, "for", "match")
    assert r.returncode == 0 and "unmatched-first" not in r.stdout
    assert "No learned rules apply to Match the lists." in r.stdout
    r = run(cli, ws, "confirm", "unmatched-first")
    assert r.returncode == 0, r.text
    assert rules_file(ws)[0]["state"] == "active" and tool_rules(ws, "match") == ["unmatched-first"]
    assert run(cli, ws, "for", "match").stdout.strip() == "unmatched-first: List unmatched rows first."
    r = run(cli, ws, "confirm", "unmatched-first")
    assert r.returncode == 1 and "already in use" in r.stderr


def test_hold_keeps_the_rule_out_with_a_reason(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    add(cli, ws, "drop-blanks", "Leave out rows with blanks.", "match", "--pending")
    r = run(cli, ws, "hold", "drop-blanks", "--reason", "Example 1 would lose 6 rows")
    assert r.returncode == 0, r.text
    assert "Example 1 would lose 6 rows" in r.stdout
    saved = rules_file(ws)[0]
    assert saved["state"] == "held" and saved["held_reason"] == "Example 1 would lose 6 rows"
    assert tool_rules(ws, "match") == []
    assert "drop-blanks" not in run(cli, ws, "for", "match").stdout
    r = run(cli, ws, "hold", "drop-blanks", "--reason", "again")
    assert r.returncode == 1 and "already on hold" in r.stderr


def test_hold_refuses_an_active_rule(ws, write_tool, cli):
    write_tool(ws, id="match")
    add(cli, ws, "one", "Text.")
    r = run(cli, ws, "hold", "one", "--reason", "x")
    assert r.returncode == 1 and "Only a rule waiting for a check can be put on hold." in r.stderr


def test_rules_for_includes_everywhere_rules(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    write_tool(ws, id="brief", name="Check a brief")
    add(cli, ws, "mine", "Name both files.", "match")
    add(cli, ws, "theirs", "Use short sentences.", "brief")
    add(cli, ws, "all", "Say offering, never product.", "everywhere")
    r = run(cli, ws, "for", "match")
    assert r.stdout.splitlines() == ["mine: Name both files.", "all: Say offering, never product."]
    data = json.loads(run(cli, ws, "for", "match", "--json").stdout)
    assert [d["id"] for d in data] == ["mine", "all"] and data[0]["text"] == "Name both files."
    assert tool_rules(ws, "match") == ["mine"] and tool_rules(ws, "brief") == ["theirs"]
    r = run(cli, ws, "for", "nothing")
    assert r.returncode == 1 and "There is no tool called nothing." in r.stderr


def test_forget_removes_it_everywhere(ws, write_tool, cli):
    write_tool(ws, id="match", rules=["keep-me"])
    write_tool(ws, id="old", status="retired", folder="archive")
    add(cli, ws, "unmatched-first", "List unmatched rows first.")
    r = run(cli, ws, "forget", "unmatched-first")
    assert r.returncode == 0 and r.stdout.strip() == "I will stop applying this rule: List unmatched rows first."
    assert rules_file(ws) == [] and tool_rules(ws, "match") == ["keep-me"]
    r = run(cli, ws, "forget", "unmatched-first")
    assert r.returncode == 1 and "There is no learned rule called unmatched-first." in r.stderr


def test_forget_clears_archived_tools_too(ws, write_tool, cli):
    write_tool(ws, id="match")
    add(cli, ws, "one", "Name both files.")
    p = workspace.Paths(ws)
    tool = registry.find(p, "match")
    (ws / "archive").mkdir()
    (ws / ".claude/skills/match").rename(ws / "archive/match")
    run(cli, ws, "forget", "one")
    assert tool_rules(ws, "match", "archive") == [] and tool.rules == ["one"]


def test_promote_makes_a_waiting_copy_and_keeps_the_original(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    write_tool(ws, id="brief", name="Check a brief")
    add(cli, ws, "name-files", "Name both files.")
    r = run(cli, ws, "promote", "name-files")
    assert r.returncode == 0, r.text
    assert "name-files-everywhere" in r.stdout and "Match the lists" in r.stdout
    original, copy = rules_file(ws)
    assert original["id"] == "name-files" and original["scope"] == ["match"] and original["state"] == "active"
    assert copy["id"] == "name-files-everywhere" and copy["scope"] == "everywhere" and copy["state"] == "pending"
    assert copy["replaces"] == "name-files" and copy["text"] == "Name both files."
    assert tool_rules(ws, "match") == ["name-files"]
    assert run(cli, ws, "for", "match").stdout.strip() == "name-files: Name both files."
    assert "name-files" not in run(cli, ws, "for", "brief").stdout
    r = run(cli, ws, "promote", "name-files")
    assert r.returncode == 1 and "already waiting for a check on every tool" in r.stderr
    r = run(cli, ws, "confirm", "name-files-everywhere")
    assert r.returncode == 0, r.text
    assert "every tool" in r.stdout
    (only,) = rules_file(ws)
    assert only["id"] == "name-files-everywhere" and only["state"] == "active" and only["scope"] == "everywhere"
    assert "replaces" not in only
    assert tool_rules(ws, "match") == []
    assert run(cli, ws, "for", "match").stdout.strip() == "name-files-everywhere: Name both files."
    assert "name-files" in run(cli, ws, "for", "brief").stdout
    r = run(cli, ws, "promote", "name-files-everywhere")
    assert r.returncode == 1 and "already used everywhere" in r.stderr


def test_promotion_held_removes_the_copy(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    write_tool(ws, id="brief", name="Check a brief")
    add(cli, ws, "name-files", "Name both files.")
    run(cli, ws, "promote", "name-files")
    r = run(cli, ws, "hold", "name-files-everywhere", "--reason", "Check a brief example 1 would get worse")
    assert r.returncode == 0 and "Match the lists" in r.stdout
    (saved,) = rules_file(ws)
    assert saved["id"] == "name-files" and saved["scope"] == ["match"] and saved["state"] == "active"
    assert saved["held_reason"] == "Check a brief example 1 would get worse"
    assert tool_rules(ws, "match") == ["name-files"]
    assert "name-files" in run(cli, ws, "for", "match").stdout
    assert "name-files" not in run(cli, ws, "for", "brief").stdout


def test_promotion_without_its_original(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    add(cli, ws, "name-files", "Name both files.")
    run(cli, ws, "promote", "name-files")
    run(cli, ws, "forget", "name-files")
    r = run(cli, ws, "hold", "name-files-everywhere", "--reason", "An example would get worse")
    assert r.returncode == 0, r.text
    (saved,) = rules_file(ws)
    assert saved["id"] == "name-files-everywhere" and saved["state"] == "held"


def test_confirm_takes_only_waiting_rules(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    add(cli, ws, "drop-blanks", "Leave out rows with blanks.", "match", "--pending")
    run(cli, ws, "hold", "drop-blanks", "--reason", "Example 1 would lose 6 rows")
    r = run(cli, ws, "confirm", "drop-blanks")
    assert r.returncode == 1 and "Only a rule waiting for a check can be put in use." in r.stderr
    assert rules_file(ws)[0]["state"] == "held"


def test_old_promotion_still_goes_back_on_hold(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    (ws / "assistant/profile.yaml").write_text(yaml.safe_dump({"rules": [
        {"id": "name-files", "text": "Name both files.", "reason": "r", "scope": "everywhere", "added": T,
         "state": "pending", "held_reason": None, "scope_before": ["match"]}]}), encoding="utf-8")
    r = run(cli, ws, "hold", "name-files", "--reason", "worse")
    assert r.returncode == 0, r.text
    saved = rules_file(ws)[0]
    assert saved["scope"] == ["match"] and saved["state"] == "active"


def test_promote_refuses_a_pending_rule(ws, write_tool, cli):
    write_tool(ws, id="match")
    add(cli, ws, "one", "Text.", "match", "--pending")
    r = run(cli, ws, "promote", "one")
    assert r.returncode == 1 and "Check it on its own tool first." in r.stderr


def test_list_groups_by_state(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    add(cli, ws, "a", "Name both files.")
    add(cli, ws, "b", "Count blanks.", "match", "--pending")
    add(cli, ws, "c", "Drop blanks.", "match", "--pending")
    run(cli, ws, "hold", "c", "--reason", "Example 1 would lose rows")
    r = run(cli, ws, "list")
    assert r.returncode == 0
    assert r.stdout.index("Active:") < r.stdout.index("Waiting for a check:") < r.stdout.index("On hold:")
    assert "  a: Name both files. (Match the lists)" in r.stdout
    assert "  c: Drop blanks. (Match the lists) Why: Example 1 would lose rows" in r.stdout
    data = json.loads(run(cli, ws, "list", "--json").stdout)
    assert [r["id"] for r in data["active"]] == ["a"] and [r["id"] for r in data["pending"]] == ["b"]
    assert [r["id"] for r in data["held"]] == ["c"]


def test_list_when_empty(ws, cli):
    assert run(cli, ws, "list").stdout.strip() == "No learned rules yet."


def test_similar_ranks_active_rules(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    write_tool(ws, id="brief", name="Check a brief")
    add(cli, ws, "a", "Name both export files in the sources line.", "match")
    add(cli, ws, "b", "Use short sentences.", "brief")
    add(cli, ws, "c", "Name the export files.", "brief", "--pending")
    r = run(cli, ws, "similar", "Always name the export files")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert lines[0].startswith("a (Match the lists): Name both export files in the sources line.")
    assert "Shared words: export, file, name." in lines[0]
    assert all(not line.startswith(("b ", "c ")) for line in lines)
    assert run(cli, ws, "similar", "unrelated words").stdout.strip() == "No similar rules yet."


def test_dashboard_shows_only_active_rules_as_used(ws, write_tool, cli):
    write_tool(ws, id="match", name="Match the lists")
    add(cli, ws, "a", "Name both files.")
    add(cli, ws, "b", "Count blanks.", "match", "--pending")
    add(cli, ws, "c", "Say offering.", "everywhere")
    html = (ws / "dashboard/index.html").read_text(encoding="utf-8")
    card = html.split(">My tools</h2>", 1)[1].split("</h2>", 1)[0]
    assert "Name both files." in card and "Say offering." in card and "Count blanks." not in card
    assert "Waiting for a check" in html
