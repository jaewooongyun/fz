#!/bin/bash
# gpt-cli: none — 사본 저장소의 scripts/health-check.sh 는 exit 0 스텁이다(실제 health-check · GPT CLI 에 닿지 않는다)
# diff-parse: not-a-diff — 이 러너는 diff 를 읽지 않는다. 출하 게이트 사본을 돌려 종료 코드와 출력 줄(고정 글자)만 본다
# modes: default caller=health
# 출하 게이트 --release 회귀 — 누수 축(커밋마다 신원 · 메시지 · 추가 줄 · 태그의 tagger · 주석 · 태그 없는 첫 출하)과 판정 불가
#   전파를 실제 진입점으로 돌려 종료 코드와 실패한 축의 줄을 단언한다.
#
# ⛔ 진입점은 자기 파일의 부모 폴더를 루트로 삼는다(저장소 인자가 없다). 그래서 --tree 의 출하 게이트 · 누수 규칙 정본 · 노트 표
#    검사기와 그것이 import 하는 형제 모듈을 임시 저장소의 scripts/ 에 복사하고 그 사본을 돌린다. ④ health-check 는 exit 0
#    스텁으로 대신한다 — 사본에서 실제 health-check 를 돌면 이 러너가 다시 불린다. 진입점이 복사 목록 밖의 형제 스크립트를
#    부르거나 사본이 그런 모듈을 import 하면 준비 실패(UNRUN)다 — 사본에 없으면 모든 셀이 누수와 무관한 축으로 실패한다.
# ⛔ 임시 저장소는 누수 밖 축(버전 3곳 · CHANGELOG 최상단 절과 finding 표 · README · 노트 · 가이드 2개 · 작업 로그 제목 2개 ·
#    실행 비트)이 통과할 파일을 갖춘다 — 빠지면 다른 축의 불일치로도 exit 1 이 나 누수 셀이 판별력을 잃는다. 깨끗한 대조 셀이
#    먼저 0 에 닿고, 음성 셀은 대조 저장소에서 한 가지만 바꾼다. exit 1 · 2 셀은 실패한 축의 줄 글자도 단언한다(종료 코드만
#    보면 다른 축의 실패로도 통과한다).
# ⛔ 음성 토큰(회사 꼴 메일 · 키 꼴 · 홈 경로 · 대역 밖 자리표시자 번호)은 쪼개 적고 실행할 때 잇는다 — 이 파일이 누수 규칙 ·
#    커밋 훅에 걸리지 않게. 비공개 규칙 파일(합성 회사 이름 한 줄)은 저장소 밖에 둔다 — 안에 두면 전문 검사가 규칙 줄 자체를 잡는다.
# ⛔ git 은 격리한다 — 전역 · 시스템 설정과 기본 무시 · 속성 파일을 끊고(진입점이 부르는 git 도) 훅 · 서명을 끄고 신원은 합성
#    noreply 다. 커밋 · 태그는 mktemp 임시 저장소에만 만든다. 진입점의 임시 로그도 그 안에 실행마다 따로 둔다(병렬 러너 · 셀끼리
#    겹치지 않는다).
# 셀(기대 exit):
#   0   rel-clean(기준 주석 태그) · rel-no-tag-clean-exit0(v* 태그 없는 첫 출하) · rel-lightweight-tag-clean-exit0
#   0→1 rel-rules-empty-builtin-only — 빈 규칙 파일은 내장 규칙만(이름에만 비공개 이름이 든 noreply 신원 통과) · 규칙 파일이면 적중 ·
#       env 에 비공개 규칙 파일이 있어도 명시한 --rules(빈 파일)가 앞선다
#   0→1 rel-new-hook-nonexec-exit1 — 기준 태그 뒤에 새로 생긴 훅: 0755 면 통과 · 0644 면 모드 축 불일치
#   1   rel-corp-author-exit1 · rel-commit-message-exit1 · rel-tagger-corp-exit1 · rel-tag-annotation-exit1 ·
#       rel-intermediate-commit-exit1(중간 커밋이 더하고 다음 커밋이 지운 줄 — 범위 두 끝 비교는 깨끗하다) ·
#       rel-merge-commit-first-parent-exit1(기준 태그 쪽 옆 가지를 들인 병합 — 첫 부모와의 차이) ·
#       rel-head-tagged-uses-prior(HEAD 의 태그를 빼고 직전 태그 뒤를 본다) · rel-no-tag-modebit-exit1(0644 셔뱅 파일) ·
#       rel-no-finding-table-exit1(최상단 절에 finding 표도 '닫은 finding 없음' 표지도 없다 — 출하는 표 필수 모드로 부른다) ·
#       rel-changelog-internal-id-exit1(최상단 절의 finding 표에 내부 추적 번호 — 공개 CHANGELOG 에 적지 않는다)
#   2   rel-mixed-violation-and-unrun-exit2(위반 + 판정 불가) · rel-binary-or-utf16-added-exit2(바이너리 · UTF-16 · 커밋한 latin-1) ·
#       rel-untracked-undecodable-exit2 · rel-describe-fail-exit2(닿지 않는 v* 태그만) · rel-release-no-rules-arg-exit2 ·
#       rel-rules-file-missing-exit2 · rel-unknown-arg-exit2 ·
#       rel-unreachable-old-tag-exit2(HEAD 에서 닿지 않는 커밋을 가리키는 로컬 태그 — 그 커밋은 어느 축도 보지 않았다)
#   1   rel-release-note-untracked-exit1(그 판의 노트가 인덱스에 없다 — 커밋 축) · rel-health-check-fail-exit1(④ 스텁이 exit 1)
#   0   gate-selftest-hostile-global-config-exit0(서명을 강제하는 전역 git 설정 아래의 출하 게이트 self-test) ·
#       host-config-params-ignored(부모 git 의 -c 설정을 물려받은 자식 실행 — 자식은 앞의 두 셀만 돈다)
# 출력: 셀마다 `PASS <셀>` 또는 `FAIL <셀> — 사유` + 그 셀이 돌린 진입점 출력과 진입점이 남긴 실패 로그(③-b · ④)의 끝 20줄씩
#   (들여씀). 전건 통과면 `RELEASE_RANGE_OK …`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(`UNRUN:` — 인자 · 도구 · 대상 부재 · 사본에 빠진 형제 스크립트 · 임시 저장소)
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 러너가 든 트리 — health-check 는 인자 없이 부른다)
set -u
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "UNRUN: --tree 에 경로가 없다"; exit 2; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "UNRUN: --tree 경로가 없다: $2"; exit 2; }; shift 2 ;;
    *) echo "UNRUN: 알 수 없는 인자: $1 (사용: run.sh [--tree <플러그인 트리>])"; exit 2 ;;
  esac
