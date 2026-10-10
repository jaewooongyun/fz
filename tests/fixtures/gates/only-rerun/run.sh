#!/bin/bash
# diff-parse: not-a-diff — `^- ` 정규식은 원장 게이트 줄(- [ ] G1:)을 찾는다. diff 를 다루지 않는다.
# `--only` 재실행 fixture (F-330) — 이름을 댄 충족 게이트를 판정기가 실제로 다시 돌리는지 동작으로 본다.
# CHECK 는 셀 폴더의 카운터 파일을 올리고 `run=<n>` 을 출력한다 — 증거 레코드에 시각 필드가 없어서, 재실행 여부를
# 카운터(프로세스가 돌았다)와 증거 `output=` 의 run 값(원장 도장이 새로 찍혔다) 두 곳에서 관측한다.
#   only-reruns-met          충족 G1 에 `--only G1` → PASS · reran 1 · stamp-only 0 · 카운터 1→2 · 증거 run=1→run=2  (판별)
#   only-sees-stale          충족 뒤 CHECK 가 읽는 파일을 망가뜨리고 `--only G1` → FAIL exit 1 · `--status` 도 미충족  (판별 — F-330 오라클)
#   only-named-subset        G1 · G2 충족, `--only G1` → G1 만 다시 돈다 · G2 카운터 · 증거 불변                     (판별)
#   default-run-stamp-only   선택자 없는 기본 실행은 그대로 — MET 줄 · stamp-only 1 · 카운터 · 바이트 불변             (대조)
#   status-only-no-run       `--status --only G1` 은 CHECK 를 돌리지 않는다 · 바이트 불변                              (대조)
#   reverify-only-reruns     `--reverify --only G1` 은 원래대로 다시 돈다                                              (대조)
#   closed-only-noop         STATE closed 원장에 `--only G1` · 기본 실행 → `STATE closed — no-op` · 카운터 · 바이트 불변  (대조)
# 기준 트리(4.44.0)는 `--only` 로 이름을 댄 충족 게이트를 도장만 읽고 넘긴다 — 판별 셀 3개가 FAIL 해 exit 1.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 파일 · 임시 폴더 · 단언기 고장 · 돈 셀 집합이 기대 집합과 다름)
#   ⛔ 끝 줄은 실제로 끝까지 돈 셀 목록과 수다(`CELLS n=<돈 수>/<기대 수> ran=…`). 셀을 하나 지우거나 건너뛰면 집합이 달라져 3 이다.
# ⛔ 셀마다 임시 ROOT. 바깥 FZ_GATES_LEDGER · FZ_GATES_OFF · FZ_GATES_TRACE 는 자식에게 넘기지 않는다.
# usage: run.sh [--scripts <scripts 폴더>]   (기본: 이 fixture 가 든 트리의 scripts/ — health-check 글롭이 인자 없이 부른다)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
S="$(cd "$HERE/../../../../scripts" 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --scripts) [ $# -ge 2 ] || { echo "SETUP --scripts 에 경로가 없다"; exit 3; }
               S="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --scripts 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -n "$S" ] && [ -f "$S/gate_check.py" ] || { echo "SETUP gate_check.py 없음: ${S:-?}"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$S" <<'PY'
import os, pathlib, re, shutil, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

GC = pathlib.Path(sys.argv[1]) / "gate_check.py"
PY = sys.executable
EXPECTED = ("only-reruns-met", "only-sees-stale", "only-named-subset", "default-run-stamp-only",
            "status-only-no-run", "reverify-only-reruns", "closed-only-noop")
RAN, FAIL = [], []
ENV = {k: v for k, v in os.environ.items() if k not in ("FZ_GATES_LEDGER", "FZ_GATES_OFF", "FZ_GATES_TRACE")}
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def gate(gid):
    """카운터 `n.<gid>` 를 올리고 `target` 이 정확히 `ok` 한 줄일 때만 통과하는 게이트. cwd 는 ROOT 다."""
    return (f"- [ ] {gid}: 카운터 게이트 {gid}\n"
            f"  CRITERION: {gid} 를 돌릴 때마다 카운터가 오르고 target 이 ok 면 통과한다\n"
            f"  CHECK: n=$(cat n.{gid} 2>/dev/null || echo 0); n=$((n+1)); echo $n > n.{gid}; "
            f"grep -qx ok target && echo \"{gid} ok run=$n\"\n"
            f"  EXPECT: {gid} ok\n"
            f"  EVIDENCE: pending\n")


