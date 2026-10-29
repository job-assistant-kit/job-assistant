---
name: show-tools
description: Show the person their tools page and a plain list of their tools with the words that start each one, and retire or bring back a tool when they ask. Use when the person says "show my tools", "what can you do for me", "what tools do I have", "open my tools page", "retire" followed by a tool's name, or "bring back" followed by a tool's name.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Show my tools

The person wants to see what their assistant can do for them, or to stop or start using one of their tools.

## How to behave throughout

- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command.
- Ask at most one question at a time.
- Retire or bring back a tool only on their clear yes to that tool.

## The helper

Every step below uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Run each helper line on its own, from the assistant folder, exactly in that form. Do not join it with other commands. The helper prints plain sentences; pass the meaning on in your own words.

## Steps

### 1. Open the tools page

Run `ja dashboard --open`. It opens the tools page in their browser. If it says it could not open a browser, tell them the page is `dashboard/index.html` in their assistant folder and that they can open it by double-clicking it.

### 2. Give the plain list

Run `ja tools`. For each tool, tell them in one line its name, whether it is ready to use, and the words that start it. When a tool shows a reason ("Why:"), add that reason in plain words. If it lists no tools, tell them to say "automate this" and show you a task they do by hand.

Do not mention upkeep items unless they ask. The tools page shows them.

### 3. Retire a tool

When they say "retire" and a tool's name: run `ja tools` to find the tool's id. Ask: "Shall I retire <name>? You can bring it back any time." Only on a clear yes, run `ja tool retire <id>` and tell them in one sentence what it printed.

### 4. Bring back a tool

When they say "bring back" and a tool's name: the retired tools are in the `archive/` folder, one folder per tool named by its id. Read the `name` line of each `archive/<id>/tool.yaml` to find the one they mean. Then run `ja tool restore <id>` and tell them in one sentence how it shows now.
