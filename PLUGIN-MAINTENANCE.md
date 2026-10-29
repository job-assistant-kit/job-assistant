# Plugin maintenance

This page is for the person who keeps the job-assistant kit working. The README covers installing and using it.

## How it works

The kit is a Claude Code plugin. Its instruction pages (skills) tell Claude what to do; one Python helper, `ja.py`, does every job that must give the same answer each time: the tool records, statuses, the tool index in the assistant notes, the tools page, run and build records, the published-numbers ledger, saved examples, rules, and upkeep. Claude writes the words; the helper decides facts and statuses.

The person's own content lives in a separate assistant folder that `ja init` creates. A kit update never changes that folder's content.

## Layout

```
.claude-plugin/marketplace.json        local marketplace listing the plugin
install.sh                             one-command install, update, and first session (see the README)
plugin/
  .claude-plugin/plugin.json           plugin manifest (name, version)
  hooks/hooks.json                     session start and after-tool hooks
  skills/<name>/SKILL.md               automate-this, check-number, fix-tool, learn,
                                       set-me-up, show-tools, upkeep
  skills/automate-this/recipes/*.md    the nine recipes
  skills/set-me-up/                    role-card-template.md
  skills/automate-this/questions.md    question bank for building a tool
  templates/                           built-skill.md, adopted-skill.md, checklist.yaml, facts.py
  templates/workspace/                 files copied into a new assistant folder
  scripts/ja.py                        helper entry (argument parsing only)
  scripts/ja/*.py                      helper modules
  scripts/ja/templates/dashboard.html.j2
  scripts/ja/templates/fonts/          Fraunces and Instrument Sans (SIL Open Font License), copied next to the tools page
  scripts/hook_session_start.py        session start hook
  scripts/hook_record_run.py           after-tool hook on the Skill tool
  scripts/hook_drive_gate.py           check before each Drive create action
  tests/                               pytest suite and synthetic fixtures
  pyproject.toml, uv.lock              test environment only
README.md, PLUGIN-MAINTENANCE.md
```

`ja.py` and both hook scripts carry the same inline dependency header (PEP 723: Python 3.11 or later, pyyaml, jinja2, openpyxl), so `uv run --script` builds one cached environment that all three share.

## How the pages call the helper

- Kit pages run `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action>` and allow exactly that line, quoted and unquoted, in their `allowed-tools`.
- Tool pages in an assistant folder are not part of the kit, so `${CLAUDE_PLUGIN_ROOT}` is not filled in for them. They call the helper by its full path. Every helper run records its own path on the `ja_path:` line of `assistant/.job-assistant` and, when the path moved (a kit update), rewrites that line, the allow rules in `.claude/settings.local.json`, and the full path in every tool page (`helper.sync`).
- A tool folder, `.claude/skills/<id>/`, is a protected path: Claude Code asks before every write there, even with an allow rule. So the steps never write there directly. They write into `data/drafts/<id>/` and run `ja tool add` or `ja tool files`, which check the files and put them in place.

## Helper command reference

Run as `uv run --script plugin/scripts/ja.py <command>`. Every command accepts `--workspace PATH` (the assistant folder; default: `JA_WORKSPACE`, then the nearest parent folder with the marker file) and `--today YYYY-MM-DD` (for tests). Output is plain sentences; `--json` gives output for code where listed. User errors print one plain sentence on stderr and exit 1.

