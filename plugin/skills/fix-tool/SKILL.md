---
name: fix-tool
description: Find out why one of the person's tools broke or gave a wrong answer, explain it in plain words, and fix it. Use when the person says "this broke", "the metrics tool is not working", "this gave the wrong answer", "it failed", "something is off with", "update" followed by a tool's name, or "make" a tool "more reliable", or pastes an error message, for tools built here and tools they inherited.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Fix a tool

One of the person's tools stopped working or gave a wrong answer. Find the cause, explain it in plain words, and fix it, or prepare the fix when the tool lives somewhere else.

## How to behave throughout

- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command. Never show raw error text; say what it means.
- Look before you change anything. Say what you checked.
- Never post, send, share, edit, delete, push, deploy, or publish anything in another system. Prepare drafts and steps instead.

## The helper

Every step below uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Run each helper line on its own, from the assistant folder, exactly in that form. Do not join it with other commands. The helper prints plain sentences; read them and pass the meaning on in your own words.

The tool's own folder (`.claude/skills/<id>/`) is protected: never write there yourself. Change copies in the draft folder and let the helper put them in place.

## Steps

### 1. Find the tool

Run `ja tools`. Match what the person said to one tool by its name or example words. If two could fit, ask which one. Read its record, `.claude/skills/<id>/tool.yaml`, and its section of `RUNBOOK.md`.

### 2. Look for the cause

Check in this order and stop at the first clear cause:

1. The input. Ask which file they used if you do not know. Run `ja input check <id> <files>`. A wrong or old file is the most common cause; show the steps it prints for getting the right one.
2. The sources. Run `ja sources list`. A copy past its freshness limit, or a document that changed, can make results wrong.
3. The saved examples. Run `ja proof run <id>`. Facts that changed on a saved example point to a change in the tool or its facts step.
4. The facts step. Run `ja facts run <id> <files>` on their file and read any problem it reports.
5. For a tool they inherited: read `lives_at`, `how_to_run`, `inputs`, and `last_good_run` in its record. Compare what they see with what good output looks like. An error message they paste usually names the step that failed.
6. A wrong answer with correct facts: compare the result with the tool's `checklist.yaml` to find which item it missed.

### 3. Explain it

Tell them in two or three plain sentences: what went wrong, why, and what you propose. Ask before changing the tool.

### 4. Fix it

For a tool built here:

1. Run `ja tool draft <id>`. Its files are now in `data/drafts/<id>/`.
2. Make the change there: the instructions page, `facts.py`, `checklist.yaml`, or `input.yaml`.
3. Run `ja tool files <id>`. If it reports a problem, fix the draft and run it again.
4. Run `ja proof run <id>`. For each saved example, write the result again and confirm every checklist item it prints.
5. Run `ja tool improve <id> --change "<what changed, in plain words>" --reason "<why, in their words>"`.
6. Run `ja check <id> --result pass --detail "<what you checked>"` when every example passes. Otherwise run `ja check <id> --result fail --detail "<what still fails>"` and tell them what is left.
7. If the cause was a document that changed, run `ja sources checked <source id>` once every tool that uses it has passed its check again. `ja tools` shows which tools still need an update.

To make a tool more reliable (offered after it has had five accepted results): the change is a facts step. Follow items 1 to 6 to add `facts.py` in the draft folder and move the counting, adding up, and matching that the tool's steps do by hand into it. Its facts must give the same answers as the saved examples.

For a tool they inherited that lives somewhere else (a shared sheet, a web app, a scheduled job):

1. Write the change as a draft in the inbox folder, such as `inbox/<id>-fix.md`: what to change, where, and why.
2. Write numbered steps they or the owner can follow to apply it. Say who to ask if they cannot.
3. Never push, deploy, or publish the change yourself. The assistant folder blocks those actions.
4. Once they say it works again, run `ja check <id> --result pass --detail "<what they confirmed>"`. Until then, run `ja check <id> --result fail --detail "<the cause you found>"`.
5. Run `ja tool improve <id> --change "<what changed>" --reason "<why>"` after a fix is applied.

### 5. Close

Tell them in one sentence whether the tool works again, and if not, what is still needed and from whom.
