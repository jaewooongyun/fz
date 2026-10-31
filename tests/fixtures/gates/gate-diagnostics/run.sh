#!/bin/bash
# 판정기 · Stop 훅 진단 문구 회귀 판정 (F-393 · F-202) — 거부 · 차단은 그대로 두고 **사유와 안내**가 사실과 맞는지 본다.
#
# F-393: verify-gates 응답이 큰따옴표 든 게이트 제목을 옮기며 역슬래시를 더하자 --verdict-check 가 'stale 응답' 으로 거부했다 —
#   거부는 맞지만 사유가 틀려 원인(옮겨 적기 이스케이프)을 가렸다.
# F-202: MANUAL 게이트가 미충족이면 Stop 훅은 '충족 or ABANDON' 만 안내했다 — 사용자 확인(--confirm · TTY)이 유일한 출구인
#   게이트에서 에이전트를 EVIDENCE 직접 기록이나 거짓 포기로 이끈다(2026-11-01 이 판 진행 중 재관측).
# 셀:
#   verdict-escape-label   응답 제목이 따옴표 앞에 역슬래시만 더했다 → exit 1 · '이스케이프 차이' · 'stale' 없음
#   verdict-stale-label    응답 제목이 실제로 다르다 → exit 1 · 'stale 응답'(대조 — 두 트리 모두)
#   hook-manual-hint       미충족 MANUAL 게이트 원장 → 차단(exit 2) · 사유에 '--confirm' 안내가 ABANDON 안내보다 먼저
#   hook-command-no-hint   미충족 command 게이트만 → 차단 · '--confirm' 안내 없음(대조 — 두 트리 모두)
#   hook-manual-hint-truncated  미충족 9개(command 8 + 마지막 MANUAL) — 요약 id 는 8개에서 잘린다 → 그래도 M9 안내(GPT check)
#   hook-manual-hint-many-ledgers  MANUAL 대기 원장 4개 → 안내 줄에 넷 다(앞 3개로 조용히 자르면 넷째 원장의 대기가 사라진다 — 실측)
#   hook-manual-hint-budget  MANUAL 대기 원장 8개 × 60자 id 8개 → 목록은 생략 수를 남기고, 안내 문장(--confirm · ABANDON 금지)과
#                            판정 명령 줄이 사유에 남는다(목록이 사유 예산을 먹어 꼬리가 잘리면 안 된다 — GPT check)
# 끝 — 판정한 셀 집합 = 기대 셀 집합(F-408)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
# usage: run.sh [--tree <플러그인 트리>]
set -u

DONE=0 fail=0 TMP=""
finish() {
  local rc=$?
  [ -n "$TMP" ] && rm -rf "${TMP:?}"
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ] && [ "$DONE" -ne 1 ]; then echo "SETUP 판정 줄 없이 끝났다(exit $rc)"; exit 3; fi
  exit "$rc"
}
trap finish EXIT
setup_fail() { echo "SETUP $*"; exit 3; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || setup_fail "fixture 경로 해석 실패"
TREE="$(cd "$HERE/../../../.." && pwd)" || setup_fail "기본 트리 해석 실패"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || setup_fail "--tree 에 경로가 없다"; TREE="$(cd "$2" 2>/dev/null && pwd)" || setup_fail "--tree 경로 없음: $2"; shift 2 ;;
    *) setup_fail "알 수 없는 인자: $1" ;;
  esac
done
EXPECT_CELLS="verdict-escape-label verdict-stale-label hook-manual-hint hook-command-no-hint hook-manual-hint-truncated hook-manual-hint-many-ledgers hook-manual-hint-budget"
G="$TREE/scripts/gate_check.py" H="$TREE/scripts/gate_stop_hook.py"
[ -f "$G" ] && [ -f "$H" ] || setup_fail "gate_check.py · gate_stop_hook.py 없음: $TREE"
command -v python3 >/dev/null 2>&1 || setup_fail "python3 부재"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-gate-diag.XXXXXX")" || setup_fail "임시 폴더 실패"
for v in FZ_GATES_LEDGER FZ_GATES_OFF FZ_GATES_TRACE FZ_GATES_HOOK_BUDGET_S; do unset "$v"; done