| Command | What it does |
|---|---|
| `init PATH [--name NAME]` | Create an assistant folder from the template; refuses a non-empty folder; starts git history |
| `tools [--json]` | List active tools with status and first example words |
| `index` | Rewrite the tool index between the markers in CLAUDE.md |
| `dashboard [--open]` | Write `dashboard/index.html` and its fonts, and print the page's link; `--open` opens the browser and never fails without one |
| `start set --file PATH` / `start hide` / `start show` | The getting-started section at the top of the tools page: save it from a file (reach, recorded, gaps, first), fold it away, open it again |
| `record run\|accepted\|corrected TOOL` | Append a run record |
| `record task --words TEXT` | Note work done without a tool |
| `record build --tool T --questions N --corrections N [--recipe R] [--minutes N]` | Record a finished build; minutes come from `build start` when not given |
| `build start --id ID` | Note when a build started |
| `build unfinished [--json]` | Builds started and not recorded, with the steps done and the next one |
| `ledger add ... [--replace]` / `ledger compare --metric M --value V --unit U [--json]` | Published-numbers ledger; compare warns past a 15 percent change and refuses when the unit differs from the last published number |
| `ledger metrics [--json]` | The metrics already published, each with its unit, last period, and approval date |
| `numbers note ...` / `numbers approve --metric M --period P [--method-notes TEXT] [--replace]` | Number sign-off note, then approval into the ledger; the note refuses when the unit differs from the last published number |
| `check TOOL --result pass\|fail [--detail TEXT]` | Record a check result with today's date; a pass is refused while the tool has no saved example |
| `role set --file PATH` | Replace the role description between its markers |
| `settings deny NAME...` / `settings show` | Block connector write actions; list blocked and allowed actions. While saving to Drive is on, the Drive create action is left open |
| `drive start [--title T]` / `drive set --folder ID_OR_LINK --private yes\|no [--link URL]` / `drive off` | Drafts folder in Drive: get ready to create it, turn saving on for it, turn saving off. `start` and `set` take the Drive create action off the deny list; `off` puts it back |
| `drive status [--tool TOOL]` | Whether saving is on; with a tool, whether to save its accepted result and the exact parentId and title to use. Confidential tools are not saved to a shared folder |
| `sources add ...` / `sources exported ID DATE` / `sources list [--json]` | The sources list and export dates |
| `sources changed ID` / `sources checked ID` | Set or clear a source's changed mark |
| `tool add --from FILE` | Add a tool from a record file (built tools also get their page and checklist) |
| `tool draft ID` / `tool files ID [--from DIR]` | Copy a tool's files to its draft folder; check changed files and put them in place |
| `tool improve ID --change TEXT --reason TEXT` | Note an improvement |
| `tool status ID STATUS` / `tool retire ID` / `tool restore ID` | Declared status, archive, restore |
| `input check TOOL FILE...` | Check files against the tool's `input.yaml` |
| `facts run TOOL [FILE...] [--input NAME=FILE]... [--json]` | Run the tool's facts step with a time limit and check its output. When the tool lists its inputs (`input.yaml`), each file is matched to one input by type and required columns, or by the name given with `--input`; anything unclear is refused ("Say which file is which."). The step then receives `--input "<name>=<path>"` pairs in the order of the input list |
| `proof save TOOL --input FILE... --output FILE` / `proof run TOOL [--case N]` / `proof list TOOL` | Saved examples and checks against them; `proof run` compares facts and counts exactly, and fails (and records a failed check) for an example missing its result, missing or unreadable facts on a tool with a facts step, or unreadable details |
| `part add --from FILE` / `parts [--json]` / `search WORD... [--json]` | Parts library and word search over tools and parts |
| `rules add\|for\|confirm\|hold\|forget\|promote\|list\|similar ...` | Learned rules with staging; `confirm` takes only a rule waiting for a check; `promote ID` adds a waiting copy `ID-everywhere` and leaves the original in use until the copy is confirmed (it replaces the original) or held (the copy is removed) |
| `knowledge add --fact TEXT --source TEXT` / `knowledge list` / `knowledge forget TEXT` | Facts the person taught, with sources |
| `upkeep [--write] [--json]` | What needs attention, most urgent first; `--write` saves `data/upkeep.json` |
| `inbox clean [--yes]` | List inbox files more than 30 days old; delete them with `--yes` |
| `launcher [--yes] [--bin-dir D] [--apps-dir D] [--desktop-dir D]` | The shortcut; shows what it would write unless `--yes` |
| `env [--json]` | Which needed programs are installed |

`uv run --script plugin/scripts/ja.py <command> --help` gives the full options of each.

## Data contracts

Keep these names. Later code and the person's existing folders depend on them.

### Paths in an assistant folder

