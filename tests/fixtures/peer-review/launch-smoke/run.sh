#!/bin/bash
# launch smoke 산출기 회귀 판정 (F-366) — 재구성 diff → 실제 risk_scan → 대체 실행기 → 합성 리포트 → --check-report.
#
# F-366: Tier 1 리뷰가 루트 화면을 바꾼 PR 에 실행 단계가 없어 신규 설치 1회 실행이면 보였을 검은 화면을 놓쳤다.
#   오라클 — setRootViewController 를 바꾼 PR 이면 smoke 실행 또는 미실행 배너, 문자열만 바꾼 PR 이면 실행하지 않는다.
# 셀:
#   surface-root-swap      재구성 diff(루트 화면 교체) → risk_scan launch_surface.flag = true(coverage)
#   surface-string-only    문자열만 바꾼 diff → flag = false(verification — 오탐 0)
#   surface-entry-context  진입점 안에서 루트만 바꾼 diff(main.tsx 의 root.render · 문맥 줄 createRoot) → flag = true
#   smoke-expect-early     expect 를 찍은 뒤 64KiB 넘는 로그 → 여전히 SMOKE PASS(꼬리만 보면 FAIL)
#   malformed-rule-banner  launchSmoke 가 배열 → '⛔ 실행 미검증 — 규칙 형식 오류' · 예외 없이 exit 0
#   smoke-pass             대체 실행기 exit 0 · expect 출력 → 'SMOKE PASS' · 끝 줄 포함
#   smoke-expect-mismatch  exit 0 이지만 expect 없음 → 'SMOKE FAIL' · expect 불일치
#   smoke-timeout          끝나지 않는 실행기(손자 sleep 의 PID 를 즉시 기록) → 'SMOKE TIMEOUT' · 상한 안에 반환 · 그 PID 가 죽었다
#   head-mismatch-banner   --expect-head ≠ repo HEAD → '⛔ 실행 미검증 — HEAD 불일치' · 실행기 미실행
#   no-rule-banner         rules.json 에 launchSmoke 없음 → '⛔ 실행 미검증 — 규칙 없음' · 실행기 미실행
#   flag-false             flag false → '대상 아님' · 실행기 미실행 · --check-report 생략(exit 0)
#   report-missing         리포트에 요약 줄 없음 → --check-report exit 1
#   report-included        리포트에 요약 줄 있음 → --check-report exit 0(양성 대조)
#   tier-call-lines        modules/peer-review-tiers.md — Tier 1 Analyze 에 산출기 · Tier 1 Deliver 에 --check-report · Tier 2 절에 둘 다
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
EXPECT_CELLS="surface-root-swap surface-string-only surface-entry-context smoke-pass smoke-expect-mismatch smoke-timeout smoke-expect-early head-mismatch-banner no-rule-banner malformed-rule-banner flag-false report-missing report-included tier-call-lines"
for c in git python3; do command -v "$c" >/dev/null 2>&1 || setup_fail "$c 부재"; done
RISK="$TREE/skills/fz-peer-review/scripts/risk_scan.py"
SMOKE="$TREE/skills/fz-peer-review/scripts/launch_smoke.py"
TIERS="$TREE/modules/peer-review-tiers.md"
[ -f "$RISK" ] || setup_fail "risk_scan.py 없음: $RISK"
[ -f "$TIERS" ] || setup_fail "peer-review-tiers.md 없음"
# ⛔ launch_smoke.py 부재는 준비 실패가 아니라 셀 실패다 — 기준 트리(산출기 없음)가 1 로 끝나야 되돌림이 성립한다

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-launch-smoke.XXXXXX")" || setup_fail "임시 폴더 실패"
export GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=f GIT_AUTHOR_EMAIL=f@f.f GIT_COMMITTER_NAME=f GIT_COMMITTER_EMAIL=f@f.f
: > "$GIT_CONFIG_GLOBAL"

