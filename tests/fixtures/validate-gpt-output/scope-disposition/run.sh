#!/bin/bash
# review 스키마 scope_disposition null 거부 fixture (F-216 N4 · SC-12) — 실제 schemas/gpt_review_schema.json 과
# scripts/validate-gpt-output.py 를 그대로 쓴다. 완전한 1.1 응답 한 벌에서 한 필드만 바꾼 셀을 검증기 CLI 에 넣는다.
#   valid      분류값 5종(scope-in · scope-out · invariant-risk · parent-reopen · improvement) — 각각 exit 0
#   null       1.1 + scope_disposition null — exit 1 · 오류가 /issues[0]/scope_disposition 만 가리킨다.
#              스키마의 type 과 enum 양쪽에 null 이 없다 — 한쪽만 빼도 거부는 되지만, 둘이 어긋난 스키마를
#              CLI 구조화 출력(--output-schema)이 받는지는 따로 확인하지 않았다(EC-27)
#   bad-value  1.1 + 목록 밖 값 — exit 1 · 같은 필드
#   missing    1.1 + 키 없음 — exit 1 · 같은 필드(required)
#   v1.0       schemaVersion 1.0 + 유효 분류값 — exit 1 · /schemaVersion 만 가리킨다(1.0 퇴역)
# ⛔ 1.1 에서만 null 을 막는 조건부 키워드(if/then · oneOf · anyOf · allOf · const)는 검증기가 모른다 — 그렇게 쓴
#    스키마는 검증기가 exit 2(스키마 문제)로 낸다. exit 2 는 거부가 아니다 → 준비 실패 3 으로 센다.
# 기준 트리는 1.1+null 과 1.0 을 받고 type·enum 에 null 이 있어 null · v1.0 셀이 놓친다 → exit 1.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 검증기·스키마 부재 · 검증기 exit 0/1 밖 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 게이트가 기능 부재 재현 없이 통과한다 — 그래서 3 이다.
#      python 의 미처리 예외(기본 exit 1)는 excepthook 으로, python 이 0/1/3 밖으로 끝나면 바깥 셸이 3 으로 바꾼다.
# ⛔ 셀 입력은 python 임시 폴더에만 쓴다. 트리에 바이트코드를 남기지 않는다.
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -f "$R/scripts/validate-gpt-output.py" ] || { echo "SETUP validate-gpt-output.py 없음: $R"; exit 3; }
[ -f "$R/schemas/gpt_review_schema.json" ] || { echo "SETUP gpt_review_schema.json 없음: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" <<'PY'
import json, os, pathlib, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

TREE = pathlib.Path(sys.argv[1])
VAL = TREE / "scripts" / "validate-gpt-output.py"
SCHEMA = TREE / "schemas" / "gpt_review_schema.json"
VALUES = ["scope-in", "scope-out", "invariant-risk", "parent-reopen", "improvement"]
SDF = "/issues[0]/scope_disposition"
FAIL, N = [], [0]


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    N[0] += 1
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-300:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def doc(version="1.1", sd="scope-in", drop=False):
    """review 스키마의 required 를 전부 채운 응답 — 바꾸는 것은 schemaVersion 과 issues[0].scope_disposition 뿐이다."""
    issue = {"id": "ISSUE-001", "severity": "major", "category": "logic_error", "description": "fixture",
             "location": {"file": "scripts/x.py", "symbol": None, "line_range": "1-2"},
             "suggestion": None, "confidence": 80, "code_snippet": None, "alternatives": None,
             "recommended": None, "scope_disposition": sd}
    if drop:
        del issue["scope_disposition"]
    return {"schemaVersion": version, "review_id": "REV-001", "timestamp": "2026-10-09T00:00:00Z",
            "review_type": "code_review", "issues": [issue],
            "summary": {"total_issues": 1, "by_severity": {"critical": 0, "major": 1, "minor": 0, "suggestion": 0},
                        "by_category": "logic_error 1"},
            "verdict": "needs_revision", "overall_feedback": "fixture", "strengths": []}


def run(tmp, name, obj):
    """검증기 CLI 실행 → (exit, 오류 줄, 출력). ⛔ exit 0/1 밖 · traceback 은 거부가 아니라 측정 불가 → Setup."""
    p = tmp / f"{name}.json"
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON_COLORS="0")
    r = subprocess.run([sys.executable, "-B", str(VAL), str(p), str(SCHEMA)],
                       capture_output=True, text=True, env=e, timeout=60)
    out = (r.stdout + r.stderr).strip()
    if r.returncode not in (0, 1) or "Traceback (most recent call last)" in out:
        raise Setup(f"{name}: 검증기 exit {r.returncode} — 0/1 밖(2 = 스키마 문제·사용법)·traceback 은 거부가 아니다 · {out[-300:]}")
    errs = [ln.strip() for ln in r.stderr.splitlines() if ln.startswith("   ")]
    if r.returncode == 1 and not errs:   # 오류 줄 없는 exit 1(출력 로드 실패 등)은 거부 판정이 아니다 — 1 로 내면 기준 게이트가 결함 재현 없이 찬다
        raise Setup(f"{name}: 검증기 exit 1 인데 필드 오류 줄 0 — 거부가 아니라 측정 불가 · {out[-300:]}")
    return r.returncode, errs, out


