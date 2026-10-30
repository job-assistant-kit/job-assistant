#!/usr/bin/env bash
# Installs Job Assistant, creates the assistant folder and its shortcut, and opens the
# first session. Run it again at any time to update: it keeps the folder as it is.
#
#   bash install.sh [--folder PATH] [--source PATH] [--app desktop|terminal] [--no-start] [--yes]
#
#   --folder PATH   where to keep the assistant folder (default: ~/job-assistant)
#   --source PATH   install from a local copy of the kit instead of GitHub
#   --app WHERE     open the assistant in the Claude desktop app or in a terminal
#                   (default: ask on a Mac with the Claude app, else terminal)
#   --no-start      stop when everything is ready, without opening the first session
#   --yes           answer yes to every question (the first name stays the default)
set -euo pipefail

REPO="job-assistant-kit/job-assistant"
MARKETPLACE="job-assistant"
PLUGIN="job-assistant@job-assistant"
BEST_CLAUDE="2.1.295"

folder="$HOME/job-assistant"
source_dir=""
start=1
assume_yes=0
app=""

while [ $# -gt 0 ]; do
  case "$1" in
    --folder) folder="${2:?--folder needs a path}"; shift 2 ;;
    --source) source_dir="${2:?--source needs a path}"; shift 2 ;;
    --no-start) start=0; shift ;;
    --yes) assume_yes=1; shift ;;
    --app) app="${2:?--app needs desktop or terminal}"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1. Run with --help to see the options." >&2; exit 2 ;;
  esac
done

case "$app" in ""|desktop|terminal) ;; *) echo "--app must be desktop or terminal." >&2; exit 2 ;; esac

# shellcheck disable=SC2088  # matches a literal ~ the person typed in quotes
case "$folder" in "~"|"~/"*) folder="$HOME${folder#\~}" ;; esac

# Questions read the keyboard, so the script also works when it arrives through a pipe.
tty_in=/dev/stdin
if (exec </dev/tty) 2>/dev/null; then tty_in=/dev/tty; fi

say() { printf '%s\n' "$*"; }
step() { printf '\n== %s ==\n' "$*"; }
stop() { printf '\n%s\n' "$*" >&2; exit 1; }

ask_yes() {  # ask_yes "Question?"  -> 0 for yes (the default), 1 for no
  [ "$assume_yes" = 1 ] && return 0
  local answer
  printf '%s [Y/n] ' "$1"
  read -r answer <"$tty_in" || answer=""
  case "$answer" in [nN]*) return 1 ;; *) return 0 ;; esac
}

older_than() {  # older_than 2.1.280 2.1.295  -> 0 when the first version is older
  local -a a b
  local i
  IFS=. read -r -a a <<<"$1"
  IFS=. read -r -a b <<<"$2"
  for i in 0 1 2; do
    if [ "${a[i]:-0}" -lt "${b[i]:-0}" ]; then return 0; fi
    if [ "${a[i]:-0}" -gt "${b[i]:-0}" ]; then return 1; fi
  done
  return 1
}

say "This sets up Job Assistant on this computer. It takes a few minutes."

