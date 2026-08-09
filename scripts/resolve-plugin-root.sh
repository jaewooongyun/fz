#!/bin/bash
# 플러그인 루트를 자기 위치에서 해석해 stdout으로 출력한다.
#
# 왜 필요한가 (2026-08-09 외부 감사 ISSUE-008 + ISSUE-PLAN-001):
#   `modules/cross-validation.md`의 `get_codex_skill_path()`와 8개 호출부가 `FZ_PLUGIN_ROOT`를
#   **소비**하는데 레포 어디에도 **할당이 없었다**(실측: 소비 10곳 / 할당 0곳). 전부 빈 값이 전달돼
#   Tier 2b(플러그인 번들 `codex-skills/`)가 **항상 건너뛰어졌다.**
#   1차 처방은 `cd "{스킬 base directory}/../.."` 였으나 `{…}`는 **치환되지 않는 리터럴**이라 실행 불가였다.
#
# ⛔ `$0`을 쓰지 않는다: `source`로 불러오면 `$0`은 **호출자**를 가리킨다.
#    `BASH_SOURCE[0]`은 sourced/executed 양쪽에서 **이 파일**을 가리킨다.
#
# usage:
#   FZ_PLUGIN_ROOT="$("$(dirname "${BASH_SOURCE[0]}")/resolve-plugin-root.sh")"   # 스크립트 안에서
#   FZ_PLUGIN_ROOT="$(/절대/경로/scripts/resolve-plugin-root.sh)"                  # 절대경로를 아는 호출자
#
# ⛔ 부트스트랩 순환 주의: **이 스크립트의 경로를 모르는 호출자는 이 스크립트를 쓸 수 없다.**
#    마크다운 스니펫(Lead가 읽고 실행하는 절차)은 스킬 주입 헤더
#    `Base directory for this skill: …/skills/fz-codex` 에서 `../..`를 유도해 **절대경로로** 1회 export한다.
#    → 절차 정본: `modules/cross-validation.md` § FZ_PLUGIN_ROOT 초기화
#
# exit: 0=루트 출력 / 2=마커 검증 실패(플러그인 루트가 아님 — ⛔ 빈 값으로 조용히 통과시키지 않는다)
set -u

# ⛔ `pwd -P` — 심볼릭 링크를 통해 호출되면 논리 경로(링크의 부모)가 잡혀 마커 검증이 실패한다 (ISSUE-012)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SELF_DIR/.." && pwd -P)"

# fail-closed 마커 검증 — `codex-skills/`는 Tier 2b의 전제, `guides/`는 플러그인 식별자
if [ ! -d "$ROOT/codex-skills" ] || [ ! -d "$ROOT/guides" ]; then
  echo "⛔ 플러그인 루트가 아님: $ROOT (codex-skills/ 또는 guides/ 부재)" >&2
  exit 2
fi

echo "$ROOT"
