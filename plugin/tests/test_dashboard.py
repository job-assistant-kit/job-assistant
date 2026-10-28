from datetime import date
from ja import dashboard, workspace, records

def test_dashboard_renders_tools_and_labels(ws, write_tool):
    write_tool(ws, id="a", name="Answer a question", status="working", your_minutes_by_hand=30)
    write_tool(ws, id="b", name="TTM review", status="draft-not-checked")
    p = workspace.Paths(ws)
    for i in range(4): records.add_run(p, "a", "run", ts=f"2026-10-0{i+1}T09:00:00")
    html = dashboard.render(p, today=date(2026, 10, 28))
    assert "Answer a question" in html and "TTM review" in html
    assert "Draft, not checked" in html
    assert "2.0 hrs" in html and "your estimate, not measured" in html

def test_dashboard_escapes_content(ws, write_tool):
    write_tool(ws, id="x", name="<script>alert(1)</script>")
    html = dashboard.render(workspace.Paths(ws), today=date(2026, 10, 28))
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html

def test_dashboard_no_em_dash(ws, write_tool):
    write_tool(ws, id="a")
    assert "\u2014" not in dashboard.render(workspace.Paths(ws), today=date(2026, 10, 28))

def test_dashboard_hides_estimate_without_data(ws, write_tool):
    write_tool(ws, id="a")
    assert "your estimate" not in dashboard.render(workspace.Paths(ws), today=date(2026, 10, 28))

def test_dashboard_writes_file(ws, write_tool):
    write_tool(ws, id="a")
    out = dashboard.write(workspace.Paths(ws), today=date(2026, 10, 28))
    assert out.exists() and out.name == "index.html"


# Extra coverage beyond the plan contract.

import re

T = date(2026, 10, 28)

def section(html, heading):
    """Text of the section that starts with the given h2 heading, up to the next h2."""
    start = html.index(f">{heading}</h2>")
    nxt = html.find("<h2", start)
    return html[start: nxt if nxt != -1 else len(html)]

def test_only_this_quarter_counts(ws, write_tool):
    write_tool(ws, id="a", your_minutes_by_hand=60)
    p = workspace.Paths(ws)
    records.add_run(p, "a", "run", ts="2026-09-30T09:00:00")
    records.add_run(p, "a", "run", ts="2026-10-02T09:00:00")
    html = dashboard.render(p, today=T)
    assert "1.0 hrs" in html
    assert re.search(r"<b>1</b><span>times used this quarter</span>", html)
    assert "Used 2 times" in html

def test_needs_your_ok_lists_reasons_and_words(ws, write_tool):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Drive\n  access: file\n  exported: 2026-10-10\n")
    write_tool(ws, id="a", name="Answer a question", sources=["faq"])
    write_tool(ws, id="b", name="TTM review", status="draft-not-checked")
    write_tool(ws, id="c", name="Fine tool")
    html = dashboard.render(workspace.Paths(ws), today=T)
    ok = section(html, "Needs your OK")
    assert "Your copy of OLM FAQ is 18 days old" in ok
    assert "update Answer a question" in ok and "check TTM review" in ok
    assert "Fine tool" not in ok
    assert re.search(r"<b>2</b><span>needs your OK</span>", html)
    assert re.search(r"<b>1</b><span>tools working</span>", html)

def test_no_needs_section_when_all_working(ws, write_tool):
    write_tool(ws, id="a")
    assert ">Needs your OK</h2>" not in dashboard.render(workspace.Paths(ws), today=T)

def test_card_details(ws, write_tool):
    (ws / "assistant/profile.yaml").write_text(
        "rules:\n- id: short\n  text: Replies are 3 sentences or less.\n  reason: From 3 of your edits.\n"
        "  scope: [a]\n  added: 2026-10-20\n")
    write_tool(ws, id="a", name="Answer a question", examples=["answer this", "reply to this"],
               manual_steps=["Open the FAQ", "Save it to the inbox"], rules=["short"],
               last_check={"date": "2026-10-27", "result": "pass", "detail": ""},
               improvements=[{"date": "2026-10-20", "change": "Shorter replies.", "reason": "Learned from 3 of your edits."}])
    p = workspace.Paths(ws)
    records.add_run(p, "a", "run", ts="2026-10-28T09:00:00")
    card = section(dashboard.render(p, today=T), "My tools")
    for text in ["answer this", "Used 1 time", "Last used today", "Last check passed Oct 27",
                 "Files you drop in", "You do:", "Open the FAQ", "Replies are 3 sentences or less.",
                 "Improvements (1)", "Shorter replies.", "<details"]:
        assert text in card, text
    assert "reply to this" not in card

