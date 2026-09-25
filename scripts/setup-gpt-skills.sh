#!/bin/bash
# setup-gpt-skills.sh
# GPT 네이티브 스킬과 fz 플러그인 스킬을 ~/.codex/skills/에 심볼릭 링크로 등록합니다.
# fz 생태계를 clone한 후 1회 실행하면 됩니다.
#
# Usage: bash <fz-plugin-dir>/scripts/setup-gpt-skills.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GPT_SOURCE_DIR="$PLUGIN_DIR/gpt-skills"
PLUGIN_SOURCE_DIR="$PLUGIN_DIR/skills"
# ⛔ 테스트 주입점 — 회귀 검증이 실제 사용자 디렉토리를 변경하지 않도록 override 를 받는다.
#    기본값은 GPT CLI 네임스페이스(`~/.codex/` — 개명 금지, CLI 소유 경로다).
TARGET_DIR="${FZ_SKILL_TARGET:-$HOME/.codex/skills}"

for source_dir in "$GPT_SOURCE_DIR" "$PLUGIN_SOURCE_DIR"; do
  if [ ! -d "$source_dir" ]; then
    echo "Error: skill directory not found at $source_dir"
    exit 1
  fi
done

mkdir -p "$TARGET_DIR"

linked=0
skipped=0

for source_dir in "$GPT_SOURCE_DIR" "$PLUGIN_SOURCE_DIR"; do
  for skill_dir in "$source_dir"/*; do
    [ -d "$skill_dir" ] || continue
    [ -f "$skill_dir/SKILL.md" ] || continue

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
done

# ── prune: 소스에서 사라진 `fz-*` 심볼릭 제거
# ⛔ 왜 필요한가: 위 루프는 **소스 디렉토리를 순회**하므로 이름이 바뀌거나 삭제된 스킬의
#    옛 링크는 영원히 남는다(2026-09-06 codex→gpt 개명에서 실측). 링크가 죽어도 아무 게이트가 잡지 않는다.
# ⛔ dangling 만 제거한다 — 살아있는 링크 · 실제 디렉토리 · `fz-` 아닌 링크는 건드리지 않는다.
pruned=0
for link in "$TARGET_DIR"/fz-*; do
  [ -L "$link" ] || continue      # 심볼릭이 아니면 skip (실제 디렉토리 보호)
  [ -e "$link" ] && continue      # 타겟이 살아 있으면 skip
  echo "  prune: $(basename "$link") (dangling)"
  rm "$link"
  pruned=$((pruned + 1))
done

echo ""
echo "Done: $linked linked, $skipped skipped, $pruned pruned."
echo "Verify: ls -la $TARGET_DIR/fz-*"