step "1 of 6: Claude Code"
command -v claude >/dev/null 2>&1 || stop "Claude Code is not installed. Install it and sign in
(https://docs.claude.com/en/docs/claude-code/setup), then run this again."
claude_version="$(claude --version 2>/dev/null | awk '{print $1}')"
say "Claude Code $claude_version is installed."
if [[ "$claude_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] && older_than "$claude_version" "$BEST_CLAUDE"; then
  say "Version $BEST_CLAUDE or later works best. To update, run: claude update"
fi

step "2 of 6: git and uv"
if ! git --version >/dev/null 2>&1; then
  if [ "$(uname -s)" = Darwin ]; then
    xcode-select --install >/dev/null 2>&1 || true
    stop "git is not installed. A window may have opened to install the Mac developer tools.
Finish that install, then run this again."
  fi
  stop "git is not installed. Install it with your system's package manager
(for example: sudo dnf install git), then run this again."
fi
say "git is installed."
if ! command -v uv >/dev/null 2>&1; then
  ask_yes "Job Assistant needs uv, a small program that runs its helper. Install uv now?" ||
    stop "Job Assistant cannot run without uv. Install it from https://docs.astral.sh/uv/ and run this again."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || stop "uv did not install. Install it from https://docs.astral.sh/uv/ and run this again."
fi
say "uv is installed."

step "3 of 6: access to the kit"
if [ -n "$source_dir" ]; then
  source_dir="$(cd "$source_dir" && pwd)" || stop "The folder $source_dir does not exist."
  [ -f "$source_dir/.claude-plugin/marketplace.json" ] || stop "$source_dir is not a copy of the Job Assistant kit."
  say "Using the local copy at $source_dir."
  market_source="$source_dir"
else
  market_source="$REPO"
  can_read() { GIT_TERMINAL_PROMPT=0 git ls-remote "https://github.com/$REPO.git" HEAD >/dev/null 2>&1; }
  if ! can_read; then
    if ! command -v gh >/dev/null 2>&1; then
      if [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null 2>&1 &&
         ask_yes "The kit is in a private GitHub repository. Install the GitHub sign-in tool (gh) now?"; then
        brew install gh
      else
        stop "The kit is in a private GitHub repository, and this computer is not signed in to GitHub.
Install the GitHub sign-in tool from https://cli.github.com (for example: sudo dnf install gh),
then run this again."
      fi
    fi
    if ! gh auth status --hostname github.com >/dev/null 2>&1; then
      say "Sign in to GitHub. A browser window opens; follow the steps there."
      gh auth login --hostname github.com --git-protocol https --web <"$tty_in"
    fi
    gh auth setup-git --hostname github.com
    can_read || stop "Your GitHub account cannot see the kit yet. Ask the person who shared it
to give your account read access to $REPO, then run this again."
  fi
  say "This computer can read the kit on GitHub."
fi

step "4 of 6: install the assistant"
if claude plugin marketplace list 2>/dev/null | grep -qE "^[^[:alnum:]]*${MARKETPLACE}\$"; then
  claude plugin marketplace update "$MARKETPLACE" >/dev/null
else
  claude plugin marketplace add "$market_source" >/dev/null
fi
plugin_json() { claude plugin list --json 2>/dev/null; }
installed_path() {
  plugin_json | uv run --quiet --no-project python -c '
import json, sys
for p in json.load(sys.stdin):
    if p.get("id") == sys.argv[1] and p.get("scope") == "user":
        print(p["installPath"]); break' "$PLUGIN"
}
if [ -n "$(installed_path)" ]; then
  claude plugin update "$PLUGIN" >/dev/null
else
  claude plugin install "$PLUGIN" >/dev/null
fi
root="$(installed_path)"
[ -n "$root" ] && [ -f "$root/scripts/ja.py" ] || stop "The assistant did not install. Run this again; if it fails twice,
send the person who shared the kit the output above."
say "Job Assistant $(basename "$root") is installed."

ja() { uv run --quiet --script "$root/scripts/ja.py" "$@"; }

step "5 of 6: your assistant folder"
new_folder=0
if ja --workspace "$folder" tools >/dev/null 2>&1; then
  say "Your assistant folder is already at $folder. Everything in it stays as it is."
else
  if [ -e "$folder" ] && [ -n "$(ls -A "$folder" 2>/dev/null)" ]; then
    stop "$folder already has other files in it. Run this again with --folder and a new folder,
for example: bash install.sh --folder ~/my-assistant"
  fi
  new_folder=1
  first=""
  if [ "$assume_yes" = 0 ]; then
    printf 'What is your first name? It names your assistant. (Press Enter to skip) '
    read -r first <"$tty_in" || first=""
  fi
  if [ -n "$first" ]; then ja init "$folder" --name "$first's Assistant"; else ja init "$folder"; fi
fi

step "6 of 6: how you open your assistant"
has_desktop_app() {
  [ "$(uname -s)" = Darwin ] && { [ -d /Applications/Claude.app ] || [ -d "$HOME/Applications/Claude.app" ]; }
}
if [ -z "$app" ]; then
  app=terminal
  if has_desktop_app && ask_yes "You have the Claude desktop app. Use your assistant there? (No uses a terminal window.)"; then
    app=desktop
  fi
fi

if [ "$app" = desktop ]; then
  if [ "$start" = 1 ] && [ "$(uname -s)" = Darwin ]; then
    open -a Claude 2>/dev/null || true
  fi
  say ""
  if [ "$new_folder" = 1 ]; then
    say "Everything is installed. In the Claude app:"
    say "  1. Open Code and choose Open folder."
    say "  2. Pick $folder."
    say "  3. If it asks whether you trust the folder, choose Yes."
    say "  4. Say \"set up my job assistant\" and paste your job description."
  else
    say "Everything is up to date. In the Claude app, open Code with $folder as usual."
    say "If the app was open during the update, start a new session so it uses the new version."
  fi
  exit 0
fi

open_it="from the shortcut"
if ask_yes "Add a shortcut that opens your assistant with one click? It adds two small files and changes nothing else."; then
  ja --workspace "$folder" launcher --yes
else
  open_it="by starting Claude Code inside $folder"
  say "No shortcut. Open your assistant $open_it."
fi

if [ "$start" = 0 ]; then
  say ""
  if [ "$new_folder" = 1 ]; then
    say "Everything is ready. Open your assistant $open_it and say \"set up my job assistant\"."
  else
    say "Everything is up to date. Open your assistant $open_it as usual."
  fi
  exit 0
fi

# Claude Code must inherit the terminal as it is. Handing it a newly opened /dev/tty crashes it
# on macOS, so when this script arrived through a pipe, say how to open it instead.
if [ ! -t 0 ]; then
  say ""
  say "Everything is ready. To start, run: cd \"$folder\" && claude"
  [ "$new_folder" = 1 ] && say "Then say \"set up my job assistant\" and paste your job description."
  exit 0
fi

say ""
cd "$folder"
if [ "$new_folder" = 0 ]; then
  say "Everything is up to date. Claude Code now opens in your assistant folder."
  exec claude
fi
say "Everything is installed. Claude Code now opens in your assistant folder."
say "When it asks whether you trust this folder, choose Yes. Then paste your job description."
exec claude "set up my job assistant"
