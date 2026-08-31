#!/bin/bash
# diff-parse: hunk-state — base 목록 파서가 `in_hunk` 를 추적한다. 변경 규모 셈은
#   `numstat_fallback.awk` 에 위임(그쪽도 hunk-state).
# Gather 의 결정론 구간을 한 번에 수집한다 — Lead 의 순차 도구 호출을 줄인다.
#
# 왜 스크립트인가: 병목이 fan-out 이 아니라 **Lead 의 순차 작업**이라는 실측이 있다
# (agent 0콜 실행도 분 단위가 걸렸다). 렌즈에는 Bash 가 없으므로
# (`agent-team-guide.md` — 워크플로 워커는 acceptEdits 강제, tools 제거가 유일 방어)
# 병렬화 대신 **Lead 쪽 호출 횟수**를 줄이는 것이 남은 레버다.
#
# ⛔ 이 스크립트가 하지 않는 것 — 판단이 필요한 수집:
#   · old-new-pairs   변경 *함수* 단위로 자르려면 언어 파싱이 필요하다
#   · producer-consumer / caller-analysis / convention-samples  심볼 탐색(Serena) 영역
#   · semantic-mapping  의미 대응은 사람·모델 판단
#   위 항목은 Lead 가 채운다. 스크립트는 **원재료**까지만 만든다.
#
# usage:
#   gather.sh --work-dir DIR --target (PR번호|브랜치) [--base BRANCH]
#
# ⛔ Tier 인자를 받지 않는다. 이 스크립트는 Tier 와 무관하게 **원재료만** 만들고,
#    무엇을 읽을지는 Lead 가 Tier 별 canonical set 으로 고른다 — 수집을 여기서
#    줄이면 Tier 승격 시 다시 호출해야 한다.
#
# exit: 0 성공 / 2 사용법 / 3 대상 해석 실패 / 4 수집 실패 / 5 base 원본 전건 실패
#   ⛔ 5 는 산출물을 **남긴다** — diff 는 유효하고 origin 근거만 없다. 진행 여부는 호출자 판단.
#   ⛔ 실패 시 부분 산출물을 남기지 않는다 — 반쯤 찬 WORK_DIR 은 "수집했는데 없었다"로 오독된다.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() {
  echo "GATHER-FAIL($1): $2" >&2
  [ -n "${STAGE_DIR:-}" ] && rm -rf "$STAGE_DIR"
  [ -n "${INCOMING:-}" ] && rm -rf "$INCOMING"
  exit "$1"
}

WORK_DIR="" TARGET="" BASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --work-dir) [ $# -ge 2 ] || die 2 "--work-dir 는 값이 필요하다"; WORK_DIR="$2"; shift 2 ;;
    --target)   [ $# -ge 2 ] || die 2 "--target 은 값이 필요하다";   TARGET="$2";   shift 2 ;;
    --base)     [ $# -ge 2 ] || die 2 "--base 는 값이 필요하다";     BASE="$2";     shift 2 ;;
    *) die 2 "알 수 없는 인자: $1" ;;
  esac
done
[ -n "$WORK_DIR" ] || die 2 "--work-dir 필수"
[ -n "$TARGET" ]   || die 2 "--target 필수"

# ⛔ staging 에 모으고 마지막에 옮긴다. 중간 실패가 WORK_DIR 을 오염시키지 않는다.
STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/fz-gather.XXXXXX")" || die 4 "임시 디렉터리 생성 실패"

is_pr=false
[[ "$TARGET" =~ ^[0-9]+$ ]] && is_pr=true

# ── diff + 메타 ──────────────────────────────────────────────
if $is_pr; then
  command -v gh >/dev/null 2>&1 || die 3 "PR 번호를 받았으나 gh 가 없다 — 브랜치명으로 호출하라"
  gh pr view "$TARGET" --json baseRefName,headRefName,title,body,additions,deletions,files \
     > "$STAGE_DIR/pr-meta.json" 2>/dev/null || die 3 "PR $TARGET 조회 실패"
  BASE="${BASE:-$(python3 -c "import json,sys;print(json.load(open('$STAGE_DIR/pr-meta.json'))['baseRefName'])" 2>/dev/null)}"
  gh pr diff "$TARGET" > "$STAGE_DIR/diff.patch" 2>/dev/null || die 3 "PR $TARGET diff 실패"
  python3 - "$STAGE_DIR" <<'PY' || die 4 "requirements 생성 실패"
