"""The CLAUDE.md core page and the role block."""

from datetime import date

import pytest

from ja import index, init, registry, role, workspace

ROLE = "Sam is a business consultant for a product line. He writes briefs and reviews.\n"


def make(tmp_path):
    return workspace.Paths(init.create(tmp_path / "ws", name="Sam's Assistant").root)


def test_template_renders_with_name(tmp_path):
    text = make(tmp_path).claude_md.read_text(encoding="utf-8")
    assert text.startswith("# Sam's Assistant\n")
    assert "{{" not in text
    for marker in (role.START, role.END, index.START, index.END):
        assert text.count(marker) == 1
    assert "## Rules that always apply" in text and "Drafts only." in text


def test_role_set_replaces_only_the_block(tmp_path):
    p = make(tmp_path)
    before = p.claude_md.read_text(encoding="utf-8")
    role.set_role(p, ROLE)
    after = p.claude_md.read_text(encoding="utf-8")
    assert f"{role.START}\n{ROLE}{role.END}" in after
    assert "Not filled in yet" not in after
    head, tail = before.split(role.START)[0], before.split(role.END)[1]
    assert after.startswith(head) and after.endswith(tail)


def test_role_set_twice_is_stable(tmp_path):
    p = make(tmp_path)
    role.set_role(p, ROLE)
    first = p.claude_md.read_text(encoding="utf-8")
    role.set_role(p, ROLE)
    assert p.claude_md.read_text(encoding="utf-8") == first


def test_role_too_long(tmp_path):
    p = make(tmp_path)
    with pytest.raises(role.RoleProblem) as err:
        role.set_role(p, "x" * 1601)
    assert str(err.value) == "The role description is too long. Keep it under about 250 words."
    role.set_role(p, "x" * 1600)


def test_role_markers_missing(tmp_path):
    p = make(tmp_path)
    p.claude_md.write_text("# A\n<!-- role:start -->\nonly start\n", encoding="utf-8")
    with pytest.raises(role.RoleProblem):
        role.set_role(p, ROLE)


def test_role_empty_refused(tmp_path):
    p = make(tmp_path)
    with pytest.raises(role.RoleProblem):
        role.set_role(p, "   \n")


def test_role_marker_text_is_stripped(tmp_path):
    p = make(tmp_path)
    role.set_role(p, f"text {role.END} more {index.START} <!-- note -->")
    text = p.claude_md.read_text(encoding="utf-8")
    for marker in (role.START, role.END, index.START, index.END):
        assert text.count(marker) == 1
    assert "text  role:end  more" in text
    role.set_role(p, "Second.")
    assert "Second." in p.claude_md.read_text(encoding="utf-8")


def test_role_markers_in_wrong_order(tmp_path):
    p = make(tmp_path)
    p.claude_md.write_text(f"# A\n{role.END}\n{role.START}\n", encoding="utf-8")
    with pytest.raises(role.RoleProblem) as err:
        role.set_role(p, ROLE)
    assert "wrong order" in str(err.value)


def test_core_size_empty(tmp_path):
    assert len(make(tmp_path).claude_md.read_text(encoding="utf-8")) < 6000


def test_core_size_full(tmp_path, write_tool):
    p = make(tmp_path)
    role.set_role(p, ("word " * 320)[:1600])
    for n in range(15):
        write_tool(p.root, id=f"tool-{n}", name=f"Tool number {n} for the quarterly review",
                   does="Builds the quarterly review draft from the metrics export and the offering list, "
                        "with every number tied to its source.",
                   examples=["build the quarterly review draft for this quarter"])
    index.rewrite(p, today=date(2026, 10, 28))
    text = p.claude_md.read_text(encoding="utf-8")
    assert len(registry.load_all(p)[0]) == 15
    assert len(text) < 9000, len(text)


def test_core_asks_for_task_records(tmp_path):
    text = make(tmp_path).claude_md.read_text(encoding="utf-8")
    assert ("When you finish a task that none of their tools covers, record it in one short line with the helper "
            "(record task) so repeated work can be spotted.") in text