RAN=""
ran() { case " $RAN " in *" ${1%%:*} "*) ;; *) RAN="${RAN:+$RAN }${1%%:*}" ;; esac; }
ok() { ran "$1"; echo "PASS  $1"; }
no() { ran "$1"; echo "FAIL  $1  — $2"; fail=$((fail + 1)); }

# ── 재구성 diff (F-366 형태: 루트 화면 교체) · 대조 diff(문자열만) ──
cat > "$TMP/root-swap.diff" <<'EOF'
diff --git a/App/SceneDelegate.swift b/App/SceneDelegate.swift
--- a/App/SceneDelegate.swift
+++ b/App/SceneDelegate.swift
@@ -10,7 +10,7 @@ final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
         let window = UIWindow(windowScene: windowScene)
-        window.rootViewController = LaunchViewController()
+        window.rootViewController = HomeContainerViewController()
         window.makeKeyAndVisible()
         self.window = window
EOF
cat > "$TMP/string-only.diff" <<'EOF'
diff --git a/Feature/Home/HomeTitleView.swift b/Feature/Home/HomeTitleView.swift
--- a/Feature/Home/HomeTitleView.swift
+++ b/Feature/Home/HomeTitleView.swift
@@ -3,5 +3,5 @@ final class HomeTitleView: UIView {
     func configure() {
-        titleLabel.text = "추천 콘텐츠"
+        titleLabel.text = "오늘의 추천"
     }
EOF
flag_of() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]));ls=d.get('launch_surface');print('absent' if ls is None else str(ls.get('flag')).lower())" "$1" 2>/dev/null || echo "unreadable"; }
python3 "$RISK" "$TMP/root-swap.diff" --json > "$TMP/risk-root.json" 2>"$TMP/risk-root.err" || setup_fail "risk_scan 실행 실패(root-swap)"
python3 "$RISK" "$TMP/string-only.diff" --json > "$TMP/risk-str.json" 2>"$TMP/risk-str.err" || setup_fail "risk_scan 실행 실패(string-only)"
printf 'diff --git a/web/src/main.tsx b/web/src/main.tsx\n--- a/web/src/main.tsx\n+++ b/web/src/main.tsx\n@@ -5,3 +5,3 @@ import App from "./App"\n const root = createRoot(document.getElementById("root")!)\n-root.render(<OldApp />)\n+root.render(<NewApp />)\n' > "$TMP/entry-context.diff"
python3 "$RISK" "$TMP/entry-context.diff" --json > "$TMP/risk-ctx.json" 2>/dev/null || setup_fail "risk_scan 실행 실패(entry-context)"
f=$(flag_of "$TMP/risk-root.json")
[ "$f" = true ] && ok "surface-root-swap: 루트 화면 교체 diff → launch_surface.flag = true ($(python3 -c "import json;print(', '.join(json.load(open('$TMP/risk-root.json'))['launch_surface']['signals'][:2]))"))" \
  || no "surface-root-swap: 루트 화면 교체 diff → launch_surface.flag = true" "flag=$f"
f=$(flag_of "$TMP/risk-str.json")
[ "$f" = false ] && ok "surface-string-only: 문자열만 바꾼 diff → flag = false (오탐 0)" || no "surface-string-only: 문자열만 바꾼 diff → flag = false" "flag=$f"
f=$(flag_of "$TMP/risk-ctx.json")
[ "$f" = true ] && ok "surface-entry-context: 진입점 안 루트 교체(root.render · 문맥 createRoot) → flag = true" || no "surface-entry-context: flag = true" "flag=$f"

