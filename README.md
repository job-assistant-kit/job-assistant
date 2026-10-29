# Job Assistant

Job Assistant turns the repeated parts of a job into tools you can use by asking in plain words. You show it one real example of a task, it builds a tool for that task, checks the tool on your example, and keeps it for next time. It learns from your corrections, and it keeps every result a draft until you send it yourself.

It works inside Claude Code, on a Mac or a Linux computer.

## For the person who installs it

### What the computer needs

- Claude Code, installed and signed in. Version 2.1.295 or later is best: older versions ask before each save to Drive if the Drive check fails to run.
- uv, the program that runs the assistant's helper. Install it from https://docs.astral.sh/uv/.
- git, for version history of the assistant folder. Without git the assistant still works, with no history.
- Optional: Google Drive connected in your claude.ai account settings (Connectors), for the drafts folder in Drive. This works only when Claude Code signs in with a claude.ai account. When it signs in through Google Vertex AI, Amazon Bedrock, or an API key, connectors do not appear and drafts stay in the assistant folder.

### Install

1. Add the kit to Claude Code:

   ```
   claude plugin marketplace add job-assistant-kit/job-assistant
   ```

   The repository is private. The person needs read access to it, and git on their computer must be signed in to GitHub (for example with `gh auth login` and `gh auth setup-git`). To use a local copy instead, run `claude plugin marketplace add /path/to/job-assistant` and keep the folder where it is.

2. Install it:

   ```
   claude plugin install job-assistant@job-assistant
   ```

3. Check that `claude plugin list` shows `job-assistant`, then start a new Claude session. If you installed or updated from inside a running session, run `/reload-plugins` there instead.

### Update

```
claude plugin marketplace update job-assistant
claude plugin update job-assistant@job-assistant
```

Then start a new session, or run `/reload-plugins` in an open one.

Then close and reopen Claude Code. An update never changes the person's assistant folder: their tools, rules, sources, and files stay as they are.

## For the person who uses it

### The first session

1. Open Claude Code in an empty folder.
2. Say "set up my job assistant" and paste or share your job description.
3. The assistant asks where to keep your assistant folder and offers a shortcut that opens it with one click. Say yes to the shortcut.
4. Close the window and open the assistant from the shortcut.
5. The first time the assistant folder opens, Claude Code asks whether you trust this folder. Answer yes. The folder's settings, including the blocks on changes to your other systems and the permission for the assistant's own steps to run without asking, apply only after you say yes.
6. Say "set up my job assistant" again. The assistant reads your job description, asks two or three questions, notes the tools you already look after, and suggests the first tasks to automate. It learns the rest as you work: when you ask it to automate something, it asks only what it does not know yet, and remembers the answers.

Always open the assistant from the shortcut, so it starts in your folder.

### What to say

| Say | What happens |
|---|---|
| "set up my job assistant" | Setup: your role, your documents, the tools you already look after |
| "automate this" with a file, screenshot, link, or pasted text | A new tool, built and checked on your example |
| The words a tool lists, such as "check this brief" | The tool runs |
| "this broke" or "this gave the wrong answer" | The assistant finds the cause and explains it plainly |
| "that was wrong", "change it so ...", "always", "never" | The assistant learns the correction, after checking it does not spoil earlier results |
| "what have you learned?" or "forget that" | Shows or removes what it learned |
| "is this number safe to send?" | Number sign-off: compared with the last published number and checked against the method |
| "show my tools" or "what can you do for me?" | Opens your tools page and lists your tools |
| "anything I should know?" | Up to three things that need your attention, such as a tool that is due |
| "clean my inbox" | Lists inbox files older than 30 days and deletes them only on your yes |
| "retire" or "bring back" with a tool's name | Puts a tool away or brings it back |
| "save my drafts to Drive" or "stop saving to Drive" | Turns the private drafts folder in your Google Drive on or off |

### What it never does

- It never posts, sends, edits, shares, or deletes anything in your other systems. Those actions are blocked by the folder's settings, not just by instructions. It prepares drafts and tells you where to paste them. The one exception, if you turn it on during setup: it saves each result you approve as a new file in one private drafts folder in your Google Drive. A separate check refuses any other place, and it still cannot change, share, or delete anything there.
- It never writes outside your assistant folder, except the shortcut, and only after you say yes.
- It never puts internal names in a web search. Searches use general role words only, and it shows you the searches before running them.
- It never puts your data in version history. Files you drop in, exports, saved examples, and run records stay in the folder on your computer and are left out of git.
- It never calls a number checked. A number for leaders stays "Draft, not checked" until you approve it.

### Where things are

Inside your assistant folder:

| Place | What it holds |
|---|---|
| `inbox/` | Files you drop in for the assistant |
| `dashboard/index.html` | Your tools page |
| `CLAUDE.md` | The assistant's notes about your role and your tools |
| `assistant/` | Your role, sources, learned rules, and what you taught it |
| `.claude/skills/` | Your tools |
| `archive/` | Retired tools, ready to bring back |
| `data/` | Run records, saved examples, and working files (never in git) |

For maintainers: see `PLUGIN-MAINTENANCE.md`.