done
[ -n "$TREE" ] || { echo "UNRUN: 플러그인 트리를 정하지 못했다"; exit 2; }
for c in git python3; do command -v "$c" >/dev/null 2>&1 || { echo "UNRUN: $c 부재 — 픽스처를 만들 수 없다"; exit 2; }; done
# 사본으로 돌릴 것 — 출하 게이트 · 누수 규칙 정본 · ③-b 노트 표 검사기와 그것이 import 하는 형제 모듈
SRCS="check_release_sync.sh leak_rules.py check_release_notes.py md_section.py"
for s in $SRCS; do [ -f "$TREE/scripts/$s" ] || { echo "UNRUN: 대상 부재 — scripts/$s"; exit 2; }; done
# SRCS 가 진입점의 실제 의존과 맞는가 — 진입점 코드 줄이 부르는 `scripts/<이름>.py|sh` 와 사본 모듈이 import 하는 형제 모듈이
#    SRCS(+ ④ 스텁) 밖이면 준비 실패다. 진입점이 새 도우미를 부르게 되면 여기서 멈춘다(SRCS 에 더한다). 실제 health-check 는
#    스텁으로 바뀌므로 스캔하지 않는다
PYTHONIOENCODING=utf-8 python3 -c 'import os, re, sys
d, srcs = sys.argv[1], sys.argv[2].split()
have, need = set(srcs) | {sys.argv[3]}, set()
for s in srcs:
    with open(os.path.join(d, s), encoding="utf-8", errors="surrogateescape") as f:
        for ln in f:
            if s.endswith(".sh") and not ln.lstrip().startswith("#"):
                need.update(re.findall(r"scripts/([\w.-]+\.(?:py|sh))\b", ln))
            m = re.match(r"\s*(?:from\s+(\w+)\s+import\b|import\s+([\w ,]+))", ln)
            for mod in ([m.group(1)] if m and m.group(1) else re.findall(r"\w+", m.group(2)) if m else []):
                if os.path.isfile(os.path.join(d, mod + ".py")):
                    need.add(mod + ".py")
miss = sorted(need - have)
if miss:
    print("UNRUN: 진입점 사본에 빠진 형제 스크립트 — " + " ".join(miss) + " (SRCS 에 더한다)")
    sys.exit(2)' "$TREE/scripts" "$SRCS" health-check.sh \
  || { rc=$?; [ "$rc" = 2 ] || echo "UNRUN: 진입점의 형제 스크립트 의존을 확인하지 못했다(python3 exit $rc)"; exit 2; }

# 바깥 git 환경(훅이 건 GIT_DIR · GIT_INDEX_FILE 등)이 임시 저장소의 git 을 바깥 저장소로 돌리지 않게 끊는다. 비공개 규칙은 --rules 로만 준다
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE GIT_PREFIX FZ_NEUTRALIZE_RULES
# 부모 git 이 `-c` 로 넘긴 설정도 끊는다 — 남으면 셀 저장소의 로컬 설정(core.fileMode)을 덮어 실행 비트 축이 갈린다
unset GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fz-relrange.XXXXXX")" && [ -n "$WORK" ] && [ -d "$WORK" ] \
  || { echo "UNRUN: 임시 폴더를 만들지 못했다"; exit 2; }
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/out" "$WORK/tmp" "$WORK/xdg" || { echo "UNRUN: 임시 폴더 준비 실패"; exit 2; }
# 이 러너의 git 과 진입점이 부르는 git 모두 전역 · 시스템 설정과 기본 무시 · 속성 파일(XDG)을 읽지 않는다 — 색 · 외부 diff · 무시 규칙이
#    판정을 바꾸지 않게. 바이트코드를 쓰지 않는다(임시 저장소에 생긴 파일은 누수 축이 미추적 파일로 읽는다). 임시 파일도 WORK 안이다
#    (진입점의 임시 로그는 실행마다 WORK/tmp/<출력 이름> — gate)
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$WORK" \
  XDG_CONFIG_HOME="$WORK/xdg" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 TMPDIR="$WORK/tmp"

# 합성 신원 — 신원 축의 허용 꼴(noreply)이다. 셀의 적중은 주입한 것에서만 나온다
SID="0+fz-relrange@users.noreply.github.com"
# 음성 토큰 — 쪼개 적고 실행할 때 잇는다. 비공개 규칙은 합성 회사 이름 하나다(빈 규칙 파일 = 내장 규칙만)
CORPN="qzrel""corp"; CORPM="dev@${CORPN}.test"; HOMEP="/Us""ers/alice"; KEYP="AB""C-4821"; OOBP="TK""T-4821"
RULES_CORP="$WORK/rules-corp.txt" RULES_EMPTY="$WORK/rules-empty.txt"
{ printf '%s\n' '# 합성 비공개 규칙(시험용) — 한 줄 한 정규식' "(?i)$CORPN" > "$RULES_CORP" && : > "$RULES_EMPTY"; } \
  || { echo "UNRUN: 규칙 파일을 만들지 못했다"; exit 2; }

