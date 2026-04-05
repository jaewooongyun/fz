#!/bin/bash
# setup-codex-skills.sh
# Codex 네이티브 스킬을 ~/.codex/skills/에 심볼릭 링크로 등록합니다.
# fz 생태계를 clone한 후 1회 실행하면 됩니다.
#
# Usage: bash ~/.claude/scripts/setup-codex-skills.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/../codex-skills" && pwd)"
TARGET_DIR="$HOME/.codex/skills"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "Error: codex-skills directory not found at $SOURCE_DIR"
  exit 1
fi

mkdir -p "$TARGET_DIR"

linked=0
skipped=0

for skill_dir in "$SOURCE_DIR"/fz-*; do
  skill_name="$(basename "$skill_dir")"
  target="$TARGET_DIR/$skill_name"

  if [ -L "$target" ]; then
    # Already a symlink — update if pointing elsewhere
    current="$(readlink "$target")"
    if [ "$current" = "$skill_dir" ]; then
      echo "  skip: $skill_name (already linked)"
      skipped=$((skipped + 1))
      continue
    fi
    rm "$target"
  elif [ -d "$target" ]; then
    echo "  skip: $skill_name (real directory exists — manual resolution needed)"
    skipped=$((skipped + 1))
    continue
  fi

  ln -s "$skill_dir" "$target"
  echo "  link: $skill_name -> $skill_dir"
  linked=$((linked + 1))
done

echo ""
echo "Done: $linked linked, $skipped skipped."
echo "Verify: ls -la $TARGET_DIR/fz-*"
