#!/usr/bin/env bash
#
# scripts/lint-model-explicit.sh
# fz-plugin workflows 모델 배선 lint (deterministic — H1 원칙)
#
# 목적 (experiment-log §5.8 ⑤ 측정 지원 · Anti-Pattern Constraint 감시):
#   ① 전 workflow(workflows/*.js)의 agent 호출 opts 에 model: 명시 강제
#      → AC-6 (model 생략 전환 금지 — 생략 시 agent 정의 기본 model 로 강등)
#   ①-b 전 workflow 의 agent 호출 opts 에 effort: 명시 강제 (표준 effort=xhigh)
#      → agent() 는 model+effort 모두 명시 의무 (skill-authoring §12) — effort 생략 시 세션 값이 아니라 워커 모델 기본으로 돈다 (Opus 5.5 = medium, 2026-09-25 실측)
#   ② repo 전체 model: 'fable' 총계 == EXPECTED_FABLE 고정
#      기대 분포: search-cross-verify.js ×1 + plan-collaborative.js ×2 = 3
#      → AC-1 ("fable 지정은 정확히 3곳") 양방향 강제: 무단 확산(>3) · 무단 제거(<3) 모두 차단
#      ⚠️ AC-5(C안 확산 금지: plan integrate·recheck / discover merge·landscape / review arch)는
#         *부분* 커버만 됨 — 이 검사는 총계 기반이라, 총계가 그대로 유지되는 swap(예: review-arch
#         호출에 fable 추가 + 기존 3곳 중 1곳을 다른 model 로 동시 변경 → 총계 3 유지)은 미탐.
#         단일 편집(총계 2/4 로 변화)은 정상 포착. same-total swap 은 AC-1 생산 스테이지 규칙 +
#         코드리뷰가 backstop (완전 자동 차단은 label-set 검사 필요).
#      ⛔ fable 지정 지점을 의도적으로 늘리거나 줄이면 아래 EXPECTED_FABLE 값도 함께 갱신할 것
#   ③ CLAUDE_CODE_SUBAGENT_MODEL 환경변수 설정 시 경고 (exit 0 유지 — 경고만)
#      → AC-2 (전면 override 금지 — workflow 의 model explicit 지정과 충돌 소지)
#
# 검사 원리: agent 호출 opts 리터럴은 전부 single-line 이며 'agentType:' 를 고유 마커로
#   갖는다 (주석의 destructuring {..model, agentType} 는 콜론이 없어 자동 제외). 따라서
#   'agentType:' 를 포함한 라인은 'model:' · 'effort:' 도 같은 라인에 포함해야 한다.
#
# exit: 0=PASS / 1=lint 위반(model/effort 누락 또는 fable≠기대) / 2=설정 오류(대상 미탐)

set -euo pipefail

# ── 대상 workflows 디렉토리: 인자 우선, 없으면 스크립트 위치 기준(scripts/의 부모/workflows) ──
#    (git rev-parse 대신 스크립트 상대 경로 — 임시 사본 디렉토리(비-git repo 포함)에서도 동작)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ⛔ `--baseline FILE` 은 위치 인자가 아니다 — workflows 디렉토리로 해석되지 않게 **먼저** 벗긴다.
BASELINE=""
if [ "${1:-}" = "--baseline" ]; then
  BASELINE="${2:-}"
  [ -n "$BASELINE" ] || { echo "❌ --baseline 은 값이 필요하다" >&2; exit 2; }
  shift 2
fi

WORKFLOWS_DIR="${1:-$(dirname "$SCRIPT_DIR")/workflows}"

if [ ! -d "$WORKFLOWS_DIR" ]; then
  echo "❌ lint-model-explicit: workflows 디렉토리 없음: $WORKFLOWS_DIR" >&2
  exit 2
fi

EXPECTED_FABLE=3

# ── ①-c label 별 model/effort baseline 대조 (--baseline FILE) ──
#   ⛔ 왜 필요한가: ①·①-b 는 "그 줄에 model·effort 키가 있는가" 만 본다. 콜마다 **값**을 바꾸고
#      다른 줄에 같은 문자열을 추가하면 총계·존재 검사를 모두 통과한다(GPT verify #12).
#      baseline 은 `파일::label → {model, effort}` 매핑을 고정해 그 경로를 막는다.
#   값 변경이 정당한 경우(sweep/ablation 통과)엔 baseline 파일도 함께 갱신한다 — 근거는 experiment-log.
if [ -n "$BASELINE" ]; then
  [ -f "$BASELINE" ] || { echo "❌ --baseline 파일이 없다: $BASELINE" >&2; exit 2; }
  python3 - "$BASELINE" "$WORKFLOWS_DIR" <<'PY'
import json, re, sys, glob, os
baseline_path, wf_dir = sys.argv[1], sys.argv[2]
with open(baseline_path, encoding="utf-8") as fh:
    want = json.load(fh).get("calls") or {}