| Path | Holds |
|---|---|
| `assistant/.job-assistant` | Marker file; also the `ja_path:` line |
| `assistant/profile.yaml` | Learned rules |
| `assistant/sources.yaml` | Sources list |
| `assistant/knowledge.md` | Facts taught, one per line with source and date |
| `.claude/skills/<id>/` | A tool: `tool.yaml`, `SKILL.md`, `checklist.yaml`, optional `input.yaml` and `facts.py` |
| `.claude/settings.json` | Write blocks (deny) and the helper allow rule |
| `.claude/drive-drafts.json` | Drafts folder choice: `{state: off}`, `{state: creating, title}`, or `{state: on, folder_id, private, checked, link}`. Under `.claude/` so only the helper changes it without a prompt |
| `.claude/settings.local.json` | Allow rules for the helper's exact current path (written by `helper.sync`) |
| `archive/<id>/` | Retired tools |
| `parts/<id>/` | Shared parts: `part.yaml` with `part.py` (code) or `part.md` (writer) |
| `data/records/runs.jsonl`, `builds.jsonl`, `tasks.jsonl` | Run, build, and task records |
| `data/records/building/<id>.json` | Start times of builds in progress |
| `data/ledger.jsonl` | Published numbers |
| `data/numbers/pending.jsonl` | Numbers waiting for approval |
| `data/proofs/<id>/case-N/` | Saved examples: `inputs/`, the accepted output `output.md`, `facts.json` (tools with a facts step), `meta.json` ({saved, inputs: file names in run order, received, roles: {file name: input name} when the tool lists its inputs}). The input order comes only from `meta.json`; when it cannot be read the example is damaged and its inputs are never guessed from the folder |
| `data/drafts/<id>/` | Working copies of a tool's files |
| `data/last/` | The latest facts run per tool |
| `data/upkeep.json` | Upkeep items from the last `upkeep --write` |
| `inbox/` | Files the person drops in |
| `dashboard/index.html`, `dashboard/fonts/` | The tools page and its fonts. Static HTML, no JavaScript, no outside requests |
| `assistant/getting-started.yaml` | The getting-started section: reach, recorded, gaps, first (one to five automations), hidden |
| `CLAUDE.md` | Assistant notes with the tool index markers. A `RUNBOOK.md` that earlier versions wrote is removed |

`inbox/`, `data/`, `dashboard/`, and `.claude/settings.local.json` are in the folder's `.gitignore`.

### tool.yaml

| Field | Type | Required | Notes |
|---|---|---|---|
| id | `^[a-z0-9-]+$`, equals the folder name | yes | also the tool page's name |
| name | text | yes | plain name shown to the person |
| does | text | yes | one sentence |
| examples | list of text, at least 1 | yes | words that start it |
| kind | `built` or `adopted` | yes | adopted tools also carry `lives_at`, `how_to_run`, `inputs`, `outputs`, `last_good_run` |
| recipe | text or null | no | recipe id |
| status | `working`, `draft-not-checked`, `being-built`, `paused`, `retired` | yes | declared; `needs-update` is computed, never stored |
| rhythm | `on-demand`, `daily`, `weekly`, `monthly`, `quarterly` | yes | |
| sources | list of source ids | no | |
| data_path | text | yes | plain words |
| manual_steps | list of text | no | |
| your_minutes_by_hand | whole number or null | no | the person's estimate, never shown as measured |
| confidential | true or false | no | |
| exec_numbers | true or false | no | numbers go to leaders, so they go through sign-off |
| rules | list of rule ids | no | kept in step with the profile |
| improvements | list of {date, change, reason} | no | |
| last_check | {date, result: `pass` or `fail`, detail} or null | no | |
| created | YYYY-MM-DD | yes | |

Unknown fields are kept on save. An invalid record is reported as `<id>: <field> <problem>` and skipped by commands that read all tools.

### Other records

