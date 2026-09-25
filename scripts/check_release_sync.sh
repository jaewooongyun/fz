#!/bin/bash
# scripts/check_release_sync.sh — 릴리즈 산출물이 서로를 가리키는지 본다 (plan-final S10).
#
# ⛔ 왜 신설인가: `health-check.sh` 는 계약·문법·회귀를 보지만 **이번 변경의 문서 동기와 버전
#    갱신은 증명하지 않는다**(verify-gates S10 revise 지적). 버전이 세 곳에 흩어져 있어
#    한 곳만 올리는 실패가 실제로 있었다(v4.33.0 CHANGELOG "적용은 했는데 커밋하지 않았다").
#
# 검사: ① plugin.json == marketplace.json ② CHANGELOG 최상단 == plugin.json
#       ③ 가이드가 sweep 기록 위치(§5.8 ⑥)를 가리키는가 ④ health-check exit 0
# exit: 0=전부 충족(DOCS_SYNC_OK) / 1=불일치 / 2=대상 부재(측정 실패)
#
# 모드:
#   (없음)      ①~④ — 수동·CI 용. health-check 포함이라 **32초** 걸린다
#   --release   ①~④ + ⑤ **커밋 축**. 릴리즈 직전 게이트
#   --staged    ⑤만, staged 내용 기준. ⛔ pre-commit 용 — health-check 를 뺀다
#   --self-test 임시 git 리포로 ⑤의 실패/통과 쌍을 확인
#
# ⛔ **커밋 축을 기본 모드에 넣지 않는 이유**: pre-commit 은 *커밋하려는 중* 이라
#    깨끗한 워킹트리를 요구할 수 없다. 그래서 축을 `--release` 로 분리한다.
# ⛔ **워킹트리 전체의 청결을 보지 않는 이유**: 릴리즈 후 쌓인 다음 버전 작업이
#    정상 상태이므로 오탐이 된다. 보는 것은 **선언된 버전 자신의 산출물이 HEAD 에 있는가** 다 —
#    이것이 원래 실패 모드(v4.33.0 "적용은 했는데 커밋하지 않았다")의 정확한 오라클이다.
set -uo pipefail

MODE=""
case "${1:-}" in
  --release)   MODE="release" ;;
  --staged)    MODE="staged" ;;
  --self-test) MODE="self-test" ;;
  "")          MODE="default" ;;
  *) echo "❌ 알 수 없는 인자: $1 (사용: [--release|--staged|--self-test])"; exit 2 ;;
esac
#   루트는 **자기 위치**에서 해석한다 (`BASH_SOURCE[0]` — `$0` 는 source 시 호출자를 가리킨다)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SELF_DIR/.." && pwd)"
cd "$ROOT_DIR" || { echo "❌ 플러그인 루트로 이동 실패: $ROOT_DIR"; exit 2; }

fail=0
note() { echo "  ❌ $1"; fail=$((fail + 1)); }

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

# ⑤ 커밋 축 — **선언된 버전 자신의 산출물이 HEAD 에 있는가.**
#    ⛔ 워킹트리 전체의 청결을 보지 않는다(다음 버전 작업이 쌓이는 것은 정상).
#    반환: 0=충족 · 1=불일치(사유를 stdout 에) · 2=측정 불가
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
  local rel="docs/releases/v${ver}.md"
  if [ -f "$repo/$rel" ]; then
    git -C "$repo" ls-files --error-unmatch "$rel" >/dev/null 2>&1 \
      || { echo "  ❌ $rel 이 untracked — 릴리즈 문서가 커밋되지 않았다"; bad=1; }
  else
    echo "  ❌ $rel 이 없다 — 선언된 버전의 릴리즈 문서가 부재"; bad=1
  fi

  # 버전 3곳 중 커밋 안 된 수정이 남아 있으면 HEAD 와 디스크가 갈린 상태다
  local dirty
  dirty=$(git -C "$repo" status --porcelain -- .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md 2>/dev/null)
  [ -z "$dirty" ] || { echo "  ❌ 버전 선언 파일에 미커밋 수정이 있다:"; echo "$dirty" | sed 's/^/      /'; bad=1; }

  return "$bad"
}

