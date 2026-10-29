---
name: upkeep
description: Tell the person what needs their attention, at most three things, and help with each one. Use when the person says "anything I should know", "what needs my attention", "what is coming up", "anything due", "clean my inbox", or "fix my sources", or opens the assistant with a greeting and no task.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Anything I should know

The person wants to know what needs their attention: tools that are due, tools that need an update, builds left half done, old files in the inbox, and ideas for new tools. Tell them the most urgent things first and help with the one they pick.

## How to behave throughout

- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command.
- Ask at most one question at a time.
- Never delete, retire, or change anything without their clear yes to that exact thing.
- Look at connected documents only to read when they last changed. Never edit, share, or move them.

## The helper

Every step below uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Run each helper line on its own, from the assistant folder, exactly in that form. Do not join it with other commands. The helper prints plain sentences; pass the meaning on in your own words.

## Steps

### 1. Look for changed documents

Run `ja upkeep --json`. Its `watch` list names the living documents the tools read through a connector, with `checked`, the oldest date a tool that uses it was checked.

For each one, look up the document through the connector by its name or where it lives, and read only its last modified time. When it changed after `checked`, run `ja sources changed <id>`. When `checked` is empty, or the connector is not available, leave it.

### 2. Tell them

Run `ja upkeep`. It prints the items in order, most urgent first, each with the words to say.

Tell them at most three items, in that order, each in one plain sentence with the words to say. If there are more, say how many more there are and that they are on the tools page. If it says nothing needs attention, say so in one sentence.

### 3. Help with the one they pick

- A tool that is due: run it the way its own steps say, with the words given.
- "clean my inbox": run `ja inbox clean`. Read out the files it lists and ask: "Shall I delete these files?" Only on a clear yes, run `ja inbox clean --yes` and tell them how many were deleted.
- A tool that needs an update because a copy of a document is too old: ask them for a fresh copy, with the steps the tool gives for getting it, and the date it was saved. When it is in the inbox, run `ja sources exported <source id> <date of the copy>`. Look up the source id with `ja sources list --json`.
- A tool that needs an update because a document changed or a check failed: follow the fix-tool steps. When every tool that uses a changed document has passed its check again, run `ja sources checked <id>`.
- "fix my sources": an entry in the sources list has a mistake. Tell them which document it is and what is wrong in plain words, ask for the right details one at a time, and correct only that entry in `assistant/sources.yaml`.
- "finish <name>": follow the automate-this steps. They pick up the build where it stopped.
- "make <name> more reliable": follow the fix-tool steps to add a facts step.
- "retire <name>": follow the show-tools steps.
- An idea ("automate this"): the next time they do that task, offer to build a tool for it with the automate-this steps.
