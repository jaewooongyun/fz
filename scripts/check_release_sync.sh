#!/bin/bash
# scripts/check_release_sync.sh — 릴리즈 산출물이 서로를 가리키는지 본다 (plan-final S10).
#
# ⛔ 왜 신설인가: `health-check.sh` 는 계약·문법·회귀를 보지만 **이번 변경의 문서 동기와 버전
#    갱신은 증명하지 않는다**(verify-gates S10 revise 지적). 버전이 세 곳에 흩어져 있어
#    한 곳만 올리는 실패가 실제로 있었다(v4.33.0 CHANGELOG "적용은 했는데 커밋하지 않았다").
#
# 검사: ① plugin.json == marketplace.json ② CHANGELOG 최상단 == plugin.json
#       ①-b 하위 플러그인(marketplace 두 번째 항목부터 · 리포 안 폴더) 버전 동기와 바뀐 뒤 버전 올림
#       ③ 가이드가 sweep 기록 위치(§5.8 ⑥)를 가리키는가 ④ health-check exit 0
#       ②-b README · CHANGELOG 의 노트 절 참조(§N · § 이름 · '이름' 절)가 그 노트 제목에 있다(F-421)
#       ②-c 직전 출하 태그(v* · HEAD 에 붙은 태그는 뺀다) 대비 파일 모드 변경 0 — 허용 목록 tests/fixtures/release-mode-allow.txt(F-427).
#           직전 태그가 없으면(첫 출하) `.githooks/*` 와 셔뱅 추적 파일의 실행 비트를 절대 기준으로 본다
# exit: 0=전부 충족(DOCS_SYNC_OK · RELEASE_SYNC_OK) / 1=불일치 / 2=대상 부재 · 인자 오류 · 판정 불가(측정 실패)
#       ⛔ 판정 불가 = 누수 축(정본 모듈이 2 를 냈거나 끝 줄이 종료 코드와 맞지 않는다) 또는 목록 추출(기준 태그 · 로컬 태그 · 변경 목록 ·
#          git status · git ls-files) 실패. 불일치가 함께 있어도 2 다(health-check 의 규약과 같다 — 미판정이 실패보다 앞선다). 그 밖의 축 미판정은 불일치로 센다
# diff-parse: not-a-diff — 이 스크립트는 diff 를 읽지 않는다. ⑦ · ⑧ 의 추가 줄 해석은 누수 규칙 정본(scripts/leak_rules.py)이 한다
#
# 모드(모드 다음의 옵션은 순서와 무관하게 받는다 · 모르는 인자는 exit 2):
#   (없음)      ①~④ — 수동·CI 용. health-check 포함이라 **약 7분 20초** 걸린다(2026-11-08 실측 439s)
#   --release --rules <파일>
#               ①~④ + ⑤ **커밋 축** + ⑥ **findings 축**(노트가 닫은 finding 을 밝혔는가) + ⑦ · ⑧ **누수 축**. 릴리즈 직전 게이트.
#               ⛔ 비공개 규칙 파일을 명시로 요구한다 — 인자 없음 · 파일 없음은 exit 2, 빈 파일은 '내장 규칙만' 이라는 명시다.
#                  env(FZ_NEUTRALIZE_RULES) · 유지관리자 표지로 추정하지 않는다(규칙 없이 돌면 비공개 이름이 그대로 통과한다)
#               기준 = 직전 출하 태그(v* · HEAD 에 붙은 태그는 뺀다 — 자기 자신과 비교하면 공허하게 통과한다)
#                 기준 있음: ⑧ `기준..HEAD` 의 커밋마다(신원 · 메시지 · 머리 · 추가 줄) + ⑦ HEAD 대비 작업 트리(커밋하지 않은 줄 · 미추적 파일)
#                 기준 없음(v* 태그가 없는 첫 출하): ⑧ 루트부터 HEAD 까지의 커밋마다 + 작업 트리 전문
#                 v* 태그가 있는데 HEAD 에서 닿는 직전 태그가 없으면(옆 이력에 남은 옛 태그 · git 오류) 판정 불가다
#                 볼 태그 = 로컬 태그 전부 — 주석 태그는 tagger · 주석, 가벼운 태그는 세기만 한다
#   --staged    ⑤만, staged 내용 기준. ⛔ pre-commit 용 — health-check 를 뺀다
#   --neutralize-diff <ref> [--rules <파일>]
#               ⑦만 — <ref> 대비 추가 줄(미추적 파일 포함) × 중립화 규칙 적중 0 (F-420). 규칙 파일을 주지 않으면 env FZ_NEUTRALIZE_RULES 를 쓴다
#               판정은 누수 규칙 정본(scripts/leak_rules.py --range · 문서 정책)이 한다. 내장 규칙은 프로젝트를 드러내지 않는 모양만
#               본다(개인 홈 · 작업 폴더 경로 · 허용 밖 메일 도메인 · 예약 번호 밖 자리표시자 · 티켓 키 꼴 · PR 번호 꼴 · 합성 목록 밖 워크플로 실행 ID).
#               조직 · 제품 이름 같은 비공개 규칙은 공개 트리에 두지 않는다 — `--rules`(또는 FZ_NEUTRALIZE_RULES) 파일에 한 줄 한 정규식
#   --self-test 임시 git 리포로 ⑤의 실패/통과 쌍 · 축 함수 · 판정 불가 전파(최종 exit 2)를 확인
#
# ⛔ **커밋 축을 기본 모드에 넣지 않는 이유**: pre-commit 은 *커밋하려는 중* 이라
#    깨끗한 워킹트리를 요구할 수 없다. 그래서 축을 `--release` 로 분리한다.
# ⛔ **워킹트리 전체의 청결을 보지 않는 이유**: 릴리즈 후 쌓인 다음 버전 작업이
#    정상 상태이므로 오탐이 된다. 보는 것은 **선언된 버전 자신의 산출물이 HEAD 에 있는가** 다 —
#    이것이 원래 실패 모드(v4.33.0 "적용은 했는데 커밋하지 않았다")의 정확한 오라클이다.
set -uo pipefail

MODE="" NREF="" NRULES="${FZ_NEUTRALIZE_RULES:-}" RULES_GIVEN=0
USAGE="사용: [--release --rules <파일>|--staged|--self-test|--neutralize-diff <ref> [--rules <파일>]]"
case "${1:-}" in
  --release)   MODE="release" ;;
  --staged)    MODE="staged" ;;
  --self-test) MODE="self-test" ;;
  --neutralize-diff)
    MODE="neutralize"; NREF="${2:-}"
    case "$NREF" in ""|-*) echo "❌ --neutralize-diff 에 기준 ref 가 없다 ($USAGE)"; exit 2 ;; esac ;;
  "")          MODE="default" ;;
  *) echo "❌ 알 수 없는 인자: $1 ($USAGE)"; exit 2 ;;