# ── 작업 트리 · 규칙 · 대체 실행기 ──
REPO="$TMP/repo"
{ git init -q "$REPO" && printf 'x\n' > "$REPO/a" && git -C "$REPO" add a && git -C "$REPO" -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -qm init; } || setup_fail "작업 트리 준비 실패"
HEADSHA=$(git -C "$REPO" rev-parse HEAD)
python3 - "$TMP" <<'PY' || setup_fail "risk · rules 준비 실패"
import json, sys
t = sys.argv[1]
json.dump({"launch_surface": {"flag": True, "signals": ["token:rootViewController = (App/SceneDelegate.swift)"]}, "risk": 0}, open(t + "/risk-on.json", "w"))
json.dump({"launch_surface": {"flag": False, "signals": []}, "risk": 0}, open(t + "/risk-off.json", "w"))
axes = ["architecturePattern", "uiStack", "dependencyDirection", "naming", "placement", "conventions"]
def rules(cmd, exp="LAUNCH-OK", tmo=20):
    return {"schemaVersion": 1, "axes": {a: None for a in axes}, "rules": [], "conflicts": [], "gaps": axes,
            "launchSmoke": {"command": cmd, "expect": exp, "timeout_s": tmo}}
json.dump(rules("printf 'boot\\nLAUNCH-OK\\n'; touch ran.flag"), open(t + "/rules-pass.json", "w"))
json.dump(rules("printf 'boot\\nblack screen\\n'; touch ran.flag"), open(t + "/rules-mismatch.json", "w"))
json.dump(rules("touch ran.flag; sleep 60 & echo $! > gc.pid; wait", tmo=2), open(t + "/rules-hang.json", "w"))
r = rules("x"); del r["launchSmoke"]; json.dump(r, open(t + "/rules-none.json", "w"))
r = rules("x"); r["launchSmoke"] = []; json.dump(r, open(t + "/rules-bad.json", "w"))
json.dump(rules("printf 'LAUNCH-OK\\n'; head -c 200000 /dev/zero | tr '\\0' 'x'; printf '\\nbye\\n'"), open(t + "/rules-early.json", "w"))
PY
# $1=셀 $2=risk $3=rules $4=expect-head — 산출기를 부르고 요약 줄(첫 줄)을 SUM 에 담는다
smoke() {
  rm -f "$REPO/ran.flag" "$REPO/gc.pid" "$TMP/$1.md"
  if [ ! -f "$SMOKE" ]; then RC=127 SUM="(launch_smoke.py 없음)"; return; fi
  local t0=$SECONDS
  python3 "$SMOKE" --risk "$2" --rule "$3" --repo "$REPO" --expect-head "$4" --out "$TMP/$1.md" > "$TMP/$1.out" 2>&1; RC=$?
  EL=$((SECONDS - t0))
  SUM=$(head -1 "$TMP/$1.md" 2>/dev/null)
}
ran_flag() { [ -e "$REPO/ran.flag" ] && echo 실행됨 || echo 미실행; }

smoke smoke-pass "$TMP/risk-on.json" "$TMP/rules-pass.json" "$HEADSHA"
case "$RC:$SUM" in
  "0:launch smoke — SMOKE PASS · exit 0 · expect 일치 · HEAD ${HEADSHA:0:7}") grep -q '^LAUNCH-OK$' "$TMP/smoke-pass.md" && ok "smoke-pass: SMOKE PASS · expect 일치 · 끝 줄 포함" || no "smoke-pass: 끝 줄 포함" "출력 꼬리에 LAUNCH-OK 없음" ;;
  *) no "smoke-pass: SMOKE PASS" "rc=$RC · ${SUM:-요약 없음}" ;;
esac
smoke smoke-expect-mismatch "$TMP/risk-on.json" "$TMP/rules-mismatch.json" "$HEADSHA"
case "$RC:$SUM" in
  "0:launch smoke — SMOKE FAIL · exit 0 · expect 불일치"*) ok "smoke-expect-mismatch: exit 0 이어도 expect 없으면 SMOKE FAIL" ;;
  *) no "smoke-expect-mismatch: SMOKE FAIL" "rc=$RC · ${SUM:-요약 없음}" ;;