npass=0 nfail=0 WHY="" SHOW="" LOGD="" RUNL="" GATE_NR="" GRC="" OUT="" R="" C1="" HEADC="" GX_ANAME="" GX_AMAIL="" GX_CMAIL=""
die() { echo "UNRUN: 픽스처 준비 실패 — $* (⛔ 통과 아님)"; exit 2; }
# 격리 git — 훅 · 서명을 끈다. 신원은 GX_ANAME · GX_AMAIL · GX_CMAIL(빈 값 = 합성 noreply). 주석 태그의 tagger 는 committer 값이다
gx() {
  GIT_AUTHOR_NAME="${GX_ANAME:-fz-relrange}" GIT_AUTHOR_EMAIL="${GX_AMAIL:-$SID}" \
    GIT_COMMITTER_NAME=fz-relrange GIT_COMMITTER_EMAIL="${GX_CMAIL:-$SID}" \
    git -c core.hooksPath=/dev/null -c commit.gpgsign=false -c tag.gpgsign=false "$@"
}
# 실패면 준비 실패(exit 2). ⛔ $( ) 안에서 부르지 않는다 — exit 가 서브셸에 갇힌다
gi() { gx "$@" >/dev/null 2>&1 || die "git $*"; }
put() {   # $1=저장소 안 경로 · 나머지=줄 — 폴더를 만들고 줄마다 개행으로 쓴다
  local rel="$1" p="$R/$1"; shift
  mkdir -p "$(dirname "$p")" && printf '%s\n' "$@" > "$p" || die "쓰기 $rel"
}
raw() {   # $1=저장소 안 경로 · $2=utf16|latin1|binary — UTF-8 로 읽지 못하는 파일(UTF-16 은 BOM 없이 — 글자 사이에 NUL 이 낀다)
  python3 -c 'import sys
data = {"utf16": "plain text\n".encode("utf-16-le"), "latin1": "café\n".encode("latin-1"), "binary": bytes(range(256))}[sys.argv[2]]
open(sys.argv[1], "wb").write(data)' "$R/$1" "$2" || die "쓰기 $1"
}
cl_section() {   # $1=판 · $2=날짜 — CHANGELOG 절 하나(제목 + '닫은 finding 없음.' 표지 — 공개 CHANGELOG 에 내부 추적 번호를 적지 않는다)
  printf '### v%s (%s) — 출하\n\n닫은 finding 없음.\n\n' "$1" "$2"
}
version_files() {   # $1=1.0.0|1.1.0 — 버전 3곳 · CHANGELOG(최상단 절 = 그 판) · 그 판의 노트(없음 표지)
  local v="$1"
  put .claude-plugin/plugin.json "{\"name\": \"relfix\", \"version\": \"$v\"}"
  put .claude-plugin/marketplace.json "{\"name\": \"relfix\", \"plugins\": [{\"name\": \"relfix\", \"source\": \"./\", \"version\": \"$v\"}]}"
  put "docs/releases/v$v.md" "# v$v — 출하 노트" '' "닫은 finding 없음."   # 공개 노트에는 내부 추적 번호를 적지 않는다(F-759 규약 — Closes 는 관리자 메모)
  { printf '# Changelog\n\n'
    [ "$v" = 1.0.0 ] || cl_section 1.1.0 2026-01-02
    cl_section 1.0.0 2026-01-01; } > "$R/CHANGELOG.md" || die "쓰기 CHANGELOG.md"
}
base_repo() {   # $1=셀 — 전역 R 에 v1.0.0 산출물 전부를 커밋한 저장소(전역 C1 · 태그 없음)
  local s
  R="$WORK/$1"
  gi -c init.defaultBranch=main init -q "$R"
  [ -d "$R/.git" ] || die "$1 저장소가 만들어지지 않았다"
  gi -C "$R" config core.fileMode true
  mkdir -p "$R/scripts" || die "mkdir $1/scripts"
  # 셔뱅 파일은 실행 비트를 준다 — 태그 없는 저장소의 모드 축이 추적 셔뱅 파일의 실행 비트(인덱스 · 작업 트리)를 절대 기준으로 본다
  for s in $SRCS; do cp "$TREE/scripts/$s" "$R/scripts/$s" && chmod 755 "$R/scripts/$s" || die "사본 scripts/$s"; done
  put scripts/health-check.sh '#!/bin/bash' '# 출하 게이트 ④ 의 시험용 스텁 — 실제 health-check 를 돌리지 않는다' 'exit 0'
  chmod 755 "$R/scripts/health-check.sh" || die "chmod scripts/health-check.sh"
  put .gitignore '__pycache__/' '*.pyc'
  put README.md '# relfix' '' '출하 게이트 회귀 픽스처다.'
  put guides/skill-authoring.md '# 스킬 작성' '' 'sweep 결과는 experiment-log 의 §5.8 ⑥ 표에 적는다.'
  put guides/model-guide.md '# 모델 가이드' '' 'sweep 결과는 experiment-log 의 §5.8 ⑥ 표에 적는다.'
  put experiment-log.md '# 실험 로그' '' '### ⑥ 세션 effort sweep' '' '## §5.9 구조 ablation'
  put docs/releases/_TEMPLATE.md '# v{버전} — {한 줄 요약}' '' '닫은 finding 은 Closes: 줄로 적는다.'
  version_files 1.0.0
  gi -C "$R" add -A
  gi -C "$R" commit -qm "v1.0.0"
  C1="$(gx -C "$R" rev-parse HEAD)" && [ -n "$C1" ] || die "$1 첫 커밋 이름"
}
commit() {   # $1=메시지 · $2=author 메일 · $3=committer 메일 · $4=author 이름(빈 값 = 합성) — 작업 트리 전부를 커밋. 전역 HEADC
  GX_AMAIL="${2:-}" GX_CMAIL="${3:-}" GX_ANAME="${4:-}"
  gi -C "$R" add -A
  gi -C "$R" commit -qm "$1"
  GX_AMAIL="" GX_CMAIL="" GX_ANAME=""
  HEADC="$(gx -C "$R" rev-parse HEAD)" && [ -n "$HEADC" ] || die "커밋 이름"
}
tag_v100() {   # $1=annotated|lightweight · $2=가리킬 커밋 · $3=주석(빈 값 = 기본) · $4=tagger 메일(빈 값 = 합성) — 기준 태그 v1.0.0
  if [ "$1" = annotated ]; then
    GX_CMAIL="${4:-}"; gi -C "$R" tag -a -m "${3:-v1.0.0 출하}" v1.0.0 "$2"; GX_CMAIL=""
  else
    gi -C "$R" tag v1.0.0 "$2"
  fi
}
tagged_repo() {   # $1=셀 — 대조 저장소: C1 + 주석 태그 v1.0.0 + 작업 트리를 v1.1.0 으로 올림(커밋은 셀이 한다)
  base_repo "$1"; tag_v100 annotated "$C1"; version_files 1.1.0
}
gate() {   # $1=저장소 · $2=출력 이름 · 나머지=진입점 인자 — 저장소의 사본 진입점을 돌린다. 출력 OUT · 종료 코드 GRC.
           #    진입점의 임시 로그(③-b · ④ 가 실패하면 남는다)는 실행마다 WORK/tmp/<출력 이름> 이다 — verdict 가 실패 셀에서 덤프한다
  local repo="$1" td="$WORK/tmp/$2"; OUT="$WORK/out/$2.txt"; shift 2
  mkdir -p "$td" || die "임시 폴더 tmp/${td##*/}"
  SHOW="$SHOW$OUT"$'\n'; LOGD="$LOGD$td"$'\n'
  (cd "$repo" && TMPDIR="$td" FZ_NEUTRALIZE_RULES="${GATE_NR:-}" bash scripts/check_release_sync.sh "$@") > "$OUT" 2>&1
  GRC=$?
}
want() {   # $1=기대 exit · 나머지=출력(OUT)에 있어야 할 글자(앞이 '!' 면 없어야 할 글자) — 어긋남은 WHY 에 덧붙인다
  local rc="$1" n; shift
  [ "$GRC" = "$rc" ] || WHY="$WHY · ${RUNL:+$RUNL }exit $GRC (기대 $rc)"
  for n in "$@"; do
    case "$n" in
      '!'*) ! /usr/bin/grep -qF -- "${n#!}" "$OUT" || WHY="$WHY · ${RUNL:+$RUNL }없어야 할 줄: ${n#!}" ;;
      *) /usr/bin/grep -qF -- "$n" "$OUT" || WHY="$WHY · ${RUNL:+$RUNL }없는 줄: $n" ;;
    esac
  done
}
verdict() {   # $1=셀 — WHY 가 비었으면 PASS · 아니면 FAIL + 사유 + 그 셀이 돌린 진입점 출력의 끝 20줄 + 진입점이 남긴 임시 로그의
              #    끝 20줄. WHY · SHOW · LOGD 를 비운다
  if [ -z "$WHY" ]; then
    echo "PASS $1"; npass=$((npass + 1))
  else
    echo "FAIL $1 —${WHY# ·}"; nfail=$((nfail + 1))
    printf '%s' "$SHOW" | while IFS= read -r f; do
      [ -f "$f" ] || continue
      echo "    ── ${f##*/}"; tail -n 20 "$f" | sed 's/^/    /'
    done
    # 통과한 검사의 로그는 진입점이 지운다 — 남은 파일은 실패 note 가 가리키는 로그다(러너가 끝나면 WORK 와 함께 지워진다)
    printf '%s' "$LOGD" | while IFS= read -r d; do
      for f in "$d"/*; do
        [ -f "$f" ] || continue
        echo "    ── 남은 로그 ${d##*/}/${f##*/}"; tail -n 20 "$f" | sed 's/^/    /'
      done
    done
  fi
  WHY="" SHOW="" LOGD=""
}
finish() {   # 끝 줄을 내고 끝낸다 — 자식 실행(host-config-params-ignored)은 앞의 두 셀 뒤에 부른다
  if [ "$nfail" -eq 0 ] && [ "$npass" -gt 0 ]; then
    echo "RELEASE_RANGE_OK (셀 ${npass}개 — 출하 게이트 사본의 --release 종료 코드와 실패한 축의 줄)"
    exit 0
  fi
  echo "release-range: 실패 ${nfail}건 · 통과 ${npass}건"
  exit 1
}

