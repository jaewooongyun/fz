#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff_anchors.py 의 JSON 출력과 exit code 만 본다. diff 파싱은 diff_anchors.py 소관.
# 인라인 앵커 오라클 A1~A11 (skills/fz-peer-review/references/test-spec.md) — 합성 fixture 기준.
#
# ⛔ fixture 는 합성 재현이다 — 좌표 · 본문 · 경로를 생성기(tests/fixtures/peer-review/synthetic-sample-gen/gen.py)의
#    좌표 표가 정하고, A1~A7 의 기대값은 그 표에서 유도한다. 마지막 셀이 생성기 출력과 patch 가 같은 바이트인지 본다
#    (생성기는 따로 배선하지 않는다 — 이 러너가 갈림을 잡는다). A8~A11 은 명세대로 작은 diff 를 여기서 만든다.
#    generator-check-crlf-detected 는 줄 끝만 다른 patch 를 생성기가 다르다고 보는지, crash-is-unrun-exit2 는 단언기 고장이
#    exit 2 + `UNRUN:` 줄로 끝나고 임시 폴더를 남기지 않는지 본다(자식 실행 — 자식은 그 셀을 돌지 않는다).
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류(`UNRUN:` 줄 — 대상 부재 · 단언기가 예외로 끝남)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../../../.."
DA="$ROOT/skills/fz-peer-review/scripts/diff_anchors.py"
FX="$ROOT/skills/fz-peer-review/references/fixtures/synthetic-sample.patch"
GEN="$ROOT/tests/fixtures/peer-review/synthetic-sample-gen/gen.py"
[ -f "$DA" ] && [ -f "$FX" ] && [ -f "$GEN" ] || { echo "UNRUN: diff_anchors.py · fixture · 생성기 가운데 없는 것이 있다"; exit 2; }
python3 - "$DA" "$FX" "$GEN" "${BASH_SOURCE[0]}" <<'PY'
import atexit, json, os, shutil, subprocess, sys, tempfile, traceback
da, fx, gen, runner = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
tmp = tempfile.mkdtemp(prefix="anchors-")
atexit.register(shutil.rmtree, tmp, True)


def _crash(*exc):
    # 단언기 고장은 불일치(1)가 아니다 — 머리말의 exit 2 다. os._exit 는 atexit 를 건너뛰므로 임시 폴더를 여기서 지운다
    traceback.print_exception(*exc)
    print("UNRUN: 실행 오류 — 단언기가 예외로 끝났다(⛔ 통과 아님)")
    sys.stdout.flush()
    shutil.rmtree(tmp, True)
    os._exit(2)


sys.excepthook = _crash

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

fails = total = 0
def check(name, ok, detail=""):
    global fails, total
    total += 1
    print(("PASS  " if ok else "FAIL  ") + f"{name:<44} {detail}")
    fails += 0 if ok else 1

rc, _, o = run(fx, [{"path": "CartSummaryView.swift", "start": 92, "end": 105}])
a = sorted((x["start_line"], x["line"], x["hunk_start"], x["hunk_end"]) for x in (o or {}).get("anchorable", []))
check("A1 겹치는 hunk 둘 다", a == [(92, 96, 89, 96), (101, 105, 101, 109)], str(a))
rc, _, o = run(fx, [{"path": "CheckoutContext.swift", "start": 61, "end": 74}])
na = (o or {}).get("non_anchorable", [])
check("A2 hunk 밖 = outside_diff", not (o or {}).get("anchorable") and len(na) == 1 and na[0]["reason"] == "outside_diff", str(na))
rc, _, o = run(fx, [{"path": "CheckoutEngine.swift", "start": 172, "end": 198}])
a = (o or {}).get("anchorable", [])
check("A3 hunk 안 완전 포함", len(a) == 1 and (a[0]["start_line"], a[0]["line"], a[0]["hunk_start"], a[0]["hunk_end"]) == (172, 198, 170, 206), str(a))
rc, _, o = run(fx, [{"path": "NoSuchFile.swift", "start": 1, "end": 10}])
na = (o or {}).get("non_anchorable", [])
check("A4 없는 경로 = path_not_in_diff · exit 0", rc == 0 and len(na) == 1 and na[0]["reason"] == "path_not_in_diff", f"exit={rc}")
rc, out, _ = run(fx, [{"path": "CheckoutEngine.swift", "start": 20, "end": 10}])
check("A5 start>end = exit 1 · stdout 0바이트", rc == 1 and out == "" and "start > end" in last_err and "Traceback" not in last_err, f"exit={rc} stdout={len(out)}B")
rc, _, o = run(fx, [{"path": "CheckoutEngine.swift", "start": 172, "end": 198}])
a = (o or {}).get("anchorable", [])
check("A6 side 생략 = RIGHT", bool(a) and a[0]["side"] == "RIGHT", str(a[:1]))
rc, _, o = run(fx, [{"path": "CheckoutEngine.swift", "start": 134, "end": 151, "side": "LEFT"}])
a = (o or {}).get("anchorable", [])
check("A7 LEFT 좌표계", len(a) == 1 and (a[0]["side"], a[0]["start_line"], a[0]["line"]) == ("LEFT", 134, 151), str(a))
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
d11 = mk("a11.patch", "diff --git a/.claude-plugin/plugin.json b/.claude-plugin/plugin.json\n--- a/.claude-plugin/plugin.json\n"
       "+++ b/.claude-plugin/plugin.json\n@@ -1 +1 @@\n-a\n+b\n")
