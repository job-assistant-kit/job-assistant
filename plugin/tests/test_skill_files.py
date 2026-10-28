"""Checks on the instruction pages shipped with the assistant."""

import re
from pathlib import Path

import yaml

PLUGIN = Path(__file__).parents[1]
SKILLS = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
SKIP_DIRS = {".venv", ".pytest_cache", "__pycache__"}
TEXT_SUFFIXES = {".md", ".py", ".j2", ".json", ".yaml", ".yml", ".toml", ".txt", ".html", ""}
BANNED = ("skill", "plugin", "script", "repo", "mcp", "yaml", "json", "terminal", "command")


def plugin_text_files():
    for path in PLUGIN.rglob("*"):
        if path.is_file() and not SKIP_DIRS.intersection(path.relative_to(PLUGIN).parts) \
                and path.suffix in TEXT_SUFFIXES and path.name != "uv.lock":
            yield path


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return yaml.safe_load(text.split("---\n", 2)[1]), text.split("---\n", 2)[2]


def prose(text):
    """Text with frontmatter, fenced blocks, and code spans removed."""
    if text.startswith("---\n"):
        text = text.split("---\n", 2)[2]
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def test_there_are_skills():
    assert [p.parent.name for p in SKILLS] == ["set-me-up"]


def test_frontmatter_valid():
    for path in SKILLS:
        front, body = frontmatter(path)
        assert front["name"] == path.parent.name
        assert isinstance(front["description"], str) and front["description"].strip()
        assert len(front["description"]) < 1024, path
        assert body.strip()


def test_set_me_up_triggers():
    front, _ = frontmatter(PLUGIN / "skills/set-me-up/SKILL.md")
    for phrase in ("set me up", "get started", "here is my job description", "set up my assistant"):
        assert phrase in front["description"]


def test_helper_path_resolves():
    for path in SKILLS:
        text = path.read_text(encoding="utf-8")
        for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([^\"\s`)]+)", text):
            assert (path.parent / rel).resolve().is_file(), rel
        for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"\s`)]+)", text):
            assert (PLUGIN / rel).resolve().exists(), rel


def test_no_em_dashes_anywhere():
    bad = [str(p) for p in plugin_text_files() if "\u2014" in p.read_text(encoding="utf-8", errors="replace")]
    assert bad == []


def test_no_double_hyphen_punctuation_in_prose():
    bad = []
    for p in plugin_text_files():
        if p.suffix in (".md", ".j2") and re.search(r"\s--\s", prose(p.read_text(encoding="utf-8"))):
            bad.append(str(p))
    assert bad == []


def test_quoted_phrases_use_plain_words():
    pages = [*SKILLS, *(PLUGIN / "skills").glob("*/*.md"), PLUGIN / "templates/adopted-skill.md",
             PLUGIN / "templates/workspace/CLAUDE.md"]
    bad = []
    for page in set(pages):
        for phrase in re.findall(r'"([^"\n]+)"', prose(page.read_text(encoding="utf-8"))):
            words = re.findall(r"[a-z]+", phrase.lower())
            hits = [w for w in BANNED if w in words]
            if hits:
                bad.append(f"{page.name}: {phrase}")
    assert bad == []


def test_banned_word_check_catches_problems():
    phrase = "Run the script from the terminal"
    assert [w for w in BANNED if w in re.findall(r"[a-z]+", phrase.lower())] == ["script", "terminal"]


def test_set_me_up_flow():
    text = (PLUGIN / "skills/set-me-up/SKILL.md").read_text(encoding="utf-8")
    assert "command -v" not in text and "ja env" in text
    assert not re.search(r"\brm\b", text) and "delete the file" not in text
    assert "close this window" in text and "whenever you open the assistant from its shortcut" in text
    assert "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" in text
