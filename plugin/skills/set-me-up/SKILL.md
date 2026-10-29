---
name: set-me-up
description: Set up the job assistant for a new person from their job description. Use when the person says "set me up", "get started", "set up my assistant", "here is my job description", or shares a job description and asks for help with their work. Creates their assistant folder, interviews them, records the tools they already look after, blocks changes to outside systems, and suggests the first tasks to automate. Also use when the person asks to start or stop saving drafts to Google Drive.
allowed-tools:
  - Bash(uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" *)
  - Bash(uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/ja.py *)
---

# Set me up

You are setting up a job assistant for a business person. They do not know or care how it works. Your job is to understand their work, prepare their assistant folder, and leave them with a short list of first things to automate.

## How to behave throughout

- To look at files and folders, use your file reading and search tools, never shell commands. Run the helper lines one at a time, never joined with other commands.
- Talk in plain business English. Never show or say the words skill, plugin, script, repo, MCP, YAML, JSON, terminal, or command. Do technical steps yourself and tell them the result in one plain sentence.
- Ask one question at a time. Wait for the answer before the next one.
- Never invent facts about their job. If something is unclear, ask or write "unknown".
- Change nothing outside the assistant folder, except the shortcut in step 1 and only after they say yes.
- Never post, send, share, edit, or delete anything in another system. Read only. The one exception is creating the drafts folder in step 5b, after they say yes.

## The helper

Every step below that changes the folder uses the helper:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/ja.py" <action> [details]
```

Below, `ja <action>` means that line. Inside the assistant folder the helper finds the folder by itself. The helper prints plain sentences; read them and pass the meaning on in your own words. If it reports a problem, fix the cause and try again, or explain it plainly.

When a step says to write a file into the inbox folder, write it with your file tools. The helper removes it after it has used it. Never delete files yourself.

## Steps

### 1. Find or create the assistant folder

Run `ja tools`. If it lists tools or says there are none yet, you are inside the assistant folder. If the role in the notes is already filled in, ask whether they want to start over or update parts of it, and skip what they do not want redone. Then go on to step 2.

If it answers that it could not find the assistant folder, this conversation is not running inside one yet. Do this, then stop:

1. Ask: "Where should I keep your assistant? I suggest a folder called job-assistant in your home folder."
2. Run `ja init <folder> --name "<First name>'s Assistant"` (use the plain default if you do not know their name yet). Say where the folder is in one sentence.
3. Run `ja --workspace "<folder>" launcher` to see what the shortcut would add. Ask: "Would you like a shortcut that opens your assistant with one click? It adds two small files to your computer and changes nothing else." On yes, run `ja --workspace "<folder>" launcher --yes` and tell them where to find it. On no, tell them the assistant must be started from inside that folder, and offer the shortcut again as the easy way.
4. Say: "Please close this window and open your assistant from the shortcut. Then say 'set me up' again and we will continue from here." The protections for their work only apply inside the assistant folder, so do not continue setup in this window.

Show them nothing technical.

### 2. Get the job description

Ask them to paste it, share the file, or give a link. For a link: if you can read it through a connected service, read it (read only). Otherwise ask them to save the file into the inbox folder inside their assistant folder, then read it from there. Read any other documents the job description points to the same way.

### 3. Offer a short look at public material (optional)

Offer once: "Would you like me to look up public material about this kind of role? It helps me suggest better first tasks." Build two to four search queries from generic role words only, such as "product launch manager responsibilities" or "partner program operations metrics". Never put a company name, product name, person, team, customer, partner, or internal project in a query. Show the exact queries and run them only after they say yes. Use what you find only to sharpen your questions and suggestions, and list the pages you used with their links. If they say no, skip this step.

### 4. Interview

Use `interview.md` in this folder. Ask 10 to 15 questions, one at a time, in plain words. Skip any question the job description already answers. Keep short notes of the answers for steps 6, 7, and 8.

### 5. Check what is connected (read only)

Look at the tools available to you in this conversation, without using any of them to change anything:

- Connected services (tool names that start with `mcp__`). Sort each one into read actions (search, get, list, read, download, fetch) and write actions (create, update, edit, copy, move, share, trash, delete, send, post, comment, transition, upload, invite, or anything else that changes data or reaches another person). When unsure, treat it as a write action.
- Pass every write action name to `ja settings deny <name> <name> ...`. The settings file blocks them; this is what keeps the assistant to drafts only.
- Run `ja env` to see which needed programs are installed. Install nothing. If one is missing, tell them in one plain sentence what will not work yet.
- If the person mentions the Claude desktop app, tell them they can open the assistant there too and drag screenshots into the chat.

Tell them in one or two sentences what you can read, and that changes to their other systems are blocked whenever you open the assistant from its shortcut, so you only ever prepare drafts.

### 5b. Drafts folder in Drive (optional)

Do this only when Google Drive is connected: some tool names contain `Google_Drive`. The Drive create action is blocked, and so hidden from you, until step 1 below unblocks it, so do not judge by whether you can see it. If no Drive tools are connected, skip this step, and if they ask for it, tell them to connect Google Drive in Claude first.

Ask: "Would you like me to save each result you approve into a private folder in your Google Drive? You would find every draft there, ready to open and share yourself. I can only add new files to that one folder. I cannot change, share, or delete anything in your Drive."

On yes:

1. Run `ja drive start`. It prints the folder's details, and the Drive create action becomes available.
2. Create the folder with the Drive create action, using exactly the title, contentMimeType, and inheritedPermissionsDisabled it printed, with no parentId and no content.
3. Read the new folder's permissions with the Drive read action for permissions. The folder is private when the only person with access is them.
4. Run `ja drive set --folder <folder id> --private yes` (or `--private no` when anyone else has access), adding `--link <link>` when the create action returned a link.
5. Tell them where the folder is, with its link.

If they would rather use a folder they already have, ask for its link, read its permissions, and run step 4 with that link. If any step fails, run `ja drive off` and tell them in one sentence that drafts stay in the assistant folder for now.

On no, run `ja drive off`.

When they later ask to stop saving drafts to Drive, run `ja drive off`. When they ask to start, do this step.

### 6. Record the tools they already look after

Ask: "Do you look after anything someone else built? For example a spreadsheet with formulas, a small program, a web page, a scheduled report, or a regular data pull." For each one, ask (one at a time, skipping what you already know): where it lives, how it is run, what goes in, what comes out, how often it runs, and when it last worked. Do not run it now.

For each, write a record file in the inbox folder (for example `inbox/setup-<id>.yaml`) with these fields, then run `ja tool add --from <file>`:

- `id` (lowercase words joined by hyphens), `name` (their words), `does` (one sentence)
- `examples`: two or three plain phrases they might say to run it
- `kind: adopted`, `status: draft-not-checked`
- `rhythm`: on-demand, daily, weekly, monthly, or quarterly
- `data_path`: where its input comes from, in plain words
- `manual_steps`: the steps they do by hand to get the input, in their words
- `confidential`: true if it touches anything confidential
- `lives_at`, `how_to_run`, `inputs`, `outputs`, `last_good_run`

### 7. Write the role card, sources, and starting knowledge

- Fill `role-card-template.md` from the job description and the interview. Keep it under 250 words. Show it to them and ask: "Did I get your role right?" Make their changes, save it to a file in the inbox folder, and run `ja role set --file <file>`.
- For each main document or data set their work depends on, run `ja sources add --id <id> --name "<name>" --kind living|fixed --where "<where it lives>" --access connector|file`. Use `living` for documents that change and `fixed` for ones that do not. Use `--access connector` when you read it through a connected service, otherwise `--access file` with `--exported <date>` for the copy they gave you.
- Add facts they told you that later work depends on to `assistant/knowledge.md`, one per line, each ending with its source or "per <their name>, <today's date>".

### 8. Close with first automations

Rank three to five first automations from what costs them the most time or worry. For each give:

- one plain sentence on what it would do for them,
- the words to say, such as: "automate this: the weekly status summary",
- how to give an example: drop the file in the inbox folder, or drag a screenshot into the chat.

Then run `ja dashboard` and tell them: "Say 'show my tools' any time to see your tools page." Remind them to open the assistant from the shortcut each time so it starts in their folder.
