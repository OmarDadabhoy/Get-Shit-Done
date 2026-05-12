#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/skills/get-shit-done"
DEST="${CODEX_HOME:-$HOME/.codex}/skills/get-shit-done"
COMMAND_SRC="$ROOT/commands/get-shit-done.md"
CLAUDE_COMMAND_DEST="${CLAUDE_HOME:-$HOME/.claude}/commands/get-shit-done.md"
CODEX_COMMAND_DEST="${CODEX_HOME:-$HOME/.codex}/commands/get-shit-done.md"

mkdir -p "$(dirname "$DEST")"

if [ -e "$DEST" ] && [ ! -L "$DEST" ]; then
  echo "Refusing to replace existing non-symlink skill: $DEST" >&2
  exit 1
fi

if [ -L "$DEST" ]; then
  rm "$DEST"
fi

ln -s "$SRC" "$DEST"
echo "Installed Codex skill symlink: $DEST -> $SRC"

for COMMAND_DEST in "$CLAUDE_COMMAND_DEST" "$CODEX_COMMAND_DEST"; do
  mkdir -p "$(dirname "$COMMAND_DEST")"
  if [ -e "$COMMAND_DEST" ] && [ ! -L "$COMMAND_DEST" ]; then
    echo "Refusing to replace existing non-symlink command: $COMMAND_DEST" >&2
    continue
  fi
  if [ -L "$COMMAND_DEST" ]; then
    rm "$COMMAND_DEST"
  fi
  ln -s "$COMMAND_SRC" "$COMMAND_DEST"
  echo "Installed slash command symlink: $COMMAND_DEST -> $COMMAND_SRC"
done