# $1=폴더 $2=steps JSON — 원장을 만들고 확정 · 착수한다(planned → active)
mkledger() {
  mkdir -p "$1" && printf '%s' "$2" > "$1/steps.json" \
    && python3 "$G" --from-plan "$1/steps.json" --root "$1" --out "$1/gates/plan.md" >/dev/null 2>&1 \
    && python3 "$G" --finalize "$1/gates/plan.md" >/dev/null 2>&1 \
    && python3 "$G" --set-state planned "$1/gates/plan.md" >/dev/null 2>&1 \
    && python3 "$G" --set-state active "$1/gates/plan.md" >/dev/null 2>&1 || setup_fail "원장 준비 실패: $1"
}
# $1=원장 — 그 원장만 판정하는 Stop 훅 1회 → 차단 사유를 R_TXT 에 · 종료 코드를 HRC 에(⛔ 명령 치환으로 부르지 않는다 — HRC 가 서브셸에 갇힌다)
hookreason() {
  mkdir -p "$TMP/home" && : > "$TMP/t.jsonl" || setup_fail "훅 입력 준비 실패"
  local out
  out=$(printf '{"hook_event_name":"Stop","cwd":"%s","session_id":"diag-%s","transcript_path":"%s"}' "$(dirname "$(dirname "$1")")" "$RANDOM" "$TMP/t.jsonl" \
        | HOME="$TMP/home" FZ_GATES_LEDGER="$1" python3 -B "$H" 2>&1); HRC=$?
  R_TXT=$(printf '%s\n' "$out" | python3 -c 'import json,sys
for l in sys.stdin:
    if l.startswith("{\"decision\""): print(json.loads(l)["reason"])')
}

RAN=""
ran() { case " $RAN " in *" ${1%%:*} "*) ;; *) RAN="${RAN:+$RAN }${1%%:*}" ;; esac; }
ok() { ran "$1"; echo "PASS  $1"; }
no() { ran "$1"; echo "FAIL  $1  — $2"; fail=$((fail + 1)); }