- `sources.yaml`: list of {id, name, kind: `living` or `fixed`, where, access: `connector` or `file`, version, exported: YYYY-MM-DD or null, fresh_days (default 7), changed (default false)}. Stale: a living source read from a file whose copy is older than `fresh_days`, or any export date in the future. A file source with no export date has no copy yet: it is not stale, and upkeep lists it once as a reminder (kind `nocopy`, shown under Ideas).
- `profile.yaml`: {rules: list of {id, text, reason, scope: `everywhere` or list of tool ids, added, state: `pending`, `active`, or `held` (missing means active), held_reason, replaces: the id of the rule a promoted copy will take the place of (only on copies made by `rules promote`)}}. Only active rules are used. Ids are unique. Older profiles may hold `scope_before` on a rule promoted in place; holding such a rule puts it back on those tools.
- `runs.jsonl`: {ts, tool, event: `run`, `accepted`, or `corrected`}. `tasks.jsonl`: {ts, event: `task`, words}. `builds.jsonl`: {ts, tool, recipe, questions, corrections, minutes}. `ledger.jsonl`: {metric, period, value, unit, source, method_notes, approved_on, tool}. Metric names and periods match without regard to case or spaces around them; a new number takes the name already in the ledger. One row per metric and period: adding a period already approved is refused unless `--replace` is given, which rewrites the ledger with the new row in place of the old one. Noting a period already approved compares with the latest entry approved before that period's first approval, and the note says when the period was approved and as what.
- Facts step output (printed by `facts.py`): {facts: list of {id, label, value, unit, source, notes}, counts: {name: whole number}, problems: list of sentences}.
- `upkeep.json`: {date, items: list of {kind, text, say, tool, name}}. Kinds in order of urgency: `due`, `update`, `unfinished`, `inbox`, `idea`, `stable`, `retire`.

### Effective status

First match wins: a declared `retired`, `paused`, or `being-built`; a failed last check, or a stale, changed, duplicate, or unknown source, gives `needs-update`; a declared `working` without a passed check made on or after the latest improvement gives `draft-not-checked`; otherwise the declared value. Labels for the person: Working, Draft, not checked, Needs update, Being built, Paused, Retired.

### Upkeep rules

- Due: quarterly tools 14 days before the calendar quarter ends when not run this quarter; monthly tools 5 days before the month ends when not run this month; weekly tools 6 days after the last run (or after they were made). Daily tools get no due notice.
- Retire offer: built, on-demand tools unused (or unused since made) for 90 days. Never for rhythm tools or inherited tools, whose runs often happen outside the assistant.
- Update: tools whose effective status is `needs-update`, with the reasons; entries in the sources list that cannot be read.
- Unfinished builds, from `build unfinished`.
- Inbox: files anywhere under `inbox/` last changed more than 30 days ago, except `.keep` placeholders and links.
- Idea: three or more task records in the last 30 days that share most of the shorter one's words (at least two, common short words left out).
- Stable: built tools with five or more accepted runs and no facts step.

## Facts step safety

A tool's facts step is code the assistant wrote, and it runs without asking. The boundary is `scripts/ja/runner.py`:

- `ja facts run` starts the step as `uv run --no-project --with openpyxl python runner.py <folder> <facts.py> <inputs>` (inputs as `--input name=path` pairs, or plain paths when the tool lists none; the runner may read only the path part, never a path hidden in a name), in its own process group. On the time limit the whole group is killed.
- The runner installs a Python audit hook before the step runs. The hook refuses, at the moment it happens: network use (`socket.*` and the protocol client events), starting programs (`subprocess.*`, `os.system`, `os.exec*`, `os.spawn*`, `os.posix_spawn`, `os.fork*`, `os.kill*`), native code (`ctypes.*`, importing `ctypes`, `_ctypes`, `cffi`), any file write or change (`open` in a write mode or with write flags, `os.remove`, `os.rename`, `os.mkdir`, `shutil.*`, and the rest in `_PREFIXES`), reading files outside the assistant folder, the Python install, and the input files given, and adding another hook. A refused action ends the run with exit code 3 and `JA-BLOCKED: <what>`; the helper turns that into a plain sentence.
- Only `openpyxl` may be added as extra software. `ja tool files` and `ja facts run` refuse an inline dependency header that names anything else.
- The source check in `safety.py` stays only as an early, friendly refusal.
- Bytecode caching is off for the step, and the file type table is loaded before the hook, so ordinary imports need no write or wide read access.
- Tests: `tests/test_runner.py` runs every known bypass for real (asyncio, aliased and star imports of `os`, `sys.modules`, `posix`, computed `__import__`, `importlib` with a variable, `eval` and `exec`, `pathlib` writes to `.claude/settings.json`, a part changed after it was added, `ctypes`, a swallowed refusal).
- Verified on Python 3.14.7, 2026-10-29.

Limit, stated plainly: an audit hook is strong in-process enforcement for code written by the assistant. It is not an operating system sandbox. Code that already runs native code could get around it, which is why native code loading is refused first.

