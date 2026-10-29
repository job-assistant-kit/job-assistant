---
name: set-me-up
description: Set up the job assistant for a new person from their job description. Use when the person says "set up my job assistant", "set up my assistant", "here is my job description", or shares a job description and asks for help with their work. Creates their assistant folder, reads their job description, records the tools they already look after, blocks changes to outside systems, and suggests the first tasks to automate. Also use when the person asks to start or stop saving drafts to Google Drive.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Set up my job assistant

You are setting up a job assistant for a business person. They do not know or care how it works. Your job is to understand their work, prepare their assistant folder, and leave them with a short list of first things to automate.

## How to behave throughout

- To look at files and folders, use your file reading and search tools, never shell commands. Run the helper lines one at a time, never joined with other commands.
- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command. Do technical steps yourself and tell them the result in one plain sentence.
- Ask one question at a time. Wait for the answer before the next one.
- Never invent facts about their job. If something is unclear, ask or write "unknown".
- Change nothing outside the assistant folder, except the shortcut in step 1 and only after they say yes.
- Never post, send, share, edit, or delete anything in another system. Read only. The one exception is creating the drafts folder in step 4, after they say yes.

## The helper

Every step below that changes the folder uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Inside the assistant folder the helper finds the folder by itself. The helper prints plain sentences; read them and pass the meaning on in your own words. If it reports a problem, fix the cause and try again, or explain it plainly.

When a step says to write a file into the inbox folder, write it with your file tools. The helper removes it after it has used it. Never delete files yourself.

## Steps

Setup asks as little as it can. You learn the rest of their work later, one task at a time, when they ask you to automate something. Do not interview them about their week, their time, or their audiences here.

### 1. Find or create the assistant folder

Run `ja tools`. If it lists tools or says there are none yet, you are inside the assistant folder. If the role in the notes is already filled in, ask whether they want to start over or update parts of it, and skip what they do not want redone. Then go on to step 2.

If it answers that it could not find the assistant folder, this conversation is not running inside one yet. Do this, then stop:

1. Say: "I'll keep your assistant in a folder called job-assistant in your home folder. Tell me if you want it somewhere else." Use their answer if they give one.
2. Run `ja init <folder> --name "<First name>'s Assistant"` (use the plain default if you do not know their name yet). Say where the folder is in one sentence.
3. Run `ja --workspace "<folder>" launcher` to see what the shortcut would add. Ask: "Would you like a shortcut that opens your assistant with one click? It adds two small files to your computer and changes nothing else." On yes, run `ja --workspace "<folder>" launcher --yes` and tell them where to find it. On no, tell them the assistant must be started from inside that folder, and offer the shortcut again as the easy way.
4. Say: "Please close this window and open your assistant from the shortcut. Then say 'set up my job assistant' again and we will continue from here." The protections for their work only apply inside the assistant folder, so do not continue setup in this window.

Show them nothing technical.

### 2. Get the job description

Ask them to paste it, share the file, or give a link. For a link: if you can read it through a connected service, read it (read only). Otherwise ask them to save the file into the inbox folder inside their assistant folder, then read it from there. Read any other documents the job description points to the same way.

If the job description does not say what work recurs (what they produce, how often, and for whom), ask up to three of these, one at a time, and no more:

- "What do you do every week without fail?"
- "What takes most of your time?"
- "Which of your work goes to leaders or onto published pages?"

### 3. Check what is connected (read only)

Look at the tools available to you in this conversation, without using any of them to change anything:

- Connected services (tool names that start with `mcp__`). Sort each one into read actions (search, get, list, read, download, fetch) and write actions (create, update, edit, copy, move, share, trash, delete, send, post, comment, transition, upload, invite, or anything else that changes data or reaches another person). When unsure, treat it as a write action.
- Pass every write action name to `ja settings deny <name> <name> ...`. The settings file blocks them; this is what keeps the assistant to drafts only.
- Run `ja env` to see which needed programs are installed. Install nothing. If one is missing, tell them in one plain sentence what will not work yet.
- If the person mentions the Claude desktop app, tell them they can open the assistant there too and drag screenshots into the chat.

Tell them in one or two sentences what you can read, and that changes to their other systems are blocked whenever you open the assistant from its shortcut, so you only ever prepare drafts.

### 4. Drafts folder in Drive (optional)

Skip this step without mentioning Drive when `ja env` in step 3 said claude.ai connectors are not available; the drafts folder cannot work there. Otherwise do it only when Google Drive is connected: some tool names contain `Google_Drive`. The Drive create action is blocked, and so hidden from you, until step 1 below unblocks it, so do not judge by whether you can see it. If no Drive tools are connected, say in one sentence: "If you connect Google Drive in your Claude account settings later, I can save the drafts you approve into a private folder there. Just say 'save my drafts to Drive'." Then go on to step 5.

