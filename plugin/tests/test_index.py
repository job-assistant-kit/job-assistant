from datetime import date
from ja import index, workspace

def test_index_rewrites_block_only(ws, write_tool):
    (ws / "CLAUDE.md").write_text("Top\n<!-- tool-index:start -->\nold\n<!-- tool-index:end -->\nBottom\n")
    write_tool(ws, id="brief-check", name="Check a brief", does="Lists gaps.", examples=["check this brief"])
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    text = (ws / "CLAUDE.md").read_text()
    assert text.startswith("Top\n") and text.endswith("Bottom\n")
    assert '- Check a brief (Working): Lists gaps. Say: "check this brief".' in text
    assert "old" not in text

def test_index_excludes_retired(ws, write_tool):
    write_tool(ws, id="old", name="Retired slide builder", status="retired")
    write_tool(ws, id="a", name="Active tool")
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    block = (ws / "CLAUDE.md").read_text().split("tool-index:start")[1]
    assert "Retired slide builder" not in block and "Active tool" in block

def test_missing_markers(ws):
    (ws / "CLAUDE.md").write_text("no markers\n")
    import pytest
    with pytest.raises(index.MarkersMissing):
        index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))

def test_empty_index_message(ws):
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    assert "No tools yet." in (ws / "CLAUDE.md").read_text()


# Extra coverage beyond the plan contract.

def test_index_uses_effective_status(ws, write_tool):
    write_tool(ws, id="a", name="A", sources=["missing"])
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    assert "- A (Needs update):" in (ws / "CLAUDE.md").read_text()

def test_index_is_stable(ws, write_tool):
    write_tool(ws, id="a")
    p = workspace.Paths(ws)
    index.rewrite(p, today=date(2026, 10, 28))
    first = (ws / "CLAUDE.md").read_text()
    index.rewrite(p, today=date(2026, 10, 28))
    assert (ws / "CLAUDE.md").read_text() == first

def test_index_skips_invalid_and_keeps_one_line_each(ws, write_tool):
    write_tool(ws, id="a", name="A", does="Line one\nline two")
    write_tool(ws, id="bad", status="great")
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    block = (ws / "CLAUDE.md").read_text().split("tool-index:start -->\n")[1].split("<!--")[0]
    assert block == '- A (Working): Line one line two. Say: "do one".\n'

def test_end_before_start_is_missing(ws):
    (ws / "CLAUDE.md").write_text("<!-- tool-index:end -->\n<!-- tool-index:start -->\n")
    import pytest
    with pytest.raises(index.MarkersMissing):
        index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))

def test_index_marks_unchecked_working_tool_as_draft(ws, write_tool):
    write_tool(ws, id="a", name="A", last_check=None)
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    assert "- A (Draft, not checked):" in (ws / "CLAUDE.md").read_text()

def test_index_keeps_windows_line_endings(ws, write_tool):
    (ws / "CLAUDE.md").write_bytes(b"Top\r\n<!-- tool-index:start -->\r\nold\r\n<!-- tool-index:end -->\r\nBottom\r\n")
    write_tool(ws, id="a", name="A")
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    raw = (ws / "CLAUDE.md").read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n")
    assert b'- A (Working): Does one thing. Say: "do one".\r\n' in raw

def test_index_keeps_unix_line_endings(ws, write_tool):
    write_tool(ws, id="a")
    index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    assert b"\r" not in (ws / "CLAUDE.md").read_bytes()

def test_index_returns_problems(ws, write_tool):
    write_tool(ws, id="bad", status="great")
    problems = index.rewrite(workspace.Paths(ws), today=date(2026, 10, 28))
    assert problems == ["bad: status must be one of working, draft-not-checked, being-built, paused, retired"]


def test_marker_text_in_tool_cannot_break_notes(ws, write_tool):
    from ja import workspace
    write_tool(ws, id="evil", name="Evil <!-- tool-index:end --> name", does="Ends <!-- here -->.",
               examples=["say <!-- tool-index:start -->"])
    p = workspace.Paths(ws)
    index.rewrite(p, today=date(2026, 10, 28))
    first = (ws / "CLAUDE.md").read_text()
    assert first.count("<!--") == 2 and first.count("-->") == 2
    assert "Evil tool-index:end name" in first
    index.rewrite(p, today=date(2026, 10, 28))
    assert (ws / "CLAUDE.md").read_text() == first
