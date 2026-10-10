#!/bin/bash
# 배출 INDEX 정리 · 레지스트리 잠금 fixture (F-372) — 대기열 행 재계산과 잠금을 동작으로 본다.
#
# 셀마다 임시 레지스트리를 만들고 eject_findings.py CLI 를 돌려 INDEX.md · .archive · APPLIED · 잠금 파일을 단언한다.
#   index           1건 · 여러 건 · 같은 번호 다른 slug · 멱등 · INDEX 부재 · 쓰기 실패 · 중단→복구 · reconcile 뒤 0 ·
#                   읽기~교체 사이 변경 · 마지막 확인 직후 협조 writer 잠금 대기 · ./entries/ 변형 · --audit 잔존 탐지
#   telemetry       fz_telemetry_report --findings-dir 가 배출 전후의 같은 레지스트리를 배출 건수만큼 차이로 읽는다
#   lock            SIGKILL 된 보유자 뒤 획득 · 살아 있는 보유자면 상한 대기 뒤 비0 · 파일만 남은 상태 획득
#   applied-records applied_records 결과가 고정 기대값과 같고, --base 가 주어지면 기준 트리 결과와도 같다
# 기준 트리는 INDEX 를 읽지도 쓰지도 않고 --prune-index · 잠금 · 시험 훅이 없어 이 fixture 가 exit 1 이다.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 임시 레지스트리 · 보유자 기동 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 게이트가 기능 부재 재현 없이 통과한다 — 그래서 3 이다.
#      python 의 미처리 예외(기본 exit 1)도 excepthook 으로 3 으로 바꾼다.
# ⛔ 임시 레지스트리만 쓴다 — 실제 레지스트리 경로는 받지 않는다. 트리에 바이트코드를 남기지 않는다.
# ⛔ 시험 틈은 eject_findings.py 의 FZ_REGISTRY_TEST_HOOK 하나다(운영 경로에서는 무동작).
# usage: run.sh [--tree <플러그인 루트>] [--cells <셀|묶음>,…] [--base <기준 트리>]   (기본: 이 fixture 가 든 트리 · 전체 셀)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
CELLS=""
BASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    --cells) [ $# -ge 2 ] || { echo "SETUP --cells 에 값이 없다"; exit 3; }
             CELLS="$2"; shift 2 ;;
    --base) [ $# -ge 2 ] || { echo "SETUP --base 에 경로가 없다"; exit 3; }
            BASE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --base 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -f "$R/scripts/eject_findings.py" ] || { echo "SETUP eject_findings.py 없음: $R"; exit 3; }