Ask: "Would you like me to save each result you approve into a private folder in your Google Drive? You would find every draft there, ready to open and share yourself. I can only add new files to that one folder. I cannot change, share, or delete anything in your Drive."

On yes:

1. Run `ja drive start`. It prints the folder's details, and the Drive create action becomes available.
2. Create the folder with the Drive create action, using exactly the title, contentMimeType, and inheritedPermissionsDisabled it printed, with no parentId and no content.
3. Read the new folder's permissions with the Drive read action for permissions. The folder is private when the only person with access is them.
4. Run `ja drive set --folder <folder id> --private yes` (or `--private no` when anyone else has access), adding `--link <link>` when the create action returned a link.
5. Tell them where the folder is, with its link.

If they would rather use a folder they already have, ask for its link, read its permissions, and run the `ja drive set` line above with that link. If any step fails, run `ja drive off` and tell them in one sentence that drafts stay in the assistant folder for now.

On no, run `ja drive off`.

When they later ask to stop saving drafts to Drive, run `ja drive off`. When they ask to start, do this step.

### 5. Record the tools they already look after

For each tool the job description says they look after or are taking over from someone else (a program, a pipeline, a spreadsheet with formulas, an app, a scheduled report), write a record file in the inbox folder (for example `inbox/setup-<id>.yaml`) and run `ja tool add --from <file>`. Use what the job description says, and write "unknown" for what it does not say:

- `id` (lowercase words joined by hyphens), `name` (their words), `does` (one sentence)
- `examples`: two or three plain phrases they might say to run it
- `kind: adopted`, `status: draft-not-checked`
- `rhythm`: your best guess; `data_path`: where its input comes from, or "unknown"
- `assumed`: the fields you guessed, from rhythm, data_path, manual_steps, your_minutes_by_hand, confidential, exec_numbers
- `confidential`: true if the job description suggests it touches anything confidential
- `lives_at`, `how_to_run`, `inputs`, `outputs`, `last_good_run`: what the job description says, else "unknown"

Then ask one question: "Do you look after anything else that someone else built? And who built the ones I found, in case we need them?" Record any new ones the same way. Save who built each one with `ja knowledge add --fact "<tool name> was built by <person>" --source "per <their name>, <today's date>"`. Do not run any of them now.

### 6. Write the role card, sources, and starting knowledge

- Fill `role-card-template.md` from the job description. Keep it under 250 words. Write "unknown, I will fill this in as we work" for parts it does not cover. Show it and ask: "Did I get your role right?" Make their changes, save it to a file in the inbox folder, and run `ja role set --file <file>`.
- Add only the documents and data that the first automations in step 7 will read, at most six, with `ja sources add --id <id> --name "<name>" --kind living|fixed --where "<where it lives>" --access connector|file`. Use `living` for documents that change and `fixed` for ones that do not. Use `--access connector` when you read it through a connected service, otherwise `--access file`, with `--exported <date>` only when they gave you a copy. Other documents are added when a tool first reads them.
- Add facts the job description states that later work depends on with `ja knowledge add --fact "<fact>" --source "job description, <today's date>"`.

### 7. Close with the getting-started page

Rank three to five first automations from the job description: recurring work first, then work that goes to leaders, then what it calls painful or manual.

Write `inbox/getting-started.yaml` with these parts, in plain words, and run `ja start set --file inbox/getting-started.yaml`:

- `reach`: one or two sentences on what you can and cannot read, from step 3, and that changes to their other systems are blocked so you only prepare drafts.
- `recorded`: short lines on what you recorded: the tools they look after (by name), how many sources, the role card, and how many facts.
- `gaps`: things only they can sort out, such as access, an ownership handover, or a missing document for a tool they look after. Leave it empty if there are none.
- `first`: the ranked automations. Each has `name`, `does` (one plain sentence), `say` (the words, such as "automate this: the weekly status summary"), and `give` (the example to drop in the inbox, or a screenshot to drag into the chat).

Then close with three short lines, and nothing else:

1. "You're set up. Everything is on your getting-started page: <the link the helper printed>."
2. "When you're ready, pick whichever first automation takes most of your time, drop an example in the inbox, and say 'automate this'. I'll ask the few things I need as we go."
3. "Open the assistant from the shortcut each time, so the protections are on."

Do not repeat the page's content in the chat.