# ── 대조 — 아래 음성 셀은 이 저장소들에서 한 가지만 바꾼다. 인자 셀 셋은 rel-clean 저장소를 그대로 쓴다 ──
tagged_repo rel-clean; commit "v1.1.0"; RCLEAN="$R"
gate "$R" rel-clean --release --rules "$RULES_CORP"
want 0 "  누수 축 기준: v1.0.0" "LEAK_CLEAN range:HEAD files=" "LEAK_CLEAN commits:v1.0.0..HEAD commits=1 annotated=1 lightweight=0 files=" \
  "  ✅ health-check exit 0" "RELEASE_SYNC_OK ("
verdict rel-clean

# 태그 없는 첫 출하 — 루트부터 커밋마다 + 작업 트리 전문(⑦ 은 돌지 않는다) · 실행 비트는 절대 기준
base_repo rel-no-tag-clean-exit0; version_files 1.1.0; commit "v1.1.0"
gate "$R" rel-no-tag-clean-exit0 --release --rules "$RULES_CORP"
want 0 "  누수 축 기준: 직전 v* 태그 없음 — 루트부터 커밋마다 + 작업 트리 전문" "  ℹ️ 직전 v* 태그 없음 — 실행 비트를 절대 기준으로 본다" \
  "LEAK_CLEAN commits:HEAD commits=2 annotated=0 lightweight=0 with-tree files=" "! range:HEAD" "RELEASE_SYNC_OK ("
verdict rel-no-tag-clean-exit0
[ -z "${FZ_RELRANGE_CHILD:-}" ] || finish   # 자식 실행은 여기까지다 — 실행 비트를 절대 기준으로 보는 셀까지 돌면 충분하다