import json, sys, os
d = json.load(open(os.path.join(sys.argv[1], 'pr-meta.json')))
with open(os.path.join(sys.argv[1], 'requirements.md'), 'w', encoding='utf-8') as fh:
    fh.write("# 요구사항\n\n## 제목\n%s\n\n## 본문\n%s\n" % (d.get('title', ''), d.get('body') or '(없음)'))
PY
else
  if [ -z "$BASE" ]; then
    case "$TARGET" in
      feature/*) BASE="develop" ;;
      hotfix/*)  BASE="main" ;;
      *) die 3 "base 를 결정할 수 없다 — --base 로 지정하라 (⛔ 추측하지 않는다)" ;;
    esac
  fi
  git rev-parse --verify "$BASE" >/dev/null 2>&1 || die 3 "base '$BASE' 를 찾을 수 없다"
  git diff "${BASE}...${TARGET}" > "$STAGE_DIR/diff.patch" 2>/dev/null || die 3 "diff 실패"
  printf '# 요구사항\n\n(브랜치 입력 — PR 메타 없음. Lead 가 티켓에서 채운다)\n' > "$STAGE_DIR/requirements.md"
fi

[ -s "$STAGE_DIR/diff.patch" ] || die 4 "diff 가 비어 있다 — 대상이 맞는지 확인하라"

# ── 변경 규모 (tier 판정 입력) ────────────────────────────────
git diff --numstat "${BASE}...${TARGET}" > "$STAGE_DIR/numstat.txt" 2>/dev/null || \
  awk -f "$HERE/numstat_fallback.awk" \
      "$STAGE_DIR/diff.patch" > "$STAGE_DIR/numstat.txt"
  # ⛔ PR 경로는 로컬 ref 부재로 `--numstat` 이 **항상 실패**한다 → 이 폴백이 매번 돈다.
  #    셈 규칙과 그 근거는 `numstat_fallback.awk` 안에. 회귀: tests/fixtures/peer-review/numstat-fallback/

# ── base 원본 (origin 판정 근거) ──────────────────────────────
# ⛔ base 쪽 경로(`--- a/…`)를 읽는다. `+++ b/…` 는 두 경우에 **틀린다**:
#   · 삭제 파일은 `+++ /dev/null` 이라 목록에 아예 안 잡힌다 — 삭제가 핵심인 PR 에서
#     origin 판정의 근거가 통째로 빈다
#   · rename 은 새 경로가 base 에 없어 `git show` 가 조용히 실패한다
# ⛔ 경로를 평탄화하지 않는다. `/`→`_` 는 `a_b/c` 와 `a/b_c` 를 한 파일로 만든다.
#   디렉터리 구조를 그대로 미러링한다.
mkdir -p "$STAGE_DIR/base"
python3 - "$STAGE_DIR/diff.patch" > "$STAGE_DIR/base-manifest.tsv" <<'PY' || die 4 "diff 파싱 실패"
import ast, sys

def unquote(p):
    """core.quotePath 로 이스케이프된 경로를 되돌린다 (`"a/f\\303\\251o"`)."""
    if len(p) >= 2 and p.startswith('"') and p.endswith('"'):
        try:
            s = ast.literal_eval(p)
        except (ValueError, SyntaxError):
            return p[1:-1]
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return p


def side_path(raw, side):
    p = unquote(raw.strip())
    if p == "/dev/null":
        return None
    return p[2:] if p.startswith(side + "/") else p


def safe(p):
    """base/ 밖으로 쓰지 못하게 막는다. git 경로는 리포 상대이지만 입력을 신뢰하지 않는다."""
    if not p or p.startswith("/"):
        return None
    return None if any(seg in ("..", "") for seg in p.split("/")) else p


def from_header(rest):
    """`---` 가 없는 블록(순수 rename·바이너리)용 휴리스틱.
    ⚠️ 공백이 든 경로는 모호하다 — 마지막 ` b/` 로 자른다."""
    if not (rest.startswith("a/") or rest.startswith('"a/')):
        return None
    idx = rest.rfind(" b/")
    if idx < 0:
        idx = rest.rfind(' "b/')
    return side_path(rest[:idx], "a") if idx >= 0 else None


entries, cur, in_hunk = [], None, False
with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if line.startswith("diff --git "):
            if cur:
                entries.append(cur)
            cur = {"old": None, "new": None, "status": "modified",
                   "header": line[len("diff --git "):]}
            in_hunk = False
            continue
        if cur is None:
            continue
        # ⛔ hunk 안의 `--- a/x` 는 `-- a/x` 를 **삭제한 소스 행**이다 (diff 를 담은 diff).
        #    상태를 안 보면 남의 파일 경로를 base 목록에 넣는다.
        if line.startswith("@@"):
            in_hunk = True
            continue
        if in_hunk:
            continue
        if line.startswith("new file mode"):
            cur["status"] = "added"
        elif line.startswith("deleted file mode"):
            cur["status"] = "deleted"
        elif line.startswith("rename from "):
            cur["old"] = line[len("rename from "):].strip()
            cur["status"] = "renamed"
        elif line.startswith("rename to "):
            cur["new"] = line[len("rename to "):].strip()
        elif line.startswith("--- "):
            cur["old"] = side_path(line[4:], "a")
        elif line.startswith("+++ "):
            cur["new"] = side_path(line[4:], "b")
if cur:
    entries.append(cur)

for e in entries:
    old = e["old"]
    if old is None and e["status"] != "added":
        old = from_header(e["header"])
    print("%s\t%s\t%s" % (e["status"], safe(old) or "", e["new"] or ""))
PY

# ⛔ PR 경로의 `baseRefName` 은 **원격 브랜치 이름**이다 — 로컬에 그 ref 가 없을 수 있다.
#    실측(#4766): `feature/mini-player` 로컬 부재 → `git show` 25건 전부 실패 → base 원본 **0/25**.
#    브랜치 경로엔 `rev-parse --verify` 가드가 있는데 PR 경로엔 없어 실패가 조용히 아래로 흘렀다.
#    remote 접두를 붙여 재해석한다. 원격이 여럿이면 upstream → origin 순.
if $is_pr && ! git rev-parse --verify "$BASE" >/dev/null 2>&1; then
  for rem in upstream origin $(git remote 2>/dev/null); do
    if git rev-parse --verify "${rem}/${BASE}" >/dev/null 2>&1; then
      echo "GATHER-NOTE: base '$BASE' 로컬 부재 → '${rem}/${BASE}' 로 해석" >&2
      BASE="${rem}/${BASE}"
      break
    fi
  done
fi

# `git diff A...B` 는 **merge-base** 기준이다. BASE 팁이 앞서 있으면 팁의 내용은
# diff 가 비교한 원본이 아니다 — 해석되는 경우에만 merge-base 로 바꾼다.
BASE_REF="$BASE"
HEAD_REF="$TARGET"
if $is_pr; then
  # PR 번호로는 로컬 head 를 알 수 없다. 스킬 Gather Step 0.5 가 만드는 `pr-{N}` 을 먼저 보고,
  # 없으면 fetch 된 `refs/pull/{N}/head` 를 본다. 둘 다 없으면 merge-base 를 못 구한다.
  for cand in "pr-${TARGET}" "refs/pull/${TARGET}/head"; do
    if git rev-parse --verify "$cand" >/dev/null 2>&1; then HEAD_REF="$cand"; break; fi
  done
  [ "$HEAD_REF" = "$TARGET" ] && HEAD_REF=""
fi
# ⛔ `A...B` 는 **merge-base** 기준이다. base 팁이 분기 후 앞서 있으면 팁의 내용은
#    diff 가 비교한 원본이 아니다 — PR 경로에서도 반드시 맞춘다.
#    실측(#4766): base 팁 996457677c ≠ merge-base 807d1769a2cc. 팁을 읽으면 origin 판정이
#    "regression" 을 "pre-existing" 으로, 또는 그 반대로 뒤집는다.
if [ -n "$HEAD_REF" ]; then
  mb=$(git merge-base "$BASE" "$HEAD_REF" 2>/dev/null) && [ -n "$mb" ] && BASE_REF="$mb"
fi

# ── 리뷰 표면 진단 (stale merge-base) ────────────────────────
# ⛔ `diff` 는 merge-base 기준이라, base 가 분기 후 앞서 나가면 **이미 base 에 있는 변경**이
#    diff 에 다시 나타난다. 그러면 Tier 판정이 위로 틀리고(리뷰 예산 낭비) 리뷰어는 이미
#    리뷰·머지된 코드를 다시 본다.
#    실측(#4766): base 가 분기점보다 39커밋 앞. head 3커밋 중 **2개가 이미 base 에 있어**
#    diff 가 26파일 +304/−182 로 보였으나 실제 리뷰 표면은 18파일 +83/−83 이었다 (2.9배).
# ⚠️ `git cherry` 는 patch-id 로 판정하며 **머지 커밋을 제외**한다. 스쿼시·리베이스로 해시가
#    바뀐 동일 패치는 잡지만, 내용이 조금이라도 다르면 `+` 로 남는다 — 놓침이 있는 도구다.
{
  printf '# 리뷰 표면

'
  if [ "$BASE_REF" != "$BASE" ] && [ -n "$HEAD_REF" ]; then
    ahead=$(git rev-list --count "${BASE_REF}..${BASE}" 2>/dev/null || echo "?")
    printf 'base 팁이 분기점(`%s`)보다 **%s커밋 앞서** 있다.

' "${BASE_REF:0:10}" "$ahead"
    dup=$(git cherry "$BASE" "$HEAD_REF" 2>/dev/null | grep -c '^-' || true)
    new=$(git cherry "$BASE" "$HEAD_REF" 2>/dev/null | grep -c '^+' || true)
    if [ "${dup:-0}" -gt 0 ]; then
      printf '⛔ **head 커밋 %s개가 이미 base 에 있다** (patch-id 일치). 신규는 %s개다 —
' "$dup" "$new"
      printf 'diff 와 Tier 판정이 그만큼 부풀려져 있다. 아래 `-` 커밋은 리뷰 대상이 아니다.

'
      printf '```
'
      git cherry -v "$BASE" "$HEAD_REF" 2>/dev/null | cut -c1-100
      printf '```

'
      printf '⭐ 리뷰 표면만 보려면: `git show <+ 커밋>` 또는 base 를 현재 팁으로 rebase 후 재수집.
'
    else
      printf '중복 커밋은 없다 (`git cherry` 기준). diff 전체가 리뷰 대상이다.
'
    fi
  else
    printf '분기점 == base 팁 (또는 head ref 미해석). 중복 진단을 하지 않았다.
'
  fi
} > "$STAGE_DIR/review-surface.md"

# ── 이동 리팩토링 드리프트 (조건부) ──────────────────────────
# ⛔ 동등성과 드리프트는 **다른 축**이다. 다중집합 차가 "값 표현식 변화 0" 을 보여도
#    이동이 만든 **문서·구조 드리프트**는 거기 안 나타난다.
#    실측(PR): 동등성 통과 후 Lead 단독 리뷰가 이슈 0건을 냈으나 3렌즈가
#    `origin: regression` 3건을 찾았다 — 새 파일 헤더가 그 파일에 없는 심볼을 가리켰고(A4),
#    분리 후 기능이 5개 지점에 흩어졌다(Q2).
#
# ⛔ **판정 대상은 `git cherry` 의 `+` 커밋분이다.** 중복 커밋을 포함하면 오탐이 난다 —
#    실측: #4766(개명 PR)이 "이동" 으로 잡혔는데, 그 신규 파일은 이미 base 에 머지된
#    OBS-25 분이었고 리뷰 대상 커밋만 보면 `new file mode` 가 **0건**이다.
DRIFT_RANGE=""
if [ -n "$HEAD_REF" ]; then
  # `+` = base 에 없는 커밋. 하나면 그 커밋, 여럿이면 merge-base..head 를 그대로 쓴다.
  plus=$(git cherry "$BASE" "$HEAD_REF" 2>/dev/null | awk '$1=="+"{print $2}')
  cnt=$(printf '%s\n' "$plus" | grep -c . || true)
  if [ "${cnt:-0}" -eq 1 ]; then DRIFT_RANGE="$(printf '%s' "$plus")^!"
  elif [ "${cnt:-0}" -gt 1 ]; then DRIFT_RANGE="${BASE_REF}..${HEAD_REF}"
  fi
fi

if [ -n "$DRIFT_RANGE" ] && git show "$DRIFT_RANGE" >/dev/null 2>&1; then
  git show "$DRIFT_RANGE" > "$STAGE_DIR/.drift-src.patch" 2>/dev/null || true
  if [ -f "$HERE/move_drift.py" ] && [ -s "$STAGE_DIR/.drift-src.patch" ]; then
    python3 "$HERE/move_drift.py" "$STAGE_DIR/.drift-src.patch" "$DRIFT_RANGE" \
      > "$STAGE_DIR/evidence-move-drift.md" 2>/dev/null || rm -f "$STAGE_DIR/evidence-move-drift.md"
  fi
  rm -f "$STAGE_DIR/.drift-src.patch"
fi

# ── 리뷰 표면 patch (중복 커밋 제외) ────────────────────────────
# ⛔ 신설 근거: `review-surface.md` 는 중복 커밋을 **진단**하지만 커밋 해시·제목만 담는다.
#    렌즈는 Bash·git 이 없어(`peer-review.js` OVERRIDE) 그 해시로 hunk 를 필터할 수 없다 —
#    판정을 넘겨도 렌즈 입력은 부풀려진 `diff.patch` 그대로였다.
#    ⭐ 조언("`git show <+ 커밋>` 또는 rebase 후 재수집")도 렌즈가 할 수 없는 일이다.
# ⛔ 신규 로직 0 — 위 DRIFT_RANGE(= `+` 커밋 범위)를 그대로 재사용한다.
# ⛔ diff.patch 를 덮지 않는다 — 원본은 Tier·numstat·risk_scan 의 입력이고 그 판정은 별 축이다.
if [ -n "$DRIFT_RANGE" ] && [ "${dup:-0}" -gt 0 ]; then
  if git diff "$DRIFT_RANGE" > "$STAGE_DIR/review-surface.patch" 2>/dev/null      && [ -s "$STAGE_DIR/review-surface.patch" ]; then
    echo "  review-surface.patch — 중복 ${dup}커밋 제외한 리뷰 표면 ($(command grep -c '^diff --git' "$STAGE_DIR/review-surface.patch" 2>/dev/null || echo '?')파일)"
  else
    rm -f "$STAGE_DIR/review-surface.patch"
    echo "⚠️  review-surface.patch 생성 실패 — 렌즈는 diff.patch 전량을 받는다(부풀림 잔존)"
  fi
fi

saved=0 expected=0 missing=""
# ⛔ `IFS=$'\t' read -r a b c` 를 쓰지 않는다 — **탭은 IFS 공백**이라 연속 탭이 하나로
#    합쳐진다. `added\t\tfresh.txt` 가 `old=fresh.txt` 로 읽혀 신규 파일이 전부
#    "base 에서 못 읽었다"로 보고된다 (경고가 노이즈가 되어 무시된다).
#    빈 칸을 보존하려면 줄을 통째로 읽고 직접 자른다.
while IFS= read -r row; do
  status="${row%%$'\t'*}"
  rest="${row#*$'\t'}"
  old="${rest%%$'\t'*}"
  [ -n "$old" ] && [ "$old" != "$row" ] || continue
  expected=$((expected+1))
  out="$STAGE_DIR/base/$old"
  mkdir -p "$(dirname "$out")" 2>/dev/null || { missing="${missing}"$'\n'"- \`${old}\` (${status} — 디렉터리 생성 실패)"; continue; }
  if git show "${BASE_REF}:${old}" > "$out" 2>/dev/null; then
    saved=$((saved+1))
  else
    rm -f "$out"
    missing="${missing}"$'\n'"- \`${old}\` (${status})"
  fi
done < "$STAGE_DIR/base-manifest.tsv"

{
  printf '# base 원본\n\n'
  printf '대상 base: `%s`' "$BASE"
  if [ "$BASE_REF" != "$BASE" ]; then
    printf ' (merge-base `%s`)' "$BASE_REF"
  else
    # ⛔ 주석의 *부재*를 "팁을 읽었다"는 신호로 쓰지 않는다 — 읽는 사람은 그 규칙을 모른다.
    printf ' — ⚠️ **브랜치 팁 기준**(merge-base 해석 실패 — PR 이면 `pr-%s` 미fetch). base 가 분기 후 앞서 있으면 여기 원본은 diff 가 비교한 것이 아니다' "$TARGET"
  fi
  printf '\n\n수집: %d / %d개\n\n' "$saved" "$expected"
  printf '원본은 `base/` 아래에 **리포지토리 경로 그대로** 있다. 변경 목록·상태는 `base-manifest.tsv`.\n'
  printf '신규 파일(`added`)은 base 에 없으므로 애초에 대상이 아니다 — 위 분모에서도 빠진다.\n'
  if [ -n "$missing" ]; then
    printf '\n## ⛔ 수집 실패 — origin 판정 근거 없음\n\n'
    printf '아래 파일은 base 에 있어야 하는데 읽지 못했다. **regression / pre-existing 을 판정할 수 없다**\n'
    printf '(base ref 미fetch 등). 이 파일들의 issue 는 origin 을 단정하지 말고 `미지정`으로 둔다.\n%s\n' "$missing"
  fi
} > "$STAGE_DIR/base-behavior.md"

# ── 위험 판정 (auto-tier 입력) ────────────────────────────────
if [ -f "$HERE/risk_scan.py" ]; then
  python3 "$HERE/risk_scan.py" "$STAGE_DIR/diff.patch" --json > "$STAGE_DIR/risk.json" 2>/dev/null \
    || echo '{"risk":null,"note":"risk_scan 실패 — 승격 근거 없음"}' > "$STAGE_DIR/risk.json"
fi

# ── 커밋 ─────────────────────────────────────────────────────
# ⛔ 두 문제를 같이 막는다.
#   ① `cp -R` 중간 실패 → WORK_DIR 에 반쯤 찬 산출물. 값비싼 복사(TMPDIR→WORK_DIR,
#      파일시스템이 다를 수 있다)를 WORK_DIR **안**의 숨은 디렉터리로 먼저 하고,
#      실패하면 그것만 지운다. 그다음은 같은 파일시스템 rename 이라 항목별로 원자적이다.
#   ② 이전 실행의 잔여물 → 이번에 안 덮은 파일이 이번 결과처럼 보인다.
#      특히 `base/` 는 트리라서 덮어쓰기로는 옛 파일이 남는다.
#      이 스크립트가 만든 이름만 지운다 — WORK_DIR 의 다른 산출물은 건드리지 않는다.
mkdir -p "$WORK_DIR" || die 4 "WORK_DIR 생성 실패: $WORK_DIR"
INCOMING="$WORK_DIR/.gather-incoming.$$"
rm -rf "$INCOMING"
mkdir -p "$INCOMING" || die 4 "수신 디렉터리 생성 실패"
cp -R "$STAGE_DIR"/. "$INCOMING"/ || die 4 "산출물 복사 실패"

moved=0
for a in "$INCOMING"/*; do
  [ -e "$a" ] || break            # glob 미매치 — 복사가 비었다
  name="$(basename "$a")"
  rm -rf "$WORK_DIR/$name"        # 이전 실행 잔여물 제거 (이 스크립트 소유 이름만)
  mv "$a" "$WORK_DIR/$name" || die 4 "이동 실패: $name"
  moved=$((moved+1))
done
[ "$moved" -gt 0 ] || die 4 "옮길 산출물이 없다 — 수집이 비었다"

# ⛔ base 원본 **전건 실패**는 exit 0 으로 넘기지 않는다. origin(regression vs pre-existing)
#    판정 근거가 통째로 없는데 스크립트가 성공을 반환하면, 리뷰는 근거 없이 진행된다.
#    실측(#4766): 0/25 인데 exit 0 이었다. 부분 실패는 경고(base-behavior.md)로 남기고 통과시킨다 —
#    일부 신규 경로가 base 에 없는 것은 정상이기 때문이다.
if [ "$expected" -gt 0 ] && [ "$saved" -eq 0 ]; then
  echo "GATHER-FAIL(5): base 원본 0/${expected} — origin 판정 근거가 없다." >&2
  echo "  base ref '$BASE' 가 이 리포에서 해석되는지 확인하라 (PR 이면 remote 접두)." >&2
  echo "  산출물은 남긴다 — diff 는 유효하므로 origin 없이 진행할지는 호출자가 판단한다." >&2
  exit 5
fi
rmdir "$INCOMING" 2>/dev/null
rm -rf "$STAGE_DIR"

added=$(awk '{a+=$1} END{print a+0}' "$WORK_DIR/numstat.txt")
deleted=$(awk '{d+=$2} END{print d+0}' "$WORK_DIR/numstat.txt")
echo "수집 완료 — base=$BASE / +$added −$deleted / base 원본 ${saved}/${expected}개"
echo "  diff.patch · requirements.md · base-behavior.md · base/ · base-manifest.tsv · review-surface.md · review-surface.patch(중복 커밋 시) · numstat.txt · risk.json"
[ -f "$WORK_DIR/evidence-move-drift.md" ] && echo "  ⭐ evidence-move-drift.md — 이동 리팩토링 감지. 동등성과 **별개 축**이다"
grep -q '⛔ \*\*head 커밋' "$WORK_DIR/review-surface.md" 2>/dev/null && \
  echo "⚠️  중복 커밋 감지 — review-surface.md 를 먼저 읽어라. Tier 판정이 부풀려져 있다"
echo "⛔ Lead 가 채울 것: old-new-pairs · producer-consumer · caller-analysis · convention-samples · semantic-mapping (Tier 별 canonical set 참조)"
