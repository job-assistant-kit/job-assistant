---
name: automate-this
description: Build a new tool from one real example of the person's work, check it on that example, and keep it for next time. Use when the person says "automate this", "make this automatic", "can you do this for me every time", "build me a tool", "I do this every week", or shares a screenshot, file, link, or pasted text and asks for it to be done automatically from now on.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Automate this

The person wants a piece of their work done for them from now on. Build a tool from the example they gave, run it on that example now, and keep it once they say the result looks right. They do not know or care how it works.

## How to behave throughout

- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command. Do technical steps yourself and tell them the result in one plain sentence.
- Ask at most three questions about the task, one at a time, plus the confidentiality question.
- Never post, send, share, edit, or delete anything in another system. Read only. Results are drafts.
- Numbers, counts, dates, and matches come from the tool's facts step, never from your own counting.

## The helper

Every step below uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Run each helper line on its own, from the assistant folder, exactly in that form. Do not join it with other commands. The helper prints plain sentences; read them and pass the meaning on in your own words. If it reports a problem, fix the cause and run it again.

The tool's own folder (`.claude/skills/<id>/`) is protected: never write there yourself. Write the tool's files in its draft folder, `data/drafts/<id>/`, and the helper puts them in place. Write files the person should see, such as results, in the `inbox/` folder.

## Steps

### 1. Start

First run `ja build unfinished`. If it lists a build, ask: "You started <name> on <date>. Shall I finish it?" On yes, use that id, skip `ja build start`, and pick up at the step it names as next: write the tool record (step 5), run it on their example (step 6), or record the check and the build (step 7). Read the tool's files in `data/drafts/<id>/` and its saved example, if any, before you go on. On no, start the new request below.

Pick a short id for the new tool: lowercase words joined by hyphens that say what it does, such as `match-offering-lists`. Run `ja build start --id <id>`.

Read what they gave you:

- A file: if they say they dropped it in, look in `inbox/`. Otherwise ask them to drop it into the inbox folder in their assistant folder.
- A screenshot: read it. If the tool needs the data behind it, ask them for the file it came from.
- A link: read it through a connected service if one is available, read only. Otherwise ask them to save a copy into the inbox folder.
- Pasted text: save it as `inbox/<id>-example.md` so the tool can be checked on it later.

### 2. Look for what already exists

Run `ja search <the main words of the task>`.

- If a tool already does this, say so in one sentence and offer to run it or change it. Stop here unless they want a new one.
- If a part fits (a shared piece that reads, matches, checks, or writes something), plan to reuse it.

### 3. Ask what is missing

Ask only what you cannot see from the example, one question at a time, three at most:

1. What do you start from each time? (Which file, report, or document, and where it comes from.)
2. What do you produce, and who reads it?
3. How often do you do this, and how long does it take you by hand?

Then always ask: "Does this contain anything confidential, such as unannounced offerings, partners, or pricing?"

Count the questions you asked; the build record needs the number.

### 4. Pick the recipe

Choose the one recipe that fits best and read only that file from the `recipes/` folder next to this page:

| Recipe file | Fits when the task is to |
|---|---|
| `answer-from-sources.md` | answer questions from approved documents |
| `data-to-story.md` | turn numbers or a data export into a written update |
| `reconcile-two-lists.md` | match two lists and show what does not line up |
| `check-against-template.md` | check a document against a template or standard |
| `meeting-to-actions.md` | turn notes or a transcript into decisions and actions |
| `recurring-digest.md` | sum up what changed since last time, on a rhythm |
| `tailor-for-audience.md` | adapt a deck or document for one audience |
| `carry-a-change.md` | carry one change into every document it affects |
| `keep-it-running.md` | look after a tool they inherited |

If none fits, build from the closest one and note in the tool record's `does` what is different.

### 5. Build the tool