got = {}
for f in sorted(glob.glob(os.path.join(wf_dir, "*.js"))):
    for i, line in enumerate(open(f, encoding="utf-8"), 1):
        if "label:" not in line or "agentType:" not in line:
            continue
        lab = re.search(r"label:\s*'([^']+)'", line) or re.search(r"label:\s*`([^`]+)`", line)
        mod = re.search(r"model:\s*'([^']+)'", line)
        eff = re.search(r"effort:\s*'([^']+)'", line)
        key = f"{os.path.basename(f)}::{lab.group(1) if lab else f'line{i}'}"
        got[key] = {"model": mod.group(1) if mod else None, "effort": eff.group(1) if eff else None}
if not got:
    print("❌ lint --baseline: agent 호출을 찾지 못했다 (측정 실패)", file=sys.stderr); sys.exit(2)
diffs = []
for k in sorted(set(want) | set(got)):
    w, g = want.get(k), got.get(k)
    if w is None:
        diffs.append(f"추가된 호출: {k} = {g}")
    elif g is None:
        diffs.append(f"사라진 호출: {k} (baseline {w})")
    elif w != g:
        diffs.append(f"값 변경: {k} baseline {w} → 현재 {g}")
for d in diffs:
    print(f"❌ {d}", file=sys.stderr)
if diffs:
    print(f"lint --baseline: {len(diffs)}건 불일치 / 호출 {len(got)}개", file=sys.stderr); sys.exit(1)
print(f"✅ lint --baseline: {len(got)} 호출 전건 일치 (label 별 model·effort)")
PY
  exit $?
fi


# ── ① model 명시 검사: agentType: 마커 라인은 model: 도 포함해야 함 ──
#    (grep -nH: 대상 .js 가 1개뿐인 $1 디렉토리에서도 'file:line:' 접두 보장 — file/line 파싱 안정)
missing=0
checked=0
while IFS= read -r hit; do
  checked=$((checked + 1))
  if ! printf '%s\n' "$hit" | grep -Eq 'model[[:space:]]*:'; then
    file="${hit%%:*}"
    rest="${hit#*:}"
    lineno="${rest%%:*}"
    echo "❌ model 누락: ${file}:${lineno}" >&2
    missing=$((missing + 1))
  fi
done < <(grep -nHE 'agentType[[:space:]]*:' "$WORKFLOWS_DIR"/*.js)

if [ "$checked" -eq 0 ]; then
  echo "❌ lint-model-explicit: agent 호출(마커 agentType:)을 찾지 못함 — 대상 경로/포맷 확인: $WORKFLOWS_DIR" >&2
  exit 2
fi

# ── ①-b effort 명시 검사: agentType: 마커 라인은 effort: 도 포함해야 함 (① 동형) ──
missing_effort=0
while IFS= read -r hit; do
  if ! printf '%s\n' "$hit" | grep -Eq 'effort[[:space:]]*:'; then
    file="${hit%%:*}"
    rest="${hit#*:}"
    lineno="${rest%%:*}"
    echo "❌ effort 누락: ${file}:${lineno}" >&2
    missing_effort=$((missing_effort + 1))
  fi
done < <(grep -nHE 'agentType[[:space:]]*:' "$WORKFLOWS_DIR"/*.js)

# ── ② fable 지정 수 고정 검사 (grep no-match 시 pipefail 회피용 || true) ──
fable_count=$(grep -hoE "model[[:space:]]*:[[:space:]]*'fable'" "$WORKFLOWS_DIR"/*.js | wc -l | tr -d ' ') || true

# ── ③ 환경변수 일괄 override 경고 (AC-2 — exit 0 유지, 경고만) ──
if [ -n "${CLAUDE_CODE_SUBAGENT_MODEL:-}" ]; then
  echo "⚠️  경고: CLAUDE_CODE_SUBAGENT_MODEL='${CLAUDE_CODE_SUBAGENT_MODEL}' 설정됨 — AC-2 (전면 override 금지). workflow 의 model explicit 지정을 무력화할 수 있음."
fi

# ── 판정 ──
fail=0
if [ "$missing" -gt 0 ]; then
  echo "❌ lint-model-explicit: model 누락 ${missing}건 (AC-6 위반)" >&2
  fail=1
fi
if [ "$missing_effort" -gt 0 ]; then
  echo "❌ lint-model-explicit: effort 누락 ${missing_effort}건 (①-b 위반 — agent() 는 model+effort 모두 명시)" >&2
  fail=1
fi
if [ "$fable_count" -ne "$EXPECTED_FABLE" ]; then
  echo "❌ lint-model-explicit: fable 지정 수 ${fable_count} ≠ 기대 ${EXPECTED_FABLE} (AC-1 '정확히 3곳' 위반: >3 확산 / <3 제거) — 의도적 변경이면 EXPECTED_FABLE 갱신 필요. 현재 위치:" >&2
  grep -nHE "model[[:space:]]*:[[:space:]]*'fable'" "$WORKFLOWS_DIR"/*.js >&2 || true
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "lint-model-explicit: PASS (${checked} calls checked, fable=${fable_count})"
