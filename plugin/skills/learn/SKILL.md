---
name: learn
description: Learn from the person's corrections and teaching, check each new way of working on the saved examples before using it, and say what has been learned or forget it. Use when the person says "that was wrong", "change it so", "always", "never", "remember that", "from now on", "what have you learned", "forget that", or corrects a result a tool just gave.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Learn

The person corrected you or taught you something. Work out what kind of lesson it is, keep it in the right place, and make sure a new way of working does not spoil results they already accepted.

## How to behave throughout

- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command.
- Ask at most one question at a time.
- A lesson never overrides the rules that always apply: every claim names its source, numbers for leaders go through number sign-off, and everything stays a draft. If a correction would break one of these, say so plainly and do not save it.
- Use their own words for the lesson and for the reason.

## The helper

Every step below uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Run each helper line on its own, from the assistant folder, exactly in that form. Do not join it with other commands. The helper prints plain sentences; pass the meaning on in your own words.

## Steps

### 1. Find the tool

The correction is about the tool used most recently in this conversation. If no tool was used, or two could fit, ask which one. Run `ja tools` to match their words to a tool and its id. If the lesson is about all their work, not one tool, its scope is `everywhere`.

### 2. Decide what kind of lesson it is

- A fact (a date, a name, a policy, who owns what): save it with `ja knowledge add --fact "<the fact>" --source "<document name, or per <their name>, <date>>"`. Then redo the result if it used the wrong fact. Done.
- A one-off fix (this result only): redo the result, show it, and run `ja record corrected <id>`. Nothing is saved. Done.
- A way of working (how results should be written or arranged from now on): a rule. Go on to step 3.

If you cannot tell, ask: "Should I do it this way every time?"

If the correction needs the counting or matching to change, it is not a rule. Change the tool with the fix-tool steps instead.

### 3. Check a new rule before using it

1. Pick a short id for the rule: lowercase words joined by hyphens, such as `unmatched-first`. Write the rule as one plain sentence that starts with a verb, such as "List unmatched rows before matched ones."
2. Run `ja rules add --id <rule id> --text "<the rule>" --reason "<why, in their words>" --scope <tool id> --pending`.
3. Run `ja proof run <tool id>`. If it says there are no saved examples, there is nothing to check against: go to item 7.
4. For each saved example it lists: read the saved input files and the saved result, then write the result again following the tool's own steps, the rules from `ja rules for <tool id>`, and the new rule. Confirm each checklist item it printed. Then compare with the saved result: the new one must keep everything the person accepted there. If it says an example is damaged or missing its result, that example fails: go to item 6.
5. When every example passes:
   1. Run `ja rules confirm <rule id>`.
   2. Run `ja record corrected <tool id>`.
   3. Run `ja tool improve <tool id> --change "<the rule, in a few words>" --reason "You asked"`.
   4. Run `ja check <tool id> --result pass --detail "Saved examples still pass with the new rule"`.
   5. Redo the result they corrected with the rule, show it, and tell them in one sentence that you will do it this way from now on.
6. When any example fails:
   1. Run `ja rules hold <rule id> --reason "<which example would get worse, and how>"`.
   2. Tell them plainly which earlier result would get worse and how, and ask how to go on: change the wording of the rule, keep it on hold, or use it anyway.
   3. To change the wording: `ja rules forget <rule id>`, then start this step again with the new wording.
   4. To use it anyway, only on their clear yes: `ja rules confirm <rule id>`, then the same record, improve, and check lines as in item 5, with the detail "Used on your say-so although an example changes". Offer to keep the next result they accept as a new example.
7. When the tool has no saved examples:
   1. Confirm the rule with them in one sentence, in their words.
   2. Run `ja rules confirm <rule id>`.
   3. Run `ja record corrected <tool id>`.
   4. Run `ja tool improve <tool id> --change "<the rule, in a few words>" --reason "You asked"`.
   5. Do not run `ja check`. Nothing was checked, so no check is recorded.
   6. Redo the result they corrected with the rule and show it. Say: "There is no saved example to check this against yet, so the change is not checked." Offer to keep the next result they accept as an example.

### 4. Look for the same lesson in other tools

Run `ja rules similar <the rule's words>`. If an active rule for another tool says the same thing, ask: "You told me something similar for <other tool>. Should I do this everywhere?"

On yes:

1. Run `ja rules promote <rule id>`. The rule now waits for a check on every tool.
2. Run `ja tools`. For every tool with saved examples, run `ja proof run <id>` and check each example as in step 3, item 4.
3. All pass: run `ja rules confirm <rule id>`, then `ja rules forget <other rule id>`, because the rule for every tool now covers it. Tell them it now applies to all their tools.
4. Any fail: run `ja rules hold <rule id> --reason "<which tool's example would get worse, and how>"`. The rule goes back to the tool it came from. Tell them which tool would get worse and that the rule stays where it was.

On no, leave both rules as they are.

### 5. What have you learned

When they ask what you have learned, run `ja rules list` and `ja knowledge list`. Tell them in plain words: the ways of working you follow, and for which tools; the ones waiting for a check or on hold, and why; and the facts they taught you, with their sources.

### 6. Forget that

When they say "forget that", work out which rule or fact they mean. If it is not clear, read out the likely ones and ask which. Confirm in one sentence before removing it.

- A rule: `ja rules forget <rule id>`.
- A fact: `ja knowledge forget <words from the fact>`. If it says more than one entry matches, ask which one and run it again with more of its words.

Tell them in one sentence what you will no longer do or use.