## Hooks

`plugin/hooks/hooks.json` declares two command hooks, both in shell form with the placeholder in double quotes, stdout and stderr sent to `/dev/null`, `|| true` at the end, and a 5 second timeout:

- SessionStart (no matcher, so every start, resume, clear, and compaction): `hook_session_start.py`. In an assistant folder (the hook input's `cwd` or a parent with the marker file; `JA_WORKSPACE` is ignored), it runs `helper.sync`, writes `data/upkeep.json`, and writes the tools page. It does not rewrite CLAUDE.md.
- PostToolUse with matcher `Skill`: `hook_record_run.py`. When `tool_input.skill` (a leading `/` removed) is a tool id with a `tool.yaml` in the folder's `.claude/skills/`, it appends a `run` record. Kit pages are named `job-assistant:<name>` and never match.

- PreToolUse with matcher `mcp__claude_ai_Google_Drive__create_file`: `hook_drive_gate.py`, with a 20 second timeout and `onFailure: block`. Outside an assistant folder it prints nothing. Inside one it prints an allow or deny decision from `drive.decide`: while the folder is being set up it allows only a folder at the top of My Drive with the exact title, inherited permissions off, and no content; once on, it allows only new non-folder files whose parentId is the drafts folder. An unreadable setting denies. The script and `ja.drive` use the standard library only (no dependencies), so it starts fast. The create action is never put on the allow list: without the hook (plugin off), a create asks the person.

The first two scripts swallow all output and catch every error, then exit 0. Typed slash commands (`/<tool id>`) do not go through the Skill tool, so they are not recorded; the person talks in plain words, so Claude calls the Skill tool.

## Verified Claude Code behaviors

Checked against the Claude Code documentation at code.claude.com/docs (fetched with curl) and Claude Code 2.1.280 on this machine.

Verified 2026-10-29:

- Hook input arrives as one JSON object on stdin with the common fields `session_id`, `transcript_path`, `cwd`, `hook_event_name`, and for most events `permission_mode` (hooks reference, "Common input fields").
- SessionStart adds `source` (`startup`, `resume`, `clear`, `compact`, `fork`) and sometimes `model`. Plain text a SessionStart hook prints on stdout with exit 0 is added to Claude's context, which is why the hook prints nothing (hooks reference, "Exit code 0" and "SessionStart input").
- PostToolUse adds `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, and optionally `duration_ms`, and fires only after a tool succeeds. The matcher is tested against `tool_name`; `Skill` is an exact match (hooks reference, "Matcher patterns" and "PostToolUse input").
- The Skill tool's input parameter is `skill`, holding the page name; plugin pages are named `<plugin>:<page>`. Source: the permission rule form `Skill(skill:deploy)` in the skills page ("Restrict Claude's skill access") and the parameter form of rules in the permissions page ("Match by input parameter"). The hooks reference has no table for the Skill tool's input, so this is the documented name, not an observed one. Typing `/name` bypasses the tool hooks (hooks reference, "UserPromptExpansion").
- In a plugin's `hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}` is substituted in `command` (and `args`), and is also exported to the hook process as the environment variable `CLAUDE_PLUGIN_ROOT`, with `CLAUDE_PROJECT_DIR`. In shell form the docs ask for the placeholder in double quotes (hooks reference, "Exec form and shell form" and "Reference scripts by path"). The hooks use shell form so the output redirect and `|| true` apply. `onFailure` needs 2.1.295 and is used only by the Drive check (see below).
- Exit codes: 0 is success; 2 blocks on events that can block; any other code or a hook that cannot start is a non-blocking error with a notice. A timed-out hook's output is discarded. Default command timeout is 600 seconds, so the 5 second limit is set per hook.
- `${CLAUDE_PLUGIN_ROOT}` points at the installed version under the plugins root's `cache/<marketplace>/<plugin>/<version>/` for a marketplace installed from a git address. For a marketplace added from a local path, and for `--plugin-dir`, the plugin loads in place and `${CLAUDE_PLUGIN_ROOT}` points at the source folder. The folder template's allow rule covers the cache path; `helper.sync` adds the exact current path to `.claude/settings.local.json`, which covers the in-place cases (plugins reference, "Environment variables"; plugin loading page, "In-place and copied plugins").
- Allow rules in a project's `.claude/settings.json` apply only after the person accepts the workspace trust dialog for that folder; deny rules always apply. `claude -p` never shows the dialog (permissions page, "Project allow rules and workspace trust").
- Writes under a project's `.claude/` folder are protected paths: they prompt in `default` and `acceptEdits` modes even with an allow rule (permission modes page, "Protected paths").
- The Skill tool needs permission, so a headless `claude -p` run must pass `--allowedTools Skill` (with the helper's Bash rule) for the pages to run without a prompt (tools reference table).

Drive check, verified 2026-10-29:

- PreToolUse fires for connector actions; the matcher is tested against the full `mcp__<server>__<tool>` name (hooks reference, "Matcher patterns").
- A PreToolUse `permissionDecision: "allow"` skips the prompt but does not override a deny rule, so `drive start` and `drive set` take the create action off the deny list. A PreToolUse `"deny"` blocks even when an allow rule exists (hooks reference, "PreToolUse decision control").
- `onFailure: "block"` makes a failed or timed-out PreToolUse hook block the call; without it the call goes on through the normal permission flow (hooks reference, "Block the action when a hook fails"). It needs Claude Code 2.1.295. On older versions the key is ignored, and because the create action has no allow rule, a failed check falls back to a prompt.
- Claude Code reloads settings files when they change, so a deny list change from `drive start` or `drive off` applies in the running session (settings page, "When edits take effect").
- Observed live on 2026-10-29 with Claude Code 2.1.280 and the claude.ai Google Drive connector: a denied action is hidden from Claude's tool list, so setup checks for any Drive tool before offering the folder. After `drive start`, the create action appeared in the same session. With no allow rule, the hook's allow let the folder and a draft through in `claude -p`; a second folder, a file outside the folder, and a folder inside it were refused with the hook's reason. A `text/markdown` upload became a Google Doc.

First recorded by earlier batches on 2026-10-28, and checked again on 2026-10-29:

- Permission rules: `mcp__<server>__<tool>` names one connector action, and a deny rule removes it whatever the conversation says; an `mcp__` rule with parentheses is skipped. `Bash(<prefix> *)` allows a command with any arguments after the prefix. Both forms of the helper line, with and without quotes around the path, are allowed, because Claude may write either (permissions page, "Wildcard patterns" and "MCP").
- `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_SKILL_DIR}` are substituted in a plugin skill's text and in the Bash rules of its `allowed-tools`. `${CLAUDE_SKILL_DIR}` is the skill's own folder; `${CLAUDE_PLUGIN_ROOT}` is the plugin root and is filled in only for plugin skills. So tool pages in an assistant folder use the helper's full path instead (skills page, "Available string substitutions").

## Tests

```
cd plugin
timeout 600 uv run pytest -q
```

The suite runs the helper in process, runs the hook scripts as separate programs, and runs each hook command line through the shell as Claude Code would (skipped when uv is missing). Before each commit, also run:

```
grep -rn --exclude-dir=.venv --exclude-dir=__pycache__ $'\xe2\x80\x94' plugin/ README.md PLUGIN-MAINTENANCE.md
timeout 120 claude plugin validate .
timeout 120 claude plugin validate ./plugin
```

The first looks for the em dash character (U+2014) and must print nothing; the tests also refuse em dashes and a double hyphen used as punctuation in pages.

## Release

1. Raise `version` in `plugin/.claude-plugin/plugin.json` and in the plugin entry of `.claude-plugin/marketplace.json`. Keep them equal.
2. Run the tests and both validate lines, and `shellcheck install.sh`.
3. Commit, then `claude plugin tag plugin --dry-run` and `claude plugin tag plugin` create the `job-assistant--v<version>` git tag after checking that the two versions agree. Push the tag with `git push origin job-assistant--v<version>`. The manifest pins the version, so people get no update until it changes.
4. People update by running `install.sh` again, or by hand with `claude plugin marketplace update job-assistant` and `claude plugin update job-assistant@job-assistant`, then a new session or `/reload-plugins`.
5. To test `install.sh` without touching your own setup, run it with `CLAUDE_CONFIG_DIR` pointed at an empty folder, `--folder` pointed at a scratch folder, and `--no-start`, and answer no to the shortcut.
