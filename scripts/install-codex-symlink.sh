#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/skills/get-shit-done"
DEST="${CODEX_HOME:-$HOME/.codex}/skills/get-shit-done"

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
