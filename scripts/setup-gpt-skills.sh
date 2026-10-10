#!/bin/bash
# setup-gpt-skills.sh
# GPT 네이티브 스킬(gpt-skills/)을 GPT CLI 스킬 폴더(${CODEX_HOME:-~/.codex}/skills)에 심볼릭 링크로 등록합니다.
# fz 생태계를 clone한 후 1회 실행하면 됩니다.
#
# ⛔ Claude 스킬(skills/)은 링크하지 않는다 — 링크하면 GPT 가 역할 스킬 대신 Claude 스킬을 고른다
#    (A2-02 실측: 07-09 링크 확장 뒤 fz-reviewer 로드가 28세션 중 26회 → 31세션 중 1회).
#    이미 걸린 것은 prune 한다: 링크 대상이 `<루트>/skills/<이름>` 이고 그 루트의 `.claude-plugin/plugin.json`
#    name 이 이 플러그인과 같으면 **링크 이름과 무관하게** 지운다(구버전 캐시·개명된 스킬 포함).
# ⛔ 실제 디렉토리 · 다른 플러그인의 링크 · 소유를 판정할 수 없는 링크는 건드리지 않는다.
# 소유 = 링크 대상 `<루트>/(skills|gpt-skills)/<이름>` 의 루트가 이 플러그인 루트이거나, 루트 매니페스트 name 이 같다
#   (같은 name 의 포크·구버전 캐시는 같은 플러그인 계열로 본다). 루트가 사라져 판정할 수 없으면 보존한다.
#
# Usage: bash <fz-plugin-dir>/scripts/setup-gpt-skills.sh [--gpt-agents] [--check]
#   --gpt-agents  GPT 역할 파일(gpt-agents/*.toml — 독립 리뷰의 렌즈 역할)도 ${CODEX_HOME:-~/.codex}/agents 에 링크한다.
#                 opt-in 이다 — 없으면 agents 폴더를 건드리지 않는다. 역할 파일 형식 실측: probe/p2 ①②(S11)
#   --check       읽기 전용 점검 — 아래 두 prune 판정에 걸리는 stale 링크를 `  stale: <이름> …` 줄로 나열만 한다.
#                 판정은 `Check: N stale` 요약 줄로 한다 — 그 줄 없이 끝난 exit 1 은 stale 이 아니라 준비 오류(매니페스트 · gpt-skills 없음)다.
#                 소유를 판정할 수 없는 끊긴 `fz-*` 링크(setup 의 'keep: … 소유 판정 불가')는 `  unknown: <이름> …` 줄로 따로 낸다(stale 아님).
#                 스킬 폴더만 보고(--gpt-agents 는 무시) 아무것도 만들거나 지우지 않는다. exit: 0 = stale 0 · 1 = stale 있음

set -euo pipefail

WITH_AGENTS=0
CHECK=0
for a in "$@"; do
  case "$a" in
    --gpt-agents) WITH_AGENTS=1 ;;
    --check) CHECK=1; export PYTHONDONTWRITEBYTECODE=1 ;;   # 읽기 전용 — 시스템 python3 가 $HOME/Library/Caches 에 바이트코드를 쓰지 않게
    *) echo "Error: unknown option: $a (usage: setup-gpt-skills.sh [--gpt-agents] [--check])"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GPT_SOURCE_DIR="$PLUGIN_DIR/gpt-skills"
# ⛔ 테스트 주입점 — 회귀 검증이 실제 사용자 디렉토리를 변경하지 않도록 override 를 받는다.
#    기본값은 GPT CLI 네임스페이스(`${CODEX_HOME:-~/.codex}` — 개명 금지, CLI 소유 경로다).
TARGET_DIR="${FZ_SKILL_TARGET:-${CODEX_HOME:-$HOME/.codex}/skills}"

# 매니페스트 최상위 name — python3 가 있으면 JSON 으로 읽는다(들여쓰기·한 줄 JSON·중첩 name 에 흔들리지 않게 — 2라운드 007).
#   없으면 들여쓰기 2칸 줄만 읽는 근사로 떨어진다(author.name 4칸을 집지 않는다). 못 읽으면 빈 문자열.
plugin_name() {
  local m="$1/.claude-plugin/plugin.json"
  [ -f "$m" ] || return 0
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(d.get("name", "") if isinstance(d, dict) else "")
except Exception:
    pass' "$m" 2>/dev/null
  else
    sed -n 's/^  "name": *"\([^"]*\)".*/\1/p' "$m" | head -1
  fi
}

