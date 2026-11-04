# Security overview

This page explains how Job Assistant protects a person's work and data, and where those protections stop. It is written for the person who uses the assistant and for anyone who has to approve it.

## In short

Inside its own folder, the assistant can read what the person gives it and write drafts. It cannot send, post, edit, share, or delete anything in the person's other systems. Claude Code settings and the assistant's own code enforce this. It does not rely on instructions alone.

## Where the protections apply

All protections below apply when Claude Code is opened in the assistant folder and the person has answered yes to "Do you trust this folder?". Claude Code reads the folder's settings only after that answer. In any other folder, Claude Code runs with its normal settings and the assistant's skills do not load.

## What it can and cannot do

### Changes to other systems are blocked

The assistant folder holds a settings file, `.claude/settings.json`. Claude Code enforces its deny list: a blocked action cannot run, even when the person asks for it in the chat.

- At install, the list blocks write actions in Google Drive, Jira, Confluence, and Claude Docs, and blocks `git push`.
- During setup, the assistant looks at every connected service, sorts each action into read or write, and adds every write action to the deny list. When unsure, it treats an action as a write. Write means create, update, edit, copy, move, share, delete, send, post, comment, upload, invite, or anything else that changes data or reaches another person.

The assistant prepares drafts and tells the person where to paste them.

### One exception: the Drive drafts folder, if turned on

If the person turns it on, the assistant saves each result they approve as a new file in one Google Drive folder.

- A check runs before every Drive save. It allows a new file only in that one folder and refuses everything else. If the check fails or does not answer in time, the save is blocked.
- Changing, sharing, copying, and deleting in Drive stay blocked.
- When the assistant creates the folder, the folder does not inherit sharing from anywhere. The assistant then reads the folder's permissions and records whether only the person has access.

### Few things run without asking

Only two commands run without a prompt: the assistant's own helper and `git status`. Any other command asks the person first. So does any connector action that is not blocked. Edits outside the assistant folder also ask first.

### Code the assistant writes runs inside a guard

When the assistant builds a tool, the step that computes facts and numbers is Python code it writes. That code runs inside a guard (a Python audit hook: a check Python calls before sensitive actions). The guard refuses these actions the moment they are attempted:

- Opening a network connection.
- Starting another program.
- Loading native code.
- Creating, changing, or deleting a file.
- Reading a file outside the assistant folder and the files it was given.

Once the guard is on, the code cannot turn it off or add a hook of its own. A refused action stops the run and says what was attempted.

### The kit adds no connectors

The assistant uses only the services the person has already connected. When a connector would help, it suggests one, and installing it is the person's choice. The kit never gives the assistant new access.

## How it protects confidential information

### It decides for each tool whether the tool is confidential

Each tool records whether its work is confidential. The assistant decides this every time it builds a tool:

- It treats the task as confidential, and says so, when the task reads a source that an existing confidential tool already reads, or when its notes say this kind of document is confidential.
- Otherwise it asks: "Does this contain anything confidential, such as unannounced offerings, partners, or pricing?"
- It never saves a "not confidential" answer for later. The question comes up again for the next tool.

If a guess about a tool turns out wrong, the person can correct it, and the assistant updates the tool.

### Confidential results never go to a shared Drive folder

When the drafts folder is shared with anyone else, results from confidential tools are not saved there. They stay in the assistant folder, and the assistant says why.

### Confidential details stay out of the notes

The role card (the short description of the person's job that the assistant keeps) leaves out confidential details such as unannounced offerings, partner names, and pricing. It lists confidential topics only in general words, as topics to keep out of searches and drafts.

When a tool rewrites content for a different audience, the assistant checks with the person before including anything confidential for an outside audience.

### The person's files stay on their computer

- Files the person drops in, exports, screenshots, saved examples, run records, and the tools page stay in the assistant folder, on the person's computer.
- The assistant's rules forbid putting those files in git, in a web search, or in a message to anyone.
- Those folders (`inbox/`, `data/`, `dashboard/`) are excluded from git version history.
- Version history stays on the computer: `git push` is blocked, so nothing in it is sent anywhere.

What git does track: the assistant's notes (`CLAUDE.md`), the role card, sources list, learned rules and facts (`assistant/`), and the tools (`.claude/skills/`).

## Checks that keep results honest

- Every date, number, or policy claim names its source, or says "unknown".
- A number meant for leaders or a published page stays marked "Draft, not checked" until the person approves it. The sign-off compares it with the last published number and flags a change over 15%.
- A correction the person teaches becomes a rule only after the assistant reruns earlier results and confirms the rule does not break them.

## Limits

These are the limits of the protections, stated plainly:

- **The model sees the content.** Everything the person shares in a session goes to the model that Claude Code uses, under the person's existing account and its data terms. The kit does not change where that content goes, and it adds no new destination.
- **Protections need the right folder.** They apply only in the assistant folder after the trust answer. Opening Claude Code anywhere else removes them.
- **The deny list is a list of action names.** It blocks the write actions found at setup and the fixed set above. A service connected after setup can add write actions that are not on the list. Those still ask before running, because only the helper and `git status` run without asking, but they are not blocked outright.
- **The confidential flag is a judgment.** It comes from the person's answer or from the assistant's notes. It controls where results may be saved. It does not encrypt anything.
- **The code guard is in-process.** It is strong against mistakes in code the assistant writes. It is not an operating-system sandbox and is not built to stop a determined attacker.
- **Files on disk are as safe as the computer.** The assistant folder relies on the computer's own sign-in and disk encryption.
- **No outside audit.** The design and code had their own security reviews during the build. No independent party has audited them.