rc, _, o = run(d11, [{"path": ".claude-plugin/plugin.json", "start": 1, "end": 1}, {"path": "./.claude-plugin/plugin.json", "start": 1, "end": 1}])
check("A11 점으로 시작하는 폴더 · 선두 ./ 만 벗긴다", len((o or {}).get("anchorable", [])) == 2, str((o or {}).get("non_anchorable")))
# F-539 — 실제 탭이 든 경로. 헤더는 Git 인용(\t escape)이고 요청은 원문(실제 탭)이다. 같은 diff 의 `dir/a` 는 탭에서 잘린 이름 — 거기 붙으면 오앵커다
d12 = mk("a12.patch", 'diff --git "a/dir/a\\tb.txt" "b/dir/a\\tb.txt"\n--- "a/dir/a\\tb.txt"\n+++ "b/dir/a\\tb.txt"\n@@ -1,1 +1,2 @@\n x\n+y\n'
       "diff --git a/dir/a b/dir/a\n--- a/dir/a\n+++ b/dir/a\n@@ -1,1 +1,3 @@\n p\n+q\n+r\n")
rc, _, o = run(d12, [{"path": "dir/a\tb.txt", "start": 2, "end": 2}])
a = [(x["path"], x["start_line"], x["line"]) for x in (o or {}).get("anchorable", [])]
check("tab-path-exact 탭 경로 정확 일치 · 잘린 이름에 안 붙음", rc == 0 and a == [("dir/a\tb.txt", 2, 2)], str(a))
d13 = mk("a13.patch", "diff --git a/x/util.swift b/x/util.swift\n--- a/x/util.swift\n+++ b/x/util.swift\n@@ -1 +1,2 @@\n a\n+b\n"
       "diff --git a/y/util.swift b/y/util.swift\n--- a/y/util.swift\n+++ b/y/util.swift\n@@ -1 +1,2 @@\n a\n+b\n")
rc, _, o = run(d13, [{"path": "util.swift", "start": 2, "end": 2}, {"path": "x/util.swift", "start": 2, "end": 2}])
na = [(x["path"], x["reason"]) for x in (o or {}).get("non_anchorable", [])]
a = [x["path"] for x in (o or {}).get("anchorable", [])]
check("basename-collision 같은 basename 은 되돌림 · 전체 경로는 앵커", na == [("util.swift", "ambiguous_path")] and a == ["x/util.swift"], f"{na} · {a}")
g = subprocess.run([sys.executable, gen, "--check"], capture_output=True, text=True)
check("generator-check 생성기 출력 = patch 바이트", g.returncode == 0, f"exit={g.returncode} {g.stderr.strip()[:120]}")

def lay(box, files):
    """임시 트리 배치 — {상대 경로: 복사할 파일 경로 | 쓸 바이트}."""
    for rel, src in files.items():
        dst = os.path.join(box, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if isinstance(src, bytes):
            open(dst, "wb").write(src)
        else:
            shutil.copy(src, dst)
    return box

GEN_REL, FX_REL = "tests/fixtures/peer-review/synthetic-sample-gen/gen.py", "skills/fz-peer-review/references/fixtures/synthetic-sample.patch"
# 줄 끝만 다른 patch(CRLF) — 글자로 읽어 비교하면 같다고 나온다. 생성기 사본과 CRLF patch 를 임시 트리 배치에 두고 --check 를 돈다
crlf = lay(os.path.join(tmp, "crlf"), {GEN_REL: gen, FX_REL: open(fx, "rb").read().replace(b"\n", b"\r\n")})
g = subprocess.run([sys.executable, "-B", os.path.join(crlf, GEN_REL), "--check"], capture_output=True, text=True)
check("generator-check-crlf-detected 줄 끝만 다른 patch = exit 1", g.returncode == 1 and "DIFF:" in g.stderr, f"exit={g.returncode} {' '.join(g.stderr.split())[:120]}")
# 단언기 고장(diff_anchors.py 가 JSON 앞에 다른 줄을 낸다) — exit 2 + UNRUN 줄이고 임시 폴더를 남기지 않는다. 자식은 이 셀을 돌지 않는다
if not os.environ.get("FZ_ANCHORS_CHILD"):
    RUN_REL, DA_REL = "tests/fixtures/peer-review/anchors-synthetic/run.sh", "skills/fz-peer-review/scripts/diff_anchors.py"
    box = lay(os.path.join(tmp, "crash"), {RUN_REL: runner, GEN_REL: gen, FX_REL: fx, DA_REL: b'print("warn")\nprint("{}")\n'})
    td = os.path.join(box, "tmpd")
    os.makedirs(td)
    c = subprocess.run(["bash", os.path.join(box, RUN_REL)], capture_output=True, text=True, env=dict(os.environ, FZ_ANCHORS_CHILD="1", TMPDIR=td))
    left = [n for n in os.listdir(td) if n.startswith("anchors-")]
    check("crash-is-unrun-exit2 단언기 고장 = exit 2 · UNRUN 줄 · 임시 폴더 0", c.returncode == 2 and not left
          and any(ln.startswith("UNRUN") for ln in c.stdout.splitlines()), f"exit={c.returncode} 남은 폴더={len(left)} {c.stdout.strip()[-100:]!r}")
print(f"anchors-synthetic: {total - fails}/{total} 통과")
sys.exit(1 if fails else 0)
PY
