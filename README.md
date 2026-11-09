# Job Assistant

> **Status:** Version 0.2.3 runs end to end from a fresh clone, with 563 passing tests. The kit is in real user testing with one tester; findings from that testing are open and the interface will change. Maintained.

Job Assistant turns the repeated parts of a job into tools you can use by asking in plain words. You show it one real example of a task, it builds a tool for that task, checks the tool on your example, and keeps it for next time. It learns from your corrections, and it keeps every result a draft until you send it yourself.

It works inside Claude Code, on a Mac or a Linux computer: in a terminal, or in the Code section of the Claude desktop app. It does not work in Cowork, which does not load locally installed plugins.

## For the person who installs it

### What the computer needs

- Claude Code, installed and signed in. Version 2.1.295 or later is best: older versions ask before each save to Drive if the Drive check fails to run.
- uv, the program that runs the assistant's helper. Install it from https://docs.astral.sh/uv/.
- git, for version history of the assistant folder. Without git the assistant still works, with no history.
- Optional: Google Drive connected in your claude.ai account settings (Connectors), for the drafts folder in Drive. This works only when Claude Code signs in with a claude.ai account. When it signs in through Google Vertex AI, Amazon Bedrock, or an API key, connectors do not appear and drafts stay in the assistant folder.

### Install

One script does the whole install and opens the first session. It checks for Claude Code and git, installs uv if it is missing, signs in to GitHub if needed, installs the plugin, and creates the assistant folder. On a Mac with the Claude desktop app, it asks whether to use the assistant there; if so, it opens the app and lists the steps to open the folder. Otherwise it adds a shortcut and starts Claude Code in the folder with "set up my job assistant". The Claude Code command line must be installed either way: the script uses it to install the plugin.

Get the script one of two ways:

- Someone who has the kit sends you `install.sh`. Run `bash ~/Downloads/install.sh` (use the folder where you saved it).
- If you are already signed in to GitHub with `gh`, fetch and run it in one command:

  ```
  gh api -H "Accept: application/vnd.github.raw" repos/job-assistant-kit/job-assistant/contents/install.sh | bash
  ```

The script asks at most four things: your first name (to name the assistant), whether to use the desktop app, whether to add the shortcut, and whether to install uv if it is missing. Options: `--folder PATH` keeps the assistant somewhere other than `~/job-assistant`, `--source PATH` installs from a local copy of the kit, `--app desktop` or `--app terminal` answers the desktop app question, `--no-start` stops before opening Claude Code, and `--yes` answers yes to every question.

### Install by hand

1. Add the kit to Claude Code:

   ```
   claude plugin marketplace add job-assistant-kit/job-assistant
   ```

   The repository is public, so this step needs no GitHub sign-in. To use a local copy instead, run `claude plugin marketplace add /path/to/job-assistant` and keep the folder where it is.

2. Install it:

   ```
   claude plugin install job-assistant@job-assistant
   ```

3. Check that `claude plugin list` shows `job-assistant`, then start a new Claude session. If you installed or updated from inside a running session, run `/reload-plugins` there instead.

### Update

Run the install script again. It updates the plugin, keeps the assistant folder as it is, and opens the assistant. By hand:

```
claude plugin marketplace update job-assistant
claude plugin update job-assistant@job-assistant
```

Then start a new session, or run `/reload-plugins` in an open one. An update never changes the person's assistant folder: their tools, rules, sources, and files stay as they are.

## For the person who uses it

### The first session

After the install script, in the Claude desktop app:

1. Open Code, choose Open folder, and pick your assistant folder (`job-assistant` in your home folder).
2. If it asks whether you trust the folder, answer yes.
3. Say "set up my job assistant" and paste or share your job description. Then continue at step 3 below.

Each time after that, start a session in Code with the assistant folder open. The protections apply only there.

After the install script, in a terminal:

1. Claude Code opens in your assistant folder and asks whether you trust this folder. Answer yes. The folder's settings, including the blocks on changes to your other systems and the permission for the assistant's own steps to run without asking, apply only after you say yes.
2. Paste or share your job description when the assistant asks for it.
3. The assistant asks two or three questions, notes the tools you already look after, and opens your tools page in your browser, with your first steps at the top. The browser window may open behind Claude. To open the page again at any time, say "show my tools". It learns the rest as you work: when you ask it to automate something, it asks only what it does not know yet, and remembers the answers.

After an install by hand:

1. Open Claude Code in an empty folder and say "set up my job assistant".
2. The assistant asks where to keep your assistant folder and offers a shortcut that opens it with one click. Say yes to the shortcut.
3. Close the window, open the assistant from the shortcut, answer yes when Claude Code asks whether you trust the folder, and say "set up my job assistant" again. Then continue as above.

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
| "hide getting started" or "show getting started" | Folds the getting-started section on your tools page away, or brings it back |
| "anything I should know?" | Up to three things that need your attention, such as a tool that is due |
| "clean my inbox" | Lists inbox files older than 30 days and deletes them only on your yes |
| "retire" or "bring back" with a tool's name | Puts a tool away or brings it back |
| "save my drafts to Drive" or "stop saving to Drive" | Turns the private drafts folder in your Google Drive on or off |

### What it never does

- It never posts, sends, edits, shares, or deletes anything in your other systems. Those actions are blocked by the folder's settings, not just by instructions. It prepares drafts and tells you where to paste them. The one exception, if you turn it on during setup: it saves each result you approve as a new file in one private drafts folder in your Google Drive. A separate check refuses any other place, and it still cannot change, share, or delete anything there.
- It never writes outside your assistant folder, except the shortcut, and only after you say yes.
- It never puts your files, exports, screenshots, or saved examples in a web search.
- It never puts your data in version history. Files you drop in, exports, saved examples, and run records stay in the folder on your computer and are left out of git.
- It never calls a number checked. A number for leaders stays "Draft, not checked" until you approve it.

### Where things are

Inside your assistant folder:

| Place | What it holds |
|---|---|
| `inbox/` | Files you drop in for the assistant |
| `dashboard/index.html` | Your tools page, with the getting-started section at the top |
| `CLAUDE.md` | The assistant's notes about your role and your tools |
| `assistant/` | Your role, sources, learned rules, and what you taught it |
| `.claude/skills/` | Your tools |
| `archive/` | Retired tools, ready to bring back |
| `data/` | Run records, saved examples, and working files (never in git) |

For how it protects your work and confidential information, and where those protections stop, see [`SECURITY-OVERVIEW.md`](SECURITY-OVERVIEW.md).

For maintainers: see `PLUGIN-MAINTENANCE.md`.
