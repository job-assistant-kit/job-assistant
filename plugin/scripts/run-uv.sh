#!/bin/sh
# Runs one of the kit's Python scripts with uv. An app started from the Dock or a menu may not
# have uv's folder on its search path, so this adds the folders uv installers use.
for dir in "$HOME/.local/bin" "$HOME/.cargo/bin" /opt/homebrew/bin /usr/local/bin; do
  case ":$PATH:" in
    *":$dir:"*) ;;
    *) PATH="$PATH:$dir" ;;
  esac
done
export PATH
exec uv run --quiet --script "$@"
