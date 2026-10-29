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


RECIPES = sorted((PLUGIN / "skills/automate-this/recipes").glob("*.md"))
RECIPE_HEADINGS = ["When it fits", "What to ask", "Inputs and checks", "Facts step", "The result",
                   "Checklist items to include", "Numbers", "Watch out for", "Example requests"]


def test_there_are_skills():
    assert [p.parent.name for p in SKILLS] == ["automate-this", "fix-tool", "set-me-up"]


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
    pages = [*SKILLS, *(PLUGIN / "skills").glob("*/*.md"), *RECIPES, PLUGIN / "templates/adopted-skill.md",
             PLUGIN / "templates/built-skill.md", PLUGIN / "templates/workspace/CLAUDE.md"]
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


def test_automate_this_triggers():
    front, _ = frontmatter(PLUGIN / "skills/automate-this/SKILL.md")
    for phrase in ("automate this", "make this automatic", "can you do this for me every time", "build me a tool",
                   "screenshot"):
        assert phrase in front["description"]


def test_recipes_have_every_heading():
    names = [p.stem for p in RECIPES]
    assert names == sorted(["answer-from-sources", "data-to-story", "reconcile-two-lists", "check-against-template",
                            "meeting-to-actions", "recurring-digest", "tailor-for-audience", "carry-a-change",
                            "keep-it-running"])
    for recipe in RECIPES:
        text = recipe.read_text(encoding="utf-8")
        assert text.startswith("# Recipe: "), recipe.name
        assert re.findall(r"^## (.+)$", text, flags=re.M) == RECIPE_HEADINGS, recipe.name
        for heading in RECIPE_HEADINGS:
            body = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
            assert body.strip(), f"{recipe.name}: {heading} is empty"


def test_automate_this_names_every_recipe():
    text = (PLUGIN / "skills/automate-this/SKILL.md").read_text(encoding="utf-8")
    for recipe in RECIPES:
        assert f"`{recipe.name}`" in text, recipe.name


def test_automate_this_flow():
    text = (PLUGIN / "skills/automate-this/SKILL.md").read_text(encoding="utf-8")
    order = ["ja build start", "ja search", "Does this contain anything confidential, such as unannounced "
             "offerings, partners, or pricing?", "ja tool add --from data/drafts/", "ja tool files",
             "ja input check", "ja facts run", "Does this look right?", "ja proof save", "ja proof run",
             "ja check <id> --result pass", "ja tool status <id> working", "ja record build"]
    positions = [text.index(step) for step in order]
    assert positions == sorted(positions)
    assert "never write there yourself" in text and "Draft, not checked" in text


def _helper_actions(text):
    """Every `ja <words>` example in a page, as the words up to the first detail."""
    out = []
    for span in re.findall(r"`ja ([^`]+)`", text):
        span = re.sub(r'^--workspace "[^"]*" ', "", span)
        words = []
        for w in span.split():
            if w.startswith(("-", "<", '"')) or not re.fullmatch(r"[a-z-]+", w):
                break
            words.append(w)
        if not span.startswith("<"):
            out.append(words)
    return out


def test_every_helper_action_in_the_pages_exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ja_cli_check", PLUGIN / "scripts/ja.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.build_parser()
    commands = parser._subparsers._group_actions[0].choices
    pages = [*SKILLS, *RECIPES, PLUGIN / "templates/built-skill.md", PLUGIN / "templates/adopted-skill.md"]
    for page in pages:
        for words in _helper_actions(page.read_text(encoding="utf-8")):
            assert words and words[0] in commands, f"{page.name}: ja {' '.join(words)}"
            sub = commands[words[0]]
            actions = [a for a in sub._actions if isinstance(a, type(parser._subparsers._group_actions[0]))]
            if actions:
                assert len(words) > 1 and words[1] in actions[0].choices, f"{page.name}: ja {' '.join(words)}"


def test_fix_tool_triggers_and_flow():
    front, body = frontmatter(PLUGIN / "skills/fix-tool/SKILL.md")
    for phrase in ("this broke", "is not working", "this gave the wrong answer", "pastes an error"):
        assert phrase in front["description"]
    order = ["ja tools", "ja input check", "ja proof run", "lives_at", "how_to_run", "ja tool draft", "ja tool files",
             "ja tool improve", "ja check <id> --result pass"]
    positions = [body.index(step) for step in order]
    assert positions == sorted(positions)
    assert "Never push, deploy, or publish" in body and "RUNBOOK.md" in body
