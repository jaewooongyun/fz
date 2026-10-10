#!/bin/bash
# peer 스키마 scope_disposition null · legacy 1.0 퇴역 (F-216 N4 peer 분 · DG-15.peer=same).
#
# ⛔ 실제 `schemas/gpt_peer_review_schema.json` 과 실제 `scripts/validate-gpt-output.py` 로 돈다 — 합성 미니 스키마를
#    쓰면 누가 실제 스키마에 null 을 되살려도 잡히지 않는다(failopen 셀이 그 형태다). 같은 완전한 응답 하나에서
#    한 축만 바꾼다. 셀:
#   valid-<값>      1.1 + 분류값 5종 각각 → 통과 (양성 대조 — 막히면 정상 응답 차단이라 그쪽도 결함)
#   no-issues       1.1 + issues [] → 통과 (빈 응답 양성 대조)
#   v11-null        1.1 + scope_disposition null → 거부 (오류가 scope_disposition 을 가리킨다)
#   v10             schemaVersion "1.0" + 유효값 → 거부 (1.0 퇴역 — 오류가 schemaVersion 을 가리킨다)
#   v10-null        1.0 + null (옛 legacy 조합) → 거부
#   bogus           1.1 + 'bogus' → 거부 · missing  scope_disposition 키 부재 → 거부
#   same-as-review  peer 의 scope_disposition type·enum 집합과 schemaVersion enum 이 review 스키마와 같다(DG-15.peer=same)
#   no-legacy-text  peer 의 두 description 에 'legacy' · 'null은' 이 없다 — 도달할 수 없는 호환 설명을 남기지 않는다
# ⛔ 거부 셀은 검증기 exit 1 만 인정한다. exit 2(스키마 문제 — 미지원 키워드로 구현한 경우)는 PASS 가 아니다(SC-12).
# 기준 트리(be8c871)는 v11-null · v10 · v10-null 을 통과시켜 exit 1 이다.
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 파일 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 게이트가 결함 재현 없이 통과한다 — 그래서 3 이다(미처리 예외도 3).
# ⛔ 중첩 가드: 도는 동안 FZ_PEER_SCOPE_FIXTURE=1. 안에서 다시 불리면 `UNRUN:` 을 내고 exit 2.
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 fixture 가 든 트리 — health-check 는 인자 없이 부른다)
set -u
if [ -n "${FZ_PEER_SCOPE_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 peer-scope-disposition 이 도는 중"
  exit 2
fi
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
for f in scripts/validate-gpt-output.py schemas/gpt_peer_review_schema.json schemas/gpt_review_schema.json; do
  [ -f "$TREE/$f" ] || { echo "SETUP $f 없음: $TREE"; exit 3; }
done

FZ_PEER_SCOPE_FIXTURE=1 PYTHONDONTWRITEBYTECODE=1 python3 -B - "$TREE" <<'PY'
import copy, json, os, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
TREE = sys.argv[1]
VAL = os.path.join(TREE, "scripts/validate-gpt-output.py")
PEER = os.path.join(TREE, "schemas/gpt_peer_review_schema.json")
REVIEW = os.path.join(TREE, "schemas/gpt_review_schema.json")
VALUES = ("scope-in", "scope-out", "invariant-risk", "parent-reopen", "improvement")   # 계약 값 — 스키마에서 읽지 않는다
FAIL = []
RAN = []
SDF, SVF = "/issues[0]/scope_disposition", "/schemaVersion"


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  — " + detail))
    RAN.append(name)
    if not ok:
        FAIL.append(name)


def only(errs, *fields):
    """오류가 1건 이상이고 전부 그 필드들을 가리킨다 — 다른 이유(로드 실패 · 다른 키)의 exit 1 을 거부로 읽지 않는다."""
    return bool(errs) and all(any(x.startswith(f + ":") for f in fields) for x in errs)


ISSUE = {
    "id": "ARCH-001", "perspective": "architecture", "file": "Sources/App/Feature.swift", "line_range": "10-20",
    "severity": "major", "confidence": 80, "origin": "regression",
    "description": "fixture 이슈 — 기존 동작과 달라지는 조건과 결과를 적는다",
    "impact": "fixture 영향", "suggestion": "fixture 제안",
    "alternatives": [{"label": "A: 현재", "description": "그대로", "pros": ["변경 없음"], "cons": ["결함 유지"]}],
    "recommended": "A: 현재", "evidence_trace": "Feature.swift:10 → :20",
    "scope_disposition": "scope-in", "symptom_screen": "FeatureView", "symptom_reach": "탭 진입",
}
BASE = {"schemaVersion": "1.1", "agent": "gpt-challenger", "agent_status": "ok", "status_reason": "정상",
        "issues": [ISSUE], "challenges": [], "strengths": ["fixture"], "overall_assessment": "good"}


def variant(sv="1.1", sd="scope-in", drop=False, issues=True):
    o = copy.deepcopy(BASE)
    o["schemaVersion"] = sv
    if not issues:
        o["issues"] = []
    elif drop:
        del o["issues"][0]["scope_disposition"]
    else:
        o["issues"][0]["scope_disposition"] = sd
    return o


with tempfile.TemporaryDirectory(prefix="fz-peer-scope-") as tmp:
    def run(name, obj):
        p = os.path.join(tmp, name + ".json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)
        r = subprocess.run([sys.executable, VAL, p, PEER], capture_output=True, text=True)
        out = r.stdout + r.stderr
        # ⛔ 0/1 밖 · traceback · 필드 오류 줄 없는 exit 1(출력 로드 실패 등)은 거부가 아니라 측정 불가 — 예외로 3(E1-12 fixture 와 같은 규칙)
        if r.returncode not in (0, 1) or "Traceback (most recent call last)" in out:
            raise RuntimeError("%s: 검증기 exit %d — 0/1 밖(2 = 스키마 문제·사용법) · traceback 은 거부가 아니다 · %s" % (name, r.returncode, out[-300:]))
        errs = [ln.strip() for ln in r.stderr.splitlines() if ln.startswith("   ")]
        if r.returncode == 1 and not errs:
            raise RuntimeError("%s: 검증기 exit 1 인데 필드 오류 줄 0 — 측정 불가 · %s" % (name, out[-300:]))
        return r.returncode, errs, r.stderr

    for v in VALUES:
        rc, _, err = run("valid-" + v, variant(sd=v))
        check("valid-%s: 1.1 + %s 통과" % (v, v), rc == 0, "exit %d %s" % (rc, err.strip()[:160]))
    rc, _, err = run("no-issues", variant(issues=False))
    check("no-issues: 1.1 + issues [] 통과", rc == 0, "exit %d %s" % (rc, err.strip()[:160]))

    for name, obj, fields in (("v11-null", variant(sd=None), (SDF,)),
                              ("v10", variant(sv="1.0"), (SVF,)),
                              ("v10-null", variant(sv="1.0", sd=None), (SVF, SDF)),
                              ("bogus", variant(sd="bogus"), (SDF,)),
                              ("missing", variant(drop=True), (SDF,))):
        rc, errs, err = run(name, obj)
        # v10-null 은 두 필드를 함께 가리킬 수 있다 — 그래도 schemaVersion 은 반드시 있어야 한다
        must = fields[0]
        check("%s: 거부(검증기 exit 1 · 오류가 %s 만 가리킨다)" % (name, " · ".join(fields)),
              rc == 1 and only(errs, *fields) and any(x.startswith(must + ":") for x in errs), "exit %d %s" % (rc, err.strip()[:160]))

    peer = json.load(open(PEER, encoding="utf-8"))
    review = json.load(open(REVIEW, encoding="utf-8"))

    def axes(s):
        sd = s["properties"]["issues"]["items"]["properties"]["scope_disposition"]
        t = sd.get("type")
        return ({t} if isinstance(t, str) else set(t or ()), {repr(x) for x in sd.get("enum", ())},
                set(s["properties"]["schemaVersion"].get("enum", ())))

    pa, ra = axes(peer), axes(review)
    # 절대 단언 — review 와 같은지(상대)만 보면 두 스키마가 같이 type 에 null 을 되살려도 통과한다
    check("peer-static: scope_disposition type·enum 에 null 없음 · schemaVersion enum == ['1.1']",
          "null" not in pa[0] and "None" not in pa[1] and peer["properties"]["schemaVersion"].get("enum") == ["1.1"],
          "type %r · enum %r · schemaVersion %r" % (pa[0], pa[1], peer["properties"]["schemaVersion"].get("enum")))
    check("same-as-review: scope_disposition type·enum · schemaVersion enum 이 review 스키마와 같다",
          pa == ra, "peer %r · review %r" % (pa, ra))
    psd = peer["properties"]["issues"]["items"]["properties"]["scope_disposition"].get("description", "")
    psv = peer["properties"]["schemaVersion"].get("description", "")
    check("no-legacy-text: peer description 에 legacy · 'null은' 없음",
          not any(w in d for d in (psd, psv) for w in ("legacy", "null은")), "%r · %r" % (psd[:80], psv[:80]))

print("\n%d 건 실패" % len(FAIL))
if FAIL:
    sys.exit(1)
print("PEER_SCOPE_DISPOSITION_OK %d셀" % len(RAN))
PY
rc=$?
case "$rc" in
  0|1|3) exit "$rc" ;;
  *) echo "SETUP python 이 0/1/3 밖으로 끝났다 (exit $rc)"; exit 3 ;;
esac