def test_learned_rules_section(ws, write_tool):
    (ws / "assistant/profile.yaml").write_text(
        "rules:\n- id: offering\n  text: Say offering, never product.\n  reason: You said so on Oct 12.\n"
        "  scope: everywhere\n  added: 2026-10-12\n"
        "- id: short\n  text: Short replies.\n  reason: From edits.\n  scope: [a]\n  added: 2026-10-20\n")
    write_tool(ws, id="a", name="Answer a question")
    learned = section(dashboard.render(workspace.Paths(ws), today=T), "What I have learned about how you work")
    assert "Say offering, never product." in learned and "You said so on Oct 12." in learned
    assert "Used everywhere" in learned and "Used by Answer a question" in learned

def test_ideas_shown_and_hidden(ws, write_tool):
    write_tool(ws, id="a")
    p = workspace.Paths(ws)
    assert ">Ideas</h2>" not in dashboard.render(p, today=T)
    html = dashboard.render(p, today=T, ideas=["Automate the agenda."])
    assert "Automate the agenda." in section(html, "Ideas")

def test_retired_section(ws, write_tool):
    write_tool(ws, id="old", name="Old slide builder", status="retired", folder="archive")
    write_tool(ws, id="a")
    html = dashboard.render(workspace.Paths(ws), today=T)
    assert "Old slide builder" in section(html, "Retired")
    assert "Old slide builder" not in section(html, "My tools")

def test_tools_with_problems_listed(ws, write_tool):
    write_tool(ws, id="bad", status="great")
    html = dashboard.render(workspace.Paths(ws), today=T)
    assert "bad: status must be one of" in section(html, "Tools with problems")

def test_no_javascript(ws, write_tool):
    write_tool(ws, id="a")
    assert "<script" not in dashboard.render(workspace.Paths(ws), today=T).lower()

def test_empty_workspace(ws):
    html = dashboard.render(workspace.Paths(ws), today=T)
    assert "No tools yet." in html
    assert re.search(r"<b>0</b><span>tools working</span>", html)

def test_pill_classes(ws, write_tool):
    write_tool(ws, id="a", name="A", status="being-built")
    write_tool(ws, id="b", name="B", status="paused")
    html = dashboard.render(workspace.Paths(ws), today=T)
    assert 'class="pill build">Being built' in html and 'class="pill off">Paused' in html

def test_draft_with_passed_check_waits_for_ok(ws, write_tool):
    write_tool(ws, id="b", name="TTM review", status="draft-not-checked",
               last_check={"date": "2026-10-27", "result": "pass", "detail": ""})
    html = dashboard.render(workspace.Paths(ws), today=T)
    assert "Last check passed Oct 27. Waiting for your OK on the method." in section(html, "My tools")
    assert "Waiting for your OK on the method." in section(html, "Needs your OK")
    assert "Not checked yet" not in html

def test_unchecked_working_tool_shows_draft(ws, write_tool):
    write_tool(ws, id="a", name="New tool", last_check=None)
    html = dashboard.render(workspace.Paths(ws), today=T)
    card = section(html, "My tools")
    assert 'class="pill warn">Draft, not checked' in card and "Not checked yet" in card
    assert "check New tool" in section(html, "Needs your OK")

def test_rhythm_in_plain_words(ws, write_tool):
    write_tool(ws, id="a", name="A", rhythm="quarterly")
    write_tool(ws, id="b", name="B", rhythm="on-demand")
    card = section(dashboard.render(workspace.Paths(ws), today=T), "My tools")
    assert "Runs quarterly" in card and "When you need it" in card

def test_source_problems_listed_separately(ws, write_tool):
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: soft\n  where: x\n  access: file\n")
    write_tool(ws, id="bad", status="great")
    html = dashboard.render(workspace.Paths(ws), today=T)
    assert "faq: kind must be living or fixed" in section(html, "Sources with problems")
    assert "faq:" not in section(html, "Tools with problems")
    assert "bad: status" not in section(html, "Sources with problems")

def test_quarter_has_upper_bound(ws, write_tool):
    write_tool(ws, id="a", your_minutes_by_hand=60)
    p = workspace.Paths(ws)
    records.add_run(p, "a", "run", ts="2026-10-02T09:00:00")
    records.add_run(p, "a", "run", ts="2027-01-05T09:00:00")
    html = dashboard.render(p, today=T)
    assert re.search(r"<b>1</b><span>times used this quarter</span>", html)
    assert "1.0 hrs" in html


def test_changed_since_check_shown(ws, write_tool):
    write_tool(ws, id="a", name="Answer a question", status="working",
               last_check={"date": "2026-10-02", "result": "pass", "detail": ""},
               improvements=[{"date": "2026-10-20", "change": "Shorter", "reason": "Asked"}])
    html = dashboard.render(workspace.Paths(ws), today=date(2026, 10, 28))
    assert "Changed since its last check." in html and "Draft, not checked" in html
    assert "Waiting for your OK" not in html
