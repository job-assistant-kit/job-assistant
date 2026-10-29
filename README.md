# Job Assistant

Job Assistant turns the repeated parts of a job into tools you can use by asking in plain words. You show it one real example of a task, it builds a tool for that task, checks the tool on your example, and keeps it for next time. It learns from your corrections, and it keeps every result a draft until you send it yourself.

It works inside Claude Code, on a Mac or a Linux computer.

## For the person who installs it

### What the computer needs

- Claude Code, installed and signed in.
- uv, the program that runs the assistant's helper. Install it from https://docs.astral.sh/uv/.
- git, for version history of the assistant folder. Without git the assistant still works, with no history.

### Install

1. Add the kit to Claude Code, from a local copy of this folder or from its git address:

   ```
   claude plugin marketplace add /path/to/job-assistant
   claude plugin marketplace add <git address of this repository>
   ```

   Use one of the two lines. With a local copy, Claude Code reads the kit from that folder, so keep the folder where it is.

2. Install it:

   ```
   claude plugin install job-assistant@job-assistant
   ```

3. Check that `claude plugin list` shows `job-assistant`.

### Update

```
claude plugin marketplace update job-assistant
claude plugin update job-assistant@job-assistant
```

Then close and reopen Claude Code. An update never changes the person's assistant folder: their tools, rules, sources, and files stay as they are.

## For the person who uses it

### The first session

1. Open Claude Code in an empty folder.
2. Say "set me up" and paste or share your job description.
3. The assistant asks where to keep your assistant folder and offers a shortcut that opens it with one click. Say yes to the shortcut.
4. Close the window and open the assistant from the shortcut.
5. The first time the assistant folder opens, Claude Code asks whether you trust this folder. Answer yes. The folder's settings, including the blocks on changes to your other systems and the permission for the assistant's own steps to run without asking, apply only after you say yes.
6. Say "set me up" again. The assistant interviews you one question at a time, notes the tools you already look after, and suggests the first tasks to automate.

Always open the assistant from the shortcut, so it starts in your folder.

### What to say

| Say | What happens |
|---|---|
| "set me up" | Setup: your role, your documents, the tools you already look after |
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

### What it never does

- It never posts, sends, edits, shares, or deletes anything in your other systems. Those actions are blocked by the folder's settings, not just by instructions. It prepares drafts and tells you where to paste them.
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
| `RUNBOOK.md` | How a backup person runs each tool |
| `CLAUDE.md` | The assistant's notes about your role and your tools |
| `assistant/` | Your role, sources, learned rules, and what you taught it |
| `.claude/skills/` | Your tools |
| `archive/` | Retired tools, ready to bring back |
| `data/` | Run records, saved examples, and working files (never in git) |

For maintainers: see `PLUGIN-MAINTENANCE.md`.
