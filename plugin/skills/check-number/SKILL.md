---
name: check-number
description: Check a number before it goes to a leader, a review, or a published page, and save it once the person approves it. Use when the person asks "is this number safe to send", "check this number", "sign off this number", "can I send this to my VP", and whenever a tool whose numbers go to leaders has produced a number. Only in a job assistant folder (one that has assistant/.job-assistant); in any other folder, do not use this.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Check a number

A number is about to go to a leader, a review, or a published page. Show the person what they need to decide whether it is safe to send: how it compares with the last published number, whether it was worked out the way the method document says, and what was left out. They decide. You never call a number checked.

## How to behave throughout

- To look at files and folders, use your file reading and search tools, never shell commands. Run the helper lines one at a time, never joined with other commands.
- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command.
- Never work out, round, or adjust a number yourself. Numbers come from the tool's facts step and from the helper.
- Label the number "Draft, not checked" until the person approves it in so many words.
- Read only. Never post, send, share, or edit anything in another system.

## The helper

Every step below uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Run each helper line on its own, from the assistant folder, exactly in that form. Do not join it with other commands. The helper prints plain sentences; pass the meaning on in your own words.

## Steps

### 1. Get the details

You need: the metric (a short name, such as `ttm-days`), the value, the unit, the period (such as `2026-Q3`), and the tool that made it. When a tool just ran, take them from its facts step: the facts it printed, and its counts of rows used, left out, and in total.

First run `ja ledger metrics`. It lists the numbers already published, each with its name, its unit, and its last period. If this number is one of them, use that exact name and check that the unit is the same. Only make up a new name for a number that was never published.

If the person brings a number no tool made, ask where it came from. Without a tool you can still run `ja ledger compare --metric <metric> --value <value> --unit <unit>` and read the method, but the number cannot be saved as approved. Offer to build a tool for it with the automate-this steps.

### 2. Find the method document

Read the tool's record, `.claude/skills/<id>/tool.yaml`, and run `ja sources list --json`. The method document is the source that says how the number is defined and worked out, such as a methodology explainer. If the tool lists none, ask: "Which document says how this number should be worked out?" Add it with `ja sources add` if it is not on the list.

### 3. Check the method

1. Read the method document: through a connected service, read only, or from the person's copy in the inbox.
2. Find what it says about blanks, names that do not match, and rows to leave out. Copy its exact words.
3. Read how the tool's facts step handled the same things: its `facts.py`, the notes on each fact, and its counts.
4. Compare the two, point by point.

### 4. Write the sign-off note

Run `ja numbers note` with the details:

```
ja numbers note --metric <metric> --value <value> --unit <unit> --period <period> --tool <id> --method-source <source id> --excluded <rows left out> --total <rows in total>
```

Leave out `--excluded` and `--total` only when the facts step gives no such counts.

If the helper says the unit differs from the last published number, stop and tell the person. Ask which unit is right. Do not convert the number yourself.

### 5. Show the person

Show the note exactly as the helper printed it, then the method check in plain words:

- The method says, in its own words: "<quote>".
- The tool did: <what the facts step did, with its counts>.
- Whether they match.

If they differ, say exactly what differs. If the facts step can give the number the method's way (for example a fact that counts it both ways), give that number from its facts. If it cannot, say so and offer to fix the tool with the fix-tool steps. Never work out the other number yourself.

If the note says the method copy is old, ask for a fresh copy before relying on the method check.

If the note says the period was already approved, tell the person: a number for this period is already saved, and this one would replace it. The comparison in the note is then with the period before.

End with the label "Draft, not checked". Do not say the number is checked, safe, or approved.

### 6. Approval

Only when the person says "approve", "yes, send it", or words that plainly approve this number:

1. Run `ja numbers approve --metric <metric> --period <period> --method-notes "<one sentence on how the method was applied>"`.
2. Tell them it is saved and the next number will be compared with it.
3. If the tool shows as "Draft, not checked" because its method was not yet confirmed, ask: "Now that you have confirmed the method on a real run, shall I mark <tool name> as working?" On yes, run `ja tool status <id> working`.

If you found a difference in step 5 and they have not said how to handle it, do not approve. Ask first.

If the helper says the period was already approved, ask: "A number for <period> was already approved on <date>. Shall I replace it with this one?" Only on a clear yes, run the same approve line with `--replace` added. Without a yes, leave the saved number as it is.

If they do not approve, leave the number as a draft. It stays waiting until a new note replaces it.
