"""Upkeep: what needs the person's attention, worked out from records only."""

import json
import os
from datetime import date, datetime

from ja import dashboard, records, upkeep, workspace


def kinds(items):
    return [i.kind for i in items]


def run_on(p, tool, day, event="run"):
    records.add_run(p, tool, event, ts=f"{day}T09:00:00")


def old_file(path, day):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    stamp = datetime.fromisoformat(f"{day}T12:00:00").timestamp()
    os.utime(path, (stamp, stamp))


def test_quarterly_due_two_weeks_before_quarter_end(ws, write_tool):
    write_tool(ws, id="qor", name="Quarterly review", rhythm="quarterly", examples=["run the quarterly review"])
    p = workspace.Paths(ws)
    found = upkeep.items(p, date(2026, 12, 20))
    assert kinds(found) == ["due"]
    assert found[0].say == "run the quarterly review"
    assert "Dec 31" in found[0].text and "not run this quarter" in found[0].text
    assert upkeep.items(p, date(2026, 12, 10)) == []
    run_on(p, "qor", "2026-10-05")
    assert upkeep.items(p, date(2026, 12, 20)) == []


def test_monthly_due_five_days_before_month_end(ws, write_tool):
    write_tool(ws, id="m", name="Monthly digest", rhythm="monthly")
    p = workspace.Paths(ws)
    assert kinds(upkeep.items(p, date(2026, 10, 27))) == ["due"]
    assert upkeep.items(p, date(2026, 10, 20)) == []
    run_on(p, "m", "2026-10-02")
    assert upkeep.items(p, date(2026, 10, 27)) == []


def test_weekly_due_after_six_days(ws, write_tool):
    write_tool(ws, id="w", name="Weekly notes", rhythm="weekly", created="2026-10-01")
    p = workspace.Paths(ws)
    run_on(p, "w", "2026-10-20")
    assert kinds(upkeep.items(p, date(2026, 10, 26))) == ["due"]
    assert upkeep.items(p, date(2026, 10, 25)) == []


def test_weekly_never_run_counts_from_creation(ws, write_tool):
    write_tool(ws, id="w", name="Weekly notes", rhythm="weekly", created="2026-10-26")
    p = workspace.Paths(ws)
    assert upkeep.items(p, date(2026, 10, 28)) == []
    assert kinds(upkeep.items(p, date(2026, 11, 2))) == ["due"]


def test_on_demand_unused_for_90_days_offers_retiring(ws, write_tool):
    write_tool(ws, id="a", name="Old helper", created="2026-01-01")
    p = workspace.Paths(ws)
    run_on(p, "a", "2026-07-01")
    found = upkeep.items(p, date(2026, 9, 29))
    assert kinds(found) == ["retire"] and found[0].say == "retire Old helper"
    assert upkeep.items(p, date(2026, 9, 28)) == []


def test_never_unused_warnings_for_rhythm_or_inherited_tools(ws, write_tool):
    write_tool(ws, id="q", name="Quarterly", rhythm="quarterly", created="2025-01-01")
    write_tool(ws, id="ad", name="Inherited", kind="adopted", created="2025-01-01")
    p = workspace.Paths(ws)
    run_on(p, "q", "2026-07-02")
    assert "retire" not in kinds(upkeep.items(p, date(2026, 8, 1)))


def test_held_tools_are_left_alone(ws, write_tool):
    write_tool(ws, id="p", name="Paused one", status="paused", rhythm="weekly", created="2025-01-01")
    write_tool(ws, id="b", name="Building", status="being-built", created="2025-01-01")
    assert upkeep.items(workspace.Paths(ws), date(2026, 10, 28)) == []


def test_failed_checks_and_stale_sources(ws, write_tool):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Drive\n  access: file\n  exported: 2026-10-10\n")
    write_tool(ws, id="a", name="Answer a question", sources=["faq"])
    write_tool(ws, id="b", name="Brief check", last_check={"date": "2026-10-20", "result": "fail", "detail": "Missing a column"})
    found = upkeep.items(workspace.Paths(ws), date(2026, 10, 28))
    assert kinds(found) == ["update", "update"]
    texts = " ".join(i.text for i in found)
    assert "Your copy of OLM FAQ is 18 days old" in texts and "Last check failed: Missing a column" in texts
    assert {i.say for i in found} == {"update Answer a question", "update Brief check"}