esac
# 모드(와 --neutralize-diff 의 기준 ref)를 걷어 낸다 — 남은 것은 모드 다음의 옵션이다
case "$MODE" in default) ;; neutralize) shift 2 ;; *) shift ;; esac
# 모드 다음의 옵션 — 순서와 무관하게 받는다. ⛔ 모르는 인자는 조용히 버리지 않는다(버리면 주지 않은 규칙으로 검사한 것처럼 보인다)
while [ $# -gt 0 ]; do
  case "$1" in
    --rules)
      case "$MODE" in release|neutralize) ;; *) echo "❌ --rules 는 --release · --neutralize-diff 에서만 받는다 ($USAGE)"; exit 2 ;; esac
      [ "$RULES_GIVEN" = 0 ] || { echo "❌ --rules 를 두 번 받았다 ($USAGE)"; exit 2; }
      [ $# -ge 2 ] || { echo "❌ --rules 에 파일이 없다 ($USAGE)"; exit 2; }
      NRULES="$2"; RULES_GIVEN=1
      [ -f "$NRULES" ] || { echo "❌ --rules 파일이 없다: '${NRULES}'"; exit 2; }
      # 아래에서 자기 루트로 옮겨 간다 — 상대 경로는 지금 폴더 기준으로 고정한다(정본 모듈은 상대 경로를 -C 기준으로 푼다)
      case "$NRULES" in /*) ;; *) NRULES="$PWD/$NRULES" ;; esac
      shift 2 ;;
    *) echo "❌ 알 수 없는 인자: $1 ($USAGE)"; exit 2 ;;
  esac
done
# --release 는 비공개 규칙을 명시로만 받는다 — env · 유지관리자 표지로 추정하지 않는다(규칙 없이 돌면 비공개 이름이 그대로 통과한다)
if [ "$MODE" = "release" ] && [ "$RULES_GIVEN" = 0 ]; then
  echo "❌ --release 는 --rules <파일> 을 명시로 요구한다 — 비공개 규칙이 없으면 빈 파일을 준다(내장 규칙만) ($USAGE)"
  exit 2
fi
#   루트는 **자기 위치**에서 해석한다 (`BASH_SOURCE[0]` — `$0` 는 source 시 호출자를 가리킨다)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SELF_DIR/.." && pwd)"
cd "$ROOT_DIR" || { echo "❌ 플러그인 루트로 이동 실패: $ROOT_DIR"; exit 2; }

fail=0 unrun=0
note() { echo "  ❌ $1"; fail=$((fail + 1)); }
# 판정 불가 — 누수 축(정본 모듈의 2 · 끝 줄 불일치) · 목록 추출 실패. 최종 판정(finish)이 2 로 끝낸다 — 불일치가 함께 있어도 2 가 앞선다
#    (health-check 의 규약과 같다 — 미판정이 실패보다 앞선다). 그 밖의 축 미판정은 note 로 센다(불일치 · exit 1)
unrun_note() { echo "  ⚠️ $1 — 판정 불가(⛔ 통과 아님)"; unrun=$((unrun + 1)); }

json_version() {   # $1=파일경로 · stdout=version (실패 시 빈 문자열)
  python3 -c '
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: sys.exit(0)
p=d["plugins"][0] if isinstance(d.get("plugins"),list) and d["plugins"] else d
print(p.get("version",""))' "$1" 2>/dev/null
}

git_show_version() {   # $1=리포 · $2=ref:path · stdout=version (소비처: --staged 전용)
  git -C "$1" show "$2" 2>/dev/null | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
p=d["plugins"][0] if isinstance(d.get("plugins"),list) and d["plugins"] else d
print(p.get("version",""))' 2>/dev/null
}

# 기준 태그 — 직전 출하(`v[0-9]*` — v 다음이 숫자인 태그만 출하 태그다. `vendor-…` 같은 이름이 기준이 되면 범위가 줄어든다). 결과는 전역 REL_BASE(빈 값 = 직전 태그 없음) · REL_BASE_WHY(실패 사유). 반환: 0=정했다 · 3=목록 추출 실패
#    ⛔ HEAD 에 붙은 v* 태그는 뺀다 — 태그를 단 뒤 다시 돌리면 자기 자신과 비교해 공허하게 통과한다
#    ⛔ '직전 태그 없음'(v* 목록이 비었거나 HEAD 의 태그뿐 — 첫 출하)과 describe 실패를 가른다 — 실패를 '태그 없음' 으로 읽으면 첫 출하
#       분기로 떨어져 직전 출하와의 대조가 조용히 바뀐다. v* 태그가 있는데 HEAD 에서 닿지 않는 경우(옆 이력 · 이력을 새로 시작한 뒤 남은
#       옛 태그)도 실패다 — 옛 이력의 태그는 정리한 뒤 다시 돈다(남겨 두면 로컬 태그 일괄 push 로 옛 이력이 되살아난다)
release_base() {   # $1=리포 디렉토리
  local repo="$1" all here rest="" t nl=$'\n' excl
  excl=()
  REL_BASE="" REL_BASE_WHY=""
  all="$(git -C "$repo" tag -l 'v[0-9]*' 2>/dev/null)" || { REL_BASE_WHY="git tag -l 실패"; return 3; }
  here="$(git -C "$repo" tag -l --points-at HEAD 'v[0-9]*' 2>/dev/null)" || { REL_BASE_WHY="git tag --points-at HEAD 실패"; return 3; }
  for t in $here; do excl+=(--exclude "$t"); done
  for t in $all; do
    case "$nl$here$nl" in *"$nl$t$nl"*) ;; *) rest="$rest$t$nl" ;; esac
  done
  [ -n "$rest" ] || return 0
  REL_BASE="$(git -C "$repo" describe --tags --abbrev=0 --match 'v[0-9]*' ${excl[@]+"${excl[@]}"} HEAD 2>/dev/null)" \
    || { REL_BASE="" REL_BASE_WHY="v* 태그가 있는데 HEAD 에서 닿는 직전 태그를 git describe 가 찾지 못했다 — 옆 이력에 남은 옛 태그(이력을 새로 시작했다면 정리한다)이거나 git 오류"; return 3; }
  [ -n "$REL_BASE" ] || { REL_BASE_WHY="git describe 가 빈 값을 냈다"; return 3; }
}

# 볼 태그 — 로컬 태그 전부(v* 밖도). 결과는 전역 REL_TAGS(배열) · REL_TAGS_WHY. 반환: 0=뽑았다 · 3=목록 추출 실패
#    ⛔ 기준 이후의 태그로 좁히지 않는다 — 로컬 태그는 일괄 push 한 번으로 함께 나간다(옛 이력의 태그가 되살아나는 통로). 이미 나간
#       태그를 다시 보는 비용은 작다. 판정(이름은 경로 이름 규칙 · 주석 태그는 tagger · 주석 · 가리키는 커밋이 검사 범위 밖이면 판정 불가)은
#       정본 모듈이 한다
release_tags() {   # $1=리포 디렉토리
  local all t
  REL_TAGS=()
  REL_TAGS_WHY=""
  all="$(git -C "$1" tag -l 2>/dev/null)" || { REL_TAGS_WHY="git tag -l 실패"; return 3; }
  for t in $all; do REL_TAGS+=("$t"); done
  return 0
}

# ⑤ 커밋 축 — **선언된 버전 자신의 산출물이 HEAD 에 있는가.**
#    ⛔ 워킹트리 전체의 청결을 보지 않는다(다음 버전 작업이 쌓이는 것은 정상).
#    반환: 0=충족 · 1=불일치(사유를 stdout 에) · 2=측정 불가 · 3=릴리즈 문서 추적 여부 · 미커밋 수정 목록 추출 실패(판정 불가 — 최종 exit 2)
commit_axis() {   # $1=리포 디렉토리 · $2=선언 버전
  local repo="$1" ver="$2" bad=0
  # ⛔ 가드는 **하나**다. 이전 판은 `--git-dir` 과 `--verify HEAD` 두 줄이 같은 2를 반환해
  #    어블레이션에서 서로를 가렸다(한쪽을 지워도 픽스처가 통과). `--verify HEAD` 가
  #    비-git 과 커밋 0개를 모두 잡으므로 이것만 둔다.
  git -C "$repo" rev-parse --verify HEAD >/dev/null 2>&1 \
    || { echo "  ⚠️ git 리포가 아니거나 커밋이 없다 — 커밋 축 미판정(⛔ 통과 아님)"; return 2; }

  # ⛔ **HEAD 버전과 디스크 버전을 대조하지 않는다 — 단독 발화가 불가능하다.**
  #    `$ver` 를 디스크 plugin.json 에서 읽으므로, HEAD 가 다르면 그 파일이 **반드시** dirty 다.
  #    즉 아래 dirty 검사와 중복이고, 어블레이션에서 제거해도 픽스처가 통과했다(죽은 로직).
  #    실패 모드(v4.33.0 "적용은 했는데 커밋하지 않았다")를 잡는 것은 dirty 검사 쪽이다.

  # 선언 버전의 릴리즈 문서가 **추적되는가** — 디스크 존재만으로는 릴리즈가 아니다
  #    ⛔ 목록 명령의 실패를 'untracked' 로 읽지 않는다 — --error-unmatch 는 1(맞는 경로 없음) 밖이 실패다(인덱스를 읽지 못함 등)
  local rel="docs/releases/v${ver}.md" lrc=0 unr=0
  if [ -f "$repo/$rel" ]; then
    git -C "$repo" ls-files --error-unmatch "$rel" >/dev/null 2>&1 || lrc=$?
    case "$lrc" in
      0) ;;
      1) echo "  ❌ $rel 이 untracked — 릴리즈 문서가 커밋되지 않았다"; bad=1 ;;
      *) echo "  ⚠️ git ls-files 실패(exit $lrc) — 릴리즈 문서가 추적되는지 뽑지 못했다(⛔ 통과 아님)"; unr=1 ;;
    esac
  else
    echo "  ❌ $rel 이 없다 — 선언된 버전의 릴리즈 문서가 부재"; bad=1
  fi

  # 버전 3곳과 선언 버전의 릴리즈 문서에 커밋 안 된 수정이 남아 있으면 HEAD 와 디스크가 갈린 상태다. 릴리즈 문서도 본다 — findings 축(⑥)은
  #    작업 트리의 노트를 읽는다. 추적만 확인하면 작업 트리에서만 더한 `Closes:` 줄 · 표지로 통과하고, 태그가 가리킬 커밋의 노트에는 그
  #    선언이 없다
  #    ⛔ git status 의 실패를 '수정 없음' 으로 읽지 않는다 — 빈 출력과 목록 추출 실패는 다르다
  local dirty
  if dirty=$(git -C "$repo" status --porcelain -- .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md "$rel" 2>/dev/null); then
    [ -z "$dirty" ] || { echo "  ❌ 버전 선언 파일 · 릴리즈 문서에 미커밋 수정이 있다:"; echo "$dirty" | sed 's/^/      /'; bad=1; }
  else
    echo "  ⚠️ git status 실패 — 버전 선언 파일 · 릴리즈 문서의 미커밋 수정 목록을 뽑지 못했다(⛔ 통과 아님)"; unr=1
  fi

  # 목록 추출 실패는 불일치보다 앞선다 — 3(판정 불가)을 돌려준다(axis_note 가 최종 exit 2 로 올린다)
  [ "$unr" = 0 ] || return 3
  return "$bad"
}

# ⑥ findings 축 — 선언 버전 노트가 **닫은 finding 을 밝혔는가**: 코드 블록 밖의 `Closes:` 줄(finding 번호가 하나 이상) 또는 줄 머리 꼴의 '닫은 finding
#    없음' 표지. 선언 판정은 노트 검사기(check_release_notes.py --findings-decl) 한 곳이 한다 — CHANGELOG 표 필수 모드의 표지와 같은 정의다.
#    ⛔ 레지스트리를 읽지 않는다 — 레지스트리 없는 머신에서도 같은 판정이다. applied ↔ Closes 대조는
#       check_release_closes.py 를 명시로 돌린다(CLAUDE.md 릴리스 절차).
#    반환: 0=선언 있음 · 1=선언 없음 · 2=노트 부재 · 선언 판정 실패(미판정)
findings_axis() {   # $1=노트 경로
  local n="$1" out rc
  [ -f "$n" ] || { echo "  ⚠️ $n 없음 — findings 축 미판정(⛔ 통과 아님)"; return 2; }
  # ⛔ 템플릿 원문이 두 술어를 이미 충족한다(_TEMPLATE.md 의 자리표시 Closes 줄 · 따옴표 안 표지 안내) — 둘 다 선언이 아니다
  if grep -E '^Closes:' "$n" | grep -Eq 'F-00[12]-(some|another)-slug'; then
    echo "  ❌ $n 의 Closes: 줄에 템플릿 자리표시 slug 가 남았다 — 닫은 엔트리로 바꾸거나 줄을 지운다"; return 1
  fi
  # 선언 판정은 노트 검사기에 넘긴다 — 코드 블록 밖의 `Closes:` 줄(finding 번호가 하나 이상) 또는 줄 머리 꼴 표지. 여기에 판정 사본을 두지 않는다(두 벌이면
  #    한 벌만 고쳐진다 — 울타리를 가리는 법이 그렇게 갈렸다).
  #    ⛔ 종료 코드와 끝 줄을 함께 본다 — 파이썬 예외도 exit 1 이라 종료 코드만 보면 충돌이 '선언 없음' 으로 읽힌다
  out="$(python3 "$SELF_DIR/check_release_notes.py" --findings-decl "$n" 2>&1)"; rc=$?
  case "$rc:${out##*$'\n'}" in
    "0:FINDINGS_DECL closes"|"0:FINDINGS_DECL marker") return 0 ;;
    "1:FINDINGS_DECL none") ;;
    *) echo "  ⚠️ $n 의 선언 판정을 하지 못했다(노트 검사기 exit $rc · $(printf '%s' "${out##*$'\n'}" | cut -c1-120)) — findings 축 미판정(⛔ 통과 아님)"
       return 2 ;;
  esac
  echo "  ❌ $n 에 Closes: 줄도 '닫은 finding 없음' 표지도 없다 — 닫은 것을 적거나 없음을 밝힌다(표지는 줄 머리에 둔다 · 코드 블록 안은 세지 않는다)"
  return 1
}

# ①-b 하위 플러그인 — marketplace 두 번째 항목부터, source 가 이 리포 안 폴더(`./…`)인 것마다 둘을 본다.
#    · 그 폴더 `.claude-plugin/plugin.json` 의 버전 == marketplace 항목의 버전
#    · 직전 릴리스 태그(`v*`)에 그 폴더가 있었고 그 뒤 내용이 바뀌었으면(미커밋 · untracked 포함) 버전도 바뀌었다 —
#      같은 버전이면 `plugin update` 가 바뀐 내용을 건너뛴다. v* 태그가 없거나 태그에 없던 폴더(새 플러그인)는 넘어간다.
#    ⛔ 직전 태그는 HEAD 에 붙은 태그를 **포함한** describe 다 — ②-c · ⑦ · ⑧ 의 release_base(HEAD 태그를 뺀다)와 뜻이 다르다. 태그를 단 뒤
#       다시 돌리면 그 태그 이후의 변경(미커밋 · untracked)만 본다. self-test 의 sub-changed-* 셀이 HEAD 태그 대비 변경을 단언한다
#    반환: 0=충족 · 1=불일치(사유를 stdout 에) · 2=marketplace 의 plugins 를 읽지 못함 · 3=직전 태그 · 변경 목록 추출 실패(판정 불가)
subplugin_axis() {   # $1=리포 디렉토리
  python3 - "$1" <<'PY'
import json, subprocess, sys
repo = sys.argv[1]
def git(*args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
def version_of(text):
    try:
        value = json.loads(text)
    except Exception:
        return ""
    return value.get("version", "") if isinstance(value, dict) else ""
try:
    with open(f"{repo}/.claude-plugin/marketplace.json", encoding="utf-8") as f:
        plugins = json.load(f)["plugins"]
    assert isinstance(plugins, list)
except Exception:
    print("  ⚠️ marketplace.json 의 plugins 를 읽지 못했다 — 하위 플러그인 미판정(⛔ 통과 아님)")
    sys.exit(2)
# 직전 태그 — 'v* 태그 없음'(목록이 비었다 → 버전 올림 검사를 건너뛴다)과 목록 · describe 실패(판정 불가 → 3)를 가른다.
#   ⛔ 실패를 '태그 없음' 으로 읽으면 바뀐 하위 플러그인의 버전 올림 검사가 조용히 빠진다. 기준은 HEAD 태그를 포함한다(머리 주석)
vtags = git("tag", "-l", "v[0-9]*")
found = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*") if vtags.returncode == 0 and vtags.stdout.strip() else None
tag = found.stdout.strip() if found is not None and found.returncode == 0 else ""
if vtags.returncode != 0:
    tag_unrun = "git tag -l 실패"
elif found is not None and not tag:
    tag_unrun = "v* 태그가 있는데 git describe 가 실패했다(HEAD 에서 닿는 v* 태그 없음 · git 오류)"
else:
    tag_unrun = ""
bad = unrun = 0
for entry in plugins[1:]:
    source = entry.get("source") if isinstance(entry, dict) else None
    if not isinstance(source, str) or not source.startswith("./"):
        continue
    path = source[2:].rstrip("/")
    name, listed = entry.get("name", path), entry.get("version", "")
    try:
        with open(f"{repo}/{path}/.claude-plugin/plugin.json", encoding="utf-8") as f:
            own = version_of(f.read())
    except OSError:
        own = ""
    if own == "" or own != listed:
        print(f"  ❌ {name}: {path}/.claude-plugin/plugin.json({own or '읽지 못함'}) ≠ marketplace({listed})")
        bad = 1
        continue
    if tag_unrun:
        if not unrun:
            print(f"  ⚠️ {tag_unrun} — 하위 플러그인의 직전 태그를 정하지 못했다(⛔ 통과 아님)")
        unrun = 1
        continue
    if tag == "":
        continue
    before = git("show", f"{tag}:{path}/.claude-plugin/plugin.json")
    if before.returncode != 0:
        continue
    # ⛔ 목록 명령의 실패를 '바뀌지 않음' 으로 읽지 않는다 — diff --quiet 는 0(같음) · 1(다름) 밖이 실패다
    diff = git("diff", "--quiet", tag, "--", path)
    others = git("ls-files", "--others", "--exclude-standard", "--", path)
    if diff.returncode not in (0, 1) or others.returncode != 0:
        print(f"  ⚠️ {name}: {tag} 뒤 {path} 의 변경 목록을 뽑지 못했다(git diff · ls-files 실패 — ⛔ 통과 아님)")
        unrun = 1
        continue
    changed = diff.returncode == 1 or others.stdout.strip() != ""
    if changed and version_of(before.stdout) == own:
        print(f"  ❌ {name}: {tag} 뒤 {path} 가 바뀌었는데 버전이 {own} 그대로다 — plugin update 가 건너뛴다")
        bad = 1
sys.exit(3 if unrun else bad)
PY
}

# ②-b 노트 절 참조 — README · CHANGELOG 가 노트의 절을 번호(§2) · 이름(§ 남은 것) · 따옴표('X' 절)로 가리키면 그 절이 노트에 있어야 한다.
#    노트는 줄 안의 `docs/releases/vX.md` 가 있으면 그것, 없으면 CHANGELOG 는 가장 가까운 위 `### vX` 절 · README 는 최상단 버전.
#    이름 대조: 노트 제목에서 괄호 · ` — ` 뒤를 뗀 앞부분으로 참조 문장이 시작하면 해소(`§ 남은 것에 적었다` → `## 남은 것 (가이드 갱신)`).
#    ⛔ 노트 제목을 고친 뒤 옛 제목을 가리키는 요약이 남던 실패(F-421 — README:154 · CHANGELOG 두 곳)를 잡는다
#    반환: 0=충족 · 1=끊긴 참조(사유를 stdout 에) · 2=CHANGELOG 부재
note_ref_axis() {   # $1=리포 디렉토리
  python3 - "$1" <<'PY'
import os, re, sys
repo = sys.argv[1]
SEC_RE = re.compile(r"(?:릴리[즈스]\s*노트|docs/releases/v(\d+\.\d+\.\d+)\.md`?)\s*§\s*(\S.*)")
QUO_RE = re.compile(r"(?:노트(?:의)?|docs/releases/v(\d+\.\d+\.\d+)\.md`?)\s*'([^'\n]+)'\s*절")
VER_RE = re.compile(r"^###\s+v(\d+\.\d+\.\d+)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

def norm(s):
    return re.sub(r"[`*]", "", s).strip()

def core(h):
    return re.split(r"\s+—\s+|\s*\(", norm(h), maxsplit=1)[0].strip()

cache = {}
def heads(ver):
    if ver not in cache:
        p = os.path.join(repo, "docs", "releases", f"v{ver}.md")
        if not os.path.isfile(p):
            cache[ver] = None
        else:
            out, fence = [], False
            for ln in open(p, encoding="utf-8"):
                if FENCE_RE.match(ln):
                    fence = not fence
                    continue
                m = re.match(r"^#{1,6}\s+(.*)", ln)
                if m and not fence:
                    out.append(norm(m.group(1)))
            cache[ver] = out
    return cache[ver]

def sec_ok(hs, rest):
    rest = norm(rest)
    m = re.match(r"(\d+)(?!\d)", rest)
    if m:
        return any(re.match(rf"(?:§\s*)?{m.group(1)}(?:[.)]|\s|$)", h) for h in hs)
    return any(core(h) and rest.startswith(core(h)) for h in hs)

def quote_ok(hs, name):
    name = norm(name)
    return any(name == core(h) or name in h for h in hs)

cl = os.path.join(repo, "CHANGELOG.md")
if not os.path.isfile(cl):
    print("  ⚠️ CHANGELOG.md 없음 — 노트 절 참조 미판정(⛔ 통과 아님)")
    sys.exit(2)
lines = open(cl, encoding="utf-8").read().split("\n")
top = next((m.group(1) for m in map(VER_RE.match, lines) if m), None)
bad = 0
for rel in ("README.md", "CHANGELOG.md"):
    p = os.path.join(repo, rel)
    if not os.path.isfile(p):
        continue
    cur, fence = (top if rel == "README.md" else None), False
    for i, ln in enumerate(open(p, encoding="utf-8").read().split("\n"), 1):
        if FENCE_RE.match(ln):
            fence = not fence
            continue
        if fence:
            continue
        vm = VER_RE.match(ln)
        if vm and rel == "CHANGELOG.md":
            cur = vm.group(1)
            continue
        for rx, ok in ((SEC_RE, sec_ok), (QUO_RE, quote_ok)):
            for m in rx.finditer(ln):
                ver = m.group(1) or cur
                if ver is None:
                    continue
                hs = heads(ver)
                if hs is None:
                    print(f"  ❌ {rel}:{i}: 노트 v{ver} 가 없다 — 절 참조 '{m.group(2)[:40]}' 를 확인할 곳이 없다")
                    bad = 1
                elif not ok(hs, m.group(2)):
                    print(f"  ❌ {rel}:{i}: 노트 v{ver} 에 '{norm(m.group(2))[:40]}' 절이 없다 — 노트 제목을 고친 뒤 옛 이름이 남았다")
                    bad = 1
sys.exit(bad)
PY
}

# ②-c 허용 목록 — tests/fixtures/release-mode-allow.txt 의 경로 줄(한 줄 한 경로 · `#` 주석 · 빈 줄 무시). 없거나 읽지 못하면 빈 목록이다
#    (허용을 넓히는 쪽으로 실패하지 않는다). ⛔ 두 경로(직전 태그 대비 · 실행 비트 절대 기준)가 이 한 벌을 쓴다 — 읽는 법을 두 벌 두면
#    한 벌만 고쳐진다
mode_allow() {   # $1=리포 디렉토리 · stdout=허용 경로(한 줄 하나)
  local f="$1/tests/fixtures/release-mode-allow.txt"
  [ -f "$f" ] || return 0
  # 훅은 허용 대상이 아니다(목록 머리말이 그렇게 적는다) — 적혀 있어도 내보내지 않는다: 0644 훅은 git 이 건너뛰는 죽은 훅이다
  grep -vE '^[[:space:]]*(#|$)' "$f" 2>/dev/null | grep -v '^\.githooks/'
  return 0
}

# ②-c 직전 태그 없음 — 비교할 직전 출하가 없으면 실행 비트를 절대 기준으로 본다: 추적 파일 가운데 `.githooks/*` 와 셔뱅(`#!`)으로
#    시작하는 파일은 커밋(HEAD) · 인덱스 · 작업 트리 모두 실행 가능이어야 한다(허용 목록 = $2 — mode_allow 의 출력 · 커밋에 없는 새 파일은
#    인덱스 · 작업 트리만 본다). 출하되는 것은 커밋이다 — 작업 트리에서만 고친 실행 비트는 통과가 아니다. 일괄 치환 도구가 떨어뜨린
#    실행 비트가 태그 없는 첫 출하에서 영구히 빠지지 않게 한다. 심볼릭 링크 · 하위 저장소는 보지 않는다.
#    대상은 커밋으로도 정한다 — 커밋에 0644 로 남은 훅과 셔뱅 스크립트(커밋의 블롭이 `#!` 로 시작)는 인덱스에서 뺐거나 작업 트리에서
#    지웠거나 셔뱅 줄을 지웠어도 적중이다(커밋하지 않으면 그대로 출하된다). 작업 트리에서 지우기만 한 그 밖의 파일은 보지 않는다.
#    반환: 0=충족 · 1=실행 비트 없음 · 3=추적 파일 목록 · 커밋의 모드 목록 추출 · 읽기 실패(판정 불가)
exec_bit_axis() {   # $1=리포 디렉토리 · $2=허용 경로(mode_allow 의 출력)
  python3 - "$1" "$2" <<'PY'
import hashlib, os, stat, subprocess, sys
repo, allow = sys.argv[1], {ln for ln in sys.argv[2].split("\n") if ln}
r = subprocess.run(["git", "-C", repo, "ls-files", "-s", "-z"], capture_output=True)
if r.returncode != 0:
    print("  ⚠️ git ls-files -s 실패 — 실행 비트를 볼 추적 파일 목록을 뽑지 못했다(⛔ 통과 아님)")
    sys.exit(3)
h = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "-z", "HEAD"], capture_output=True)
if h.returncode != 0:
    print("  ⚠️ git ls-tree HEAD 실패 — 커밋의 파일 모드를 읽지 못했다(⛔ 통과 아님)")
    sys.exit(3)
head_mode = {raw: meta.split(b" ", 1)[0] for meta, sep, raw in (e.partition(b"\t") for e in h.stdout.split(b"\0")) if sep}
head_sha = {raw: meta.split(b" ")[2] for meta, sep, raw in (e.partition(b"\t") for e in h.stdout.split(b"\0")) if sep}
bad = unrun = 0
seen = set()   # 아래 순회가 판정한 경로 — 커밋에만 남은 것을 가릴 때 뺀다(같은 파일을 두 번 적지 않는다)
same = set()   # 작업 트리의 내용이 커밋의 블롭과 같은 경로 — 아래 순회가 이미 본 내용이라 커밋의 블롭을 다시 읽지 않는다
for ent in r.stdout.split(b"\0"):
    meta, sep, raw = ent.partition(b"\t")
    mode = meta.split(b" ", 1)[0]
    if not sep or mode not in (b"100644", b"100755"):
        continue   # 심볼릭 링크(120000) · 하위 저장소(160000)는 실행 비트가 없다
    path, shown = raw.decode("utf-8", "surrogateescape"), raw.decode("utf-8", "backslashreplace")
    full = os.path.join(repo, path)
    try:
        st = os.lstat(full)
        if not stat.S_ISREG(st.st_mode):
            continue
        with open(full, "rb") as f:
            data = f.read()
        head = data[:2]
    except FileNotFoundError:
        continue   # 작업 트리에서 지운 파일 — 커밋에 0644 훅 · 셔뱅 스크립트로 남았는지는 아래 순회가 본다
    except OSError as e:
        print(f"  ⚠️ {shown} 를 읽지 못했다 — {e.strerror or type(e).__name__}(⛔ 통과 아님)")
        unrun = 1
        continue
    want = head_sha.get(raw)   # 객체 이름 = 해시("blob <길이>\0" + 내용) — 저장소의 해시 방식은 이름 길이로 가린다
    if want and hashlib.new("sha256" if len(want) == 64 else "sha1", b"blob %d\0" % len(data) + data).hexdigest().encode() == want:
        same.add(raw)
    if not (path.startswith(".githooks/") or head == b"#!") or path in allow:
        continue
    seen.add(raw)
    hm = head_mode.get(raw)   # 커밋에 없는 새 파일은 인덱스 · 작업 트리만 본다
    lack = [w for w, ok in (("HEAD " + (hm or b"").decode(), hm != b"100644"), ("인덱스 " + mode.decode(), mode == b"100755"),
                            ("작업 트리", bool(st.st_mode & 0o111))) if not ok]
    if lack:
        how = "의도한 것이면 tests/fixtures/release-mode-allow.txt 에 적는다"
        if path.startswith(".githooks/"):   # 훅은 허용 목록으로 풀리지 않는다(mode_allow 가 훅 줄을 뺀다) — 따라 하면 풀리는 안내만 낸다
            head_lacks = lack[0].startswith("HEAD")   # 순서는 HEAD · 인덱스 · 작업 트리다
            how = "훅은 허용 목록으로 풀 수 없다 — " + (
                "실행 비트는 이미 줬다. 커밋한 뒤 다시 돌린다" if head_lacks and len(lack) == 1
                else "실행 비트를 준다(chmod +x 뒤 stage)" + (" · 그리고 커밋한다" if head_lacks else ""))
        print(f"  ❌ 실행 비트가 없다({' · '.join(lack)}): {shown} — 직전 태그가 없어 절대 기준으로 본다. {how}")
        bad = 1
# 커밋에만 남은 것 — 위 순회는 작업 트리의 파일로 대상을 정한다(훅이거나 셔뱅으로 시작한다). 인덱스에서 뺐거나 작업 트리에서 지웠거나 셔뱅
#   줄을 지운 파일은 위에서 대상이 아니었다. 커밋하지 않았으면 태그가 가리킬 커밋에는 0644 훅 · 셔뱅 스크립트가 그대로다. 훅이 아닌 파일은
#   커밋의 블롭이 셔뱅으로 시작할 때만 대상이다 — 작업 트리의 내용이 커밋의 블롭과 같으면 위 순회가 이미 본 내용이라 블롭을 읽지 않는다
for raw, hm in sorted(head_mode.items()):
    if raw in seen or hm != b"100644":
        continue
    path, shown = raw.decode("utf-8", "surrogateescape"), raw.decode("utf-8", "backslashreplace")
    if not raw.startswith(b".githooks/"):
        if path in allow or raw in same:
            continue
        blob = subprocess.run(["git", "-C", repo, "cat-file", "blob", head_sha[raw].decode()], capture_output=True)
        if blob.returncode != 0:
            print(f"  ⚠️ 커밋의 {shown} 를 읽지 못했다 — git cat-file 실패(⛔ 통과 아님)")
            unrun = 1
            continue
        if blob.stdout[:2] != b"#!":
            continue
    print(f"  ❌ 실행 비트가 없다(HEAD 100644 — 작업 트리에서는 뺐거나 바꿨다): {shown} — 바꾼 것을 커밋한 뒤 다시 돌린다")
    bad = 1
sys.exit(3 if unrun else bad)
PY
}

# ②-c 파일 모드 — 직전 출하 태그(release_base — v* · HEAD 에 붙은 태그는 뺀다) 대비 `mode change` 가 허용 목록 밖에 있으면 불일치(F-427:
#    원자 교체가 0755 를 0644 로 바꿨는데 검증 경로는 모두 `bash <파일>` 이라 실행 비트 없이도 돌았다). 직전 태그가 없으면 실행 비트를
#    절대 기준으로 본다(exec_bit_axis) — 건너뛰면 태그 없는 첫 출하에서 떨어진 실행 비트가 영구히 빠진다.
#    직전 태그 뒤에 0644 로 새로 생긴 훅(.githooks/*)도 불일치다 — 새 파일은 `create mode` 줄이라 모드 변경 대조에 잡히지
#    않고, git 은 실행 비트가 없는 훅을 조용히 건너뛴다(F-604). 셔뱅 스크립트는 인터프리터로 부르므로 여기서 보지 않는다.
#    이름 바꾸기 감지는 끈다(--no-renames) — 켜 두면 옮겨 온 훅이 `rename` 줄로만 나와 `create mode` 줄이 없다.
#    커밋(HEAD)과 작업 트리를 둘 다 직전 태그와 견준다 — 커밋은 출하되는 내용이고, 작업 트리는 커밋하기 전에 떨어진 실행 비트를 일찍
#    알린다. 작업 트리만 보면 chmod 로 고치고 커밋하지 않은 채 다시 돌린 게이트가 통과한다(태그가 가리킬 커밋에는 바뀐 모드가 남는다).
#    허용 목록 = mode_allow(tests/fixtures/release-mode-allow.txt) — 없으면 빈 목록.
#    반환: 0=충족 · 1=허용 밖 모드 변경 · 실행 비트 없음 · 새로 생긴 0644 훅 · 2=git 리포 아님 · 3=기준 태그 · 모드 목록 추출 실패(판정 불가)
mode_changed() {   # $1=`git diff --summary` 출력 · $2=허용 목록 → stdout: 허용 밖 `mode change` 경로(한 줄 하나)
  local to p
  while IFS=' ' read -r to p; do
    [ -n "$p" ] || continue
    # 훅(.githooks/*)은 허용 목록에 적을 수 없다(mode_allow 가 뺀다) — 실행 가능해진 변경은 고친 것이다. 0644 로 끝나는 변경만 잡는다
    #    (고친 것까지 잡으면 다음 태그까지 풀 길이 없다)
    case "$p" in .githooks/*) [ "$to" = 100644 ] || continue ;; esac
    grep -qxF -- "$p" <<< "$2" || printf '%s\n' "$p"
  done < <(sed -n 's/^ mode change [0-7]* => \([0-7]*\) \(.*\)$/\1 \2/p' <<< "$1")
}
hook_created_plain() {   # $1=`git diff --summary` 출력 · $2=허용 목록 → stdout: 0644 로 새로 생긴 훅(.githooks/*)의 경로(한 줄 하나)
  local m p
  while IFS=' ' read -r m p; do
    [ -n "$p" ] && [ "$m" = 100644 ] || continue
    grep -qxF -- "$p" <<< "$2" || printf '%s\n' "$p"
  done < <(sed -n 's/^ create mode \([0-7]*\) \(\.githooks\/.*\)$/\1 \2/p' <<< "$1")
}
mode_axis() {   # $1=리포 디렉토리
  local repo="$1" allowed head_sum work_sum w h bad=0 path
  git -C "$repo" rev-parse --verify HEAD >/dev/null 2>&1 \
    || { echo "  ⚠️ git 리포가 아니거나 커밋이 없다 — 모드 축 미판정(⛔ 통과 아님)"; return 2; }
  allowed="$(mode_allow "$repo")"
  release_base "$repo" || { echo "  ⚠️ 모드 축의 기준 태그를 정하지 못했다 — $REL_BASE_WHY(⛔ 통과 아님)"; return 3; }
  if [ -z "$REL_BASE" ]; then
    echo "  ℹ️ 직전 v* 태그 없음 — 실행 비트를 절대 기준으로 본다"
    exec_bit_axis "$repo" "$allowed"; return $?
  fi
  head_sum="$(git -C "$repo" -c core.quotepath=off diff --summary --no-renames "$REL_BASE" HEAD -- . 2>/dev/null)" \
    || { echo "  ⚠️ git diff --summary $REL_BASE HEAD 실패 — 커밋의 모드 변경 목록을 뽑지 못했다(⛔ 통과 아님)"; return 3; }
  work_sum="$(git -C "$repo" -c core.quotepath=off diff --summary --no-renames "$REL_BASE" -- . 2>/dev/null)" \
    || { echo "  ⚠️ git diff --summary $REL_BASE 실패 — 모드 변경 목록을 뽑지 못했다(⛔ 통과 아님)"; return 3; }
  # 작업 트리 쪽 적중을 먼저 적고, 커밋에만 남은 것(작업 트리에서는 되돌렸다)은 따로 적는다 — 고칠 곳이 다르다(커밋해야 한다)
  w="$(mode_changed "$work_sum" "$allowed")"; h="$(mode_changed "$head_sum" "$allowed")"
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    case "$path" in   # 훅은 허용 목록으로 풀리지 않는다(mode_allow 가 훅 줄을 뺀다) — 따라 하면 풀리는 안내만 낸다. 훅은 실행 비트를 잃은 경우만 여기에 온다
      .githooks/*) echo "  ❌ $REL_BASE 뒤 훅이 실행 비트를 잃었다: $path — 훅은 허용 목록으로 풀 수 없다(git 은 실행 비트가 없는 훅을 조용히 건너뛴다). 실행 비트를 되돌린다(chmod +x 뒤 stage)" ;;
      *) echo "  ❌ $REL_BASE 뒤 파일 모드가 바뀌었다: $path — 의도한 변경이면 tests/fixtures/release-mode-allow.txt 에 적는다" ;;
    esac; bad=1
  done <<< "$w"
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    if grep -qxF -- "$path" <<< "$w"; then continue; fi
    echo "  ❌ $REL_BASE 뒤 파일 모드가 바뀌었다(커밋 HEAD — 작업 트리에서 되돌린 모드가 커밋되지 않았다): $path — 커밋한 뒤 다시 돌린다"; bad=1
  done <<< "$h"
  w="$(hook_created_plain "$work_sum" "$allowed")"; h="$(hook_created_plain "$head_sum" "$allowed")"
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    echo "  ❌ $REL_BASE 뒤 새로 생긴 훅에 실행 비트가 없다(100644): $path — git 은 실행 비트가 없는 훅을 조용히 건너뛴다"; bad=1
  done <<< "$w"
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    if grep -qxF -- "$path" <<< "$w"; then continue; fi
    echo "  ❌ $REL_BASE 뒤 새로 생긴 훅에 실행 비트가 없다(100644 · 커밋 HEAD — 작업 트리에서 고친 모드가 커밋되지 않았다): $path — 커밋한 뒤 다시 돌린다"; bad=1
  done <<< "$h"
  return "$bad"
}

# ⑦ 중립화 — <ref> 대비 추가 줄(미추적 파일 포함)에 공개 저장소에 두면 안 되는 식별자가 있는가(F-420).
#    판정은 누수 규칙 정본(scripts/leak_rules.py --range · 문서 정책)이 한다 — 여기에 규칙 사본을 두지 않는다(사본은 한 벌만 고쳐진다).
#    비공개 이름 규칙은 $3 파일(한 줄 한 정규식 · `#` 주석)로만 받는다 — 규칙 자체가 프로젝트를 드러내므로 트리에 두지 않는다.
#    ⛔ 정본 모듈은 자기 위치로 옮겨 가지 않는다 — 검사할 저장소를 -C 로 넘긴다(이 스크립트는 자기 루트로 cd 했다).
#    ⛔ $3 이 비공개 규칙의 전부다(비었으면 내장 규칙만) — 정본 모듈이 env 를 다시 읽지 않게 FZ_NEUTRALIZE_RULES 를 비워 부른다.
#    반환: 0=적중 0 · 1=적중(`❌ 파일:줄: 규칙 — 토큰` · 이름 적중은 줄 없이 `❌ 마디: 경로 이름 · 규칙 — 토큰`) · 2=판정 불가(ref · git · 규칙 파일 · 정규식 · 디코드 · 바이너리 — `UNRUN:` 줄)
neutralize_axis() {   # $1=리포 · $2=기준 ref · $3=비공개 규칙 파일(빈 값 가능)
  if [ -n "${3:-}" ]; then
    FZ_NEUTRALIZE_RULES="" python3 "$ROOT_DIR/scripts/leak_rules.py" -C "$1" --range="$2" --rules="$3"
  else
    FZ_NEUTRALIZE_RULES="" python3 "$ROOT_DIR/scripts/leak_rules.py" -C "$1" --range="$2"
  fi
}

# ⑧ 커밋마다 축 — 출하 범위의 커밋을 하나씩 본다: 신원(author · committer) · 메시지 · 그 밖의 머리 · 추가 줄 · 새 경로 이름(첫 부모 대비 · --no-renames).
#    넘긴 태그도 본다 — 이름(경로 이름 규칙) · 주석 태그의 tagger · 주석 · 머리. 가리키는 커밋이 검사 범위 밖이면 판정 불가다(옛 이력에
#    남은 태그 — 올리면 그 커밋이 함께 나간다). 판정은 정본 모듈(--commits)이 한다.
#    기준 태그가 있으면 `기준..HEAD`, 없으면(v* 태그가 없는 첫 출하) 루트부터 HEAD 까지의 커밋 전부 + 작업 트리 전문(--with-tree)이다.
#    ⛔ 비공개 규칙 파일은 언제나 명시로 넘긴다($3 — 빈 파일 = 내장 규칙만). 정본 모듈이 env 를 다시 읽지 않게 FZ_NEUTRALIZE_RULES 를 비운다.
#    반환: 0=적중 0 · 1=적중(`❌ 신원 …` · `❌ 메시지 …` · `❌ 머리 …` · `❌ 추가 줄 …` · `❌ 경로 …` · `❌ tagger …` · `❌ 주석 …` · `❌ 전문 …`) ·
#          2=판정 불가(`UNRUN:` 줄 — 적중이 함께 있어도 2)
leak_axis() {   # $1=리포 · $2=기준 태그(빈 값 = 태그 없음) · $3=비공개 규칙 파일 · 나머지=볼 태그 이름
  local repo="$1" base="$2" rules="$3" t args; shift 3
  args=(-C "$repo" "--rules=$rules")
  for t in ${1+"$@"}; do args+=("--tag=$t"); done
  if [ -n "$base" ]; then args+=("--commits=$base..HEAD"); else args+=(--commits=HEAD --with-tree); fi
  FZ_NEUTRALIZE_RULES="" python3 "$ROOT_DIR/scripts/leak_rules.py" "${args[@]}"
}

# 누수 축 묶음(⑦ · ⑧) — 출하 경로가 부르는 그대로다(self-test 의 판정 불가 전파 셀도 이 함수를 부른다). ⑧ 은 커밋만 본다 —
#    기준이 있으면 ⑦ 을 HEAD 대비로 함께 돌아 커밋하지 않은 줄 · 미추적 파일을 본다(기준 대비로 돌면 커밋된 줄이 ⑦ · ⑧ 에 두 번 나온다).
#    기준이 없으면 ⑧ 의 작업 트리 전문(--with-tree)이 대신한다
release_leak() {   # $1=리포 · $2=기준 태그(빈 값 = 태그 없는 첫 출하) · $3=비공개 규칙 파일 · 나머지=볼 태그 이름
  local repo="$1" base="$2" rules="$3"; shift 3
  [ -z "$base" ] || leak_note "중립화 축" neutralize_axis "$repo" HEAD "$rules"
  leak_note "커밋마다 축" leak_axis "$repo" "$base" "$rules" ${1+"$@"}
}

# 축 판정 줄 — `축 함수 || { 2 → 미판정 note · 3 → 목록 추출 실패(판정 불가) · 그 밖 → 불일치 +1 }`. 2(판정 불가)는 통과가 아니다:
#    미판정 note 를 남겨 최종 판정(finish)이 0 을 내지 못하게 한다. 3 은 목록(기준 태그 · 변경 목록 · git status · git ls-files)을 뽑지
#    못한 것이라 unrun 으로 올린다(최종 exit 2). ⛔ 2 · 3 을 적중(1)과 한 칸으로 접지 않는다 — 고칠 것과 돌리지 못한 검사는 사유가 다르다
axis_note() {   # $1=축 이름(미판정 줄에 싣는다) · 나머지=부를 축 함수와 인자
  local name="$1" rc=0; shift
  "$@" || { rc=$?; case "$rc" in 2) note "$name 미판정 — 통과가 아니다" ;; 3) unrun_note "$name 목록 추출 실패" ;; *) fail=$((fail + 1)) ;; esac; }
}

# 누수 축 판정 줄 — 정본 모듈은 0(끝 줄 `LEAK_CLEAN`) · 1(적중 · 끝 줄 `LEAK_HIT`) · 2(판정 불가 — ref · git · diff · 규칙 파일 · 정규식 ·
#    디코드 · 바이너리)다. 종료 코드와 끝 줄이 맞지 않으면(파이썬 예외의 1 · 시그널 등) 판정 불가다 — unrun 으로 올려 최종 exit 를 2 로
#    만든다. ⛔ 판정 불가를 적중(1)과 한 칸으로 접지 않는다 — 접으면 다른 위반과 섞여 exit 1 로 끝난다
leak_note() {   # $1=축 이름 · 나머지=부를 축 함수와 인자
  local name="$1" out rc=0 last nl=$'\n'; shift
  out="$("$@")" || rc=$?
  [ -z "$out" ] || printf '%s\n' "$out"
  last=${out##*$nl}
  case "$rc:$last" in
    "0:LEAK_CLEAN "*) ;;
    "1:LEAK_HIT "*) fail=$((fail + 1)) ;;
    *) unrun_note "$name 미판정(정본 모듈 exit $rc)" ;;
  esac
}

# 최종 판정 — 판정 불가(unrun — 누수 축 · 목록 추출)가 하나라도 있으면 2 다(불일치가 함께 있어도 — 미판정이 위반보다 앞선다). 그다음
#    note(불일치 · 축 미판정)가 하나라도 있으면 1 이다. ⛔ 미판정 note 도 여기서 0 을 막는다(통과로 세지 않는다)
finish() {
  if [ "$unrun" -gt 0 ]; then
    echo "릴리즈 동기 판정 불가 ${unrun}건 · 불일치 ${fail}건 — 판정 불가가 앞선다(⛔ 통과 아님)"
    exit 2
  fi
  if [ "$fail" -gt 0 ]; then
    echo "릴리즈 동기 불일치 ${fail}건"
    exit 1
  fi
  if [ "$MODE" = "release" ]; then
    echo "RELEASE_SYNC_OK (버전 3곳 일치 · 가이드→표 참조 4건 · 노트 절 참조 · 모드 변경 0 · health-check exit 0 · 커밋 축 · 누수 축(중립화 · 커밋마다 신원 · 메시지 · 추가 줄 · 태그) · findings 선언 있음 — applied ↔ Closes 대조는 check_release_closes.py)"
  else
    echo "DOCS_SYNC_OK (버전 3곳 일치 · 가이드→표 참조 4건 · 노트 절 참조 · 모드 변경 0 · health-check exit 0)"
  fi
  exit 0
}

# ── --self-test — 임시 git 리포로 ⑤의 실패/통과 쌍을 확인한다 ────────────────
if [ "$MODE" = "self-test" ]; then
  pass=0; failed=0
  # 바깥 git 환경(훅이 건 GIT_DIR · GIT_INDEX_FILE 등)이 임시 저장소의 git 을 바깥 저장소로 돌리지 않게 끊는다
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE GIT_PREFIX
  # 호스트의 전역 · 시스템 git 설정도 끊는다 — 서명 강제(commit.gpgsign) · 전역 훅 경로가 임시 저장소의 커밋을 막으면 셀이 준비 실패(2)로
  #    끝난다. 아래 gx 를 쓰는 셀은 따로 끊지만 mk · mkr 로 만든 저장소는 이 줄에 기댄다
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  # 부모 git 이 `-c` 로 넘긴 설정도 끊는다 — 전역 · 시스템 설정을 끊어도 이 둘로는 서명 강제가 들어온다
  unset GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT
  # ⛔ git 단계의 exit code 를 버리지 않는다 — 실패를 삼키면 **위조 픽스처**가 만들어지고
  #    자기시험이 아무것도 증명하지 않는다 (`lint_contracts` #N5 가 이것을 잡는다).
  #    ⛔ `mk` 밖에 정의한다 — `mk` 는 `$( )` 서브셸에서 돌아, 그 안에서 정의하면 호출부(③ · ⑧)에 없다.
  gq() { "$@" >/dev/null 2>&1 || { echo "⛔ 픽스처 준비 실패: $*" >&2; exit 2; }; }
  mk() {   # $1=버전 · stdout=리포 경로 (v$1 을 전부 커밋한 상태)
    local d ver="$1"
    d=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX")
    mkdir -p "$d/.claude-plugin" "$d/docs/releases"
    printf '{"version": "%s"}\n' "$ver" > "$d/.claude-plugin/plugin.json"
    printf '{"plugins": [{"version": "%s"}]}\n' "$ver" > "$d/.claude-plugin/marketplace.json"
    printf '# Changelog\n\n### v%s (2026-01-01) — x\n' "$ver" > "$d/CHANGELOG.md"
    printf '# v%s\n' "$ver" > "$d/docs/releases/v${ver}.md"
    gq git -C "$d" init -q
    gq git -C "$d" -c user.email=t@t -c user.name=t add -A
    gq git -C "$d" -c user.email=t@t -c user.name=t commit -qm "v$ver"
    echo "$d"
  }
  # ⛔ `R=$(mk …)` 는 **명령 치환 서브셸**이라 mk 안의 `exit 2` 가 런을 멈추지 못한다 —
  #    실측: 서브셸만 죽고 `$R` 이 비어 `/CHANGELOG.md` 에 쓰려 했고 자기시험은 4/5 로 계속됐다.
  #    그래서 호출부에서 종료코드와 산출물을 **둘 다** 검산한다.
  #    ⛔⛔ **`exit` 는 `$( )` 를 벗어나지 못한다.** 그래서 이 함수는 경로를 stdout 이 아니라
  #        전역 `REPO` 에 담고, 호출부는 치환 **없이** `mkr 1.0.0` 로 부른다. 치환으로 부르면
  #        여기의 `exit 2` 가 다시 서브셸에 갇힌다(실측: 두 층 모두에서 갇혔다).
  REPO=""
  mkr() {
    REPO=$(mk "$1") || { echo "⛔ 픽스처 준비 실패 (mk 종료코드)" >&2; exit 2; }
    [ -n "$REPO" ] && [ -d "$REPO/.git" ] \
      || { echo "⛔ 픽스처 리포가 만들어지지 않았다: '${REPO}'" >&2; exit 2; }
  }

  ok_() { pass=$((pass+1)); [ -n "${FZ_SELFTEST_LIST:-}" ] && echo "PASS $1"; return 0; }   # 통과 줄 — 게이트가 셀 이름으로 센다
  case_() {   # $1=이름 · $2=기대 반환 · $3=리포 · $4=선언버전
    local out rc
    out=$(commit_axis "$3" "$4"); rc=$?
    if [ "$rc" = "$2" ]; then ok_ "$1"
    else failed=$((failed+1)); echo "  FAIL $1: 반환 $rc (기대 $2)"; echo "$out" | sed 's/^/        /'; fi
  }

  # ① 정상 — 전부 커밋됨
  mkr 1.0.0; R="$REPO"; case_ "all-committed" 0 "$R" "1.0.0"; rm -rf "$R"

  # ② 결함 — 버전만 디스크에서 올리고 커밋하지 않았다 (v4.33.0 실패 모드)
  mkr 1.0.0; R="$REPO"
  printf '{"version": "1.1.0"}\n' > "$R/.claude-plugin/plugin.json"
  case_ "bump-without-release-doc" 1 "$R" "1.1.0"; rm -rf "$R"
  #    ⚠️ 이 픽스처는 **격리형이 아니다** — dirty 와 릴리즈 문서 부재가 함께 발화한다.
  #       현실적 상태(버전 올리고 문서를 빠뜨림)라서 남기고, 각 검사의 격리는 아래 두 건이 한다.

  # ③ 결함 — 릴리즈 문서가 untracked
  mkr 1.0.0; R="$REPO"
  printf '{"version": "1.1.0"}\n' > "$R/.claude-plugin/plugin.json"
  printf '{"plugins": [{"version": "1.1.0"}]}\n' > "$R/.claude-plugin/marketplace.json"
  printf '# Changelog\n\n### v1.1.0 (2026-01-02) — y\n' > "$R/CHANGELOG.md"
  printf '# v1.1.0\n' > "$R/docs/releases/v1.1.0.md"
  gq git -C "$R" -c user.email=t@t -c user.name=t add .claude-plugin CHANGELOG.md
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm "v1.1.0 (릴리즈 문서 빠뜨림)"
  case_ "release-doc-untracked" 1 "$R" "1.1.0"; rm -rf "$R"

  # ④ 결함 — 릴리즈 문서는 추적된 채로 **버전 선언 파일만** 더럽다.
  #    ⛔ 이 픽스처가 dirty 검사를 **격리**한다. 릴리즈 문서를 빼면 다른 검사가 발화해
  #       dirty 를 지워도 통과했다(실측 — 헛돌이였다).
  mkr 1.0.0; R="$REPO"
  printf '# Changelog\n\n### v1.0.0 (2026-01-01) — x\n\n추가 한 줄\n' > "$R/CHANGELOG.md"
  case_ "version-file-dirty-only" 1 "$R" "1.0.0"; rm -rf "$R"

  # ④-b 결함 — 릴리즈 문서를 작업 트리에서만 고쳤다(추적은 된다 · 버전 선언 파일은 깨끗하다). findings 축은 작업 트리의 노트를 읽으므로
  #    커밋하지 않은 `Closes:` 줄로 통과하면 태그가 가리킬 커밋의 노트에는 그 선언이 없다
  mkr 1.0.0; R="$REPO"
  printf '\nCloses: F-001\n' >> "$R/docs/releases/v1.0.0.md"
  case_ "release-doc-dirty-only" 1 "$R" "1.0.0"; rm -rf "$R"

  # ⑤ 측정 불가 — git 리포가 아니다. ⛔ 미판정은 통과가 아니다
  R=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX"); case_ "not-a-repo" 2 "$R" "1.0.0"; rm -rf "$R"

  # ①-b 하위 플러그인 — v1.0.0 태그 리포에 `mods/sub` 를 둔다. $1=태그 때 둘지(yes/no) · $2=하위 버전
  sub_files() {   # $1=리포 · $2=하위 plugin.json 버전 · $3=marketplace 하위 버전
    mkdir -p "$1/mods/sub/.claude-plugin"
    printf '{"version": "%s"}\n' "$2" > "$1/mods/sub/.claude-plugin/plugin.json"
    printf '{"plugins": [{"version": "1.0.0"}, {"name": "sub", "source": "./mods/sub", "version": "%s"}]}\n' "$3" > "$1/.claude-plugin/marketplace.json"
  }
  case_sub() {   # $1=이름 · $2=기대 반환 · $3=리포
    local out rc
    out=$(subplugin_axis "$3"); rc=$?
    if [ "$rc" = "$2" ]; then ok_ "$1"
    else failed=$((failed+1)); echo "  FAIL $1: 반환 $rc (기대 $2)"; echo "$out" | sed 's/^/        /'; fi
  }
  # ⑥ 정상 — 태그 뒤 새로 생긴 하위 플러그인(태그에 없던 폴더)은 버전 올림 검사를 건너뛴다
  mkr 1.0.0; R="$REPO"; gq git -C "$R" tag v1.0.0
  sub_files "$R" 0.1.0 0.1.0; case_sub "sub-new-after-tag" 0 "$R"; rm -rf "$R"
  # ⑦ 결함 — 하위 plugin.json 과 marketplace 항목의 버전이 다르다
  mkr 1.0.0; R="$REPO"; gq git -C "$R" tag v1.0.0
  sub_files "$R" 0.1.0 0.2.0; case_sub "sub-version-mismatch" 1 "$R"; rm -rf "$R"
  # ⑧ 결함 — 태그에 있던 하위 플러그인 내용이 바뀌었는데 버전은 그대로다(untracked 파일 추가)
  mkr 1.0.0; R="$REPO"; sub_files "$R" 0.1.0 0.1.0
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm "sub 0.1.0"; gq git -C "$R" tag v1.0.0
  printf 'x\n' > "$R/mods/sub/new.ts"; case_sub "sub-changed-no-bump" 1 "$R"
  # ⑨ 정상 — 같은 변경에 두 곳 버전을 함께 올렸다(⑧ 의 대조)
  sub_files "$R" 0.1.1 0.1.1; case_sub "sub-changed-bumped" 0 "$R"; rm -rf "$R"
  # ⑩ 결함 — v 로 시작하지만 출하 태그가 아닌 이름(vendor-…)은 이 축의 기준도 되지 않는다. 기준이 되면 그 앞에서 바뀐 하위
  #    플러그인이 범위에서 빠져 버전 올림 검사를 지나간다(⑧ 의 변경을 커밋하고 그 커밋에 그런 태그를 단 꼴)
  mkr 1.0.0; R="$REPO"; sub_files "$R" 0.1.0 0.1.0
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm "sub 0.1.0"; gq git -C "$R" tag v1.0.0
  printf 'x\n' > "$R/mods/sub/new.ts"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm "sub 변경"; gq git -C "$R" tag vendor-sync
  case_sub "sub-non-version-v-tag-ignored" 1 "$R"; rm -rf "$R"
  # ⑪ 정상 — 출하 태그가 아닌 v 이름뿐이면 직전 출하가 없다(버전 올림 검사를 건너뛴다). 그 이름을 'v* 태그 있음' 으로 세면
  #    기준을 찾지 못해 판정 불가로 떨어진다
  mkr 1.0.0; R="$REPO"; sub_files "$R" 0.1.0 0.1.0
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm "sub 0.1.0"; gq git -C "$R" tag vendor-sync
  printf 'x\n' > "$R/mods/sub/new.ts"; case_sub "sub-only-non-version-v-tag-no-base" 0 "$R"; rm -rf "$R"

  # ⑥ findings 축 — 노트 선언만 본다(레지스트리 무관)
  case_fx() {   # $1=이름 · $2=기대 반환 · $3=노트 본문(빈 문자열이면 노트 없음)
    local d out rc
    d=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX")
    [ -n "$3" ] && printf '%s\n' "$3" > "$d/v9.9.9.md"
    out=$(findings_axis "$d/v9.9.9.md"); rc=$?
    rm -rf "$d"
    if [ "$rc" = "$2" ]; then ok_ "$1"
    else failed=$((failed+1)); echo "  FAIL $1: 반환 $rc (기대 $2)"; echo "$out" | sed 's/^/        /'; fi
  }
  case_fx "findings-axis-closes-ok" 0 $'# v9.9.9\n\nCloses: F-001'
  case_fx "findings-axis-no-finding-marker-ok" 0 $'# v9.9.9\n\n닫은 finding 이 없어 `Closes:` 줄을 쓰지 않는다.'
  case_fx "findings-axis-bullet-marker-ok" 0 $'# v9.9.9\n\n- 닫은 finding 없음 — 문서만 고쳤다'
  # 표지는 줄 머리 꼴이다 — 문장 중간의 언급 · 코드 블록 안의 예시(표지 · Closes 줄)는 선언이 아니다
  case_fx "findings-axis-midline-marker-fails" 1 $'# v9.9.9\n\n이 릴리즈는 닫은 finding 이 없어 `Closes:` 줄을 쓰지 않는다.'
  case_fx "findings-axis-fenced-marker-fails" 1 $'# v9.9.9\n\n```\n닫은 finding 없음\n```'
  case_fx "findings-axis-fenced-closes-fails" 1 $'# v9.9.9\n\n```\nCloses: F-001\n```'
  case_fx "findings-axis-missing-fails" 1 $'# v9.9.9\n\n<!-- Closes: 줄 없음 -->\n본문만 있다'
  # 템플릿 원문 그대로인 노트는 아무것도 선언하지 않았다 — 자리표시 Closes · 따옴표 안 표지 안내가 술어를 채우면 안 된다
  case_fx "findings-axis-template-verbatim-fails" 1 "$(cat "$ROOT_DIR/docs/releases/_TEMPLATE.md")"
  case_fx "findings-axis-quoted-marker-fails" 1 $'# v9.9.9\n\n- 닫은 것이 없으면 본문에 \'닫은 finding 이 없어 …\' 표지를 둔다'
  case_fx "findings-axis-backtick-marker-fails" 1 $'# v9.9.9\n\n- 닫은 것이 없으면 본문에 `닫은 finding 이 없어 …` 표지를 둔다'
  case_fx "findings-axis-curly-marker-fails" 1 $'# v9.9.9\n\n- 닫은 것이 없으면 본문에 ‘닫은 finding 이 없어 …’ 표지를 둔다'
  case_fx "findings-axis-empty-closes-fails" 1 $'# v9.9.9\n\nCloses:'
  #    선언 판정 도구를 부르지 못하면 미판정(2)이다 — '선언 없음'(1)으로 읽지 않는다
  FXD=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX"); printf '# v9.9.9\n\nCloses: F-001\n' > "$FXD/v9.9.9.md"
  KEEP_SELF_DIR="$SELF_DIR"; SELF_DIR="$FXD/absent"; out=$(findings_axis "$FXD/v9.9.9.md"); rc=$?; SELF_DIR="$KEEP_SELF_DIR"; rm -rf "$FXD"
  if [ "$rc" = 2 ] && grep -q '선언 판정을 하지 못했다' <<< "$out"; then ok_ "findings-axis-decl-tool-missing-unrun"
  else failed=$((failed+1)); echo "  FAIL findings-axis-decl-tool-missing-unrun: 반환 $rc (기대 2)"; echo "$out" | sed 's/^/        /'; fi
  # 기본 모드는 ⑥ 을 부르지 않고 FZ_FINDINGS_ROOT 도 읽지 않는다 — 실행 확인은 기본 모드 전체 실행(health-check 포함)이 맡는다
  calls=$(grep -n 'findings_axis "\$' "${BASH_SOURCE[0]}" | grep -v 'case_fx\|out=\$(findings_axis' | cut -d: -f1)
  dm_ok=1
  for ln in $calls; do sed -n "$((ln - 1)),${ln}p" "${BASH_SOURCE[0]}" | grep -q 'MODE" = "release"' || dm_ok=0; done
  [ -n "$calls" ] || dm_ok=0
  sed -n '/^findings_axis()/,/^}/p' "${BASH_SOURCE[0]}" | grep -q 'FZ_FINDINGS_ROOT' && dm_ok=0
  if [ "$dm_ok" = 1 ]; then ok_ "default-mode-no-registry-ok"; else failed=$((failed+1)); echo "  FAIL default-mode-no-registry-ok: ⑥ 호출이 release 가드 밖이거나 레지스트리를 읽는다"; fi

  # 축 판정 공용 — $1=이름 · $2=기대 반환 · 나머지=부를 함수와 인자
  case_ax() {
    local name="$1" want="$2" out rc; shift 2
    out=$("$@"); rc=$?
    if [ "$rc" = "$want" ]; then ok_ "$name"
    else failed=$((failed+1)); echo "  FAIL $name: 반환 $rc (기대 $want)"; echo "$out" | sed 's/^/        /'; fi
  }

  # ②-b 노트 절 참조(F-421) — 노트 제목 둘(무엇이 바뀌었나 · 2. 검증)과 CHANGELOG 한 줄
  nr() {   # $1=CHANGELOG 본문 줄 · stdout 없음 · 전역 R 에 리포
    R=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX"); mkdir -p "$R/docs/releases"
    printf '# v1.0.0 — x\n\n## 무엇이 바뀌었나\n\n## 2. 검증\n\n## 남은 것 (가이드 갱신)\n' > "$R/docs/releases/v1.0.0.md"
    printf '# Changelog\n\n### v1.0.0 (2026-01-01) — x\n\n%s\n' "$1" > "$R/CHANGELOG.md"
  }
  nr "자세한 표는 릴리즈 노트 § 무엇을 고쳤나 에 있다"; case_ax "f421-note-section-ref-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  nr "자세한 표는 릴리즈 노트 § 무엇이 바뀌었나 에 있다"; case_ax "f421-note-section-ref-ok" 0 note_ref_axis "$R"; rm -rf "$R"
  nr "남은 일은 릴리즈 노트 § 남은 것에 적었다"; case_ax "f421-note-section-prefix-ok" 0 note_ref_axis "$R"; rm -rf "$R"
  nr "결과는 릴리즈 노트 §3 표"; case_ax "f421-note-section-number-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  nr "결과는 릴리즈 노트 §2 표"; case_ax "f421-note-section-number-ok" 0 note_ref_axis "$R"; rm -rf "$R"
  nr "근거: docs/releases/v1.0.0.md 'Closes 줄 규약' 절"; case_ax "f421-quoted-section-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  nr "근거: docs/releases/v2.0.0.md '무엇이 바뀌었나' 절"; case_ax "f421-note-file-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  # 실제 트리 — 지금 README · CHANGELOG 의 참조가 모두 풀린다(이 검사가 막을 회귀의 출발점)
  case_ax "f421-real-tree-refs-ok" 0 note_ref_axis "$ROOT_DIR"

  # ②-c 모드 변경(F-427) — 태그 v1.0.0 의 0755 스크립트를 0644 로. 태그가 HEAD 에만 있어 직전 태그가 없다 — 실행 비트 절대 기준
  #    경로(exec_bit_axis)를 돈다. 직전 태그 대비 경로는 아래 mode-head-tag-* 셀이 본다
  mkr 1.0.0; R="$REPO"; printf '#!/bin/bash\n' > "$R/run.sh"; chmod 755 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm s
  gq git -C "$R" tag v1.0.0; chmod 644 "$R/run.sh"
  case_ax "f427-mode-change-flagged" 1 mode_axis "$R"
  #    안내는 따라 하면 풀려야 한다 — 훅이 아닌 파일은 허용 목록을 가리킨다(훅 쪽은 아래 *-hook-*-advice-not-allowlist 셀이 본다)
  out=$(mode_axis "$R")
  if grep -q 'release-mode-allow.txt 에 적는다' <<< "$out" && ! grep -q '훅은 허용 목록으로' <<< "$out"; then ok_ "exec-bit-script-advice-names-allowlist"
  else failed=$((failed+1)); echo "  FAIL exec-bit-script-advice-names-allowlist: 스크립트 안내가 허용 목록을 가리키지 않는다"; echo "$out" | sed 's/^/        /'; fi
  mkdir -p "$R/tests/fixtures"; printf '# 의도한 변경\nrun.sh\n' > "$R/tests/fixtures/release-mode-allow.txt"
  case_ax "f427-mode-change-allowlisted" 0 mode_axis "$R"
  chmod 755 "$R/run.sh"; rm -rf "$R/tests"; case_ax "f427-no-mode-change-ok" 0 mode_axis "$R"; rm -rf "$R"
  #    커밋에 0644 로 든 셔뱅 파일 — 작업 트리와 인덱스에서만 고친 것은 통과가 아니다(출하되는 것은 커밋이다). 커밋하면 통과다
  mkr 1.0.0; R="$REPO"; printf '#!/bin/bash\n' > "$R/run.sh"; chmod 644 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm s
  chmod 755 "$R/run.sh"; gq git -C "$R" add -A
  case_ax "exec-bit-fixed-uncommitted-flagged" 1 mode_axis "$R"
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm fix; case_ax "exec-bit-fixed-committed-ok" 0 mode_axis "$R"; rm -rf "$R"
  #    허용 목록에 훅을 적어도 허용하지 않는다 — 태그 없는 저장소의 0644 훅은 목록과 무관하게 불일치다
  mkr 1.0.0; R="$REPO"; mkdir -p "$R/.githooks" "$R/tests/fixtures"; printf '#!/bin/bash\n' > "$R/.githooks/pre-push"; chmod 644 "$R/.githooks/pre-push"
  printf '.githooks/pre-push\n' > "$R/tests/fixtures/release-mode-allow.txt"
  #    커밋 전(인덱스에만 있는 새 훅)에도 같다 — 이때는 커밋 쪽 순회가 볼 것이 없어, 허용 목록에서 훅을 빼는 것만이 막는다
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; case_ax "mode-allowlisted-staged-hook-still-flagged" 1 mode_axis "$R"
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm hook
  case_ax "mode-allowlisted-hook-still-flagged" 1 mode_axis "$R"
  #    인덱스 · 작업 트리에 있는 훅은 한 번만 적는다 — 커밋에만 남은 훅을 보는 순회가 같은 훅을 다시 적지 않는다
  out=$(mode_axis "$R"); rc=$(grep -c '❌' <<< "$out")
  if [ "$rc" = 1 ]; then ok_ "exec-bit-present-hook-reported-once"
  else failed=$((failed+1)); echo "  FAIL exec-bit-present-hook-reported-once: ❌ 줄 $rc (기대 1)"; echo "$out" | sed 's/^/        /'; fi
  #    훅은 허용 목록으로 풀리지 않는다 — 허용 목록에 적으라는 안내를 내면 따라 해도 그대로 막힌다
  if grep -q '훅은 허용 목록으로 풀 수 없다' <<< "$out" && ! grep -q 'release-mode-allow.txt 에 적는다' <<< "$out"; then ok_ "exec-bit-hook-advice-not-allowlist"
  else failed=$((failed+1)); echo "  FAIL exec-bit-hook-advice-not-allowlist: 훅 안내가 허용 목록을 가리킨다"; echo "$out" | sed 's/^/        /'; fi
  rm -rf "$R"
  #    실행 비트를 주고 stage 까지 했으면 남은 일은 커밋이다 — 그때 chmod 를 다시 권하면 따라 해도 그대로 막힌다
  mkr 1.0.0; R="$REPO"; mkdir -p "$R/.githooks"; printf '#!/bin/bash\n' > "$R/.githooks/pre-push"; chmod 644 "$R/.githooks/pre-push"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm hook
  chmod 755 "$R/.githooks/pre-push"; gq git -C "$R" add -A
  out=$(mode_axis "$R")
  if grep -q '훅은 허용 목록으로 풀 수 없다 — 실행 비트는 이미 줬다. 커밋한 뒤 다시 돌린다' <<< "$out" && ! grep -q 'chmod' <<< "$out"; then ok_ "exec-bit-hook-head-only-advice-says-commit"
  else failed=$((failed+1)); echo "  FAIL exec-bit-hook-head-only-advice-says-commit: 커밋만 남았는데 chmod 를 다시 권한다"; echo "$out" | sed 's/^/        /'; fi
  rm -rf "$R"
  #    커밋에 0644 로 남은 훅 — 작업 트리에서 지우거나 인덱스에서 빼도, 커밋하지 않았으면 태그가 가리킬 커밋에는 그대로다. 지운 것을
  #    커밋하면 통과다. 실행 가능한 훅을 지운 것 · 훅이 아닌 0644 파일(버전 선언 파일)은 이 순회가 잡지 않는다
  mkr 1.0.0; R="$REPO"; mkdir -p "$R/.githooks"; printf '#!/bin/bash\n' > "$R/.githooks/pre-push"; chmod 644 "$R/.githooks/pre-push"
  printf '#!/bin/bash\n' > "$R/.githooks/pre-commit"; chmod 755 "$R/.githooks/pre-commit"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm hooks
  rm "$R/.githooks/pre-push"; case_ax "exec-bit-head-hook-deleted-uncommitted-flagged" 1 mode_axis "$R"
  gq git -C "$R" rm -q --cached .githooks/pre-push; case_ax "exec-bit-head-hook-unstaged-uncommitted-flagged" 1 mode_axis "$R"
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm rm; rm "$R/.githooks/pre-commit"
  case_ax "exec-bit-head-exec-hook-deleted-ok" 0 mode_axis "$R"; rm -rf "$R"
  #    커밋에 0644 로 남은 셔뱅 스크립트 — 작업 트리에서 셔뱅 줄을 지우거나 파일을 지워도, 커밋하지 않았으면 커밋에는 그대로다(대상은 커밋의
  #    블롭으로도 정한다). 허용 목록의 스크립트를 지운 것 · 셔뱅이 없는 파일을 고친 것은 잡지 않는다. 커밋의 블롭을 읽지 못하면 판정 불가다
  mkr 1.0.0; R="$REPO"; printf '#!/bin/bash\necho a\n' > "$R/run.sh"; chmod 644 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm script
  printf 'echo a\n' > "$R/run.sh"; case_ax "exec-bit-head-script-shebang-removed-flagged" 1 mode_axis "$R"
  rm "$R/run.sh"; case_ax "exec-bit-head-script-deleted-flagged" 1 mode_axis "$R"; rm -rf "$R"
  mkr 1.0.0; R="$REPO"; mkdir -p "$R/tests/fixtures"; printf '#!/bin/bash\necho b\n' > "$R/ok.sh"; chmod 644 "$R/ok.sh"
  printf 'ok.sh\n' > "$R/tests/fixtures/release-mode-allow.txt"; printf 'data\n' > "$R/data.txt"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm allowed
  rm "$R/ok.sh"; printf 'data 2\n' > "$R/data.txt"; case_ax "exec-bit-head-allowlisted-and-plain-edited-ok" 0 mode_axis "$R"; rm -rf "$R"
  mkr 1.0.0; R="$REPO"; printf '#!/bin/bash\necho a\n' > "$R/run.sh"; chmod 644 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm script
  out=$(git -C "$R" rev-parse HEAD:run.sh) || { echo "⛔ 픽스처 준비 실패 (rev-parse)" >&2; exit 2; }
  printf 'echo a\n' > "$R/run.sh"; rm -f "$R/.git/objects/${out:0:2}/${out:2}"
  case_ax "list-fail-exec-bit-head-blob-unrun" 3 mode_axis "$R"; rm -rf "$R"
  #    v 로 시작하지만 출하 태그가 아닌 이름(vendor-…)은 기준이 되지 않는다 — 기준이 되면 그 앞의 모드 변경이 범위에서 빠진다
  mkr 1.0.0; R="$REPO"; printf '#!/bin/bash\n' > "$R/run.sh"; chmod 755 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm s
  gq git -C "$R" tag v1.0.0; chmod 644 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm m
  gq git -C "$R" tag vendor-sync; printf 'x\n' > "$R/x.md"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm later
  case_ax "mode-non-version-v-tag-ignored" 1 mode_axis "$R"; rm -rf "$R"
  #    출하 태그가 아닌 v 이름뿐인 저장소는 첫 출하다(실행 비트를 절대 기준으로 본다) — 그 이름을 'v* 태그 있음' 으로 세면 기준을
  #    찾지 못해 판정 불가로 떨어진다
  mkr 1.0.0; R="$REPO"; printf '#!/bin/bash\n' > "$R/run.sh"; chmod 644 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm s
  gq git -C "$R" tag vendor-sync
  case_ax "mode-only-non-version-v-tag-first-release" 1 mode_axis "$R"; rm -rf "$R"

  # ── 아래 셀의 임시 저장소 — 전역 · 시스템 git 설정을 끊고 훅 · 서명을 끄고 author · committer 를 합성 값으로 둔다.
  #    합성 신원은 누수 규칙의 허용 꼴(noreply)이다 — 셀의 적중 · 판정 불가는 주입한 것에서만 나온다
  SID="0+fz-selftest@users.noreply.github.com"
  gx() {   # 격리 git — 출력을 그대로 낸다(값을 받을 때 쓴다)
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=fz-selftest GIT_AUTHOR_EMAIL="$SID" \
      GIT_COMMITTER_NAME=fz-selftest GIT_COMMITTER_EMAIL="$SID" \
      git -c core.hooksPath=/dev/null -c commit.gpgsign=false -c tag.gpgsign=false "$@"
  }
  gi() { gq gx "$@"; }   # 격리 git — 실패면 픽스처 준비 실패(gq · exit 2)
  mki() {   # $1=버전 — 격리 저장소에 v$1 산출물을 커밋한다(전역 REPO · 태그 없음). ⛔ 치환 없이 부른다 — exit 가 서브셸에 갇히지 않게
    REPO="$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX")" || { echo "⛔ 픽스처 준비 실패 (mktemp)" >&2; exit 2; }
    mkdir -p "$REPO/.claude-plugin" "$REPO/docs/releases" || { echo "⛔ 픽스처 준비 실패 (mkdir)" >&2; exit 2; }
    printf '{"version": "%s"}\n' "$1" > "$REPO/.claude-plugin/plugin.json"
    printf '{"plugins": [{"version": "%s"}]}\n' "$1" > "$REPO/.claude-plugin/marketplace.json"
    printf '# Changelog\n\n### v%s (2026-01-01) — x\n' "$1" > "$REPO/CHANGELOG.md"
    printf '# v%s\n' "$1" > "$REPO/docs/releases/v$1.md"
    gi -C "$REPO" init -q; gi -C "$REPO" add -A; gi -C "$REPO" commit -qm "v$1"
  }

  # ②-c 기준 태그 — HEAD 에 붙은 v* 태그(v1.1.0)는 빼고 직전 태그(v1.0.0)와 비교한다(태그를 단 뒤 다시 돌려도 자기 자신과 비교하지
  #    않는다). 직전 태그 대비 경로의 허용 목록 분기 · 모드 변경 없음도 여기서 본다 — 위 f427 셀은 직전 태그가 없어 그 경로를 돌지 않는다
  mki 1.0.0; R="$REPO"; printf '#!/bin/bash\n' > "$R/run.sh"; chmod 755 "$R/run.sh"
  gi -C "$R" add -A; gi -C "$R" commit -qm s; gi -C "$R" tag v1.0.0
  chmod 644 "$R/run.sh"; gi -C "$R" add -A; gi -C "$R" commit -qm m; gi -C "$R" tag v1.1.0
  case_ax "mode-head-tag-uses-prior" 1 mode_axis "$R"
  out=$(mode_axis "$R")
  if grep -q 'release-mode-allow.txt 에 적는다' <<< "$out" && ! grep -q '훅은 허용 목록으로' <<< "$out"; then ok_ "mode-script-advice-names-allowlist"
  else failed=$((failed+1)); echo "  FAIL mode-script-advice-names-allowlist: 스크립트 안내가 허용 목록을 가리키지 않는다"; echo "$out" | sed 's/^/        /'; fi
  mkdir -p "$R/tests/fixtures"; printf '# 의도한 변경\nrun.sh\n' > "$R/tests/fixtures/release-mode-allow.txt"
  case_ax "mode-head-tag-allowlisted" 0 mode_axis "$R"
  #    작업 트리에서만 되돌린 모드는 통과가 아니다 — 커밋(HEAD)에는 바뀐 모드가 남아 있다. 커밋하고 태그를 그 커밋으로 옮기면 통과다
  rm -rf "$R/tests"; chmod 755 "$R/run.sh"; case_ax "mode-head-tag-fixed-uncommitted-flagged" 1 mode_axis "$R"
  gi -C "$R" add -A; gi -C "$R" commit -qm fix; gi -C "$R" tag -f v1.1.0
  case_ax "mode-head-tag-clean-ok" 0 mode_axis "$R"
  #    커밋은 깨끗하고 작업 트리에서만 실행 비트가 떨어졌다 — 커밋하기 전에 알린다
  chmod 644 "$R/run.sh"; case_ax "mode-worktree-only-change-flagged" 1 mode_axis "$R"; rm -rf "$R"
  # ②-c 훅의 모드 변경 — 실행 가능해진 변경(0644 → 0755)은 고친 것이라 불일치가 아니다(훅은 허용 목록에 적을 수 없어, 잡으면 풀 길이 없다).
  #    실행 비트를 잃은 변경은 허용 목록에 적어도 불일치다
  mki 1.0.0; R="$REPO"; mkdir -p "$R/.githooks" "$R/tests/fixtures"; printf '#!/bin/sh\n' > "$R/.githooks/pre-push"; chmod 644 "$R/.githooks/pre-push"
  printf '.githooks/pre-push\n' > "$R/tests/fixtures/release-mode-allow.txt"
  gi -C "$R" add -A; gi -C "$R" commit -qm s; gi -C "$R" tag v1.0.0
  chmod 755 "$R/.githooks/pre-push"; gi -C "$R" add -A; gi -C "$R" commit -qm fix
  case_ax "mode-hook-made-exec-ok" 0 mode_axis "$R"
  gi -C "$R" tag v1.0.1; chmod 644 "$R/.githooks/pre-push"; gi -C "$R" add -A; gi -C "$R" commit -qm lost
  case_ax "mode-hook-lost-exec-allowlisted-still-flagged" 1 mode_axis "$R"
  out=$(mode_axis "$R")
  if grep -q '훅은 허용 목록으로 풀 수 없다' <<< "$out" && ! grep -q 'release-mode-allow.txt 에 적는다' <<< "$out"; then ok_ "mode-hook-lost-exec-advice-not-allowlist"
  else failed=$((failed+1)); echo "  FAIL mode-hook-lost-exec-advice-not-allowlist: 훅 안내가 허용 목록을 가리킨다"; echo "$out" | sed 's/^/        /'; fi
  rm -rf "$R"
  # ②-c 이름 바꾸기로 들어온 훅 — 이름 바꾸기 감지를 켜 두면 `rename` 줄만 나오고 `create mode` 줄이 없다. 감지를 꺼야 0644 훅이 보인다
  mki 1.0.0; R="$REPO"; printf '#!/bin/sh\necho a\necho b\necho c\necho d\n' > "$R/tool.sh"; chmod 644 "$R/tool.sh"
  gi -C "$R" add -A; gi -C "$R" commit -qm s; gi -C "$R" tag v1.0.0
  mkdir -p "$R/.githooks"; gi -C "$R" mv tool.sh .githooks/post-merge; gi -C "$R" commit -qm m
  case_ax "mode-moved-hook-nonexec-flagged" 1 mode_axis "$R"
  #    커밋 쪽만 — 작업 트리에서 실행 비트를 고치고 커밋하지 않았다. 작업 트리 쪽 대조에는 0755 로 새로 생긴 훅이라 조용하고, 커밋 쪽 대조가 잡는다
  chmod 755 "$R/.githooks/post-merge"; case_ax "mode-moved-hook-fixed-uncommitted-flagged" 1 mode_axis "$R"; rm -rf "$R"
  #    작업 트리 쪽만 — 옮기기만 하고(인덱스) 커밋하지 않았다. 커밋 쪽 대조에는 훅이 없고, 작업 트리 쪽 대조가 잡는다. 태그 뒤에 커밋을 하나 둔다 —
  #    태그가 HEAD 에 있으면 직전 태그가 없는 경로(실행 비트 절대 기준)로 빠진다
  mki 1.0.0; R="$REPO"; printf '#!/bin/sh\necho a\necho b\necho c\necho d\n' > "$R/tool.sh"; chmod 644 "$R/tool.sh"
  gi -C "$R" add -A; gi -C "$R" commit -qm s; gi -C "$R" tag v1.0.0
  printf 'x\n' > "$R/x.md"; gi -C "$R" add -A; gi -C "$R" commit -qm later
  mkdir -p "$R/.githooks"; gi -C "$R" mv tool.sh .githooks/post-merge
  case_ax "mode-moved-hook-uncommitted-flagged" 1 mode_axis "$R"; rm -rf "$R"
  # ②-c 직전 태그 없음 — 실행 비트를 절대 기준으로 본다: `.githooks/*` · 셔뱅 파일은 실행 가능해야 하고 그 밖의 파일은 보지 않는다
  mki 1.0.0; R="$REPO"; mkdir -p "$R/.githooks"
  printf 'echo hook\n' > "$R/.githooks/pre-push"; printf '#!/bin/sh\n' > "$R/tool.sh"; printf 'data\n' > "$R/data.txt"
  chmod 644 "$R/.githooks/pre-push" "$R/tool.sh" "$R/data.txt"; gi -C "$R" add -A; gi -C "$R" commit -qm x
  out=$(mode_axis "$R"); rc=$?
  chmod 755 "$R/.githooks/pre-push" "$R/tool.sh"; gi -C "$R" add -A; gi -C "$R" commit -qm y
  out2=$(mode_axis "$R"); rc2=$?; seen=0
  case "$out" in *"data.txt"*) ;; *".githooks/pre-push"*"tool.sh"*) seen=1 ;; esac
  if [ "$rc" = 1 ] && [ "$seen" = 1 ] && [ "$rc2" = 0 ]; then ok_ "mode-no-tag-exec-bit-absolute"
  else failed=$((failed+1)); echo "  FAIL mode-no-tag-exec-bit-absolute: 반환 $rc · $rc2 (기대 1 · 0)"; printf '%s\n%s\n' "$out" "$out2" | sed 's/^/        /'; fi
  rm -rf "$R"
  # ②-c describe 실패 — v* 태그가 있는데 HEAD 에서 닿지 않는다(옆 이력의 커밋). '태그 없음' 으로 읽지 않고 목록 추출 실패(3)다
  mki 1.0.0; R="$REPO"
  T0="$(gx -C "$R" hash-object -t tree -w /dev/null)" && C0="$(gx -C "$R" commit-tree "$T0" -m side)" && [ -n "$C0" ] \
    || { echo "⛔ 픽스처 준비 실패: 닿지 않는 커밋" >&2; exit 2; }
  gi -C "$R" tag v0.9.0 "$C0"
  case_ax "mode-describe-fail-unrun" 3 mode_axis "$R"; rm -rf "$R"

  # ⑦ 중립화(F-420) — 판정은 누수 규칙 정본(scripts/leak_rules.py --range)이 한다. ⛔ 시험 문자열은 쪼개 쓴다 —
  #    이 파일도 추가 줄로 검사되므로 원문 그대로면 자기 자신이 걸린다. 자리표시자 번호는 예약 번호(0 으로 시작하는 3~5자리 ·
  #    기존 합성 번호)만 통과한다 — 중립 접두라도 대역 밖 번호는 적중이다
  HOMEP="/Us""ers/alice/work"; MAILP="bob@""corp-mail.io"; KEYP="AB""C-1234"; OOBP="TK""T-4821"
  mkr 1.0.0; R="$REPO"; printf 'base %s\n' "$HOMEP" > "$R/old.txt"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm base
  case_ax "f420-base-line-not-counted" 0 neutralize_axis "$R" HEAD ""
  printf '경로 %s\n' "$HOMEP" >> "$R/CHANGELOG.md"; case_ax "f420-added-line-neutralize-hit" 1 neutralize_axis "$R" HEAD ""
  gq git -C "$R" checkout -q -- CHANGELOG.md
  printf '문의 %s\n' "$MAILP" > "$R/new.md"; case_ax "f420-untracked-file-scanned" 1 neutralize_axis "$R" HEAD ""
  printf '티켓 %s · 중립 TKT-0574 · 예시 /Us''ers/example/x\n' "$KEYP" > "$R/new.md"; case_ax "f420-ticket-key-shape-hit" 1 neutralize_axis "$R" HEAD ""
  printf '중립 TKT-0574 · 예시 /Us''ers/example/x · noreply@''example.com\n' > "$R/new.md"; case_ax "f420-neutral-tokens-ok" 0 neutralize_axis "$R" HEAD ""
  printf '중립 %s\n' "$OOBP" > "$R/new.md"; case_ax "placeholder-out-of-band-hit" 1 neutralize_axis "$R" HEAD ""
  printf '중립 TKT-0574 · tkt0123 · PRJ_04567 · TICKET-012 · 기존 합성 TKT-1234\n' > "$R/new.md"; case_ax "placeholder-reserved-ok" 0 neutralize_axis "$R" HEAD ""
  printf '지적 ISSUE-001 · ISSUE-202616\n' > "$R/new.md"; case_ax "r3-issue-id-namespace-ok" 0 neutralize_axis "$R" HEAD ""
  printf '지적 ISSUE-001 · 티켓 %s\n' "$KEYP" > "$R/new.md"; case_ax "r3-issue-allow-keeps-other-keys" 1 neutralize_axis "$R" HEAD ""
  printf '(?i)acme\n' > "$R/../fz-relsync-rules.$$"; printf 'Acme 앱\n' > "$R/new.md"
  case_ax "f420-private-rules-file" 1 neutralize_axis "$R" HEAD "$R/../fz-relsync-rules.$$"; rm -f "$R/../fz-relsync-rules.$$"
  case_ax "f420-bad-ref-unrun" 2 neutralize_axis "$R" no-such-ref ""
  rm -rf "$R"

  # 정본 모듈이 2(판정 불가)를 내면 출하 경로의 누수 판정 줄(leak_note) → 최종 판정(finish)이 통과로 읽지 않는다 —
  #    최종 exit ≠ 0 · 미판정 줄 · 모듈의 `UNRUN:` 사유 줄. 2 를 내는 셋: 정규식 오류인 비공개 규칙 파일 · UTF-8 이 아닌
  #    추가 파일 · 풀리지 않는 ref. 최종 exit 가 2 인지는 아래 실패 종류별 전파 셀이 본다(이 셀은 통과가 아닌지만 본다)
  case_x2() {   # $1=사례 · $2=기준 ref · $3=비공개 규칙 파일 — 통과로 읽혔으면 x2_bad 에 사례를 덧붙인다
    local out rc ok=1
    out=$( fail=0 unrun=0; leak_note "중립화 축" neutralize_axis "$R" "$2" "$3"; finish ); rc=$?
    [ "$rc" != 0 ] || ok=0
    case "$out" in *"중립화 축 미판정"*) ;; *) ok=0 ;; esac
    case "$out" in "UNRUN:"*|*$'\n'"UNRUN:"*) ;; *) ok=0 ;; esac
    [ "$ok" = 1 ] || x2_bad="$x2_bad $1(exit $rc)"
  }
  mkr 1.0.0; R="$REPO"; BADR="$R/../fz-relsync-badrules.$$"; printf '(%s\n' "unclosed" > "$BADR"; x2_bad=""
  case_x2 "규칙-정규식" HEAD "$BADR"
  printf 'caf\351\n' > "$R/l1.txt"; case_x2 "디코드" HEAD ""; rm -f "$R/l1.txt"
  case_x2 "ref" no-such-ref ""
  rm -f "$BADR"; rm -rf "$R"
  if [ -z "$x2_bad" ]; then ok_ "leak-module-exit2-not-pass"
  else failed=$((failed+1)); echo "  FAIL leak-module-exit2-not-pass: 정본 모듈의 2 를 통과로 읽었다 —$x2_bad"; fi

  # 판정 불가 전파 — 누수 축(정본 모듈의 2)이나 목록 추출이 실패하면 다른 축의 불일치가 함께 있어도 최종 exit 는 2 다.
  #    셀마다 실패 하나를 주입하고, 불일치 note 1건을 먼저 둔 채 출하 경로의 판정 줄(release_leak · axis_note) → finish 를 돈다.
  #    2 가 불일치로 접히면 최종 exit 가 1 이라 셀이 실패한다. 종류마다 셀을 따로 둔다 — 셀 하나로는 한 종류만 이어져도 통과한다
  case_u2() {   # $1=셀 · $2=출력에 있어야 할 사유 글자 · 나머지=부를 판정 줄과 인자
    local name="$1" want="$2" out rc seen=0; shift 2
    out=$( fail=0 unrun=0; note "다른 축의 불일치(시험용)"; "$@"; finish ); rc=$?
    case "$out" in *"$want"*) seen=1 ;; esac
    if [ "$rc" = 2 ] && [ "$seen" = 1 ]; then ok_ "$name"
    else failed=$((failed+1)); echo "  FAIL $name: 최종 exit $rc (기대 2) · 사유 '$want' 출력 $seen"; echo "$out" | sed 's/^/        /'; fi
  }
  RULES0="$(mktemp "${TMPDIR:-/tmp}/fz-relsync-rules.XXXXXX")" && BADENC="$(mktemp "${TMPDIR:-/tmp}/fz-relsync-rules.XXXXXX")" \
    && BADRX="$(mktemp "${TMPDIR:-/tmp}/fz-relsync-rules.XXXXXX")" && printf '\377(?i)x\n' > "$BADENC" && printf '(%s\n' "unclosed" > "$BADRX" \
    || { echo "⛔ 픽스처 준비 실패 (규칙 파일)" >&2; exit 2; }
  # 깨끗한 범위 — 태그 v1.0.0 뒤 깨끗한 커밋 하나. 대조군: 주입이 없으면 불일치 1건만 남아 최종 exit 1 이다(아래 셀의 2 는 주입에서 나온다)
  mki 1.0.0; R="$REPO"; gi -C "$R" tag v1.0.0
  printf '깨끗한 줄\n' > "$R/n.md"; gi -C "$R" add -A; gi -C "$R" commit -qm next
  out=$( fail=0 unrun=0; note "다른 축의 불일치(시험용)"; release_leak "$R" v1.0.0 "$RULES0"; finish ); rc=$?
  if [ "$rc" = 1 ]; then ok_ "leak-propagation-control-exit1"
  else failed=$((failed+1)); echo "  FAIL leak-propagation-control-exit1: 최종 exit $rc (기대 1 — 주입 없는 깨끗한 범위)"; echo "$out" | sed 's/^/        /'; fi
  case_u2 "leak-ref-unresolved-propagates-exit2" "기준 ref 를 풀지 못했다" release_leak "$R" no-such-ref "$RULES0"
  case_u2 "leak-rules-unreadable-propagates-exit2" "비공개 규칙 파일을 읽지 못했다" release_leak "$R" v1.0.0 "$BADENC"
  case_u2 "leak-rules-bad-regex-propagates-exit2" "정규식 오류" release_leak "$R" v1.0.0 "$BADRX"
  # diff 실패 — 범위 커밋이 더한 파일의 blob 객체를 지운다(ref · 커밋 · 트리 객체는 그대로라 커밋 목록은 뽑히고 diff 만 실패한다).
  #    작업 트리 파일도 지운다 — ⑦(HEAD 대비 작업 트리)도 지운 파일의 옛 내용을 읽으려다 실패한다
  BLOB="$(gx -C "$R" rev-parse HEAD:n.md)" && OBJ="$R/.git/objects/${BLOB:0:2}/${BLOB:2}" && [ -f "$OBJ" ] && rm -f "$OBJ" "$R/n.md" \
    || { echo "⛔ 픽스처 준비 실패: n.md 의 느슨한 blob 객체를 지우지 못했다" >&2; exit 2; }
  case_u2 "leak-diff-fail-propagates-exit2" "git diff" release_leak "$R" v1.0.0 "$RULES0"
  rm -rf "$R"
  # 디코드 실패 — 범위 커밋이 UTF-8 이 아닌 텍스트(latin-1)를 더했다
  mki 1.0.0; R="$REPO"; gi -C "$R" tag v1.0.0
  printf 'caf\351\n' > "$R/l1.txt"; gi -C "$R" add -A; gi -C "$R" commit -qm latin1
  case_u2 "leak-undecodable-propagates-exit2" "UTF-8 로 읽지 못했다" release_leak "$R" v1.0.0 "$RULES0"
  rm -rf "$R"
  # 목록 추출 실패 — 인덱스 파일을 깨뜨려 인덱스를 읽는 목록 명령만 실패하게 한다(HEAD · ref · 객체는 그대로). 실패를 '목록이 비었다' ·
  #    '바뀌지 않음' 으로 읽으면 통과로 샌다
  mki 1.0.0; R="$REPO"; printf 'x' > "$R/.git/index"
  case_u2 "list-fail-commit-status-unrun" "git status 실패" axis_note "커밋 축" commit_axis "$R" "1.0.0"
  case_u2 "list-fail-commit-lsfiles-unrun" "git ls-files 실패" axis_note "커밋 축" commit_axis "$R" "1.0.0"
  case_ax "list-fail-exec-bit-unrun" 3 mode_axis "$R"
  rm -rf "$R"
  #    커밋의 트리 객체를 지운다 — 인덱스를 읽는 목록은 뽑히고 커밋의 모드 목록(ls-tree HEAD · 기준 태그 대비 HEAD diff)만 실패한다
  mki 1.0.0; R="$REPO"; TOBJ="$(gx -C "$R" rev-parse 'HEAD^{tree}')" && OBJ="$R/.git/objects/${TOBJ:0:2}/${TOBJ:2}" && [ -f "$OBJ" ] && rm -f "$OBJ" \
    || { echo "⛔ 픽스처 준비 실패: HEAD 의 트리 객체를 지우지 못했다" >&2; exit 2; }
  case_ax "list-fail-exec-bit-head-tree-unrun" 3 mode_axis "$R"; rm -rf "$R"
  mki 1.0.0; R="$REPO"; gi -C "$R" tag v1.0.0; printf 'n\n' > "$R/n.md"; gi -C "$R" add -A; gi -C "$R" commit -qm n
  printf 'x' > "$R/.git/index"
  case_ax "list-fail-mode-summary-unrun" 3 mode_axis "$R"; rm -rf "$R"
  mki 1.0.0; R="$REPO"; gi -C "$R" tag v1.0.0; printf 'n\n' > "$R/n.md"; gi -C "$R" add -A; gi -C "$R" commit -qm n
  TOBJ="$(gx -C "$R" rev-parse 'HEAD^{tree}')" && OBJ="$R/.git/objects/${TOBJ:0:2}/${TOBJ:2}" && [ -f "$OBJ" ] && rm -f "$OBJ" \
    || { echo "⛔ 픽스처 준비 실패: HEAD 의 트리 객체를 지우지 못했다" >&2; exit 2; }
  case_ax "list-fail-mode-summary-head-unrun" 3 mode_axis "$R"; rm -rf "$R"
  mki 1.0.0; R="$REPO"; sub_files "$R" 0.1.0 0.1.0; gi -C "$R" add -A; gi -C "$R" commit -qm sub; gi -C "$R" tag v1.0.0
  printf 'x' > "$R/.git/index"
  case_ax "list-fail-subplugin-unrun" 3 subplugin_axis "$R"; rm -rf "$R"
  #    --staged 는 자기 루트에서 돈다 — 스크립트 사본을 임시 저장소에 두고 실제 진입점으로 부른다
  mki 1.0.0; R="$REPO"; mkdir -p "$R/scripts" && cp "$SELF_DIR/$(basename "${BASH_SOURCE[0]}")" "$R/scripts/check_release_sync.sh" \
    || { echo "⛔ 픽스처 준비 실패: 스크립트 사본" >&2; exit 2; }
  printf 'x' > "$R/.git/index"
  out=$(bash "$R/scripts/check_release_sync.sh" --staged 2>&1); rc=$?; seen=0
  case "$out" in *"판정 불가"*) seen=1 ;; esac
  if [ "$rc" = 2 ] && [ "$seen" = 1 ]; then ok_ "list-fail-staged-unrun"
  else failed=$((failed+1)); echo "  FAIL list-fail-staged-unrun: exit $rc (기대 2 · 판정 불가 줄 $seen)"; echo "$out" | sed 's/^/        /'; fi
  rm -rf "$R"
  #    --neutralize-diff — 정본 모듈이 끝 줄 없이 exit 1 로 죽으면 적중이 아니라 판정 불가다
  mki 1.0.0; R="$REPO"; mkdir -p "$R/scripts" && cp "$SELF_DIR/$(basename "${BASH_SOURCE[0]}")" "$R/scripts/check_release_sync.sh" \
    && printf 'raise SystemExit(1)\n' > "$R/scripts/leak_rules.py" || { echo "⛔ 픽스처 준비 실패: 스크립트 사본" >&2; exit 2; }
  out=$(bash "$R/scripts/check_release_sync.sh" --neutralize-diff HEAD 2>&1); rc=$?; seen=0
  case "$out" in *"중립화 규칙 적중"*) seen=1 ;; esac
  if [ "$rc" = 2 ] && [ "$seen" = 0 ]; then ok_ "neutralize-module-crash-unrun"
  else failed=$((failed+1)); echo "  FAIL neutralize-module-crash-unrun: exit $rc (기대 2 · 적중 안내 $seen)"; echo "$out" | sed 's/^/        /'; fi
  rm -rf "$R"
  rm -f "$RULES0" "$BADENC" "$BADRX"

  echo "self-test $pass/$((pass+failed)) passed"
  [ "$failed" = 0 ] || exit 1
  exit 0
fi

# ── --staged — pre-commit 용. 버전 선언 파일이 staged 일 때만, 값싸게 ──────────
if [ "$MODE" = "staged" ]; then
  VFILES=".claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md"
  # shellcheck disable=SC2086
  touched=$(git diff --cached --name-only -- $VFILES 2>/dev/null) \
    || { echo "❌ staged 변경 목록을 뽑지 못했다(git diff --cached 실패) — 판정 불가(측정 실패 · ⛔ 통과 아님)"; exit 2; }
  [ -n "$touched" ] || { echo "STAGED_SKIP (버전 선언 파일 변경 없음)"; exit 0; }
  ipv=$(git_show_version "$ROOT_DIR" ":.claude-plugin/plugin.json")
  imv=$(git_show_version "$ROOT_DIR" ":.claude-plugin/marketplace.json")
  icv=$(git show ":CHANGELOG.md" 2>/dev/null | grep -m1 -oE '^### v[0-9]+\.[0-9]+\.[0-9]+' | sed 's/^### v//')
  [ -n "$ipv" ] || { echo "❌ staged plugin.json 에서 version 을 읽지 못했다 (측정 실패)"; exit 2; }
  echo "staged 버전: plugin=$ipv · marketplace=$imv · CHANGELOG=$icv"
  [ "$ipv" = "$imv" ] || note "staged plugin.json($ipv) ≠ marketplace.json($imv)"
  [ "$ipv" = "$icv" ] || note "staged plugin.json($ipv) ≠ CHANGELOG 최상단($icv)"
  if [ "$fail" -gt 0 ]; then
    echo "⛔ 버전 선언 ${fail}건 불일치 — 세 곳을 함께 올린다"
    echo "   우회(정당 사유 시): git commit --no-verify"
    exit 1
  fi
  echo "STAGED_OK (버전 3곳 일치)"
  exit 0
fi

# ── --neutralize-diff — ⑦만 ─────────────────────────────────────────────────
if [ "$MODE" = "neutralize" ]; then
  # 종료 코드와 끝 줄을 함께 본다(leak_note 와 같은 판정) — 파이썬 예외도 exit 1 이라 종료 코드만 보면 충돌을 적중으로 안내한다
  nl=$'\n'; rc=0
  out="$(neutralize_axis "$ROOT_DIR" "$NREF" "$NRULES")" || rc=$?
  [ -z "$out" ] || printf '%s\n' "$out"
  case "$rc:${out##*$nl}" in
    "0:LEAK_CLEAN "*) echo "NEUTRALIZE_OK ($NREF 대비 추가 줄 적중 0)"; exit 0 ;;
    "1:LEAK_HIT "*) echo "⛔ 중립화 규칙 적중 — 공개 저장소에 두기 전에 중립 표기로 바꾼다"; exit 1 ;;
  esac
  echo "⛔ 중립화 대조 판정 불가(정본 모듈 exit $rc — 위 출력의 UNRUN 줄 · 오류 · ⛔ 통과 아님)"
  exit 2
fi

for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md \
         guides/skill-authoring.md guides/model-guide.md scripts/health-check.sh; do
  [ -f "$f" ] || { echo "❌ 대상 부재: $f (측정 실패)"; exit 2; }
done

PV=$(python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])' 2>/dev/null)
MV=$(python3 -c 'import json,sys;d=json.load(open(".claude-plugin/marketplace.json"));p=d["plugins"][0] if isinstance(d.get("plugins"),list) and d["plugins"] else d;print(p.get("version",""))' 2>/dev/null)
CV=$(grep -m1 -oE '^### v[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | sed 's/^### v//')
[ -n "$PV" ] || { echo "❌ plugin.json version 을 읽지 못했다 (측정 실패)"; exit 2; }
[ -n "$CV" ] || { echo "❌ CHANGELOG 최상단 버전 헤딩을 찾지 못했다 (측정 실패)"; exit 2; }

echo "버전: plugin=$PV · marketplace=$MV · CHANGELOG=$CV"
[ "$PV" = "$MV" ] || note "plugin.json($PV) ≠ marketplace.json($MV)"
[ "$PV" = "$CV" ] || note "plugin.json($PV) ≠ CHANGELOG 최상단($CV) — 항목 없이 버전만 올리거나 그 반대"
# ①-b · ②-c 는 목록 추출 실패(3)를 판정 불가로 올린다(axis_note) — 실패를 '바뀐 것 없음' 으로 읽으면 통과로 샌다
axis_note "하위 플러그인" subplugin_axis "$ROOT_DIR"
note_ref_axis "$ROOT_DIR" || { rc=$?; [ "$rc" = 2 ] && note "노트 절 참조 미판정 — 통과가 아니다" || fail=$((fail + 1)); }
axis_note "모드 축" mode_axis "$ROOT_DIR"

# ③ sweep 결과가 어디로 가는지 가이드가 가리키는가 — 사전등록만 하고 참조가 없으면 표가 미아가 된다
grep -q '§5.8 ⑥' guides/skill-authoring.md || note "skill-authoring.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '§5.8 ⑥' guides/model-guide.md || note "model-guide.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '### ⑥ 세션 effort sweep' experiment-log.md || note "experiment-log.md 에 §5.8 ⑥ 표가 없다 (가이드가 없는 곳을 가리킨다)"
grep -q '## §5.9 구조 ablation' experiment-log.md || note "experiment-log.md 에 §5.9 표가 없다"

# 로그는 실행마다 새 임시 파일이다 — 고정 경로는 함께 도는 실행(사본 저장소에서 --release 를 도는 러너 등)끼리 덮어써 실패 사유가
#    엇갈린다. 통과한 검사의 로그는 지운다 — 실패 note 가 가리키는 로그만 남긴다
NLOG="$(mktemp "${TMPDIR:-/tmp}/fz-release-notes.XXXXXX")" && HLOG="$(mktemp "${TMPDIR:-/tmp}/fz-release-hc.XXXXXX")" \
  || { echo "❌ 임시 로그 파일을 만들지 못했다 (측정 실패)"; exit 2; }

# ③-b 최상단 절의 finding 표 — 표가 있으면 모든 행의 판정·근거·검증 절차가 차 있어야 한다(없는 릴리즈는 통과).
#    ⛔ 출하(--release)는 표 필수 모드다 — 표도 '닫은 finding 없음' 표지도 없는 절은 실패한다(표를 지우면 통과하던 구멍)
NT_ARGS=(--table-complete --version "$CV")
[ "$MODE" != "release" ] || NT_ARGS+=(--require-table)
if python3 scripts/check_release_notes.py "${NT_ARGS[@]}" >"$NLOG" 2>&1; then
  rm -f "$NLOG"
elif [ "$MODE" = "release" ]; then
  note "CHANGELOG v$CV 절에 finding 표(또는 '닫은 finding 없음' 표지)가 없거나 표에 빈 칸이 있다 (로그: $NLOG)"
else
  note "CHANGELOG v$CV finding 표에 빈 칸이 있다 (로그: $NLOG)"
fi

# ④ health-check — 이번 변경이 기존 계약을 깨지 않았는가
if bash scripts/health-check.sh >"$HLOG" 2>&1; then
  rm -f "$HLOG"
  echo "  ✅ health-check exit 0"
else
  note "health-check 실패 (로그: $HLOG)"
fi

# ⑤ 커밋 축 — `--release` 에서만. 미판정(2)은 통과로 세지 않고, 목록 추출 실패(3)는 판정 불가다(axis_note)
if [ "$MODE" = "release" ]; then
  axis_note "커밋 축" commit_axis "$ROOT_DIR" "$PV"
fi
# ⑦ · ⑧ 누수 축 — `--release` 에서만(release_leak). 기준 = 직전 출하 태그(release_base) · 볼 태그 = 로컬 태그 전부(release_tags).
#    직전 v* 태그가 없으면 첫 출하다 — 루트부터 커밋마다 + 작업 트리 전문으로 대신한다(미판정으로 끝내지 않는다).
#    ⛔ 기준 · 태그 목록을 뽑지 못하거나 정본 모듈이 2 를 내면 판정 불가다 — 최종 exit 2(불일치보다 앞선다)
if [ "$MODE" = "release" ]; then
  if release_base "$ROOT_DIR"; then
    echo "  누수 축 기준: ${REL_BASE:-직전 v* 태그 없음 — 루트부터 커밋마다 + 작업 트리 전문}"
    release_tags "$ROOT_DIR" || unrun_note "로컬 태그 목록 추출 실패 — $REL_TAGS_WHY"
    release_leak "$ROOT_DIR" "$REL_BASE" "$NRULES" ${REL_TAGS[@]+"${REL_TAGS[@]}"}
  else
    unrun_note "누수 축의 기준 태그를 정하지 못했다 — $REL_BASE_WHY"
  fi
fi
# ⑥ findings 축 — `--release` 에서만. 미판정(2)은 통과로 세지 않는다
if [ "$MODE" = "release" ]; then
  findings_axis "$ROOT_DIR/docs/releases/v${PV}.md" || { rc=$?; [ "$rc" = 2 ] && note "findings 축 미판정 — 통과가 아니다" || fail=$((fail + 1)); }
fi

finish