# 가벼운 기준 태그 — tagger · 주석 칸이 없다. 빈 값을 위반으로도 판정 불가로도 읽지 않고 세기만 한다
base_repo rel-lightweight-tag-clean-exit0; tag_v100 lightweight "$C1"; version_files 1.1.0; commit "v1.1.0"
gate "$R" rel-lightweight-tag-clean-exit0 --release --rules "$RULES_CORP"
want 0 "  누수 축 기준: v1.0.0" "commits:v1.0.0..HEAD commits=1 annotated=0 lightweight=1 " "RELEASE_SYNC_OK ("
verdict rel-lightweight-tag-clean-exit0

# 빈 규칙 파일 = 내장 규칙만 — 이름에만 합성 회사 이름이 든 신원(메일은 noreply)이 통과한다. 같은 저장소에 규칙 파일을 주면 그 신원이
#    비공개 규칙으로만 걸린다(신원 메일 적중 없음) — 빈 파일 쪽의 0 이 규칙을 읽지 않은 결과임을 가른다. env FZ_NEUTRALIZE_RULES 에
#    비공개 규칙 파일이 있어도 명시한 --rules(빈 파일)가 앞선다 — env 가 앞서면 그 신원이 걸려 1 이 된다
tagged_repo rel-rules-empty-builtin-only; commit "v1.1.0" "" "" "$CORPN dev"; S12="${HEADC:0:12}"
RUNL="빈 규칙:"; gate "$R" rel-rules-empty-builtin-only.empty --release --rules "$RULES_EMPTY"
want 0 "LEAK_CLEAN commits:v1.0.0..HEAD " "rules=0(--rules)" "RELEASE_SYNC_OK ("
RUNL="비공개 규칙:"; gate "$R" rel-rules-empty-builtin-only.corp --release --rules "$RULES_CORP"
want 1 "  ❌ 신원 $S12 author: 비공개 규칙" "!신원 메일"
RUNL="env 비공개 규칙 + 인자 빈 규칙:"; GATE_NR="$RULES_CORP"; gate "$R" rel-rules-empty-builtin-only.env --release --rules "$RULES_EMPTY"; GATE_NR=""
want 0 "rules=0(--rules)" "RELEASE_SYNC_OK ("
RUNL=""; verdict rel-rules-empty-builtin-only

# ── 위반(1) — 커밋마다 축 · 태그 축 ──
# 회사 도메인 메일로 커밋했다(author · committer) — 신원 정책(noreply 만 통과)과 비공개 규칙이 함께 잡는다
tagged_repo rel-corp-author-exit1; commit "v1.1.0" "$CORPM" "$CORPM"; S12="${HEADC:0:12}"
gate "$R" rel-corp-author-exit1 --release --rules "$RULES_CORP"
want 1 "  ❌ 신원 $S12 author: 신원 메일 — " "  ❌ 신원 $S12 author: 비공개 규칙" "  ❌ 신원 $S12 committer: 신원 메일 — " \
  "릴리즈 동기 불일치 1건"
verdict rel-corp-author-exit1

tagged_repo rel-commit-message-exit1; commit "v1.1.0 — 정리 $KEYP"; S12="${HEADC:0:12}"
gate "$R" rel-commit-message-exit1 --release --rules "$RULES_CORP"
want 1 "  ❌ 메시지 $S12:1: 티켓 키 꼴 — " "릴리즈 동기 불일치 1건"
verdict rel-commit-message-exit1

base_repo rel-tagger-corp-exit1; tag_v100 annotated "$C1" "" "$CORPM"; version_files 1.1.0; commit "v1.1.0"
gate "$R" rel-tagger-corp-exit1 --release --rules "$RULES_CORP"
want 1 "  ❌ tagger v1.0.0: 신원 메일 — " "  ❌ tagger v1.0.0: 비공개 규칙" "릴리즈 동기 불일치 1건"
verdict rel-tagger-corp-exit1

base_repo rel-tag-annotation-exit1; tag_v100 annotated "$C1" "v1.0.0 출하 — 중립 $OOBP"; version_files 1.1.0; commit "v1.1.0"
gate "$R" rel-tag-annotation-exit1 --release --rules "$RULES_CORP"
want 1 "  ❌ 주석 v1.0.0:1: 자리표시자 번호 — " "릴리즈 동기 불일치 1건"
verdict rel-tag-annotation-exit1

# 중간 커밋 — 첫 커밋이 더한 줄을 다음 커밋이 지웠다. HEAD 트리는 깨끗하다(대조: 범위 두 끝 비교는 0) — 커밋마다 봐야 잡힌다
tagged_repo rel-intermediate-commit-exit1
put notes.md "작업 경로 $HOMEP/notes"; commit "v1.1.0 작업"; CA="$HEADC"
rm -f "$R/notes.md"; commit "작업 메모 정리"; CB="$HEADC"
gate "$R" rel-intermediate-commit-exit1 --release --rules "$RULES_CORP"
ENDS="$WORK/out/rel-intermediate-commit-exit1.ends.txt"; SHOW="$SHOW$ENDS"$'\n'
python3 "$R/scripts/leak_rules.py" -C "$R" --rules="$RULES_CORP" --range=v1.0.0..HEAD > "$ENDS" 2>&1 \
  || WHY="$WHY · 범위 두 끝 비교(--range=v1.0.0..HEAD)가 0 이 아니다 — HEAD 트리가 깨끗하지 않아 중간 커밋 축을 가르지 못한다"
want 1 "  ❌ 추가 줄 ${CA:0:12} notes.md:1: 개인 홈 경로 — " "!추가 줄 ${CB:0:12} " "commits:v1.0.0..HEAD commits=2 " \
  "릴리즈 동기 불일치 1건"
verdict rel-intermediate-commit-exit1