# ── verdict-check 사유 ──
mkledger "$TMP/v" '{"title":"diag","steps":[{"id":"G1","title":"`rg \"auth\" src` 가 0건이면 멈춘다","verify":{"kind":"command","criterion":"c","command":"echo G1_OK","expect":"G1_OK"}}]}'
vjson() {   # $1=응답 제목 → 응답 JSON 파일 경로
  python3 - "$TMP/resp-$2.json" "$1" <<'PY'
import json, sys
json.dump({"gates": [{"id": "G1", "title": sys.argv[2], "kind": "command", "verdict": "accept", "measurement_fit": "fit",
                      "noninteractive": True, "rerunnable": True, "determinism": "deterministic", "side_effects": "none",
                      "reason": "r", "suggestion": None}],
           "summary": {"total": 1, "accept": 1, "revise": 0, "demote_to_manual": 0}}, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
PY
}
vjson '`rg \"auth\" src` 가 0건이면 멈춘다' esc || setup_fail "응답 준비 실패"
o=$(python3 "$G" --verdict-check "$TMP/resp-esc.json" "$TMP/v/gates/plan.md" 2>&1); rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$o" | grep -q '이스케이프 차이' && ! printf '%s' "$o" | grep -q 'stale 응답'; then ok "verdict-escape-label: 역슬래시만 더한 제목 → exit 1 · '이스케이프 차이' · stale 아님"
else no "verdict-escape-label: 이스케이프 차이 사유" "exit $rc · $(printf '%s' "$o" | grep -m1 'G1' | cut -c1-120)"; fi
vjson '다른 제목이다' stale || setup_fail "응답 준비 실패"
o=$(python3 "$G" --verdict-check "$TMP/resp-stale.json" "$TMP/v/gates/plan.md" 2>&1); rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$o" | grep -q 'stale 응답'; then ok "verdict-stale-label: 실제로 다른 제목 → exit 1 · 'stale 응답'"
else no "verdict-stale-label: stale 응답" "exit $rc · $(printf '%s' "$o" | grep -m1 'G1' | cut -c1-120)"; fi

# ── Stop 훅 안내 ──
mkledger "$TMP/m" '{"title":"diag","steps":[{"id":"M1","title":"사람이 확인한다","verify":{"kind":"manual","criterion":"사람이 확인한다"}}]}'
hookreason "$TMP/m/gates/plan.md"; r=$R_TXT
ci=$(printf '%s\n' "$r" | grep -n -- '--confirm' | head -1 | cut -d: -f1); ai=$(printf '%s\n' "$r" | grep -n 'ABANDON:' | head -1 | cut -d: -f1)
if [ "$HRC" -eq 2 ] && [ -n "$ci" ] && [ -n "$ai" ] && [ "$ci" -lt "$ai" ] && printf '%s' "$r" | grep -q 'M1'; then ok "hook-manual-hint: 미충족 MANUAL M1 → 차단 · --confirm 안내가 ABANDON 안내보다 먼저"
else no "hook-manual-hint: --confirm 안내" "exit $HRC · confirm 줄 ${ci:-없음} · ABANDON 줄 ${ai:-없음}"; fi
mkledger "$TMP/c" '{"title":"diag","steps":[{"id":"C1","title":"명령이 실패한다","verify":{"kind":"command","criterion":"c","command":"false","expect":"NEVER"}}]}'
python3 "$G" --only C1 "$TMP/c/gates/plan.md" >/dev/null 2>&1
hookreason "$TMP/c/gates/plan.md"; r=$R_TXT
if [ "$HRC" -eq 2 ] && ! printf '%s' "$r" | grep -q -- '--confirm'; then ok "hook-command-no-hint: command 게이트만 미충족 → 차단 · --confirm 안내 없음"
else no "hook-command-no-hint: 안내 없음" "exit $HRC · $(printf '%s' "$r" | grep -m1 -- '--confirm' | cut -c1-100)"; fi

steps9=$(python3 -c 'import json
s=[{"id":"C%d"%i,"title":"명령 %d"%i,"verify":{"kind":"command","criterion":"c","command":"false","expect":"NEVER"}} for i in range(1,9)]
s.append({"id":"M9","title":"사람이 확인한다","verify":{"kind":"manual","criterion":"사람이 확인한다"}})
print(json.dumps({"title":"diag","steps":s}))')
mkledger "$TMP/t9" "$steps9"
hookreason "$TMP/t9/gates/plan.md"; r=$R_TXT
if [ "$HRC" -eq 2 ] && printf '%s' "$r" | grep -q -- '--confirm' && printf '%s' "$r" | grep -q 'MANUAL 게이트 M9'; then ok "hook-manual-hint-truncated: 미충족 9개 중 마지막 MANUAL M9 → 요약이 잘려도 --confirm 안내"
else no "hook-manual-hint-truncated: M9 안내" "exit $HRC · $(printf '%s' "$r" | grep -m1 'UNMET' | cut -c1-140)"; fi

for k in 1 2 3 4; do mkledger "$TMP/q$k" "{\"title\":\"diag\",\"steps\":[{\"id\":\"Q$k\",\"title\":\"사람이 확인한다\",\"verify\":{\"kind\":\"manual\",\"criterion\":\"사람이 확인한다\"}}]}"; done
out=$(printf '{"hook_event_name":"Stop","cwd":"%s","session_id":"diag-many","transcript_path":"%s"}' "$TMP" "$TMP/t.jsonl" \
      | HOME="$TMP/home" FZ_GATES_LEDGER="$TMP/q1/gates/plan.md:$TMP/q2/gates/plan.md:$TMP/q3/gates/plan.md:$TMP/q4/gates/plan.md" python3 -B "$H" 2>&1); HRC=$?
r=$(printf '%s\n' "$out" | python3 -c 'import json,sys
for l in sys.stdin:
    if l.startswith("{\"decision\""): print(json.loads(l)["reason"])')
hint=$(printf '%s\n' "$r" | grep -- '--confirm' | head -1)
miss=""; for k in 1 2 3 4; do printf '%s' "$hint" | grep -q "Q$k" || miss="$miss Q$k"; done
if [ "$HRC" -eq 2 ] && [ -n "$hint" ] && [ -z "$miss" ]; then ok "hook-manual-hint-many-ledgers: MANUAL 대기 원장 4개 → 안내 줄에 Q1~Q4 모두"
else no "hook-manual-hint-many-ledgers: 넷 다 안내" "exit $HRC · 빠짐:${miss:- 없음} · $(printf '%s' "$hint" | cut -c1-120)"; fi

LEDS=""
for k in 1 2 3 4 5 6 7 8; do
  st=$(python3 -c 'import json,sys
k=sys.argv[1]
print(json.dumps({"title":"diag","steps":[{"id":("L%s_G%d_" % (k, j)).ljust(60, "x"),"title":"사람이 확인한다","verify":{"kind":"manual","criterion":"사람이 확인한다"}} for j in range(1,9)]}))' "$k")
  mkledger "$TMP/b$k" "$st"; LEDS="${LEDS:+$LEDS:}$TMP/b$k/gates/plan.md"
done
out=$(printf '{"hook_event_name":"Stop","cwd":"%s","session_id":"diag-budget","transcript_path":"%s"}' "$TMP" "$TMP/t.jsonl" \
      | HOME="$TMP/home" FZ_GATES_LEDGER="$LEDS" python3 -B "$H" 2>&1); HRC=$?
r=$(printf '%s\n' "$out" | python3 -c 'import json,sys
for l in sys.stdin:
    if l.startswith("{\"decision\""): print(json.loads(l)["reason"])')
if [ "$HRC" -eq 2 ] && printf '%s' "$r" | grep -q -- '--confirm <게이트ID> <원장>' && printf '%s' "$r" | grep -q 'ABANDON 하지도 않는다' \
   && printf '%s' "$r" | grep -q '^판정: ' && printf '%s' "$r" | grep -q '…외 [0-9]*개 원장'; then
  ok "hook-manual-hint-budget: 원장 8 × 긴 id 8 → 생략 수 · --confirm 안내 · 판정 줄이 남는다 (사유 $(printf '%s' "$r" | wc -c | tr -d ' ')B)"
else no "hook-manual-hint-budget: 안내 · 판정 줄 보존" "exit $HRC · confirm $(printf '%s' "$r" | grep -c -- '--confirm') · 판정 $(printf '%s' "$r" | grep -c '^판정: ') · 생략 $(printf '%s' "$r" | grep -c '외 [0-9]*개 원장')"; fi

want=$(printf '%s\n' $EXPECT_CELLS | LC_ALL=C sort -u); got=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want" = "$got" ]; then echo "PASS  셀 집합: 판정한 셀 = 기대 셀 ($(printf '%s\n' "$want" | grep -c .)개)"
else echo "FAIL  셀 집합  — 빠짐 [$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | tr '\n' ' ')]"; fail=$((fail + 1)); fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "GATE_DIAGNOSTICS_OK ran=$(printf '%s\n' $RAN | grep -c .)"