def only(errs, field):
    """오류가 1건 이상이고 전부 그 필드를 가리킨다 — 다른 이유(로드 실패 · 다른 키)의 exit 1 을 거부로 읽지 않는다."""
    return bool(errs) and all(x.startswith(field + ":") for x in errs)


def main():
    try:
        sd = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["issues"]["items"]["properties"]["scope_disposition"]
        enum = list(sd.get("enum") or [])
    except (OSError, ValueError, KeyError, TypeError) as ex:
        raise Setup(f"review 스키마에서 issues[].scope_disposition 을 읽지 못했다: {ex!r}")
    with tempfile.TemporaryDirectory(prefix="fz-scope-disposition.") as td:
        tmp = pathlib.Path(td)
        for v in VALUES:
            rc, errs, out = run(tmp, f"valid-{v}", doc(sd=v))
            check("valid", rc == 0, f"1.1 + {v} 통과 (exit {rc})", out)
        rc, errs, out = run(tmp, "null", doc(sd=None))
        check("null", rc == 1 and only(errs, SDF), f"1.1 + null 거부 — exit 1 · 오류가 {SDF} 만 가리킨다 (exit {rc})", out)
        t = sd.get("type")
        check("null", "null" not in (t if isinstance(t, list) else [t]) and None not in enum,
              f"스키마 type·enum 양쪽에 null 없음 (type={t!r} · enum 의 null {'있음' if None in enum else '없음'})")
        rc, errs, out = run(tmp, "bad-value", doc(sd="scope-maybe"))
        check("bad-value", rc == 1 and only(errs, SDF), f"1.1 + 'scope-maybe' 거부 — exit 1 · {SDF} (exit {rc})", out)
        rc, errs, out = run(tmp, "missing", doc(drop=True))
        check("missing", rc == 1 and only(errs, SDF), f"1.1 + 키 누락 거부 — exit 1 · {SDF} required (exit {rc})", out)
        rc, errs, out = run(tmp, "v1.0", doc(version="1.0"))
        check("v1.0", rc == 1 and only(errs, "/schemaVersion"), f"1.0 응답 거부 — exit 1 · /schemaVersion 만 가리킨다 (exit {rc})", out)
    if FAIL:
        print(f"FAIL {len(FAIL)}/{N[0]} — " + " | ".join(FAIL))
        return 1
    print(f"SCOPE_DISPOSITION_OK {N[0]}/{N[0]} (valid 5 통과 · null · bad-value · missing · v1.0 거부 · type·enum 의 null 0)")
    return 0


try:
    sys.exit(main())
except Setup as ex:
    print(f"SETUP {ex}")
    sys.exit(3)
PY
rc=$?
case "$rc" in
  0|1|3) exit "$rc" ;;
  *) echo "SETUP python 이 0/1/3 밖으로 끝났다 (exit $rc)"; exit 3 ;;
esac