def test_changed_source_and_broken_sources_list(ws, write_tool):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Drive\n  access: connector\n  changed: true\n"
        "- id: bad\n  name: Broken\n")
    write_tool(ws, id="a", name="Answer a question", sources=["faq"])
    found = upkeep.items(workspace.Paths(ws), date(2026, 10, 28))
    assert kinds(found) == ["update", "update"]
    assert "OLM FAQ changed since this tool was checked" in found[0].text
    assert "sources list" in found[1].text and found[1].tool is None


def test_unfinished_builds_are_listed(ws, cli):
    cli("--workspace", str(ws), "--today", "2026-10-25", "build", "start", "--id", "half-made")
    found = upkeep.items(workspace.Paths(ws), date(2026, 10, 28))
    assert kinds(found) == ["unfinished"]
    assert "Oct 25" in found[0].text and found[0].say == "finish half-made"


def test_repeated_hand_work_becomes_an_idea(ws):
    p = workspace.Paths(ws)
    for day, words in (("2026-10-05", "Wrote the partner update email"),
                       ("2026-10-12", "wrote partner update email for EMEA"),
                       ("2026-10-26", "partner update email again"),
                       ("2026-10-20", "Booked travel")):
        records.add_task(p, words, ts=f"{day}T10:00:00")
    found = upkeep.items(p, date(2026, 10, 28))
    assert kinds(found) == ["idea"]
    assert found[0].text == "You did 'partner update email again' 3 times in the last 30 days."
    assert found[0].say == "automate this"


def test_ideas_need_three_within_30_days(ws):
    p = workspace.Paths(ws)
    for day in ("2026-09-01", "2026-10-12", "2026-10-26"):
        records.add_task(p, "partner update email", ts=f"{day}T10:00:00")
    assert upkeep.items(p, date(2026, 10, 28)) == []


def test_old_inbox_files_and_clean(ws, cli):
    p = workspace.Paths(ws)
    old_file(ws / "inbox/old.csv", "2026-09-01")
    old_file(ws / "inbox/sub/older.pdf", "2026-08-01")
    old_file(ws / "inbox/new.csv", "2026-10-20")
    old_file(ws / "inbox/.keep", "2026-01-01")
    found = upkeep.items(p, date(2026, 10, 28))
    assert kinds(found) == ["inbox"]
    assert found[0].text.startswith("2 files in your inbox are more than 30 days old")
    assert found[0].say == "clean my inbox"
    listed = cli("--workspace", str(ws), "--today", "2026-10-28", "inbox", "clean")
    assert listed.returncode == 0 and "old.csv" in listed.stdout and "new.csv" not in listed.stdout
    assert (ws / "inbox/old.csv").exists()
    done = cli("--workspace", str(ws), "--today", "2026-10-28", "inbox", "clean", "--yes")
    assert done.returncode == 0 and "Deleted 2 files" in done.stdout
    assert not (ws / "inbox/old.csv").exists() and not (ws / "inbox/sub/older.pdf").exists()
    assert (ws / "inbox/new.csv").exists() and (ws / "inbox/.keep").exists()
    again = cli("--workspace", str(ws), "--today", "2026-10-28", "inbox", "clean", "--yes")
    assert "No files in your inbox are more than 30 days old" in again.stdout


def test_stable_tool_after_five_accepted_runs(ws, write_tool):
    write_tool(ws, id="a", name="Answer a question")
    p = workspace.Paths(ws)
    for i in range(4):
        run_on(p, "a", f"2026-10-1{i}", "accepted")
    assert upkeep.items(p, date(2026, 10, 28)) == []
    run_on(p, "a", "2026-10-20", "accepted")
    found = upkeep.items(p, date(2026, 10, 28))
    assert kinds(found) == ["stable"]
    assert found[0].text == ("Want me to make Answer a question more reliable by moving its counting "
                             "into a fixed step?")
    (ws / ".claude/skills/a/facts.py").write_text("print('{}')\n")
    assert upkeep.items(p, date(2026, 10, 28)) == []


def test_order_is_by_urgency(ws, write_tool, cli):
    p = workspace.Paths(ws)
    for day in ("2026-10-20", "2026-10-21", "2026-10-22"):
        records.add_task(p, "partner update email", ts=f"{day}T10:00:00")
    write_tool(ws, id="b", name="Brief check", last_check={"date": "2026-10-20", "result": "fail", "detail": ""})
    write_tool(ws, id="m", name="Monthly digest", rhythm="monthly")
    old_file(ws / "inbox/old.csv", "2026-09-01")
    cli("--workspace", str(ws), "--today", "2026-10-25", "build", "start", "--id", "half-made")
    assert kinds(upkeep.items(p, date(2026, 10, 28))) == ["due", "update", "unfinished", "inbox", "idea"]