# 링크 대상을 비교 가능한 형태로 — 상대 경로를 대상 폴더($2 · 기본 스킬 폴더) 기준으로 풀고, 중복·끝 슬래시를 걷고, 부모가 있으면 `..` 를 푼다
norm() {
  local d="$1" base="${2:-$TARGET_DIR}" parent
  case "$d" in /*) ;; *) d="$base/$d" ;; esac
  d="$(printf '%s' "$d" | tr -s '/')"
  while [ "${d%/}" != "$d" ]; do d="${d%/}"; done
  parent="$(dirname "$d")"
  [ -d "$parent" ] && d="$(cd "$parent" && pwd -P)/$(basename "$d")"
  printf '%s' "$d"
}

# $1=정규화한 대상 · $2=skills|gpt-skills — 그 폴더 바로 아래이고 루트를 이 플러그인이 소유하면 0
owned_under() {
  local d="$1" kind="$2" root
  case "$d" in */"$kind"/*) ;; *) return 1 ;; esac
  root="${d%/"$kind"/*}"
  [ "${d#"$root"/"$kind"/}" = "${d##*/}" ] || return 1
  [ "$root" = "$SELF_ROOT" ] || [ "$(plugin_name "$root")" = "$SELF_NAME" ]
}

SELF_NAME="$(plugin_name "$PLUGIN_DIR")"
SELF_ROOT="$(cd "$PLUGIN_DIR" && pwd -P)"
if [ -z "$SELF_NAME" ]; then
  echo "Error: plugin name not readable from $PLUGIN_DIR/.claude-plugin/plugin.json"
  exit 1
fi
if [ ! -d "$GPT_SOURCE_DIR" ]; then
  echo "Error: skill directory not found at $GPT_SOURCE_DIR"
  exit 1
fi