# ── --self-test — 임시 git 리포로 ⑤의 실패/통과 쌍을 확인한다 ────────────────
if [ "$MODE" = "self-test" ]; then
  pass=0; failed=0
  mk() {   # $1=버전 · stdout=리포 경로 (v$1 을 전부 커밋한 상태)
    local d ver="$1"
    d=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX")
    mkdir -p "$d/.claude-plugin" "$d/docs/releases"
    printf '{"version": "%s"}\n' "$ver" > "$d/.claude-plugin/plugin.json"
    printf '{"plugins": [{"version": "%s"}]}\n' "$ver" > "$d/.claude-plugin/marketplace.json"
    printf '# Changelog\n\n### v%s (2026-01-01) — x\n' "$ver" > "$d/CHANGELOG.md"
    printf '# v%s\n' "$ver" > "$d/docs/releases/v${ver}.md"
    # ⛔ git 단계의 exit code 를 버리지 않는다 — 실패를 삼키면 **위조 픽스처**가 만들어지고
    #    자기시험이 아무것도 증명하지 않는다 (`lint_contracts` #N5 가 이것을 잡는다).
    gq() { "$@" >/dev/null 2>&1 || { echo "⛔ 픽스처 준비 실패: $*" >&2; exit 2; }; }
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

  case_() {   # $1=이름 · $2=기대 반환 · $3=리포 · $4=선언버전
    local out rc
    out=$(commit_axis "$3" "$4"); rc=$?
    if [ "$rc" = "$2" ]; then pass=$((pass+1))
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

  # ⑤ 측정 불가 — git 리포가 아니다. ⛔ 미판정은 통과가 아니다
  R=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX"); case_ "not-a-repo" 2 "$R" "1.0.0"; rm -rf "$R"

  echo "self-test $pass/$((pass+failed)) passed"
  [ "$failed" = 0 ] || exit 1
  exit 0
fi

# ── --staged — pre-commit 용. 버전 선언 파일이 staged 일 때만, 값싸게 ──────────
if [ "$MODE" = "staged" ]; then
  VFILES=".claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md"
  # shellcheck disable=SC2086
  touched=$(git diff --cached --name-only -- $VFILES 2>/dev/null)
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

# ③ sweep 결과가 어디로 가는지 가이드가 가리키는가 — 사전등록만 하고 참조가 없으면 표가 미아가 된다
grep -q '§5.8 ⑥' guides/skill-authoring.md || note "skill-authoring.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '§5.8 ⑥' guides/model-guide.md || note "model-guide.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '### ⑥ 세션 effort sweep' experiment-log.md || note "experiment-log.md 에 §5.8 ⑥ 표가 없다 (가이드가 없는 곳을 가리킨다)"
grep -q '## §5.9 구조 ablation' experiment-log.md || note "experiment-log.md 에 §5.9 표가 없다"

# ④ health-check — 이번 변경이 기존 계약을 깨지 않았는가
if bash scripts/health-check.sh >/tmp/fz-release-hc.log 2>&1; then
  echo "  ✅ health-check exit 0"
else
  note "health-check 실패 (로그: /tmp/fz-release-hc.log)"
fi

# ⑤ 커밋 축 — `--release` 에서만. 미판정(2)은 통과로 세지 않는다
if [ "$MODE" = "release" ]; then
  commit_axis "$ROOT_DIR" "$PV" || { rc=$?; [ "$rc" = 2 ] && note "커밋 축 미판정 — 통과가 아니다" || fail=$((fail + 1)); }
fi

if [ "$fail" -gt 0 ]; then
  echo "릴리즈 동기 불일치 ${fail}건"
  exit 1
fi
if [ "$MODE" = "release" ]; then
  echo "RELEASE_SYNC_OK (버전 3곳 일치 · 가이드→표 참조 4건 · health-check exit 0 · 커밋 축 충족)"
else
  echo "DOCS_SYNC_OK (버전 3곳 일치 · 가이드→표 참조 4건 · health-check exit 0)"
fi
