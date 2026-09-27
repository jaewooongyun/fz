#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff_anchors.py 의 JSON 출력과 exit code 만 본다. diff 파싱은 diff_anchors.py 소관.
# 인라인 앵커 오라클 A1~A10 (skills/fz-peer-review/references/test-spec.md) — 합성 fixture 기준.
#
# ⛔ 옛 fixture(사내 코드)를 합성 patch 로 바꿨다(S03 · A1-04). hunk 좌표를 그대로 보존했으므로 A1~A7 의
#    기대값이 바뀌지 않는다 — 이 러너가 그 사실을 고정한다. A8~A10 은 명세대로 작은 diff 를 여기서 만든다.
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../../../.."
DA="$ROOT/skills/fz-peer-review/scripts/diff_anchors.py"
FX="$ROOT/skills/fz-peer-review/references/fixtures/synthetic-sample.patch"
[ -f "$DA" ] && [ -f "$FX" ] || { echo "diff_anchors.py 또는 fixture 없음" >&2; exit 2; }
python3 - "$DA" "$FX" <<'PY'
import json, os, subprocess, sys, tempfile
da, fx = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="anchors-")

last_err = ""

def run(diff, targets):
    global last_err
    r = subprocess.run([sys.executable, da, "--diff", diff, "--targets", json.dumps(targets)], capture_output=True, text=True)
    last_err = r.stderr   # ⛔ exit 1 + 빈 stdout 은 잡히지 않은 예외(크래시)도 만족한다 — 오류 문구로 가른다(v4.40.0 리뷰)
    out = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    return r.returncode, r.stdout, out

def mk(name, text):
    p = os.path.join(tmp, name)
    open(p, "w", encoding="utf-8").write(text)
    return p

fails = 0
def check(name, ok, detail=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + f"{name:<44} {detail}")
    fails += 0 if ok else 1

rc, _, o = run(fx, [{"path": "TimelineView.swift", "start": 423, "end": 439}])
a = sorted((x["start_line"], x["line"], x["hunk_start"], x["hunk_end"]) for x in (o or {}).get("anchorable", []))
check("A1 겹치는 hunk 둘 다", a == [(423, 428, 420, 428), (431, 439, 431, 440)], str(a))
rc, _, o = run(fx, [{"path": "EngineContext.swift", "start": 122, "end": 140}])
na = (o or {}).get("non_anchorable", [])
check("A2 hunk 밖 = outside_diff", not (o or {}).get("anchorable") and len(na) == 1 and na[0]["reason"] == "outside_diff", str(na))
rc, _, o = run(fx, [{"path": "MediaEngine.swift", "start": 1484, "end": 1513}])
a = (o or {}).get("anchorable", [])
check("A3 hunk 안 완전 포함", len(a) == 1 and (a[0]["start_line"], a[0]["line"], a[0]["hunk_start"], a[0]["hunk_end"]) == (1484, 1513, 1482, 1521), str(a))
rc, _, o = run(fx, [{"path": "NoSuchFile.swift", "start": 1, "end": 10}])
na = (o or {}).get("non_anchorable", [])
check("A4 없는 경로 = path_not_in_diff · exit 0", rc == 0 and len(na) == 1 and na[0]["reason"] == "path_not_in_diff", f"exit={rc}")
rc, out, _ = run(fx, [{"path": "MediaEngine.swift", "start": 20, "end": 10}])
check("A5 start>end = exit 1 · stdout 0바이트", rc == 1 and out == "" and "start > end" in last_err and "Traceback" not in last_err, f"exit={rc} stdout={len(out)}B")
rc, _, o = run(fx, [{"path": "MediaEngine.swift", "start": 1484, "end": 1513}])
a = (o or {}).get("anchorable", [])
check("A6 side 생략 = RIGHT", bool(a) and a[0]["side"] == "RIGHT", str(a[:1]))
rc, _, o = run(fx, [{"path": "MediaEngine.swift", "start": 1451, "end": 1470, "side": "LEFT"}])
a = (o or {}).get("anchorable", [])
check("A7 LEFT 좌표계", len(a) == 1 and (a[0]["side"], a[0]["start_line"], a[0]["line"]) == ("LEFT", 1451, 1470), str(a))
d8 = mk("a8.patch", "diff --git a/real.txt b/real.txt\n--- a/real.txt\n+++ b/real.txt\n@@ -1,2 +1,3 @@\n keep\n++++ b/fake.txt\n keep2\n")
rc, _, o = run(d8, [{"path": "real.txt", "start": 1, "end": 3}, {"path": "fake.txt", "start": 1, "end": 1}])
na = {x["path"]: x["reason"] for x in (o or {}).get("non_anchorable", [])}
check("A8 본문의 +++ 가 파일 경계를 오염 안 함", len((o or {}).get("anchorable", [])) >= 1 and na.get("fake.txt") == "path_not_in_diff", str(na))
d9 = mk("a9.patch", 'diff --git "a/dir/file name.txt" "b/dir/file name.txt"\n--- "a/dir/file name.txt"\n+++ "b/dir/file name.txt"\n@@ -1,1 +1,2 @@\n x\n+y\n')
rc, _, o = run(d9, [{"path": "dir/file name.txt", "start": 1, "end": 2}])
check("A9 quoted path 해제", len((o or {}).get("anchorable", [])) == 1, f"exit={rc}")
d10 = mk("a10.patch", "diff --git a/new.txt b/new.txt\nnew file mode 100644\n--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1,2 @@\n+a\n+b\n")
rc, _, o = run(d10, [{"path": "new.txt", "start": 1, "end": 2, "side": "LEFT"}])
na = (o or {}).get("non_anchorable", [])
rc2, _, _ = run(d10, [{"path": "new.txt", "start": 1, "end": 2, "side": "UP"}])
check("A10 신규 LEFT=no_hunks_on_side · side UP=exit 1", bool(na) and na[0]["reason"] == "no_hunks_on_side" and rc2 == 1
      and "side는" in last_err and "Traceback" not in last_err, f"UP exit={rc2}")
print(f"anchors-synthetic: {10 - fails}/10 통과")
sys.exit(1 if fails else 0)
PY
