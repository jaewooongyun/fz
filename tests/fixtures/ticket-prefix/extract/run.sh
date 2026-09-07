#!/bin/bash
# 티켓 접두 추출 **결과 계약** 회귀 판정 — 배포물의 정규식·기본 경로·우선순위 문장을 잰다.
#
# ⛔ 여기서 막는 것은 두 방향의 조용한 오분류다. 스크립트는 양쪽 다 성공하고
#    `trigger_case` 값만 틀린다 — 실패가 안 보인다.
#      (가) 접두를 넓혔더니 티켓이 아닌 표기(`PR-12`)까지 티켓이 된다
#      (나) 넓혔다면서 기존 `ASD-####` 가 조용히 빠진다 (하위호환 손실)
#
# ── 결과 계약 (S1 확정 · S2 가 코드로 구현한다) ─────────────────────────────
#   ① 티켓 정규식 = `\b(?!PR-)[A-Z]{2,6}-\d{2,5}(?![A-Za-z0-9_])`
#   ② `PR-N` 은 티켓이 아니다 — 접두 `PR-` 를 명시 제외하고 기존 **세션 fallback** 으로
#      보낸다. 원본이 `PR\s*#\d{2,5}`·`PR\d+` 를 별도 대안으로 갖고 있어
#      [skills/fz-manage/scripts/parse_memory.py:107-110], 티켓 분기가 그것을 삼키면
#      PR 표기가 티켓으로 오분류된다. 하이픈형 `PR-N` 을 PR 대안에 새로 지원하는 것은
#      additive·범위 밖이다.
#   ③ 다중 티켓 = **첫 매치 채택** + GATHER-NOTE 1행(나머지 후보 나열)
#   ④ WORK_DIR 우선순위 **보존** = 명시적 인자 > 브랜치명 > AskUserQuestion >
#      Serena Memory fallback [modules/context-artifacts.md '## Work Dir 결정']
#
# ⛔ 기대값은 **현행 동작이 아니라 계약값**이다. 그래서 S2 적용 전에는 red 가 나오는 것이
#    정상이고, exit 0 이 나오면 이 러너가 아무것도 재고 있지 않다는 뜻이다.
#    red→green 전이를 관측하는 것이 이 러너의 존재 이유다.
#
# ⛔ mktemp/trap 미사용 — 이 러너는 디스크에 쓰지 않는다. 실제 git 리포가 필요한
#    peer-review 계열과 달리 여기 입력은 전부 문자열이고, mktemp 는 읽기 전용 샌드박스의
#    외부 채점자가 러너를 못 돌리게 만든 전례가 있다
#    [tests/fixtures/cross-validation/coverage-units/run.sh:6-10].
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../../../.."
PARSE="$ROOT/skills/fz-manage/scripts/parse_memory.py"
HOOK="$ROOT/scripts/gate_stop_hook.py"
CTX="$ROOT/modules/context-artifacts.md"

for f in "$PARSE" "$HOOK" "$CTX"; do
  [ -f "$f" ] || { echo "대상 파일을 찾을 수 없다: $f" >&2; exit 2; }
done
command -v python3 >/dev/null 2>&1 || { echo "python3 이 없다" >&2; exit 2; }

FZ_PARSE="$PARSE" FZ_HOOK="$HOOK" FZ_CTX="$CTX" python3 - <<'PY'
import importlib.util
import os
import re
import sys

FAIL = 0


def ok(name):
    print("PASS  %s" % name)


def no(name, why):
    global FAIL
    print("FAIL  %s  — %s" % (name, why))
    FAIL += 1


def note(name, why):
    print("NOTE  %s  — %s" % (name, why))


# 계약 정규식 — S2 가 배포물에 넣을 문자열과 같아야 한다
CONTRACT = re.compile(r"\b(?!PR-)[A-Z]{2,6}-\d{2,5}(?![A-Za-z0-9_])")
# 대조군: `PR-` 명시 제외가 **없는** 판. 계약 ② 가 실제로 일을 하는지 보이는 데 쓴다
NO_GUARD = re.compile(r"\b[A-Z]{2,6}-\d{2,5}(?![A-Za-z0-9_])")