esac
smoke smoke-timeout "$TMP/risk-on.json" "$TMP/rules-hang.json" "$HEADSHA"
GC=$(cat "$REPO/gc.pid" 2>/dev/null)   # 실행기가 시작하자마자 적은 손자(sleep 60) PID
gc_alive() { [ -n "$GC" ] && kill -0 "$GC" 2>/dev/null; }
case "$RC:$SUM" in
  "0:launch smoke — SMOKE TIMEOUT"*)
    if [ "${EL:-99}" -le 10 ] && [ -n "$GC" ] && ! gc_alive; then ok "smoke-timeout: 상한 2초 → SMOKE TIMEOUT · ${EL}초 안에 반환 · 손자 PID $GC 종료"
    else no "smoke-timeout: 상한 안 반환 · 손자 종료" "경과 ${EL}초 · 손자 PID ${GC:-기록 없음} $(gc_alive && echo 살아 있음 || echo 종료)"; fi ;;
  *) no "smoke-timeout: SMOKE TIMEOUT" "rc=$RC · ${SUM:-요약 없음}" ;;
esac
gc_alive && kill "$GC" 2>/dev/null   # 실패한 구현이 남긴 손자 정리
smoke smoke-expect-early "$TMP/risk-on.json" "$TMP/rules-early.json" "$HEADSHA"
case "$RC:$SUM" in
  "0:launch smoke — SMOKE PASS"*) ok "smoke-expect-early: expect 뒤 200KB 로그 → SMOKE PASS(전체 로그에서 찾는다)" ;;
  *) no "smoke-expect-early: SMOKE PASS" "rc=$RC · ${SUM:-요약 없음}" ;;
esac
smoke malformed-rule-banner "$TMP/risk-on.json" "$TMP/rules-bad.json" "$HEADSHA"
case "$RC:$SUM" in
  "0:launch smoke — ⛔ 실행 미검증 — 규칙 형식 오류"*) [ "$(ran_flag)" = 미실행 ] && ok "malformed-rule-banner: launchSmoke 배열 → 형식 오류 배너 · 실행기 미실행" || no "malformed-rule-banner: 실행기 미실행" "실행했다" ;;
  *) no "malformed-rule-banner: 형식 오류 배너" "rc=$RC · ${SUM:-요약 없음} · $(tail -1 "$TMP/malformed-rule-banner.out" 2>/dev/null | cut -c1-80)" ;;
esac
smoke head-mismatch-banner "$TMP/risk-on.json" "$TMP/rules-pass.json" "0000000000000000000000000000000000000000"
case "$RC:$SUM" in
  "0:launch smoke — ⛔ 실행 미검증 — HEAD 불일치"*) [ "$(ran_flag)" = 미실행 ] && ok "head-mismatch-banner: HEAD 불일치 배너 · 실행기 미실행" || no "head-mismatch-banner: 실행기 미실행" "다른 리비전에서 실행했다" ;;
  *) no "head-mismatch-banner: HEAD 불일치 배너" "rc=$RC · ${SUM:-요약 없음}" ;;
esac
smoke no-rule-banner "$TMP/risk-on.json" "$TMP/rules-none.json" "$HEADSHA"
case "$RC:$SUM" in
  "0:launch smoke — ⛔ 실행 미검증 — 규칙 없음"*) [ "$(ran_flag)" = 미실행 ] && ok "no-rule-banner: 규칙 없음 배너 · 실행기 미실행" || no "no-rule-banner: 실행기 미실행" "규칙 없이 실행했다" ;;
  *) no "no-rule-banner: 규칙 없음 배너" "rc=$RC · ${SUM:-요약 없음}" ;;
esac
smoke flag-false "$TMP/risk-off.json" "$TMP/rules-pass.json" "$HEADSHA"
if [ "$RC" -eq 0 ] && [ "$SUM" = "launch smoke — 대상 아님(launch_surface 없음)" ] && [ "$(ran_flag)" = 미실행 ] \
   && python3 "$SMOKE" --check-report "$TMP/none.md" --smoke "$TMP/flag-false.md" >/dev/null 2>&1; then
  ok "flag-false: 대상 아님 · 실행기 미실행 · --check-report 생략(exit 0)"
