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
    assert [p.parent.name for p in SKILLS] == ["automate-this", "check-number", "fix-tool", "learn", "set-me-up",
                                               "show-tools", "upkeep"]


def test_frontmatter_valid():
    for path in SKILLS:
        front, body = frontmatter(path)
        assert front["name"] == path.parent.name
        assert isinstance(front["description"], str) and front["description"].strip()
        assert len(front["description"]) < 1024, path
        assert body.strip()


GUARD = "Only in a job assistant folder (one that has assistant/.job-assistant); in any other folder, do not use this."


def test_set_me_up_triggers():
    front, _ = frontmatter(PLUGIN / "skills/set-me-up/SKILL.md")
    for phrase in ("set up my job assistant", "here is my job description", "set up my assistant"):
        assert phrase in front["description"]
    # The kit is on in every session, so setup must not start on everyday words.
    for phrase in ("set me up", "get started"):
        assert phrase not in front["description"]


def test_skills_other_than_setup_stay_in_the_assistant_folder():
    for path in SKILLS:
        if path.parent.name == "set-me-up":
            continue
        front, _ = frontmatter(path)
        assert front["description"].rstrip().endswith(GUARD), path


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
    order = ["ja build unfinished", "Shall I finish it?", "ja build start", "ja search", "Does this contain anything confidential, such as unannounced "
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


def _banned_in_quotes(text):
    bad = []
    for phrase in re.findall(r'"([^"\n]+)"', prose(text)):
        if [w for w in BANNED if w in re.findall(r"[a-z]+", phrase.lower())]:
            bad.append(phrase)
    return bad


def test_every_skill_allows_the_helper_line_it_uses():
    for path in SKILLS:
        front, body = frontmatter(path)
        if "uv run --script" not in body:
            continue
        rules = front.get("allowed-tools") or []
        assert 'Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)' in rules, path
        assert 'Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)' in rules, path
        assert 'uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action>' in body, path


def test_rendered_built_page_is_valid_and_plain():
    from ja import tools
    from ja.registry import Tool

    for exec_numbers in (False, True):
        tool = Tool(id="match-lists", name="Match the lists", does="Matches the export to the inventory.",
                    examples=["match the lists"], kind="built", status="being-built", rhythm="monthly",
                    data_path="Two exports", created="2026-10-28", exec_numbers=exec_numbers)
        text = tools.built_skill(tool, "/kit/scripts/ja.py")
        front = yaml.safe_load(text.split("---\n", 2)[1])
        assert front["name"] == "match-lists" and len(front["description"]) < 1024
        assert _banned_in_quotes(text) == []
        assert "\u2014" not in text and not re.search(r"\s--\s", prose(text))


def test_recipes_and_steps_quote_plain_words():
    for page in [*RECIPES, *SKILLS]:
        assert _banned_in_quotes(page.read_text(encoding="utf-8")) == [], page.name


def test_check_number_triggers_and_flow():
    front, body = frontmatter(PLUGIN / "skills/check-number/SKILL.md")
    for phrase in ("is this number safe to send", "check this number", "sign off this number"):
        assert phrase in front["description"]
    assert "whenever a tool whose numbers go to leaders" in front["description"]
    order = ["ja sources list --json", "Copy its exact words", "ja numbers note", "End with the label \"Draft, not checked\"",
             "\"approve\", \"yes, send it\"", "ja numbers approve", "ja tool status <id> working"]
    positions = [body.index(step) for step in order]
    assert positions == sorted(positions)
    assert "Never work out the other number yourself." in body and "You never call a number checked." in body


def test_exec_number_tools_point_to_the_sign_off_steps():
    from ja import tools
    from ja.registry import Tool

    tool = Tool(id="ttm-report", name="TTM report", does="Reports the TTM median.", examples=["run the TTM report"],
                kind="built", status="being-built", rhythm="quarterly", data_path="The metrics export",
                created="2026-10-28", exec_numbers=True)
    text = tools.built_skill(tool, "/kit/scripts/ja.py")
    assert "follow the check-number steps" in text and "this tool (ttm-report)" in text
    automate = (PLUGIN / "skills/automate-this/SKILL.md").read_text(encoding="utf-8")
    assert "follow the check-number steps" in automate


def test_learn_triggers_and_flow():
    front, body = frontmatter(PLUGIN / "skills/learn/SKILL.md")
    for phrase in ("that was wrong", "change it so", "always", "never", "remember that", "what have you learned",
                   "forget that"):
        assert phrase in front["description"]
    order = ["ja tools", "ja knowledge add", "Should I do it this way every time?", "ja rules add", "--pending",
             "ja proof run <tool id>", "ja rules confirm <rule id>", "ja record corrected <tool id>",
             "ja tool improve <tool id>", "ja check <tool id> --result pass", "ja rules hold <rule id>",
             "ja rules similar", "Should I do this everywhere?", "ja rules promote", "ja rules list",
             "ja knowledge list", "ja rules forget <rule id>`.", "ja knowledge forget"]
    positions = [body.index(step) for step in order]
    assert positions == sorted(positions)
    assert "never overrides the rules that always apply" in body


def test_built_tools_follow_their_rules_before_writing():
    text = (PLUGIN / "templates/built-skill.md").read_text(encoding="utf-8")
    assert text.index("ja rules for {{id}}") < text.index("## Write the result") < text.index("Rules used:")


def test_core_page_helper_line_names_a_real_action():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ja_cli_core", PLUGIN / "scripts/ja.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = (PLUGIN / "templates/workspace/CLAUDE.md").read_text(encoding="utf-8")
    found = re.findall(r'uv run --script "<path>" ([a-z-]+) ([a-z-]+) --words', text)
    assert found == [("record", "task")]
    args = module.build_parser().parse_args(["record", "task", "--words", "x"])
    assert args.func.__name__ == "cmd_record_task"


def test_new_pages_ask_one_question_at_a_time_and_stay_drafts():
    for name in ("learn", "check-number", "upkeep", "show-tools"):
        body = frontmatter(PLUGIN / f"skills/{name}/SKILL.md")[1]
        assert "Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command." in body
        assert "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" in body


def test_upkeep_triggers_and_flow():
    front, body = frontmatter(PLUGIN / "skills/upkeep/SKILL.md")
    for phrase in ("anything I should know", "what needs my attention", "clean my inbox"):
        assert phrase in front["description"]
    order = ["ja upkeep --json", "watch", "ja sources changed <id>", "Run `ja upkeep`.", "at most three",
             "ja inbox clean", "ja inbox clean --yes", "ja sources exported", "ja sources checked <id>"]
    positions = [body.index(step) for step in order]
    assert positions == sorted(positions)
    assert "Never delete" in body


def test_show_tools_triggers_and_flow():
    front, body = frontmatter(PLUGIN / "skills/show-tools/SKILL.md")
    for phrase in ("show my tools", "what can you do for me", "what tools do I have", "retire", "bring back"):
        assert phrase in front["description"]
    order = ["ja dashboard --open", "ja tools", "ja tool retire <id>", "ja tool restore <id>"]
    positions = [body.index(step) for step in order]
    assert positions == sorted(positions)


def test_upkeep_words_reach_a_page_that_handles_them():
    """Each thing upkeep tells the person to say is handled by one of the assistant's pages."""
    descriptions = {p.parent.name: frontmatter(p)[0]["description"] for p in SKILLS}
    assert "update" in descriptions["fix-tool"] and "more reliable" in descriptions["fix-tool"]
    assert "finish" in descriptions["automate-this"]
    assert "retire" in descriptions["show-tools"]
    assert "clean my inbox" in descriptions["upkeep"] and "fix my sources" in descriptions["upkeep"]
    fix = frontmatter(PLUGIN / "skills/fix-tool/SKILL.md")[1]
    assert "ja sources checked" in fix and "more reliable" in fix


NO_SHELL_LINE = ("To look at files and folders, use your file reading and search tools, never shell commands. "
                 "Run the helper lines one at a time, never joined with other commands.")


def test_pages_that_read_files_forbid_shell_looking():
    root = Path(__file__).parents[1]
    for name in ("set-me-up", "automate-this", "fix-tool", "learn", "check-number", "upkeep", "show-tools"):
        assert NO_SHELL_LINE in (root / "skills" / name / "SKILL.md").read_text(encoding="utf-8"), name
    assert NO_SHELL_LINE in (root / "templates" / "workspace" / "CLAUDE.md").read_text(encoding="utf-8")


def test_drive_drafts_steps():
    setup = (PLUGIN / "skills/set-me-up/SKILL.md").read_text(encoding="utf-8")
    for line in ("ja drive start", "ja drive set --folder", "ja drive off", "inheritedPermissionsDisabled",
                 "The one exception is creating the drafts folder", "so do not judge by whether you can see it", "save my drafts to Drive",
                 "claude.ai connectors are not available"):
        assert line in setup, line
    assert "start or stop saving drafts to Google Drive" in setup.split("---")[1]
    for page in ("templates/built-skill.md", "skills/automate-this/SKILL.md"):
        text = (PLUGIN / page).read_text(encoding="utf-8")
        assert "ja drive status --tool" in text and "exactly the parentId, title, and contentMimeType" in text, page
    core = (PLUGIN / "templates/workspace/CLAUDE.md").read_text(encoding="utf-8")
    assert "when saving to Drive is on" in core
