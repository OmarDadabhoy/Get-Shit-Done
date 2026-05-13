#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/skills/get-shit-done"
AI_SLAVES_DEST="${CODEX_HOME:-$HOME/.codex}/skills/ai-slaves"
LEGACY_DEST="${CODEX_HOME:-$HOME/.codex}/skills/get-shit-done"
AI_SLAVES_COMMAND_SRC="$ROOT/commands/ai-slaves.md"
LEGACY_COMMAND_SRC="$ROOT/commands/get-shit-done.md"
CLAUDE_COMMAND_DIR="${CLAUDE_HOME:-$HOME/.claude}/commands"
CODEX_COMMAND_DIR="${CODEX_HOME:-$HOME/.codex}/commands"

for DEST in "$AI_SLAVES_DEST" "$LEGACY_DEST"; do
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
done

for COMMAND_NAME in ai-slaves get-shit-done; do
  COMMAND_SRC="$AI_SLAVES_COMMAND_SRC"
  if [ "$COMMAND_NAME" = "get-shit-done" ]; then
    COMMAND_SRC="$LEGACY_COMMAND_SRC"
  fi

  for COMMAND_DIR in "$CLAUDE_COMMAND_DIR" "$CODEX_COMMAND_DIR"; do
    COMMAND_DEST="$COMMAND_DIR/$COMMAND_NAME.md"
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
done