# 병합 커밋 — 기준 태그를 옆 가지 커밋에 둬 그 커밋은 범위 밖이다. 적중은 병합 커밋의 첫 부모 대비 diff 에서만 나온다
#    (둘째 부모 대비 · 병합을 건너뛰면 0 이다)
base_repo rel-merge-commit-first-parent-exit1
MAINB="$(gx -C "$R" symbolic-ref --short HEAD)" && [ -n "$MAINB" ] || die "기본 브랜치 이름"
gi -C "$R" checkout -q -b side
put side.md "문의 $CORPM"; commit "옆 가지"; SIDE="$HEADC"
tag_v100 annotated "$SIDE"
gi -C "$R" checkout -q "$MAINB"
version_files 1.1.0; commit "v1.1.0"
gi -C "$R" merge -q --no-ff --no-edit -m "옆 가지 병합" side
MERGE="$(gx -C "$R" rev-parse HEAD)" && [ -n "$MERGE" ] || die "병합 커밋 이름"
gate "$R" rel-merge-commit-first-parent-exit1 --release --rules "$RULES_CORP"
want 1 "  ❌ 추가 줄 ${MERGE:0:12} side.md:1: 메일 주소 — " "!${SIDE:0:12}" "commits:v1.0.0..HEAD commits=2 " \
  "릴리즈 동기 불일치 1건"
verdict rel-merge-commit-first-parent-exit1

# HEAD 에 v* 태그가 붙어도 그 태그를 빼고 직전 태그 뒤의 커밋을 본다 — 자기 자신과 비교하면 범위가 비어 공허하게 0 이다
tagged_repo rel-head-tagged-uses-prior; put notes.md "작업 경로 $HOMEP/notes"; commit "v1.1.0"; S12="${HEADC:0:12}"
gi -C "$R" tag v1.1.0
gate "$R" rel-head-tagged-uses-prior --release --rules "$RULES_CORP"
want 1 "  누수 축 기준: v1.0.0" "  ❌ 추가 줄 $S12 notes.md:1: 개인 홈 경로 — " "commits:v1.0.0..HEAD commits=1 annotated=1 lightweight=1 " \
  "릴리즈 동기 불일치 1건"
verdict rel-head-tagged-uses-prior

# 태그 없는 첫 출하 + 0644 셔뱅 파일 — 실행 비트를 절대 기준으로 본다(커밋 · 인덱스 · 작업 트리 모두 실행 가능해야 한다).
#    작업 트리와 인덱스에서만 고치고 커밋하지 않은 것도 불일치다 — 출하되는 커밋에는 0644 가 남아 있다
base_repo rel-no-tag-modebit-exit1; version_files 1.1.0
put tools/run.sh '#!/bin/bash' 'echo ok'; chmod 644 "$R/tools/run.sh" || die "chmod tools/run.sh"; commit "v1.1.0"
RUNL="커밋 0644:"; gate "$R" rel-no-tag-modebit-exit1.committed --release --rules "$RULES_CORP"
want 1 "  ℹ️ 직전 v* 태그 없음 — 실행 비트를 절대 기준으로 본다" \
  "  ❌ 실행 비트가 없다(HEAD 100644 · 인덱스 100644 · 작업 트리): tools/run.sh — " "릴리즈 동기 불일치 1건"
chmod 755 "$R/tools/run.sh" || die "chmod tools/run.sh"; gi -C "$R" add -A
RUNL="고침 미커밋:"; gate "$R" rel-no-tag-modebit-exit1.uncommitted --release --rules "$RULES_CORP"
want 1 "  ❌ 실행 비트가 없다(HEAD 100644): tools/run.sh — " "릴리즈 동기 불일치 1건"
RUNL=""; verdict rel-no-tag-modebit-exit1

# 기준 태그 뒤에 새로 생긴 훅 — 새 파일은 `create mode` 줄이라 모드 변경 대조에 잡히지 않는다. 0755 면 통과하고 0644 면 불일치다
#    (git 은 실행 비트가 없는 훅을 조용히 건너뛴다). 같은 저장소에서 모드만 바꿔 1 이 훅이 생겨서가 아니라 모드 때문임을 가른다
tagged_repo rel-new-hook-nonexec-exit1
put .githooks/post-checkout '#!/bin/bash' 'exit 0'; chmod 755 "$R/.githooks/post-checkout" || die "chmod .githooks/post-checkout"
commit "v1.1.0"
RUNL="0755:"; gate "$R" rel-new-hook-nonexec-exit1.exec --release --rules "$RULES_CORP"
want 0 "RELEASE_SYNC_OK ("
chmod 644 "$R/.githooks/post-checkout" || die "chmod .githooks/post-checkout"; commit "훅 모드"
RUNL="0644:"; gate "$R" rel-new-hook-nonexec-exit1.nonexec --release --rules "$RULES_CORP"
want 1 "  ❌ v1.0.0 뒤 새로 생긴 훅에 실행 비트가 없다(100644): .githooks/post-checkout — " "릴리즈 동기 불일치 1건"
# 작업 트리에서만 고치고 커밋하지 않았다 — 출하되는 커밋의 훅은 여전히 0644 다
chmod 755 "$R/.githooks/post-checkout" || die "chmod .githooks/post-checkout"
RUNL="고침 미커밋:"; gate "$R" rel-new-hook-nonexec-exit1.uncommitted --release --rules "$RULES_CORP"
want 1 "  ❌ v1.0.0 뒤 새로 생긴 훅에 실행 비트가 없다(100644 · 커밋 HEAD" "릴리즈 동기 불일치 1건"
RUNL=""; verdict rel-new-hook-nonexec-exit1

# ── 판정 불가(2) — 위반이 함께 있어도 2 가 앞선다 ──
# 위반(⑧ 신원) + 판정 불가(⑦ 미추적 latin-1 파일) — 최종 exit 2 · 끝 줄이 둘 다 센다
tagged_repo rel-mixed-violation-and-unrun-exit2; commit "v1.1.0" "$CORPM" "$CORPM"; S12="${HEADC:0:12}"; raw l1.txt latin1
gate "$R" rel-mixed-violation-and-unrun-exit2 --release --rules "$RULES_CORP"
want 2 "  ❌ 신원 $S12 author: 신원 메일 — " "UNRUN: UTF-8 로 읽지 못했다: l1.txt" \
  "  ⚠️ 중립화 축 미판정(정본 모듈 exit 2) — 판정 불가(⛔ 통과 아님)" \
  "릴리즈 동기 판정 불가 1건 · 불일치 1건 — 판정 불가가 앞선다(⛔ 통과 아님)"