1. Run `ja sources list --json` to see the sources list. Note the ids of the sources this tool reads. If the tool reads a document that is not on the list, add it with `ja sources add` (see the setup steps for the details it needs).
2. Write the tool record to `data/drafts/<id>/tool.yaml` with these fields:
   - `id`, `name` (their words), `does` (one sentence)
   - `examples`: two or three phrases they would say to run it
   - `kind: built`, `recipe: <recipe file name without .md>`, `status: being-built`
   - `rhythm`: on-demand, daily, weekly, monthly, or quarterly
   - `sources`: the source ids from the list
   - `data_path`: where its input comes from, in plain words
   - `manual_steps`: numbered steps, in their words, for getting the input file
   - `your_minutes_by_hand`: their estimate, as a whole number
   - `confidential`: true or false, from their answer
   - `exec_numbers`: true when its numbers go to leaders, a review, or a published page
   - `parts`: the ids of parts it reuses, if any
3. Run `ja tool add --from data/drafts/<id>/tool.yaml`. This creates the tool and puts working copies of its files in `data/drafts/<id>/`.
4. Edit `data/drafts/<id>/SKILL.md`. Replace each `<!-- fill: ... -->` note with the real instructions for this tool, following the recipe. Remove the notes. Keep the other sections as they are.
5. If the task involves anything countable or comparable (counts, totals, dates, durations, matches, changes from last time), write `data/drafts/<id>/facts.py`, starting from `facts-template.py` in the same folder. Give each fact a short, stable id and a plain label, and name the file each fact comes from. It may read only the files it is given: no internet, no other programs. To reuse a code part, call `load_part("<part id>")`.
6. Edit `data/drafts/<id>/checklist.yaml`: add the recipe's checklist items, made specific to this tool, as plain statements that are true of a good result.
7. Write `data/drafts/<id>/input.yaml`: one entry per file the tool expects, each with `name`, `types` (csv, xlsx, json, md, txt, pdf, or png), `required_columns`, and `min_rows`.
8. Run `ja tool files <id>`. If it reports a problem, fix that file in the draft folder and run it again.
9. If a piece of this tool would clearly help other tools (for example a name matcher), make it a part: write `data/drafts/parts/<part id>/part.yaml` with `id`, `name`, `does`, `kind` (reader, step, check, writer, or output), and `file`, put that file next to it, and run `ja part add --from data/drafts/parts/<part id>/part.yaml`.

### 6. Run it on their example now

1. Run `ja input check <id> <files>`. If it reports a problem with their file, tell them plainly and show the steps it prints.
2. Run `ja facts run <id> <files>` when the tool has a facts step.
3. Write the result the way the tool's page now says, using the facts exactly as printed. Check it against every checklist item.
4. When the tool's numbers go to leaders, follow the check-number steps for each number before you show it, and label each number "Draft, not checked". Do not call any number checked.
5. Show them the result.

### 7. Agree on the result

Ask: "Does this look right?"

- On a correction: change the draft files, run `ja tool files <id>` again, rerun step 6, and show the new result. Count the corrections; the build record needs the number.
- When they say it looks right:
  1. Save the result as `inbox/<id>-result.md`.
  2. Run `ja proof save <id> --input <files> --output inbox/<id>-result.md`.
  3. Run `ja proof run <id>`. The facts must match. Read the checklist it prints and confirm each item holds for the saved result.
  4. Run `ja tool improve <id> --change "Built from your example" --reason "You asked"`.
  5. Run `ja check <id> --result pass --detail "Checked on your first example"`.
  6. Run `ja tool status <id> working`. When the tool's numbers go to leaders, run `ja tool status <id> draft-not-checked` instead, and tell them it stays "Draft, not checked" until they confirm the method on a real run.
  7. Run `ja record build --tool <id> --recipe <recipe> --questions <number asked> --corrections <number of corrections>`.

### 8. Tell them how to use it

Close with one sentence, such as: "Next time, drop the new export in the inbox and say 'match the offering lists'." Use the first example phrase from the tool record.
