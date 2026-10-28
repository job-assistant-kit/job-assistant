---
name: set-me-up
description: Set up the job assistant for a new person from their job description. Use when the person says "set me up", "get started", "set up my assistant", "here is my job description", or shares a job description and asks for help with their work. Creates their assistant folder, interviews them, records the tools they already look after, blocks changes to outside systems, and suggests the first tasks to automate.
allowed-tools:
  - Bash(uv run --script *ja.py*)
---

# Set me up

You are setting up a job assistant for a business person. They do not know or care how it works. Your job is to understand their work, prepare their assistant folder, and leave them with a short list of first things to automate.

## How to behave throughout

- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command. Do technical steps yourself and tell them the result in one plain sentence.
- Ask one question at a time. Wait for the answer before the next one.
- Never invent facts about their job. If something is unclear, ask or write "unknown".
- Change nothing outside the assistant folder, except the shortcut in step 8 and only after they say yes.
- Never post, send, share, edit, or delete anything in another system. Read only.

## The helper

Every step below that changes the folder uses the helper:

```
uv run --script "${CLAUDE_SKILL_DIR}/../../scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Once the folder exists, add `--workspace "<folder>"` to every helper call so it works from any place. The helper prints plain sentences; read them and pass the meaning on in your own words. If it reports a problem, fix the cause and try again, or explain it plainly.

## Steps

### 1. Find or create the assistant folder

Run `ja tools`. If it answers that it could not find the assistant folder, ask: "Where should I keep your assistant? I suggest a folder called job-assistant in your home folder." Then run `ja init <folder> --name "<First name>'s Assistant"` (use the plain default if you do not know their name yet). If the folder already has an assistant with a filled-in role, ask whether they want to start over or update parts of it, and skip what they do not want redone.

Show them nothing technical. Say where the folder is in one sentence.

### 2. Get the job description

Ask them to paste it, share the file, or give a link. For a link: if you can read it through a connected service, read it (read only). Otherwise ask them to save the file into the inbox folder inside their assistant folder, then read it from there. Read any other documents the job description points to the same way.

### 3. Offer a short look at public material (optional)

Offer once: "Would you like me to look up public material about this kind of role? It helps me suggest better first tasks." Build two to four search queries from generic role words only, such as "product launch manager responsibilities" or "partner program operations metrics". Never put a company name, product name, person, team, customer, partner, or internal project in a query. Show the exact queries and run them only after they say yes. Use what you find only to sharpen your questions and suggestions, and list the pages you used with their links. If they say no, skip this step.

### 4. Interview

Use `interview.md` in this folder. Ask 10 to 15 questions, one at a time, in plain words. Skip any question the job description already answers. Keep short notes of the answers for steps 6, 7, and 9.

### 5. Check what is connected (read only)

Look at the tools available to you in this conversation, without using any of them to change anything:

- Connected services (tool names that start with `mcp__`). Sort each one into read actions (search, get, list, read, download, fetch) and write actions (create, update, edit, copy, move, share, trash, delete, send, post, comment, transition, upload, invite, or anything else that changes data or reaches another person). When unsure, treat it as a write action.
- Pass every write action name to `ja settings deny <name> <name> ...`. The settings file blocks them for good; this is what keeps the assistant to drafts only.
- Check, without installing anything, which of these are present: git, python3, uv. Use `command -v`.
- If the person mentions the Claude desktop app, tell them they can open the assistant there too and drag screenshots into the chat.

Tell them in one or two sentences what you can read, and that you blocked changes so you only ever prepare drafts.

### 6. Record the tools they already look after

Ask: "Do you look after anything someone else built? For example a spreadsheet with formulas, a small program, a web page, a scheduled report, or a regular data pull." For each one, ask (one at a time, skipping what you already know): where it lives, how it is run, what goes in, what comes out, how often it runs, and when it last worked. Do not run it now.

For each, write a record file in the inbox folder (for example `inbox/setup-<id>.yaml`) with these fields, then run `ja tool add --from <file>` and delete the file:

- `id` (lowercase words joined by hyphens), `name` (their words), `does` (one sentence)
- `examples`: two or three plain phrases they might say to run it
- `kind: adopted`, `status: draft-not-checked`
- `rhythm`: on-demand, daily, weekly, monthly, or quarterly
- `data_path`: where its input comes from, in plain words
- `manual_steps`: the steps they do by hand to get the input, in their words
- `confidential`: true if it touches anything confidential
- `lives_at`, `how_to_run`, `inputs`, `outputs`, `last_good_run`

### 7. Write the role card, sources, and starting knowledge

- Fill `role-card-template.md` from the job description and the interview. Keep it under 250 words. Show it to them and ask: "Did I get your role right?" Make their changes, save it to a file in the inbox folder, run `ja role set --file <file>`, then delete the file.
- For each main document or data set their work depends on, run `ja sources add --id <id> --name "<name>" --kind living|fixed --where "<where it lives>" --access connector|file`. Use `living` for documents that change and `fixed` for ones that do not. Use `--access connector` when you read it through a connected service, otherwise `--access file` with `--exported <date>` for the copy they gave you.
- Add facts they told you that later work depends on to `assistant/knowledge.md`, one per line, each ending with its source or "per <their name>, <today's date>".

### 8. Offer the shortcut

Run `ja launcher` to see what it would write. Ask: "Would you like a shortcut that opens your assistant with one click? It adds two small files to your computer and changes nothing else." On yes, run `ja launcher --yes` and tell them where to find it. On no, tell them how to open the assistant folder next time.

### 9. Close with first automations

Rank three to five first automations from what costs them the most time or worry. For each give:

- one plain sentence on what it would do for them,
- the words to say, such as: "automate this: the weekly status summary",
- how to give an example: drop the file in the inbox folder, or drag a screenshot into the chat.

Then run `ja dashboard` and tell them: "Say 'show my tools' any time to see your tools page." Remind them to open the assistant from the shortcut next time so it starts in their folder.