# ── --check: 읽기 전용 점검 — ⛔ mkdir -p 앞에서 끝낸다(스킬 폴더가 없으면 만들지 않고 stale 0 이다)
#    stale = 아래 prune ① · ② 의 판정(같은 norm · owned_under)에 걸리는 링크다. 그래서 정리(인자 없는 실행) 뒤 다시 보면 0 이다.
# ⛔ 비교 기준은 링크 대상의 설치 루트다 — 루트 매니페스트 name 으로 소유를 본다. 이 실행 트리 경로와 같은지는 보지 않는다:
#    그렇게 보면 dev 트리·격리 clone 에서 돌릴 때 설치본을 가리키는 정상 GPT 스킬 링크가 전부 stale 로 보인다(트리마다 결과가 달라진다).
#    같은 이유로 살아 있는 다른 판의 GPT 스킬 링크(인자 없는 실행이 이 판으로 다시 거는 것)와 아직 링크되지 않은 스킬은 내지 않는다.
if [ "$CHECK" -eq 1 ]; then
  stale=0; unknown=0
  for link in "$TARGET_DIR"/*; do
    [ -L "$link" ] || continue
    name="$(basename "$link")"
    dest="$(norm "$(readlink "$link")")"
    if owned_under "$dest" skills; then
      echo "  stale: $name (Claude skill link -> $dest)"                 # prune ① 대상
    else
      case "$name" in fz-*) ;; *) continue ;; esac
      [ -e "$link" ] && continue
      if ! owned_under "$dest" gpt-skills; then                               # prune ② 의 keep — 판정 불가는 stale 이 아니다
        echo "  unknown: $name (dangling — 소유 판정 불가 -> $dest)"
        unknown=$((unknown + 1)); continue
      fi
      echo "  stale: $name (dangling -> $dest)"                          # prune ② 대상
    fi
    stale=$((stale + 1))
  done
  note=""; [ "$unknown" -gt 0 ] && note=" · 판정 불가 $unknown"
  if [ "$stale" -eq 0 ]; then
    echo "Check: 0 stale in $TARGET_DIR$note"
    exit 0
  fi
  echo "Check: $stale stale in $TARGET_DIR$note — 정리: bash $PLUGIN_DIR/scripts/setup-gpt-skills.sh"
  exit 1
fi

mkdir -p "$TARGET_DIR"

linked=0
skipped=0
pruned=0

# ── prune ①: 이 플러그인의 Claude 스킬(skills/)을 가리키는 링크 — 이름 무관
#    대상이 이미 사라진 링크도 루트 매니페스트로 소유를 판정한다(구버전 캐시·삭제된 스킬).
for link in "$TARGET_DIR"/*; do
  [ -L "$link" ] || continue
  dest="$(norm "$(readlink "$link")")"
  owned_under "$dest" skills || continue
  echo "  prune: $(basename "$link") (Claude skill link -> $dest)"
  rm "$link"
  pruned=$((pruned + 1))
done

for skill_dir in "$GPT_SOURCE_DIR"/*; do
  [ -d "$skill_dir" ] || continue
  [ -f "$skill_dir/SKILL.md" ] || continue

  skill_name="$(basename "$skill_dir")"
  target="$TARGET_DIR/$skill_name"

  if [ -L "$target" ]; then
    # Already a symlink — update if pointing elsewhere (구버전 캐시를 가리키는 링크 포함)
    current="$(readlink "$target")"
    if [ "$current" = "$skill_dir" ]; then
      echo "  skip: $skill_name (already linked)"
      skipped=$((skipped + 1))
      continue
    fi
    # ⛔ 살아 있는 남의 같은 이름 링크는 바꾸지 않는다(2라운드 008). 이 플러그인 소유(구버전 캐시 포함)이거나
    #    끊어진 링크만 다시 건다 — 끊어진 링크는 가리키는 것이 없어 바꿔도 잃는 것이 없다.
    cur_norm="$(norm "$current")"
    if [ -e "$target" ] && ! owned_under "$cur_norm" gpt-skills && ! owned_under "$cur_norm" skills; then
      echo "  skip: $skill_name (다른 플러그인 링크 -> $current — manual resolution needed)"
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

# ── prune ②: 소스에서 사라진 `fz-*` 심볼릭 제거
# ⛔ 왜 필요한가: 위 루프는 **소스 디렉토리를 순회**하므로 이름이 바뀌거나 삭제된 스킬의
#    옛 링크는 영원히 남는다(2026-09-06 codex→gpt 개명에서 실측). 링크가 죽어도 아무 게이트가 잡지 않는다.
# ⛔ dangling 이면서 **이 플러그인 소유**인 것만 제거한다 — 살아있는 링크 · 실제 디렉토리 · `fz-` 아닌 링크 ·
#    다른 플러그인의 끊어진 `fz-*` 는 건드리지 않는다(GPT R-A 검토 008). 소유를 판정할 수 없으면 보존하고 알린다.
for link in "$TARGET_DIR"/fz-*; do
  [ -L "$link" ] || continue      # 심볼릭이 아니면 skip (실제 디렉토리 보호)
  [ -e "$link" ] && continue      # 타겟이 살아 있으면 skip
  dest="$(norm "$(readlink "$link")")"
  if owned_under "$dest" gpt-skills || owned_under "$dest" skills; then
    echo "  prune: $(basename "$link") (dangling)"
    rm "$link"
    pruned=$((pruned + 1))
  else
    echo "  keep: $(basename "$link") (dangling — 소유 판정 불가, 보존)"
  fi
done

# ── GPT 역할 파일 (opt-in --gpt-agents) — 스킬 링크와 같은 소유 규칙: 남의 살아 있는 링크 · 실제 파일은 건드리지 않는다
agents_linked=0
if [ "$WITH_AGENTS" -eq 1 ]; then
  AGENT_SOURCE_DIR="$PLUGIN_DIR/gpt-agents"
  AGENT_TARGET_DIR="${FZ_AGENT_TARGET:-${CODEX_HOME:-$HOME/.codex}/agents}"   # ⛔ 테스트 주입점 — FZ_SKILL_TARGET 과 같은 이유
  [ -d "$AGENT_SOURCE_DIR" ] || { echo "Error: role directory not found at $AGENT_SOURCE_DIR"; exit 1; }
  mkdir -p "$AGENT_TARGET_DIR"
  for role in "$AGENT_SOURCE_DIR"/*.toml; do
    [ -f "$role" ] || continue
    role_name="$(basename "$role")"
    target="$AGENT_TARGET_DIR/$role_name"
    if [ -L "$target" ]; then
      current="$(readlink "$target")"
      if [ "$current" = "$role" ]; then
        echo "  skip: agent $role_name (already linked)"
        continue
      fi
      cur_norm="$(norm "$current" "$AGENT_TARGET_DIR")"
      if [ -e "$target" ] && ! owned_under "$cur_norm" gpt-agents; then
        echo "  skip: agent $role_name (다른 플러그인 링크 -> $current — manual resolution needed)"
        continue
      fi
      rm "$target"
    elif [ -e "$target" ]; then
      echo "  skip: agent $role_name (real file exists — manual resolution needed)"
      continue
    fi
    ln -s "$role" "$target"
    echo "  link: agent $role_name -> $role"
    agents_linked=$((agents_linked + 1))
  done
fi

echo ""
echo "Done: $linked linked, $skipped skipped, $pruned pruned.$([ "$WITH_AGENTS" -eq 1 ] && echo " agents: $agents_linked linked.")"
echo "Verify: ls -la $TARGET_DIR/fz-*"
