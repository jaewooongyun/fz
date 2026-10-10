#!/bin/bash
# 질문형 impact 요청 fixture (F-386) — plan_resolve_impact_requests.py 가 예/아니오 · 분포를 묻는 요청을
# 단어 census 1건 성공만으로 RESOLVED 로 세지 않는지 실행으로 본다.
#   [Q] requests.json 의 질문형 요청 → `UNRESOLVED` · 사유에 '질문 미답' · census 줄은 그대로 붙는다
#   [S] 위치 · 호출자 수 요청(대조) → `RESOLVED`
#   repo/ 는 오프라인 census 대상이다. positive control 'func ' 를 이 러너가 먼저 직접 센다 —
#   0 이면 census 가 죽은 것이라 판정하지 않는다(준비 실패).
# 기준 트리(질문형 판별 없음)는 [Q] 를 RESOLVED 로 인쇄해 exit 1.
# ⛔ 셀 집합 대조(F-408): requests.json 의 요청 id 가 `EXPECTED_IDS`(Q1 · Q2 · Q3 · S1 · S2 — 순서까지)와 다르면 FAIL —
#    질문형 꼴(Q1 ' — ' 뒤 문맥 · Q3 분포+물음표)을 지워도 통과하지 않게. 끝 줄 `CELLS n=<수> ran=<…>`.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · fixture 파일 · positive control)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 이 결함 재현 없이 통과한다 — 그래서 3 이다.
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
F="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$F/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
S="$R/scripts/plan_resolve_impact_requests.py"
[ -f "$S" ] || { echo "SETUP 대상 스크립트 없음: $S"; exit 3; }
[ -s "$F/requests.json" ] && [ -d "$F/repo" ] || { echo "SETUP fixture 입력 없음: $F/requests.json · $F/repo"; exit 3; }
CTRL=$(/usr/bin/grep -rIF -- 'func ' "$F/repo" | wc -l | tr -d ' ')
[ "${CTRL:-0}" -ge 1 ] || { echo "SETUP positive control 'func ' 0건 — census 대상이 비었다(판정 불가)"; exit 3; }

OUT=$(cd "${TMPDIR:-/tmp}" && PYTHONDONTWRITEBYTECODE=1 python3 -B "$S" "$F/requests.json" --repo "$F/repo" 2>&1); RC=$?
printf '%s\n' "$OUT"
printf -- '--- 판정 (tree=%s · resolver exit=%s · control func=%s)\n' "$R" "$RC" "$CTRL"

QF_OUT="$OUT" PYTHONDONTWRITEBYTECODE=1 python3 -B - "$F/requests.json" "$RC" <<'PY'
import json, os, re, sys

reqs = json.load(open(sys.argv[1], encoding="utf-8"))["impactRequests"]
rc = int(sys.argv[2])
lines = os.environ.get("QF_OUT", "").splitlines()
ids = [re.match(r"\[([QS]\d+)\]", r).group(1) for r in reqs]
EXPECTED_IDS = ("Q1", "Q2", "Q3", "S1", "S2")   # 셀 이름 고정(F-408)
fails = []


def item(tag):
    """(판정, 그 항목 아래 줄들) — 항목 머리는 '  RESOLVED [X]' 또는 '  UNRESOLVED [X]'."""
    for i, ln in enumerate(lines):
        m = re.match(r"^  (RESOLVED|UNRESOLVED) \[" + re.escape(tag) + r"\]", ln)
        if m:
            body = []
            for nxt in lines[i + 1:]:
                if not nxt.startswith("      "):
                    break
                body.append(nxt.strip())
            return m.group(1), body
    return None, []


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        fails.append(what)


check(rc == 0, f"resolver exit 0 (실제 {rc})")
check(any(l.startswith("RESOLVE_OK") for l in lines), "RESOLVE_OK 요약 줄")
nq = sum(1 for t in ids if t.startswith("Q"))
ns = len(ids) - nq
check(nq >= 1 and ns >= 1, f"입력에 [Q] {nq} · [S] {ns} — 둘 다 있어야 대조가 선다")
check(tuple(ids) == EXPECTED_IDS, f"요청 id = {'·'.join(EXPECTED_IDS)} (실제: {'·'.join(ids) or '없음'})")
for t in ids:
    verdict, body = item(t)
    if t.startswith("Q"):
        why = next((b for b in body if b.startswith("사유:")), "")
        census = [b for b in body if b.startswith("census `")]
        check(verdict == "UNRESOLVED" and "질문 미답" in why and bool(census),
              f"[{t}] 질문형 → UNRESOLVED · 사유 '질문 미답' · census 동반 (실제: {verdict} · {why or '사유 없음'} · census {len(census)}줄)")
    else:
        check(verdict == "RESOLVED", f"[{t}] 위치 · 호출자 수 요청 → RESOLVED (실제: {verdict})")
print(f"plan-impact question-form: {'전건 통과' if not fails else f'실패 {len(fails)}건'}")
print(f"CELLS n={len(ids)} ran={','.join(ids) or '-'}")
sys.exit(1 if fails else 0)
PY