else
  no "flag-false: 대상 아님 · 실행기 미실행" "rc=$RC · ${SUM:-요약 없음} · $(ran_flag)"
fi

# ── 리포트 포함 검사 — smoke-pass 산출물로 ──
printf '# 리뷰 리포트\n\n## 요약\n문제 없음\n' > "$TMP/report-without.md"
{ printf '# 리뷰 리포트\n\n'; head -1 "$TMP/smoke-pass.md" 2>/dev/null; printf '\n## 요약\n문제 없음\n'; } > "$TMP/report-with.md"
if [ -f "$SMOKE" ]; then
  python3 "$SMOKE" --check-report "$TMP/report-without.md" --smoke "$TMP/smoke-pass.md" > "$TMP/cr1.out" 2>&1; r1=$?
  python3 "$SMOKE" --check-report "$TMP/report-with.md" --smoke "$TMP/smoke-pass.md" > "$TMP/cr2.out" 2>&1; r2=$?
else r1=127 r2=127; fi
[ "$r1" -eq 1 ] && ok "report-missing: 요약 줄 없는 리포트 → --check-report exit 1" || no "report-missing: exit 1" "exit $r1"
[ "$r2" -eq 0 ] && ok "report-included: 요약 줄 있는 리포트 → exit 0" || no "report-included: exit 0" "exit $r2 · $(head -1 "$TMP/cr2.out" 2>/dev/null)"

# ── 절차 호출 줄 — Tier 1 · Tier 2 절에 산출기, Deliver 에 --check-report ──
# 절 = 제목 줄부터 다음 `## ` 제목 전까지. ⛔ 코드 펜스 안의 `## …`(Deliver 의 집계 표 견본)는 제목이 아니다
sec() { awk -v a="$1" -v b="$2" '/^```/{fence=!fence} index($0,a)==1{f=1} f&&!fence&&index($0,b)==1&&!index($0,a){exit} f' "$TIERS"; }
t1=$(sec "## Tier 1 (Solo + GPT) 절차" "## ")
t2=$(sec "## Tier 2: Lite" "## ")
sub() { printf '%s\n' "$1" | awk -v a="$2" 'index($0,a)==1{f=1;next} f&&/^### /{exit} f'; }   # 절 안의 하위 절(### …) 본문
a1=$(sub "$t1" "### Analyze" | grep -c 'launch_smoke.py" --risk')
d1=$(sub "$t1" "### Deliver" | grep -c 'launch_smoke.py" --check-report')
a2=$(printf '%s\n' "$t2" | grep -c 'launch_smoke.py" --risk')
d2=$(printf '%s\n' "$t2" | grep -c 'launch_smoke.py" --check-report')
if [ "$a1" -ge 1 ] && [ "$d1" -ge 1 ] && [ "$a2" -ge 1 ] && [ "$d2" -ge 1 ]; then ok "tier-call-lines: Tier 1 Analyze 산출기 $a1 · Deliver --check-report $d1 · Tier 2 산출기 $a2 · --check-report $d2"
else no "tier-call-lines: Tier 1 · 2 절차 호출 줄" "Tier 1 Analyze $a1 · Deliver $d1 · Tier 2 산출기 $a2 · --check-report $d2 (Tier 1 절 $(printf '%s\n' "$t1" | grep -c .)줄)"; fi

want=$(printf '%s\n' $EXPECT_CELLS | LC_ALL=C sort -u); got=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want" = "$got" ]; then echo "PASS  셀 집합: 판정한 셀 = 기대 셀 ($(printf '%s\n' "$want" | grep -c .)개)"
else echo "FAIL  셀 집합  — 빠짐 [$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | tr '\n' ' ')]"; fail=$((fail + 1)); fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "LAUNCH_SMOKE_OK ran=$(printf '%s\n' $RAN | grep -c .)"
