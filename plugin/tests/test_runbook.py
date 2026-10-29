"""The backup person's guide (RUNBOOK.md)."""

from datetime import date

from ja import runbook, workspace

T = date(2026, 10, 28)


def test_runbook_content(ws, write_tool):
    (ws / "CLAUDE.md").write_text("# Sam's Assistant\n<!-- tool-index:start -->\n<!-- tool-index:end -->\n",
                                  encoding="utf-8")
    (ws / "assistant/sources.yaml").write_text(
        "- id: faq\n  name: OLM FAQ\n  kind: living\n  where: Shared drive, FAQ folder\n  access: connector\n",
        encoding="utf-8")
    write_tool(ws, id="brief", name="Check a brief", does="Lists gaps in a brief.",
               examples=["check this brief", "review this brief"], rhythm="weekly", sources=["faq"],
               data_path="The brief you drop in", manual_steps=["Export the brief as a PDF", "Drop it in the inbox"],
               last_check={"date": "2026-10-27", "result": "pass", "detail": ""})
    write_tool(ws, id="metrics", name="Metrics pipeline", kind="adopted", status="draft-not-checked",
               confidential=True, lives_at="A shared folder called Metrics",
               how_to_run="Open the sheet and click Refresh.", last_check=None)
    write_tool(ws, id="old", name="Old tool", status="retired")
    p = workspace.Paths(ws)
    out = runbook.write(p, today=T)
    assert out == ws / "RUNBOOK.md"
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# How to run Sam's Assistant's tools when they are away\n")
    for part in ("## Check a brief", "Lists gaps in a brief.", '"check this brief"', '"review this brief"',
                 "The brief you drop in", "1. Export the brief as a PDF", "2. Drop it in the inbox",
                 "OLM FAQ (Shared drive, FAQ folder)", "Runs weekly", "Passed on 2026-10-27", "Working",
                 "## Metrics pipeline", "A shared folder called Metrics", "Open the sheet and click Refresh.",
                 "Not checked yet", "Contains confidential data. Ask before sharing results."):
        assert part in text, part
    assert "Old tool" not in text
    brief = text.split("## Check a brief")[1].split("## ")[0]
    assert "confidential" not in brief


def test_runbook_empty(ws):
    text = runbook.render(workspace.Paths(ws), today=T)
    assert "No tools yet." in text