verdict rel-mixed-violation-and-unrun-exit2

# 범위 커밋이 더한 파일 — UTF-16 · 바이너리(git 이 바이너리로 본다 — numstat 분기)와 latin-1(git 은 텍스트로 보지만 추가 줄의
#    UTF-8 디코드가 실패한다 — 디코드 분기). 어느 쪽도 건너뛰지 않고 판정 불가다
tagged_repo rel-binary-or-utf16-added-exit2; raw u16.txt utf16; raw blob.bin binary; raw l1.txt latin1; commit "v1.1.0"; S12="${HEADC:0:12}"
gate "$R" rel-binary-or-utf16-added-exit2 --release --rules "$RULES_CORP"
want 2 "바이너리로 본 파일이다: u16.txt" "바이너리로 본 파일이다: blob.bin" "UNRUN: $S12: UTF-8 로 읽지 못했다: l1.txt:1 — " \
  "  ⚠️ 커밋마다 축 미판정(정본 모듈 exit 2) — 판정 불가(⛔ 통과 아님)" "판정 불가가 앞선다(⛔ 통과 아님)"
verdict rel-binary-or-utf16-added-exit2

# 미추적 파일 — latin-1(UTF-8 디코드 실패) · BOM 없는 UTF-16(NUL). ⑦ 이 건너뛰지 않고 판정 불가다
tagged_repo rel-untracked-undecodable-exit2; commit "v1.1.0"; raw l1.txt latin1; raw u16.txt utf16
gate "$R" rel-untracked-undecodable-exit2 --release --rules "$RULES_CORP"
want 2 "UNRUN: UTF-8 로 읽지 못했다: l1.txt" "UNRUN: NUL 바이트가 있다(UTF-16 · 바이너리): u16.txt" \
  "  ⚠️ 중립화 축 미판정(정본 모듈 exit 2) — 판정 불가(⛔ 통과 아님)" "판정 불가가 앞선다(⛔ 통과 아님)"
verdict rel-untracked-undecodable-exit2

# v* 태그가 있는데 HEAD 에서 닿지 않는다(옆 이력의 커밋) — 첫 출하로 읽지 않고 판정 불가다(누수 축은 돌지 않는다)
base_repo rel-describe-fail-exit2; version_files 1.1.0; commit "v1.1.0"
T0="$(gx -C "$R" hash-object -t tree -w /dev/null)" && [ -n "$T0" ] || die "빈 트리 객체"
O1="$(gx -C "$R" commit-tree "$T0" -m "옆 이력")" && [ -n "$O1" ] || die "닿지 않는 커밋"
gi -C "$R" tag v0.9.0 "$O1"
gate "$R" rel-describe-fail-exit2 --release --rules "$RULES_CORP"
want 2 "  ⚠️ 누수 축의 기준 태그를 정하지 못했다 — " "판정 불가가 앞선다(⛔ 통과 아님)" "!LEAK_"
verdict rel-describe-fail-exit2

# 최상단 절에 finding 표도 '닫은 finding 없음' 표지도 없다 — 대조 저장소에서 CHANGELOG 의 최상단 절만 표 없는 본문으로 바꾼다.
#    기본 모드의 표 검사는 표 없는 절을 통과시킨다. 출하 진입점이 표 필수 모드로 부르지 않으면 이 셀이 exit 0 으로 실패한다
tagged_repo rel-no-finding-table-exit1
{ printf '# Changelog\n\n### v1.1.0 (2026-01-02) — 출하\n\n표 없이 본문만 적은 절이다.\n\n'
  cl_section 1.0.0 2026-01-01; } > "$R/CHANGELOG.md" || die "쓰기 CHANGELOG.md"
commit "v1.1.0"
gate "$R" rel-no-finding-table-exit1 --release --rules "$RULES_CORP"
want 1 "CHANGELOG v1.1.0 절에 finding 표(또는 '닫은 finding 없음' 표지)가 없거나 표에 빈 칸이 있다"
verdict rel-no-finding-table-exit1

# 최상단 절에 내부 추적 번호가 든 finding 표 — 칸이 다 찼어도 공개 CHANGELOG 에는 번호를 적지 않는다(노트와 같은 규약)
tagged_repo rel-changelog-internal-id-exit1
{ printf '# Changelog\n\n### v1.1.0 (2026-01-02) — 출하\n\n| ID | 판정 | 근거 | 검증 절차 |\n|---|---|---|---|\n| F-902 | 해결 | 픽스처 셀 | `bash run.sh` |\n\n'
  cl_section 1.0.0 2026-01-01; } > "$R/CHANGELOG.md" || die "쓰기 CHANGELOG.md"
commit "v1.1.0"
gate "$R" rel-changelog-internal-id-exit1 --release --rules "$RULES_CORP"
want 1 "CHANGELOG v1.1.0 절에 내부 추적 번호가 있다" "!finding 표(또는"
verdict rel-changelog-internal-id-exit1

# ── 인자 — 대조 저장소(rel-clean)에 인자 하나만 바꿔 준다. 축에 닿기 전에 2 로 끝난다(버전 줄이 없다) ──
# --rules 없음 — env FZ_NEUTRALIZE_RULES 에 규칙 파일이 있어도 그것으로 추정하지 않는다
GATE_NR="$RULES_CORP"; gate "$RCLEAN" rel-release-no-rules-arg-exit2 --release; GATE_NR=""
want 2 "❌ --release 는 --rules <파일> 을 명시로 요구한다" "!버전: plugin="
verdict rel-release-no-rules-arg-exit2

gate "$RCLEAN" rel-rules-file-missing-exit2 --release --rules "$WORK/absent-rules.txt"
want 2 "❌ --rules 파일이 없다: " "!버전: plugin="
verdict rel-rules-file-missing-exit2