[ -f "$R/scripts/fz_telemetry_report.py" ] || { echo "SETUP fz_telemetry_report.py 없음: $R"; exit 3; }
[ -z "$BASE" ] || [ -f "$BASE/scripts/eject_findings.py" ] || { echo "SETUP 기준 eject_findings.py 없음: $BASE"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" "$CELLS" "$BASE" <<'PY'
import importlib.util, json, os, pathlib, shlex, signal, subprocess, sys, tempfile, time, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

TREE, CELLS_ARG, BASE = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
EJ = TREE / "scripts" / "eject_findings.py"
TEL = TREE / "scripts" / "fz_telemetry_report.py"
PY = sys.executable
LOCK = ".fz-registry.lock"
FAIL = []


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def run(args, env=None, script=EJ):
    """대상 트리 스크립트 실행 → (rc, stdout+stderr, 걸린 초). 시간 초과는 대상 동작이므로 rc=-9 로 단언에 넘긴다."""
    e = dict(os.environ)
    e.pop("FZ_REGISTRY_TEST_HOOK", None)
    e["FZ_REGISTRY_LOCK_WAIT"] = "2"
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(env or {})
    t0 = time.monotonic()
    try:
        p = subprocess.run([PY, "-B", str(script)] + [str(a) for a in args], capture_output=True, text=True,
                           env=e, stdin=subprocess.DEVNULL, timeout=60)
        return p.returncode, p.stdout + p.stderr, time.monotonic() - t0
    except subprocess.TimeoutExpired as x:
        return -9, f"시간 초과 60s — {x}", time.monotonic() - t0


def entry(slug):
    num = slug[:5]
    return (f"---\nid: {num}\ntitle: {slug} 시험 엔트리\ndate: 2026-10-01\nclass: hole\nfailure_class: fixture-{num.lower()}\n"
            f"status: open\ndetector: self\n---\n\n# {num} — {slug} 시험 엔트리\n")


def row(slug, dot=False):
    num = slug[:5]
    return (f"| {num} | 2026-10-01 | `hole` | fixture-{num.lower()} | {slug} 한 줄 | self | open | "
            f"[{num}]({'./' if dot else ''}entries/{slug}.md) |\n")


HEAD = ("# INDEX — 시험 레지스트리\n\n> 반영·기각되면 행을 지우고 APPLIED.md 로 옮긴다.\n\n## 대기열\n\n"
        "| ID | 날짜 | class | failure_class | 한 줄 | 탐지자 | status | 문서 |\n"
        "|----|------|:-----:|---------------|-------|:------:|:------:|------|\n")
TAIL = ("\n## 다음 ID\n\n산문 속 링크 [F-001](entries/F-001-alpha.md) 는 대기열 행이 아니다.\n\n"
        "## failure_class 목록\n\n| failure_class | 대기 엔트리 |\n|---|---|\n| `fixture-f-001` | F-001 |\n")
FOREIGN = "| F-990 | 2026-10-02 | `hole` | foreign | 다른 세션이 넣은 행 | self | open | [F-990](entries/F-990-foreign.md) |\n"
COOP = "| F-991 | 2026-10-02 | `hole` | coop | 협조 writer 가 넣은 행 | self | open | [F-991](entries/F-991-coop.md) |\n"


def index(*rows, extra=""):
    return HEAD + "".join(rows) + extra + TAIL


def reg(base, live=(), arc=(), idx=None, applied="", manifest=None):
    root = base / "reg"
    (root / "entries").mkdir(parents=True)
    for s in live:
        (root / "entries" / f"{s}.md").write_text(entry(s), encoding="utf-8")
    if arc:
        (root / ".archive").mkdir()
        for s in arc:
            (root / ".archive" / f"{s}.md").write_text(entry(s), encoding="utf-8")
    (root / "APPLIED.md").write_text("# APPLIED\n\n| 날짜 | ID | 노트 | 처리 |\n|---|---|---|---|\n" + applied, encoding="utf-8")
    if manifest is not None:
        (root / ".eject-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    if idx is not None:
        (root / "INDEX.md").write_text(idx, encoding="utf-8")
    return root


def note(base, *toks, name="v9.9.9.md"):
    p = base / name
    p.write_text("# v9.9.9\n\nCloses: " + ", ".join(toks) + "\n", encoding="utf-8")
    return p


def read(p):
    return p.read_text(encoding="utf-8") if p.is_file() else None


def eject(root, nt, env=None):
    return run(["--root", root, "--note", nt, "--version", "9.9.9"], env)


def manifest_states(root):
    p = root / ".eject-manifest.json"
    try:
        return [r.get("state") for r in json.loads(p.read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        return None


def archived_rows(root):
    """archive slug 를 가리키는 대기열 행 수 — 판정은 fixture 쪽 독립 계산(대상 트리 파서를 쓰지 않는다)."""
    arc = {q.stem for q in (root / ".archive").iterdir()} if (root / ".archive").is_dir() else set()
    t = read(root / "INDEX.md") or ""
    return sum(1 for line in t.splitlines() if line.startswith("| F-") and any(f"entries/{s}.md)" in line for s in arc))


def hook_env(base, mode, extra=None):
    h = base / "hook.py"
    if not h.is_file():
        h.write_text(HOOK, encoding="utf-8")
        (base / "writer.py").write_text(WRITER, encoding="utf-8")
    e = {"FZ_REGISTRY_TEST_HOOK": f"{shlex.quote(PY)} -B {shlex.quote(str(h))}", "EI_HOOK_MODE": mode,
         "EI_HOOK_LOG": str(base / "hook.log"), "EI_WRITER": str(base / "writer.py"),
         "EI_FOREIGN": FOREIGN, "EI_COOP": COOP}
    e.update(extra or {})
    return e


HOOK = r'''
import os, subprocess, sys, time
point, idx = sys.argv[1], sys.argv[2]
with open(os.environ["EI_HOOK_LOG"], "a", encoding="utf-8") as f:
    f.write(point + "\n")
want, _, action = os.environ.get("EI_HOOK_MODE", "").partition(":")
if point != want:
    sys.exit(0)
if action == "append":                      # 잠금을 모르는 writer 가 처음 읽기 뒤에 행을 넣는다
    with open(idx, "a", encoding="utf-8") as f:
        f.write(os.environ["EI_FOREIGN"])
elif action == "tamper":                    # 교체 뒤 비대상 행이 사라진 상태를 만든다
    drop = os.environ["EI_DROP"]
    lines = open(idx, encoding="utf-8").read().splitlines(keepends=True)
    with open(idx, "w", encoding="utf-8") as f:
        f.write("".join(l for l in lines if drop not in l))
elif action == "coop":                      # 마지막 확인 직후 협조 writer 가 같은 잠금을 잡으러 온다
    mark = os.environ["EI_MARK"]
    subprocess.Popen([sys.executable, "-B", os.environ["EI_WRITER"], os.path.join(os.path.dirname(idx), ".fz-registry.lock"),
                      idx, mark], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    end = time.monotonic() + 5
    while not os.path.exists(mark + ".trying") and time.monotonic() < end:
        time.sleep(0.02)
    time.sleep(0.4)                         # writer 가 잠금을 여러 번 시도할 틈
'''

WRITER = r'''
import fcntl, os, sys, time
lock, idx, mark = sys.argv[1:4]
fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o644)
open(mark + ".trying", "w").write("1")
tries, end = 0, time.monotonic() + 8
while True:
    tries += 1
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        break
    except BlockingIOError:
        if time.monotonic() > end:
            open(mark + ".part", "w").write(f"TIMEOUT tries={tries}\n")
            os.replace(mark + ".part", mark)
            sys.exit(1)
        time.sleep(0.05)
with open(idx, "a", encoding="utf-8") as f:
    f.write(os.environ["EI_COOP"])
open(mark + ".part", "w").write(f"DONE tries={tries}\n")
os.replace(mark + ".part", mark)
'''

HOLDER = r'''
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX)
open(sys.argv[2], "w").write(str(os.getpid()))
time.sleep(float(sys.argv[3]))
'''


def start_holder(base, root, secs):
    """별도 프로세스가 잠금을 쥔다 — 같은 프로세스의 다른 fd 로 시험하면 프로세스 종료 해제를 못 잰다."""
    h = base / "holder.py"
    h.write_text(HOLDER, encoding="utf-8")
    mark = base / "held"
    p = subprocess.Popen([PY, "-B", str(h), str(root / LOCK), str(mark), str(secs)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.monotonic() + 5
    while not mark.is_file() and time.monotonic() < end:
        time.sleep(0.02)
    if not mark.is_file():
        p.kill()
        raise Setup("보유자 프로세스가 5초 안에 잠금을 잡지 못했다")
    return p


# ── index 셀 ────────────────────────────────────────────────────────────────
def c_one(b):
    A, Bb, C = "F-001-alpha", "F-002-beta", "F-003-gamma"
    root = reg(b, live=[A, Bb, C], idx=index(row(A), row(Bb), row(C)))
    i0 = read(root / "INDEX.md")
    rc, out, _ = eject(root, note(b, A))
    i1 = read(root / "INDEX.md") or ""
    check("one", rc == 0, f"배출 exit 0 (실제 {rc})", out[-300:])
    check("one", (root / ".archive" / f"{A}.md").is_file(), "엔트리가 archive 로 이동")
    check("one", row(A) not in i1, "배출한 slug 의 대기열 행 0")
    check("one", i1 == i0.replace(row(A), ""), "비대상 줄(행·산문·다른 절) 바이트 불변")
    check("one", "INDEX.md -1행" in out, "지운 행 수 인쇄 (INDEX.md -1행)")
    check("one", "잠금은 협조 writer 끼리만 막는다" in out, "실행 출력이 잠금 밖 쓰기(비협조 Edit) 보장 없음을 알린다")
    check("one", (root / LOCK).is_file(), "협조 writer 잠금 파일 생성(.fz-registry.lock)")


def c_many(b):
    S = ["F-011-a", "F-012-b", "F-013-c", "F-014-d", "F-015-e"]
    root = reg(b, live=S, idx=index(*[row(s) for s in S]))
    i0 = read(root / "INDEX.md")
    rc, out, _ = eject(root, note(b, S[0], S[2], S[4]))
    i1 = read(root / "INDEX.md") or ""
    want = i0
    for s in (S[0], S[2], S[4]):
        want = want.replace(row(s), "")
    check("many", rc == 0, f"배출 exit 0 (실제 {rc})", out[-300:])
    check("many", i1 == want, "대상 3행만 지우고 나머지 바이트 불변")
    check("many", "INDEX.md -3행" in out, "지운 행 수 인쇄 (INDEX.md -3행)")


def c_same_number(b):
    one, two, x, keep = "F-070-one", "F-070-two", "F-071-x", "F-072-keep"
    root = reg(b, live=[two, x, keep], arc=[one], idx=index(row(one), row(two), row(x), row(keep)),
               applied=f"| 9.9.8 | {one} | `v9.9.8.md` | 릴리즈 `Closes:` 로 배출 |\n",
               manifest=[{"version": "9.9.8", "note": "v9.9.8.md", "planned": [one], "state": "done", "ejected": [one]}])
    rc, out, _ = eject(root, note(b, x))
    i1 = read(root / "INDEX.md") or ""
    check("same-number", rc == 0, f"배출 exit 0 (실제 {rc})", out[-300:])
    check("same-number", row(x) not in i1, "배출한 slug 의 행 0")
    check("same-number", row(two) in i1, "같은 번호의 live slug 행 보존(ID 가 아니라 full slug 로 식별)")
    check("same-number", row(one) in i1, "이번 배출과 무관한 예전 배출 행은 eject 가 건드리지 않는다")
    rc, out, _ = run(["--prune-index", root])
    i2 = read(root / "INDEX.md") or ""
    check("same-number", rc == 0, f"--prune-index exit 0 (실제 {rc})", out[-300:])
    check("same-number", row(one) not in i2 and row(two) in i2 and row(keep) in i2,
          "--prune-index 가 archive slug 행만 지우고 같은 번호 live 행은 남긴다")


def c_idempotent(b):
    A, Bb = "F-021-a", "F-022-b"
    root = reg(b, live=[A, Bb], idx=index(row(A), row(Bb)))
    nt = note(b, A)
    rc1, out1, _ = eject(root, nt)
    idx = root / "INDEX.md"
    i1, m1 = idx.read_bytes(), idx.stat().st_mtime_ns
    check("idempotent", rc1 == 0 and row(A).encode() not in i1, "1회차 배출 + 행 삭제", out1[-300:])
    time.sleep(0.05)
    rc2, out2, _ = eject(root, nt)
    check("idempotent", rc2 == 0, f"같은 노트 재실행 exit 0 (실제 {rc2})", out2[-300:])
    check("idempotent", idx.read_bytes() == i1 and idx.stat().st_mtime_ns == m1, "재실행이 INDEX 바이트·mtime 을 바꾸지 않는다")
    check("idempotent", "INDEX.md -0행" in out2, "재실행이 지운 행 0 을 인쇄")
    rc3, out3, _ = run(["--prune-index", root])
    check("idempotent", rc3 == 0 and "INDEX.md -0행" in out3 and idx.read_bytes() == i1 and idx.stat().st_mtime_ns == m1,
          "--prune-index 재실행도 무변경", out3[-300:])


def c_no_index(b):
    A = "F-031-a"
    root = reg(b, live=[A])
    rc, out, _ = eject(root, note(b, A))
    check("no-index", rc == 0, f"INDEX 가 없어도 배출 exit 0 (실제 {rc})", out[-300:])
    check("no-index", "NOTE: INDEX.md 없음" in out, "INDEX 부재를 NOTE 로 알린다(조용히 넘기지 않음)", out[-300:])
    check("no-index", not (root / "INDEX.md").exists(), "없던 INDEX 를 만들지 않는다")
    rc, out, _ = run(["--prune-index", root])
    check("no-index", rc == 2 and "UNRUN:" in out, f"--prune-index 는 INDEX 없으면 UNRUN exit 2 (실제 {rc})", out[-300:])


def c_write_fail(b):
    A, Bb = "F-041-a", "F-042-b"
    root = reg(b, live=[A, Bb], idx=index(row(A), row(Bb)))
    i0 = read(root / "INDEX.md")
    (root / "INDEX.md.tmp").mkdir()        # 교체용 .tmp 자리를 디렉토리로 막아 쓰기를 실패시킨다
    nt = note(b, A)
    rc, out, _ = eject(root, nt)
    check("write-fail", rc == 1, f"INDEX 쓰기 실패는 exit 1 (실제 {rc})", out[-300:])
    check("write-fail", read(root / "INDEX.md") == i0, "실패 시 원본 INDEX 바이트 그대로")
    check("write-fail", (root / ".archive" / f"{A}.md").is_file() and A in (read(root / "APPLIED.md") or "")
          and manifest_states(root) == ["done"], "이동·대장·manifest 는 남았다(복구 가능)")
    (root / "INDEX.md.tmp").rmdir()
    rc, out, _ = eject(root, nt)
    i2 = read(root / "INDEX.md") or ""
    check("write-fail", rc == 0 and row(A) not in i2 and i2 == i0.replace(row(A), ""), "막힘이 풀린 뒤 재실행이 맞춘다", out[-300:])
    check("write-fail", not (root / "INDEX.md.tmp").exists(), ".tmp 를 남기지 않는다")


def c_interrupt(b):
    # (a) 이동 뒤 대장·확정 전에 끊김 — pending 레코드 · archive 에 파일 · 대장에 없음 · INDEX 행 잔존
    A, Bb = "F-051-moved", "F-052-next"
    ba = b / "a"
    ba.mkdir()
    root = reg(ba, live=[Bb], arc=[A], idx=index(row(A), row(Bb)),
               manifest=[{"version": "9.9.8", "note": "v9.9.8.md", "planned": [A], "state": "pending", "ejected": []}])
    rc, out, _ = eject(root, note(ba, Bb))
    i1 = read(root / "INDEX.md") or ""
    ap = read(root / "APPLIED.md") or ""
    check("interrupt-recover", rc == 0, f"중단 뒤 다음 배출 exit 0 (실제 {rc})", out[-300:])
    check("interrupt-recover", A in ap and Bb in ap and manifest_states(root) == ["done", "done"], "대장 복구 + 레코드 확정")
    check("interrupt-recover", row(A) not in i1 and row(Bb) not in i1, "복구한 slug 와 새 배출 slug 의 행 0")
    # (b) 확정 뒤 INDEX 정리 전에 끊김 — 같은 노트 재실행이 skip 하면서 행을 지운다
    C, D = "F-053-done", "F-054-live"
    bb = b / "b"
    bb.mkdir()
    root = reg(bb, live=[D], arc=[C], idx=index(row(C), row(D)),
               applied=f"| 9.9.9 | {C} | `v9.9.9.md` | 릴리즈 `Closes:` 로 배출 |\n",
               manifest=[{"version": "9.9.9", "note": "v9.9.9.md", "planned": [C], "state": "done", "ejected": [C]}])
    rc, out, _ = eject(root, note(bb, C))
    i1 = read(root / "INDEX.md") or ""
    check("interrupt-recover", rc == 0 and "skip" in out, f"확정 뒤 끊긴 배출의 재실행 exit 0 + skip (실제 {rc})", out[-300:])
    check("interrupt-recover", row(C) not in i1 and row(D) in i1, "재실행이 남은 행을 지우고 live 행은 남긴다")


def c_reconcile_zero(b):
    A, L, K = "F-061-landed", "F-062-lost", "F-063-live"
    root = reg(b, live=[K], arc=[A], idx=index(row(A), row(K)),
               manifest=[{"version": "9.9.8", "note": "v9.9.8.md", "planned": [A, L], "state": "pending", "ejected": []}])
    rc, out, _ = run(["--resolve-pending", root])
    check("reconcile-zero", rc == 0, f"--resolve-pending exit 0 (실제 {rc})", out[-300:])
    check("reconcile-zero", A in (read(root / "APPLIED.md") or "") and manifest_states(root) == ["done"], "대장 복구 + 확정")
    check("reconcile-zero", archived_rows(root) == 0, f"복구 뒤 archive slug 의 대기열 행 0 (실제 {archived_rows(root)})")
    check("reconcile-zero", row(K) in (read(root / "INDEX.md") or ""), "live 행 보존")


def c_read_replace(b):
    # (a) 처음 읽기 뒤 · 교체 직전 재확인 전에 잠금 밖 writer 가 행을 넣는다 → 교체하지 않고 비0
    A, Bb = "F-081-a", "F-082-b"
    ba = b / "a"
    ba.mkdir()
    root = reg(ba, live=[A, Bb], idx=index(row(A), row(Bb)))
    nt = note(ba, A)
    rc, out, _ = eject(root, nt, hook_env(ba, "read:append"))
    i1 = read(root / "INDEX.md") or ""
    log = read(ba / "hook.log") or ""
    check("read-replace", "read" in log.split(), "시험 훅이 읽기 직후 지점에서 불렸다", f"hook.log={log!r}")
    check("read-replace", rc == 1 and "바뀌었다" in out, f"읽은 뒤 바뀐 INDEX 는 교체하지 않고 exit 1 (실제 {rc})", out[-300:])
    check("read-replace", FOREIGN in i1 and row(A) in i1, "다른 writer 의 행 생존 · 대상 행도 그대로(교체 안 함)")
    check("read-replace", not (root / "INDEX.md.tmp").exists(), ".tmp 를 남기지 않는다")
    rc, out, _ = eject(root, nt)
    i2 = read(root / "INDEX.md") or ""
    check("read-replace", rc == 0 and FOREIGN in i2 and row(A) not in i2, "재실행이 바뀐 내용 기준으로 맞춘다", out[-300:])
    # (b) 교체 뒤 비대상 행이 달라지면 비0 + 원본 백업 경로
    C, D = "F-083-c", "F-084-d"
    bb = b / "b"
    bb.mkdir()
    root = reg(bb, live=[C, D], idx=index(row(C), row(D)))
    raw0 = (root / "INDEX.md").read_bytes()
    rc, out, _ = eject(root, note(bb, C), hook_env(bb, "replaced:tamper", {"EI_DROP": f"entries/{D}.md"}))
    bak = [l.split("원본 백업: ", 1)[1].strip() for l in out.splitlines() if "원본 백업: " in l]
    check("read-replace", rc == 1 and bool(bak), f"교체 뒤 비대상 행 대조 불일치는 exit 1 + 백업 경로 출력 (실제 {rc})", out[-300:])
    check("read-replace", bool(bak) and pathlib.Path(bak[0]).is_file() and pathlib.Path(bak[0]).read_bytes() == raw0,
          "백업 파일 = 교체 전 원본 바이트")


def c_coop_writer(b):
    A, Bb = "F-091-a", "F-092-b"
    root = reg(b, live=[A, Bb], idx=index(row(A), row(Bb)))
    mark = b / "writer.mark"
    rc, out, _ = eject(root, note(b, A), hook_env(b, "replace:coop", {"EI_MARK": str(mark)}))
    log = read(b / "hook.log") or ""
    called = "replace" in log.split()
    check("coop-writer", called, "시험 훅이 마지막 확인 직후(교체 직전) 지점에서 불렸다", f"hook.log={log!r}")
    end = time.monotonic() + (8 if called else 0)
    while called and not mark.is_file() and time.monotonic() < end:
        time.sleep(0.05)
    m = read(mark) or ""
    tries = int(m.split("tries=")[1]) if m.startswith("DONE tries=") else 0
    i1 = read(root / "INDEX.md") or ""
    check("coop-writer", rc == 0, f"배출 exit 0 (실제 {rc})", out[-300:])
    check("coop-writer", tries >= 2, f"협조 writer 가 잠금을 기다렸다(시도 {tries}회 — 1회면 잠금 밖에서 끼어들었다)", m.strip())
    check("coop-writer", COOP in i1 and row(A) not in i1, "협조 writer 의 행 유실 0 · 대상 행 0")


def c_entries_variant(b):
    A, Bb, C, D = "F-101-a", "F-102-b", "F-103-c", "F-104-d"
    old = "| F-102 | 2026-10-01 | `hole` | x | 옛 이름 링크 | self | open | [F-102](entries/F-102-old-name.md) |\n"
    root = reg(b, live=[C, D], arc=[A, Bb], idx=index(row(A, dot=True), old, row(C), row(D, dot=True)))
    rc, out, _ = run(["--prune-index", root])
    i1 = read(root / "INDEX.md") or ""
    check("entries-variant", rc == 0, f"--prune-index exit 0 (실제 {rc})", out[-300:])
    check("entries-variant", row(A, dot=True) not in i1, "`./entries/` 링크 행도 같은 파일로 보고 지운다")
    check("entries-variant", old in i1 and "slug 변형" in out, "다른 slug 링크(옛 이름)는 지우지 않고 WARN", out[-300:])
    check("entries-variant", "./entries/" in out, "`./entries/` 정규화를 WARN 으로 알린다", out[-300:])
    rc, out, _ = eject(root, note(b, D))
    i2 = read(root / "INDEX.md") or ""
    check("entries-variant", rc == 0 and row(D, dot=True) not in i2 and row(C) in i2, "배출도 `./entries/` 행을 지운다", out[-300:])


def c_audit_residual(b):
    A, Bb = "F-111-legacy", "F-112-live"
    root = reg(b, live=[Bb], arc=[A], idx=index(row(A), row(Bb)),
               applied=f"| 9.9.8 | {A} | `v9.9.8.md` | 릴리즈 `Closes:` 로 배출 |\n",
               manifest=[{"version": "9.9.8", "note": "v9.9.8.md", "planned": [A], "state": "done", "ejected": [A]}])
    rc, out, _ = run(["--audit", root])
    lines = [l.split() for l in out.splitlines()]
    hit = [l for l in lines if l[:2] == ["INDEX", "잔존"] and l[2:3] == [A]]
    check("audit-residual", bool(hit), "--audit 이 배출분의 INDEX 잔존 행을 slug 로 지목", out[-300:])
    check("audit-residual", not any(l[:2] == ["INDEX", "잔존"] and l[2:3] == [Bb] for l in lines), "live 행은 잔존이 아니다")
    run(["--prune-index", root])
    rc, out, _ = run(["--audit", root])
    check("audit-residual", "INDEX 잔존 0" in out and A not in out.split("INDEX 잔존 0", 1)[-1],
          "--prune-index 뒤 잔존 0", out[-300:])


# ── telemetry 셀 ────────────────────────────────────────────────────────────
def c_telemetry(b):
    S = ["F-121-a", "F-122-b", "F-123-c", "F-124-d", "F-125-e"]
    root = reg(b, live=S, idx=index(*[row(s) for s in S]))
    (b / "projects").mkdir()

    def report(tag):
        out_json = b / f"tel-{tag}.json"
        rc, out, _ = run(["--findings-dir", root / "entries", "--projects-root", b / "projects", "--telemetry-dir", b / "tel",
                          "--plugin-root", TREE, "--since", "2026-01-01", "--until", "2026-12-31", "--json", "--out", out_json],
                         script=TEL)
        try:
            f = json.loads(out_json.read_text(encoding="utf-8"))["findings"]
            return rc, (f["n"], f["total_files"], f["skipped_no_frontmatter"]), out
        except (OSError, ValueError, KeyError, TypeError):
            return rc, None, out

    rc0, v0, o0 = report("before")
    rc, out, _ = eject(root, note(b, S[1], S[3]))
    rc1, v1, o1 = report("after")
    check("telemetry", rc0 == 0 and v0 == (5, 5, 0), f"배출 전 findings n·파일·frontmatter 없음 = 5·5·0 (실제 rc={rc0} {v0})", o0[-200:])
    check("telemetry", rc == 0, f"배출 exit 0 (실제 {rc})", out[-300:])
    check("telemetry", rc1 == 0 and v1 == (3, 3, 0), f"배출 뒤 = 3·3·0 — INDEX 정리·잠금 파일이 집계를 흔들지 않는다 (실제 rc={rc1} {v1})",
          o1[-200:])


# ── lock 셀 ─────────────────────────────────────────────────────────────────
def c_lock_sigkill(b):
    A = "F-131-a"
    root = reg(b, arc=[A], idx=index(row(A)))
    p = start_holder(b, root, 60)
    p.send_signal(signal.SIGKILL)
    p.wait(timeout=10)
    rc, out, dt = run(["--prune-index", root])
    check("lock-sigkill", rc == 0 and row(A) not in (read(root / "INDEX.md") or ""),
          f"SIGKILL 된 보유자 뒤 잠금 획득 · 정리 수행 (실제 rc={rc})", out[-300:])
    check("lock-sigkill", dt < 1.8, f"상한까지 기다리지 않는다 ({dt:.2f}s < 1.8s)")
    check("lock-sigkill", (root / LOCK).is_file(), "잠금 파일을 지우지 않는다")


def c_lock_live(b):
    A, Bb = "F-141-a", "F-142-live"
    root = reg(b, live=[Bb], arc=[A], idx=index(row(A), row(Bb)))
    i0 = read(root / "INDEX.md")
    p = start_holder(b, root, 30)
    try:
        rc, out, dt = run(["--prune-index", root], {"FZ_REGISTRY_LOCK_WAIT": "1"})
        check("lock-live-holder", rc != 0 and "UNRUN:" in out and "잠금" in out,
              f"살아 있는 보유자면 --prune-index 비0 + 잠금 UNRUN (실제 {rc})", out[-300:])
        check("lock-live-holder", dt >= 0.9, f"상한(1s)까지 기다린 뒤 끝난다 ({dt:.2f}s)")
        rc, out, _ = eject(root, note(b, Bb), {"FZ_REGISTRY_LOCK_WAIT": "1"})
        check("lock-live-holder", rc != 0 and (root / "entries" / f"{Bb}.md").is_file(),
              f"배출도 잠금을 존중 — 비0 · 이동 0 (실제 {rc})", out[-300:])
        check("lock-live-holder", read(root / "INDEX.md") == i0, "보유자가 있는 동안 INDEX 무변경")
    finally:
        p.kill()
        p.wait(timeout=10)
    rc, out, _ = run(["--prune-index", root])
    check("lock-live-holder", rc == 0 and row(A) not in (read(root / "INDEX.md") or ""), f"보유자가 끝나면 획득 (실제 {rc})", out[-300:])
    check("lock-live-holder", (root / LOCK).is_file(), "잠금 파일을 지우지 않는다")


def c_lock_stale(b):
    A = "F-151-a"
    root = reg(b, arc=[A], idx=index(row(A)))
    stale = "pid 4242 — 보유자 없이 남은 잠금 파일\n"
    (root / LOCK).write_text(stale, encoding="utf-8")
    rc, out, dt = run(["--prune-index", root])
    check("lock-stale-file", rc == 0 and row(A) not in (read(root / "INDEX.md") or ""),
          f"파일만 남은 상태에서 잠금 획득 · 정리 수행 (실제 rc={rc})", out[-300:])
    check("lock-stale-file", dt < 1.8, f"파일 존재를 잠김으로 읽지 않는다 ({dt:.2f}s < 1.8s)")
    check("lock-stale-file", read(root / LOCK) == stale, "잠금 파일을 지우거나 고쳐 쓰지 않는다")


# ── applied-records 셀 ──────────────────────────────────────────────────────
AP_INPUTS = [
    "# APPLIED\n\n| 날짜 | ID | failure_class | 한 줄 | 처리 | 반영처 |\n|---|---|---|---|---|---|\n"
    "| 2026-08-24 | **F-002** | `x` | 설명 | `applied` | 비고 |\n"
    "| 2026-08-24 | F-003 | `x` | 설명 | `applied` | 참고: F-300 도 같은 축이다 |\n"
    "| 2026-08-31 | F-050 false-alarm (works, 08-31) | x | y | works | z |\n"
    "| F-005 | 2026-08-12 | 첫 칸이 ID 인 행 |\n"
    "- 주의: F-077 이 지적한 홀이 재발했다 (산문 언급)\n"
    "=== INDEX lines 1-8 ===\n"
    "| F-154 | 2026-09-10 | 덤프된 INDEX 행 |\n\n"
    "| 4.38.0 | F-031-candidate-signal-never-promoted | `v4.38.0.md` | 릴리즈 `Closes:` 로 배출 |\n"
    "| 4.42.0 | F-348-wrapper-sandbox-mode | `v4.42.0-closes-late.md` | 릴리즈 `Closes:` 로 배출 |\n"
    "| 1 | F-032-one | `n` | 중단 복구 |\n"
    "| 9.9.9 | **F-040-bold-slug** | `n` | 수동 확정 복구 |\n"
    "| 2026-01-01 | F-032 | x | applied |\n"
    "| 날짜 | ID | 노트 | 처리 |\n",
    "# APPLIED\n\n| 날짜 | ID | 노트 | 처리 |\n|---|---|---|---|\n",
    "",
    None,
]
# 기준 트리(be8c871)에서 잰 값 — 배출 4열 · 레거시 날짜 우선 6열 · 굵은 ID · 산문 · 비고 칸 언급 · 덤프 행
AP_GOLDEN = [
    [["F-031-candidate-signal-never-promoted", "F-032-one", "F-040-bold-slug", "F-348-wrapper-sandbox-mode"],
     ["F-002", "F-003", "F-005", "F-032", "F-050", "F-154"]],
    [[], []], [[], []], [[], []],
]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def records(mod, b):
    out = []
    for i, t in enumerate(AP_INPUTS):
        p = b / f"APPLIED-{i}.md"
        if t is not None:
            p.write_text(t, encoding="utf-8")
        a, n = mod.applied_records(p)
        out.append([sorted(a), sorted(n)])
    return out


def c_applied_records(b):
    cand = load(EJ, "eject_tree")
    got = records(cand, b)
    check("applied-records", got == AP_GOLDEN, "applied_records 결과 = 고정 기대값", json.dumps(got, ensure_ascii=False)[:300])
    if BASE:
        base = load(pathlib.Path(BASE) / "scripts" / "eject_findings.py", "eject_base")
        check("applied-records", records(base, b) == got, "applied_records 결과 = 기준 트리 결과")
    dead = "applied_" + "ids"                  # 낱말을 쪼개 적는다 — 트리 전체 낱말 0 검사의 대상이다
    check("applied-records", not hasattr(cand, dead), "호출처 없던 번호 전용 함수가 사라졌다")


CELLS = {
    "one": c_one, "many": c_many, "same-number": c_same_number, "idempotent": c_idempotent, "no-index": c_no_index,
    "write-fail": c_write_fail, "interrupt-recover": c_interrupt, "reconcile-zero": c_reconcile_zero,
    "read-replace": c_read_replace, "coop-writer": c_coop_writer, "entries-variant": c_entries_variant,
    "audit-residual": c_audit_residual, "telemetry": c_telemetry,
    "lock-sigkill": c_lock_sigkill, "lock-live-holder": c_lock_live, "lock-stale-file": c_lock_stale,
    "applied-records": c_applied_records,
}
GROUPS = {
    "index": ["one", "many", "same-number", "idempotent", "no-index", "write-fail", "interrupt-recover", "reconcile-zero",
              "read-replace", "coop-writer", "entries-variant", "audit-residual"],
    "lock": ["lock-sigkill", "lock-live-holder", "lock-stale-file"],
}
picked = []
for tok in [t for t in CELLS_ARG.replace(" ", ",").split(",") if t] or list(CELLS):
    names = GROUPS.get(tok, [tok])
    for n in names:
        if n not in CELLS:
            print(f"SETUP 알 수 없는 셀: {tok} (셀: {', '.join(CELLS)} · 묶음: {', '.join(GROUPS)})")
            sys.exit(3)
        if n not in picked:
            picked.append(n)

t0 = time.monotonic()
for name in picked:
    with tempfile.TemporaryDirectory(prefix=f"eject-index-{name}-") as d:
        try:
            CELLS[name](pathlib.Path(d))
        except Setup as e:
            print(f"SETUP {name}: {e}")
            sys.exit(3)
print()
print(f"eject-index: {'전건 통과' if not FAIL else f'실패 {len(FAIL)}건'} — 셀 {len(picked)}개 · {time.monotonic() - t0:.1f}s · tree {TREE.name}")
sys.exit(1 if FAIL else 0)
PY
a=$?
# ⛔ 단언기 자체의 고장(0 · 1 · 3 밖)은 준비 실패로 바꾼다 — 그대로 두면 기능 부재 재현처럼 읽힌다
[ "$a" -eq 0 ] || [ "$a" -eq 1 ] || [ "$a" -eq 3 ] || { echo "SETUP 단언기 비정상 종료 $a"; exit 3; }
exit "$a"