spec = importlib.util.spec_from_file_location("fz_parse_memory", os.environ["FZ_PARSE"])
pm = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(pm)
except Exception as exc:  # noqa: BLE001 — 판정 불가는 실행 오류(2)지 불일치(1)가 아니다
    print("parse_memory.py 를 불러오지 못했다: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
    raise SystemExit(2)

SESSION_ID = "0f9c1d22-1111-2222-3333-444455556666"
SESSION_FM = {"metadata": "originSessionId: %s" % SESSION_ID}
SESSION_EXPECT = "session=%s" % SESSION_ID


def trigger(body, fm=None):
    return pm.extract_trigger_case(body, fm if fm is not None else {})


# ── (1) ASD-1234 → 매치 ────────────────────────────────────────────
r = trigger("ASD-1234 에서 발견한 교훈")
if r == "ASD-1234":
    ok("1 ASD-1234 매치 (하위호환)")
else:
    no("1 ASD-1234 매치 (하위호환)", "기대 'ASD-1234', 실제 %r" % r)

# ── (2) TVG-4442 → 매치 ────────────────────────────────────────────
r = trigger("TVG-4442 에서 발견한 교훈")
if r == "TVG-4442":
    ok("2 TVG-4442 매치")
else:
    no("2 TVG-4442 매치", "기대 'TVG-4442', 실제 %r (S2 전에는 red 가 정상)" % r)

# ── (3) PR-12 → 비티켓 · 세션 fallback ─────────────────────────────
#     ⛔ 부재 주장에는 대조가 필요하다: guard 없는 판은 같은 입력을 티켓으로 삼킨다
if NO_GUARD.search("PR-12") and not CONTRACT.search("PR-12"):
    ok("3a PR- 제외가 load-bearing (대조군은 PR-12 를 삼킨다)")
else:
    no("3a PR- 제외가 load-bearing",
       "대조군 %r / 계약 %r — 대조가 성립하지 않아 3b 가 공허하다"
       % (NO_GUARD.search("PR-12"), CONTRACT.search("PR-12")))
r = trigger("PR-12 리뷰에서 지적", SESSION_FM)
if r == SESSION_EXPECT:
    ok("3b PR-12 → 티켓 비매치 후 세션 fallback")
else:
    no("3b PR-12 → 티켓 비매치 후 세션 fallback", "기대 %r, 실제 %r" % (SESSION_EXPECT, r))

# ── (4) F-142 → 비매치 (접두 글자수 하한 2) ────────────────────────
r = trigger("F-142 항목을 참조")
if r is None:
    ok("4a F-142 비매치 (접두 1글자)")
else:
    no("4a F-142 비매치 (접두 1글자)", "기대 None, 실제 %r" % r)
if CONTRACT.search("FZ-142"):
    ok("4b 대조: FZ-142 는 매치 (하한이 글자수임을 보인다)")
else:
    no("4b 대조: FZ-142 는 매치", "계약 정규식이 2글자 접두를 못 잡는다 — 4a 가 공허하다")

# ── (5) 접미 토큰 → 비매치 (`(?![A-Za-z0-9_])`) ──────────────────────────────
r = trigger("TVG-12suffix 는 티켓이 아니다")
if r is None:
    ok("5a TVG-12suffix 비매치")
else:
    no("5a TVG-12suffix 비매치", "기대 None, 실제 %r" % r)
# ⛔ 대조 겸 하위호환 감시: 같은 경계 규칙을 기존 접두에도 적용한다.
#    현행 배포물은 후행 경계가 없어 'ASD-12' 를 잘라낸다 → 계약 도입은 ASD 동작도 바꾼다.
r = trigger("ASD-12suffix 는 티켓이 아니다")
if r is None:
    ok("5b ASD-12suffix 비매치 (후행 경계가 기존 접두에도 적용)")
else:
    no("5b ASD-12suffix 비매치 (후행 경계가 기존 접두에도 적용)",
       "기대 None, 실제 %r — 현행은 후행 경계가 없다. S2 후 green 이어야 한다" % r)

# ── (6) 다중 티켓 → 첫 매치 + GATHER-NOTE 후보 ─────────────────────
MULTI = "TVG-4442 와 ASD-1234 둘다 관련"
r = trigger(MULTI)
if r == "TVG-4442":
    ok("6a 다중 티켓 → 첫 매치 채택")
else:
    no("6a 다중 티켓 → 첫 매치 채택",
       "기대 'TVG-4442'(문자열 선두), 실제 %r — 대안 순서가 위치를 이긴다" % r)
cands = CONTRACT.findall(MULTI)
if cands[1:] == ["ASD-1234"]:
    ok("6b GATHER-NOTE 후보 = 나머지 %r" % (cands[1:],))
else:
    no("6b GATHER-NOTE 후보 나열", "기대 ['ASD-1234'], 실제 %r" % (cands[1:],))

# ── (7) 티켓 부재 → 비매치 + fallback 경로 도달 ────────────────────
ABSENT = "티켓 표기가 전혀 없는 본문이다"
r = trigger(ABSENT)
if r is None:
    ok("7a 티켓 부재 → 비매치")
else:
    no("7a 티켓 부재 → 비매치", "기대 None, 실제 %r" % r)
r = trigger(ABSENT, SESSION_FM)
if r == SESSION_EXPECT:
    ok("7b 티켓 부재 → 세션 fallback 도달")
else:
    no("7b 티켓 부재 → 세션 fallback 도달", "기대 %r, 실제 %r" % (SESSION_EXPECT, r))

# ── (8) 명시 인자 vs 브랜치 충돌 → 인자 승 ─────────────────────────
#     계약 ④ 는 코드가 아니라 문장이 정본이다. 순서가 보존되는지를 원문에서 잰다.
#     ⛔ 접두 비의존: 리터럴이 아니라 **등장 순서**만 본다.
ctx = open(os.environ["FZ_CTX"], encoding="utf-8").read()
prio = [ln for ln in ctx.splitlines() if "우선순위" in ln and "fallback" in ln]
if not prio:
    no("8 WORK_DIR 우선순위 4단계 순서 보존",
       "'우선순위'+'fallback' 행 미발견 — 측정 실패 (0건을 통과로 읽지 않는다)")
else:
    line = prio[0]
    marks = ["인자", "브랜치", "AskUserQuestion", "fallback"]
    at = [line.find(m) for m in marks]
    if -1 in at:
        no("8 WORK_DIR 우선순위 4단계 순서 보존",
           "단계 어휘 누락 %r — 행 원문 [%s]" % ([m for m, i in zip(marks, at) if i == -1], line.strip()))
    elif at == sorted(at):
        ok("8 WORK_DIR 우선순위 4단계 순서 보존 (명시 인자 > 브랜치 > 질문 > fallback)")
    else:
        no("8 WORK_DIR 우선순위 4단계 순서 보존",
           "순서가 뒤바뀌었다 %r — 행 원문 [%s]" % (at, line.strip()))

# ── (9) gate_stop_hook 기본 레이아웃 하위호환 ──────────────────────
#     이 기본값은 실제 mkdir 경로에 쓰인다. 접두를 일반화해도 **깊이 2 + 종단 gates**
#     라는 모양은 유지돼야 한다 — 리터럴이 아니라 모양을 고정한다.
hook = open(os.environ["FZ_HOOK"], encoding="utf-8").read()
m = re.search(r"PROBE_LAYOUT\.get\(\s*layout\s*,\s*\"([^\"]+)\"\s*\)", hook)
if not m:
    no("9 기본 레이아웃 = 깊이 2 + 종단 gates",
       "`PROBE_LAYOUT.get(layout, \"...\")` 기본값 미발견 — 측정 실패")
else:
    rel = m.group(1)
    segs = rel.split("/")
    if len(segs) == 2 and segs[1] == "gates" and segs[0]:
        ok("9 기본 레이아웃 = 깊이 2 + 종단 gates (%r)" % rel)
    else:
        no("9 기본 레이아웃 = 깊이 2 + 종단 gates", "실제 %r" % rel)

# ── (10) 한글 조사 부착형 — 후행 경계가 `(?![A-Za-z0-9_])` 라 조사는 경계 밖 ──
# 계약 초안 `(?!\w)` 은 python `\w` 가 유니코드라 한글 음절을 매치해 `ASD-1234에서` 를 떨어뜨렸다
# (실측 코퍼스 213파일 토큰 765건 중 61건 = 8.0%). 기존 접두에도 적용되는 하위호환 손실이라 경계를 ASCII 로 좁혔다.
for tok in ("ASD-1234에서", "TVG-4442를"):
    m = CONTRACT.search(tok)
    if m and m.group(0) == tok[:8]:
        ok("10 조사 부착형 %r → 매치 %r" % (tok, m.group(0)))
    else:
        no("10 조사 부착형 %r → 매치" % tok, "실제 %r" % (m.group(0) if m else None))
note("학술·표준 접두 오탐",
     "`ISO-8601`·`SHA-256`·`RFC-7231`·`COVID-19` 는 계약 정규식에 매치된다. 현 코퍼스 "
     "실측 접두 분포는 TVG/ASD/QE/TVING/ISSUE/NOTASK/ADP 로 해당 없음 — 판정 보류")

print("")
if FAIL == 0:
    print("0 건 실패 (10 케이스 판정 · 알림 1)")
    raise SystemExit(0)
print("%d 건 실패" % FAIL)
raise SystemExit(1)
PY
rc=$?
exit $rc