class Cell:
    def __init__(self, name, gates=("G1",)):
        self.name, self.gates = name, gates

    def __enter__(self):
        if self.name not in EXPECTED:
            raise Setup(f"기대 집합에 없는 셀 {self.name}")
        try:
            self.r = pathlib.Path(os.path.realpath(tempfile.mkdtemp(prefix="only-rerun.")))
            (self.r / "gates").mkdir()
            (self.r / "target").write_text("ok\n", encoding="utf-8")
            self.led = self.r / "gates" / "plan.md"
            body = "\n".join(gate(g) for g in self.gates)
            self.led.write_text(f"# Gates: only-rerun {self.name}\nROOT: {self.r}\nSTATE: active\n"
                                f"Scope: --only 재실행 fixture\n\n{body}", encoding="utf-8")
        except OSError as e:
            raise Setup(f"{self.name} 임시 원장 준비 실패: {e}")
        rc, out = self.gc("--finalize")
        if rc != 0:
            raise Setup(f"{self.name} --finalize 실패 rc={rc} {out[-300:]}")
        return self

    def __exit__(self, et, ev, tb):
        shutil.rmtree(self.r, ignore_errors=True)
        if et is None:
            RAN.append(self.name)      # 끝까지 돈 셀만 센다 — 중간 예외는 Setup(3) 으로 올라간다
        return False

    def gc(self, *args):
        try:
            p = subprocess.run([PY, "-B", str(GC), *args, str(self.led)], cwd=str(self.r), env=ENV,
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise Setup(f"{self.name} 판정기 실행 실패 {args}: {e}")
        return p.returncode, p.stdout + p.stderr

    def count(self, gid="G1"):
        f = self.r / f"n.{gid}"
        return int(f.read_text(encoding="utf-8").strip()) if f.exists() else 0

    def text(self):
        return self.led.read_text(encoding="utf-8")

    def evidence(self, gid="G1"):
        m = re.search(rf"^- \[[ x]\] {re.escape(gid)}:.*?^  EVIDENCE: ([^\n]*)$", self.text(), re.M | re.S)
        return m.group(1).strip() if m else ""

    def met_once(self, *args):
        """첫 실행으로 충족을 만든다 — 이 단계가 안 되면 셀이 재는 대상 앞에서 막힌 것이라 준비 실패다."""
        rc, out = self.gc(*args)
        if rc != 0 or any(self.count(g) != 1 for g in self.gates) or "sig=" not in self.evidence():
            raise Setup(f"{self.name} 첫 충족 실패 rc={rc} {out[-300:]}")


try:
    # ── only-reruns-met — 이름을 댄 충족 게이트가 다시 돌고 도장이 새로 찍힌다 ───────────────
    with Cell("only-reruns-met") as c:
        c.met_once("--only", "G1")
        e1 = c.evidence()
        rc, out = c.gc("--only", "G1")
        e2 = c.evidence()
        check(c.name, rc == 0 and "PASS  G1" in out, "충족 G1 에 --only G1 → PASS 줄(다시 돌았다)", f"rc={rc} {out[-300:]}")
        check(c.name, "reran: 1, stamp-only: 0" in out, "요약 reran: 1, stamp-only: 0", out[-300:])
        check(c.name, c.count() == 2, "CHECK 프로세스가 다시 돌았다(카운터 1→2)", f"카운터={c.count()}")
        check(c.name, "run=1" in e1 and "run=2" in e2 and e1 != e2, "증거가 새로 찍혔다(output run=1→run=2)",
              f"전={e1[-120:]} · 후={e2[-120:]}")
        rc, out = c.gc("--status")
        check(c.name, rc == 0, "새 증거로 --status 충족", f"rc={rc} {out[-200:]}")

    # ── only-sees-stale — 충족 뒤 대상이 바뀌면 --only 가 그것을 본다(F-330 오라클) ───────────────
    with Cell("only-sees-stale") as c:
        c.met_once("--only", "G1")
        (c.r / "target").write_text("changed\n", encoding="utf-8")
        rc, out = c.gc("--only", "G1")
        check(c.name, rc == 1 and "FAIL  G1" in out, "대상 변경 뒤 --only G1 → FAIL exit 1(옛 도장으로 통과하지 않는다)",
              f"rc={rc} {out[-300:]}")
        check(c.name, c.count() == 2, "CHECK 가 다시 돌았다(카운터 1→2)", f"카운터={c.count()}")
        rc, out = c.gc("--status")
        check(c.name, rc == 1, "떨어진 게이트는 --status 에서도 미충족", f"rc={rc} {out[-200:]}")

    # ── only-named-subset — 이름을 댄 게이트만 다시 돈다 ─────────────────────────────────────
    with Cell("only-named-subset", ("G1", "G2")) as c:
        c.met_once()
        g2 = c.evidence("G2")
        rc, out = c.gc("--only", "G1")
        check(c.name, rc == 0 and "PASS  G1" in out and "reran: 1, stamp-only: 0" in out,
              "--only G1 → G1 만 PASS · reran 1", f"rc={rc} {out[-300:]}")
        check(c.name, c.count("G1") == 2 and c.count("G2") == 1, "G1 카운터 2 · 이름 안 댄 G2 카운터 1",
              f"G1={c.count('G1')} G2={c.count('G2')}")
        check(c.name, c.evidence("G2") == g2, "G2 증거 불변", c.evidence("G2")[-120:])

    # ── default-run-stamp-only — 선택자 없는 기본 실행은 바뀌지 않는다 ──────────────────────────
    with Cell("default-run-stamp-only") as c:
        c.met_once()
        before = c.text()
        rc, out = c.gc()
        check(c.name, rc == 0 and "MET   G1" in out and "reran: 0, stamp-only: 1" in out,
              "기본 실행 → MET 줄 · reran: 0, stamp-only: 1", f"rc={rc} {out[-300:]}")
        check(c.name, c.count() == 1 and c.text() == before, "CHECK 안 돎(카운터 1) · 원장 바이트 불변", f"카운터={c.count()}")

    # ── status-only-no-run — 판정 전용 호출은 돌리지 않는다 ───────────────────────────────────
    with Cell("status-only-no-run") as c:
        c.met_once("--only", "G1")
        before = c.text()
        rc, out = c.gc("--status", "--only", "G1")
        check(c.name, rc == 0 and c.count() == 1 and c.text() == before,
              "--status --only G1 → exit 0 · 카운터 1 · 바이트 불변", f"rc={rc} 카운터={c.count()} {out[-200:]}")

    # ── reverify-only-reruns — 기존 재실행 경로는 그대로 ─────────────────────────────────────
    with Cell("reverify-only-reruns") as c:
        c.met_once("--only", "G1")
        rc, out = c.gc("--reverify", "--only", "G1")
        check(c.name, rc == 0 and "PASS  G1" in out and c.count() == 2,
              "--reverify --only G1 → PASS · 카운터 2", f"rc={rc} 카운터={c.count()} {out[-200:]}")

    # ── closed-only-noop — 닫힌 원장은 새 재실행 규칙에도 no-op ───────────────────────────────
    with Cell("closed-only-noop") as c:
        c.met_once("--only", "G1")
        for tgt in ("ready_for_review", "closed"):
            rc, out = c.gc("--set-state", tgt)
            if rc != 0:
                raise Setup(f"{c.name} --set-state {tgt} 실패 rc={rc} {out[-300:]}")
        before = c.text()
        for args in (("--only", "G1"), ()):
            rc, out = c.gc(*args)
            check(c.name, rc == 0 and "STATE closed — no-op" in out and c.count() == 1 and c.text() == before,
                  f"closed 원장 {' '.join(args) or '기본 실행'} → no-op · 카운터 1 · 바이트 불변",
                  f"rc={rc} 카운터={c.count()} {out[-200:]}")
except Setup as e:
    print(f"SETUP {e}")
    sys.exit(3)

print()
print(f"SUMMARY fail={len(FAIL)}")
for f in FAIL:
    print(f"  FAIL {f}")
missing, extra = sorted(set(EXPECTED) - set(RAN)), sorted(set(RAN) - set(EXPECTED))
dup = sorted({x for x in RAN if RAN.count(x) > 1})
if missing or extra or dup:
    print(f"CELLS-MISMATCH missing={','.join(missing) or '-'} extra={','.join(extra) or '-'} dup={','.join(dup) or '-'}")
print(f"CELLS n={len(RAN)}/{len(EXPECTED)} ran={','.join(RAN)}")
sys.exit(3 if (missing or extra or dup) else (1 if FAIL else 0))
PY