gate "$RCLEAN" rel-unknown-arg-exit2 --release --rules "$RULES_CORP" --bogus
want 2 "❌ 알 수 없는 인자: --bogus" "!버전: plugin="
verdict rel-unknown-arg-exit2

# ── 커밋 축 · ④ health-check — 대조 저장소에서 한 가지만 바꾼다 ──
# 그 판의 노트가 인덱스에 없다 — 작업 트리에는 있어 노트를 읽는 축은 통과한다. 커밋 축만 잡는다(`commit` 은 add -A 라 쓰지 않는다)
tagged_repo rel-release-note-untracked-exit1; commit "v1.1.0"
gi -C "$R" rm -q --cached docs/releases/v1.1.0.md
gi -C "$R" commit -qm "노트 빼기"
gate "$R" rel-release-note-untracked-exit1 --release --rules "$RULES_CORP"
want 1 "  ❌ docs/releases/v1.1.0.md 이 untracked — 릴리즈 문서가 커밋되지 않았다" "!RELEASE_SYNC_OK ("
verdict rel-release-note-untracked-exit1

# ④ health-check 가 실패한다 — 스텁을 exit 1 로 바꿔 커밋한다. 게이트가 그 종료 코드를 버리면 exit 0 이 나 이 셀이 실패한다
tagged_repo rel-health-check-fail-exit1
put scripts/health-check.sh '#!/bin/bash' '# 출하 게이트 ④ 의 시험용 스텁 — 실패하는 health-check' 'echo "stub: 1건 실패"' 'exit 1'
commit "v1.1.0"
gate "$R" rel-health-check-fail-exit1 --release --rules "$RULES_CORP"
want 1 "health-check 실패 (로그: " "!RELEASE_SYNC_OK ("
verdict rel-health-check-fail-exit1

# HEAD 에서 닿지 않는 커밋을 가리키는 로컬 태그(이름이 v* 가 아니어도) — 그 커밋은 범위 밖이라 어느 축도 보지 않았다. 태그를 올리면
#    그 이력째 나간다. 깨끗하다고 읽지 않고 판정 불가다(그 커밋의 홈 경로 줄은 위반으로도 세지 못한다 — 보지 않았다)
tagged_repo rel-unreachable-old-tag-exit2; commit "v1.1.0"
printf '작업 경로 %s/notes\n' "$HOMEP" > "$WORK/orphan.txt" || die "쓰기 orphan.txt"
OB="$(gx -C "$R" hash-object -w "$WORK/orphan.txt")" && [ -n "$OB" ] || die "옛 이력 blob"
OT="$(printf '100644 blob %s\tnotes.md\n' "$OB" | gx -C "$R" mktree)" && [ -n "$OT" ] || die "옛 이력 트리"
OC="$(gx -C "$R" commit-tree "$OT" -m "옛 이력")" && [ -n "$OC" ] || die "옛 이력 커밋"
gi -C "$R" tag old-snapshot "$OC"
gate "$R" rel-unreachable-old-tag-exit2 --release --rules "$RULES_CORP"
want 2 "태그가 검사 범위 밖의 커밋 1개를 가리킨다: old-snapshot" "판정 불가가 앞선다(⛔ 통과 아님)" "!RELEASE_SYNC_OK ("
verdict rel-unreachable-old-tag-exit2

# ── 호스트 git 설정 ──
# 출하 게이트 self-test 는 호스트의 git 설정을 읽지 않는다 — 서명을 강제하고 서명 프로그램이 실패하는 설정을 전역 설정 파일 ·
#    부모 git 의 `-c` 주입(GIT_CONFIG_PARAMETERS) · 환경 변수 설정(GIT_CONFIG_COUNT) 세 길로 함께 줘도 통과한다. 어느 한 길이라도
#    끊지 않으면 self-test 의 임시 저장소 커밋이 서명에서 죽는다
HOSTILE="$WORK/hostile.gitconfig"
printf '[commit]\n\tgpgsign = true\n[tag]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n' > "$HOSTILE" || die "쓰기 hostile.gitconfig"
ST_OUT="$WORK/out/gate-selftest-hostile.txt"; SHOW="$SHOW$ST_OUT"$'\n'
(cd "$TREE" && GIT_CONFIG_GLOBAL="$HOSTILE" GIT_CONFIG_PARAMETERS="'commit.gpgsign=true' 'gpg.program=false'" \
  GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=true GIT_CONFIG_KEY_1=gpg.program GIT_CONFIG_VALUE_1=false \
  bash scripts/check_release_sync.sh --self-test) > "$ST_OUT" 2>&1; ST_RC=$?
[ "$ST_RC" = 0 ] || WHY="$WHY · 적대적 git 설정(전역 파일 + 부모 git 주입 + 환경 변수 설정) 아래의 출하 게이트 self-test 가 exit $ST_RC (기대 0)"
verdict gate-selftest-hostile-global-config-exit0

# 부모 git 의 설정을 물려받은 실행 — core.filemode=false 를 두 길(`-c` 주입 GIT_CONFIG_PARAMETERS · 환경 변수 설정 GIT_CONFIG_COUNT)로
#    함께 밀어 넣어도 결과가 같아야 한다. 어느 한 길이라도 끊지 않으면 남은 길이 값을 넣는다(끊지 않으면 셀 저장소의
#    core.fileMode 를 덮어 태그 없는 첫 출하의 실행 비트 축이 갈린다). 자식은 앞의 두 셀만 돌고 끝난다
CH_OUT="$(FZ_RELRANGE_CHILD=1 GIT_CONFIG_PARAMETERS="'core.filemode=false'" GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.filemode GIT_CONFIG_VALUE_0=false \
  bash "${BASH_SOURCE[0]}" --tree "$TREE" 2>&1)"; CH_RC=$?
[ "$CH_RC" = 0 ] || WHY="$WHY · 부모 git 설정을 물려받은 자식 실행이 exit $CH_RC (기대 0) — $(printf '%s' "$CH_OUT" | /usr/bin/grep -m 3 '^FAIL' | tr '\n' ' ' | cut -c1-300)"
verdict host-config-params-ignored

finish