def test_cli_text_json_and_write(ws, write_tool, cli):
    write_tool(ws, id="m", name="Monthly digest", rhythm="monthly", examples=["make the digest"])
    out = cli("--workspace", str(ws), "--today", "2026-10-28", "upkeep")
    assert out.returncode == 0
    assert out.stdout.strip().startswith("Monthly digest is due by Oct 31")
    assert out.stdout.strip().endswith('Say "make the digest".')
    js = json.loads(cli("--workspace", str(ws), "--today", "2026-10-28", "upkeep", "--json").stdout)
    assert js["items"][0]["kind"] == "due" and js["items"][0]["say"] == "make the digest"
    assert not (ws / "data/upkeep.json").exists()
    cli("--workspace", str(ws), "--today", "2026-10-28", "upkeep", "--write")
    saved = json.loads((ws / "data/upkeep.json").read_text())
    assert saved["date"] == "2026-10-28" and saved["items"][0]["tool"] == "m"


def test_cli_nothing_to_report(ws, cli):
    out = cli("--workspace", str(ws), "--today", "2026-10-28", "upkeep")
    assert out.stdout.strip() == "Nothing needs your attention right now."


def test_json_lists_live_sources_to_watch(ws, write_tool, cli):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Drive folder X\n  access: connector\n"
        "- id: memo\n  name: Memo\n  kind: fixed\n  where: Drive\n  access: connector\n")
    write_tool(ws, id="a", name="Answer a question", sources=["faq"],
               last_check={"date": "2026-10-20", "result": "pass", "detail": ""})
    write_tool(ws, id="b", name="Other", sources=["faq"], last_check={"date": "2026-10-10", "result": "pass", "detail": ""})
    js = json.loads(cli("--workspace", str(ws), "--today", "2026-10-28", "upkeep", "--json").stdout)
    assert js["watch"] == [{"id": "faq", "name": "OLM FAQ", "where": "Drive folder X",
                            "used_by": ["Answer a question", "Other"], "checked": "2026-10-10"}]


def test_sources_changed_and_checked(ws, write_tool, cli):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Drive\n  access: connector\n")
    write_tool(ws, id="a", name="Answer a question", sources=["faq"])
    out = cli("--workspace", str(ws), "--today", "2026-10-28", "sources", "changed", "faq")
    assert out.returncode == 0 and "OLM FAQ" in out.stdout
    assert kinds(upkeep.items(workspace.Paths(ws), date(2026, 10, 28))) == ["update"]
    out = cli("--workspace", str(ws), "--today", "2026-10-28", "sources", "checked", "faq")
    assert out.returncode == 0
    assert upkeep.items(workspace.Paths(ws), date(2026, 10, 28)) == []
    bad = cli("--workspace", str(ws), "sources", "changed", "nope")
    assert bad.returncode == 1 and "There is no source called nope." in bad.stderr


def test_dashboard_shows_upkeep_items(ws, write_tool):
    write_tool(ws, id="m", name="Monthly digest", rhythm="monthly", examples=["make the digest"])
    p = workspace.Paths(ws)
    for day in ("2026-10-20", "2026-10-21", "2026-10-22"):
        records.add_task(p, "partner update email", ts=f"{day}T10:00:00")
    html = dashboard.render(p, today=date(2026, 10, 28))
    ok = html.split(">Needs your OK</h2>", 1)[1].split("<h2", 1)[0]
    assert "Monthly digest is due by Oct 31" in ok and "make the digest" in ok
    ideas = html.split(">Ideas</h2>", 1)[1].split("<h2", 1)[0]
    assert "partner update email" in ideas and "automate this" in ideas
    assert "<b>1</b><span>needs your OK</span>" in html


def test_source_with_no_copy_yet_is_a_gentle_reminder(ws, write_tool):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Drive\n  access: file\n"
        "- id: unused\n  name: Old Guide\n  kind: living\n  where: Drive\n  access: file\n")
    write_tool(ws, id="a", name="Answer a question", sources=["faq"])
    found = upkeep.items(workspace.Paths(ws), date(2026, 10, 28))
    assert kinds(found) == ["nocopy"]
    assert found[0].line == "I do not have a copy of OLM FAQ yet. Drop one in the inbox when you next use it."
    html = dashboard.render(workspace.Paths(ws), today=date(2026, 10, 28))
    assert "I do not have a copy of OLM FAQ yet." in html and "Old Guide" not in html.split("Ideas")[-1]
