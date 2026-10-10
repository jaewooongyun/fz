#!/bin/bash
# 원장 발견 한도 fixture (F-378 · F-404) — 한 cwd 아래 원장이 많아도 이 세션의 미충족 원장이 조용히 빠지지 않는지 동작으로 본다.
#   n1-own1 · n9-own9 · n10-own10 · n80-own80   원장 N개(전부 미충족) 중 사전순 **마지막**이 소유 → 훅이 그 원장으로 막는다 ·
#                         `--discover` 가 N건 전부를 보고 소유 원장 경로를 낸다(exit 0 불변) · 남의 원장 판정 상한을 넘으면 그 수를 진단
#   n8-own8 · n9-own8     회귀 · 대조 — 8개 이하 / 8번째 소유는 지금도 막힌다(출력 · 종료 불변)
#   own4-slow             소유 4개 + 남의 원장 3개 · 느린 판정기(셀 안 shim) · 예산 축소(FZ_GATES_HOOK_BUDGET_S) → 소유 원장을 먼저
#                         판정하고(남의 원장보다 앞) 예산이 다해 못 본 소유 원장이 남으면 통과하지 않는다(미판정 수 · 이유)
#   own4-budget0          소유 4개 · 예산 0 → `소유 원장 4개 미판정` 으로 차단 · 루프 방어는 그대로(2회 막고 3회째 통과)
#   foreign-only-cap      남의 원장 12개뿐 → 통과하되 상한(8) 밖 4개를 '미판정' 수로 남긴다(말없이 자르지 않는다)
#   discover-invalid-last 원장 10개 중 마지막이 계약 위반 → `--discover` exit 3 · `계약위반 1`(자르면 위반이 안 보여 exit 0)
#   discover-unreadable   원장 9개 중 마지막을 못 읽음 → `--discover` exit 0 · `원장 9건` · `미판정 1`
# 기준 트리(4.44.0)는 발견을 8개에서 잘라(`MAX_DISCOVERED`) 뒤쪽 소유 원장이 빠진 채 훅 exit 0 · `--discover` '원장 8건' 이고,
#   남의 원장을 먼저 판정하며 예산 노브를 모른다 → exit 1.
# ⛔ 셀 집합 대조(F-408): 실제로 돈 셀(단언 1개 이상)의 이름 · 횟수가 EXPECTED_CELLS 와 다르면 FAIL — 끝 줄 `CELLS n=<수> ran=<…>`.
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 스크립트 · 임시 폴더 · 원장 준비 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 스크립트 exit 1' 게이트가 결함 재현 없이 통과한다 — 그래서 3 이다(미처리 예외도 3).
# ⛔ 셀마다 임시 cwd · 임시 HOME · 고유 session_id. 바깥 FZ_GATES_LEDGER · FZ_GATES_OFF · FZ_GATES_TRACE · FZ_GATES_HOOK_BUDGET_S 는
#    자식에게 넘기지 않는다. 느린 판정기는 셀 안 shim(훅 사본 + 판정기 위임 래퍼)이라 대상 scripts 폴더를 바꾸지 않는다.
# usage: run.sh [--scripts <scripts 폴더>]   (기본: 이 fixture 가 든 트리의 scripts/ — health-check 글롭이 인자 없이 부른다)
set -u
if [ -n "${FZ_DISCOVER_LIMIT_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 discover-limit 가 도는 중"
  exit 2
fi
S="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../scripts" 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --scripts) [ $# -ge 2 ] || { echo "SETUP --scripts 에 경로가 없다"; exit 3; }
               S="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --scripts 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -n "$S" ] && [ -f "$S/gate_stop_hook.py" ] && [ -f "$S/gate_check.py" ] \
  || { echo "SETUP gate_stop_hook.py · gate_check.py 없음: ${S:-?}"; exit 3; }

FZ_DISCOVER_LIMIT_FIXTURE=1 PYTHONDONTWRITEBYTECODE=1 python3 -B - "$S" <<'PY'
import importlib.util, json, os, pathlib, re, shutil, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

SCRIPTS = pathlib.Path(sys.argv[1])
GC, HOOK = SCRIPTS / "gate_check.py", SCRIPTS / "gate_stop_hook.py"
PY = sys.executable
MAX_BLOCKS, FOREIGN_MAX = 2, 8          # 계약 값 — 훅 루프 방어 · 남의 원장 판정 상한. 훅 상수를 import 하지 않는다
BUDGET_ENV = "FZ_GATES_HOOK_BUDGET_S"
DROP_ENV = ("FZ_GATES_LEDGER", "FZ_GATES_OFF", "FZ_GATES_TRACE", BUDGET_ENV)
FAIL, CHECKS, RAN = [], [], []
for _k in DROP_ENV:            # 이 프로세스 안의 판정기 호출(남의 원장 확정)도 바깥 원장 지정 · 추적을 받지 않는다
    os.environ.pop(_k, None)
EXPECTED_CELLS = {
    "n1-own1": 1, "n9-own9": 1, "n10-own10": 1, "n80-own80": 1, "n8-own8": 1, "n9-own8": 1,
    "own4-slow": 1, "own4-budget0": 1, "foreign-only-cap": 1, "discover-invalid-last": 1, "discover-unreadable": 1,
}

# 느린 판정기 — 진짜 판정기에 위임하는 래퍼. 모듈로 불리면(훅의 원장 발견) 진짜 모듈 속성을 그대로 내보내고,
# 명령으로 불리면(훅의 `--status` 판정) 호출을 기록하고 잠깐 잔 뒤 진짜 판정기로 exec 한다.
SHIM = '''import os as _os, sys as _sys
_REAL = {real!r}
if __name__ == "__main__":
    _log = _os.environ.get("FZ_DL_JUDGE_LOG")
    if _log:
        with open(_log, "a", encoding="utf-8") as _f:
            _f.write(" ".join(_sys.argv[1:]) + "\\n")
    import time as _t
    _t.sleep(float(_os.environ.get("FZ_DL_JUDGE_SLEEP") or 0))
    _os.execv(_sys.executable, [_sys.executable, _REAL] + _sys.argv[1:])
else:
    import importlib.util as _u
    _s = _u.spec_from_file_location("fz_gate_check_real", _REAL)
    _m = _u.module_from_spec(_s)
    _s.loader.exec_module(_m)
    globals().update({{k: v for k, v in vars(_m).items() if not k.startswith("__")}})
'''


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    CHECKS.append(cell)
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def _load_gc():
    try:
        spec = importlib.util.spec_from_file_location("fz_dl_gc", GC)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:                                   # noqa: BLE001
        raise Setup(f"판정기 모듈 로드 실패: {e}")


GCMOD = _load_gc()


def ledger_text(r, dup=False):
    def gate(gid):
        return (f"- [ ] {gid}: [Step] {gid} 구현\n  CRITERION: {gid} 완료\n  CHECK: test -f impl-{gid}.done && echo ok\n"
                f"  EXPECT: ok\n  CWD: {r}\n  EVIDENCE: pending\n")
    return (f"# Gates: discover-limit fixture {r.name}\nROOT: {r}\nSTATE: active\nScope: 원장 다수 중 하나\n\n"
            + gate("S1") + "\n" + gate("S2") + ("\n" + gate("S1") if dup else ""))


class Cell:
    """셀 하나 = 임시 cwd(원장 N개) + 임시 HOME + 고유 세션 + 그 세션이 친 Bash 명령(transcript)."""
    n = 0

    def __init__(self, name):
        Cell.n += 1
        self.name, self.session, self.cmds = name, f"dl-{Cell.n}-{name}", []

    def __enter__(self):
        try:
            self.td = tempfile.TemporaryDirectory(prefix="fz-dl-")
            root = pathlib.Path(self.td.name).resolve()
            self.root, self.cwd, self.home, plug = root, root / "w", root / "home", root / "plugin"
            for d in (self.cwd, self.home, plug):
                d.mkdir()
            (plug / "scripts").symlink_to(SCRIPTS, target_is_directory=True)
        except OSError as e:
            raise Setup(f"셀 준비 실패: {e}")
        self.env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
        self.env.update(HOME=str(self.home), FZ_PLUGIN_ROOT=str(plug), PYTHONDONTWRITEBYTECODE="1")
        self.hook_path = HOOK
        self.k0 = len(CHECKS)
        return self

    def __exit__(self, *exc):
        RAN.append((self.name, sum(1 for x in CHECKS[self.k0:] if x == self.name)))
        for p in self.cwd.rglob("plan.md"):
            try:
                p.chmod(0o644)
            except OSError:
                pass
        self.td.cleanup()

    def ledgers(self, n, owned=(), dup_last=False):
        """`TICKET-%04d/gates/plan.md` N개(전부 미충족). 남의 원장은 앞선 세션이 확정(transcript 밖), `owned`(1부터)는 이
        세션이 `--finalize` 로 확정(실제 실행 + transcript). 반환 = 훅 · 판정기가 쓰는 꼴(resolve 한 경로)."""
        out = []
        for i in range(n):
            r = self.cwd / f"TICKET-{i:04d}"
            led = r / "gates" / "plan.md"
            try:
                led.parent.mkdir(parents=True)
                led.write_text(ledger_text(r, dup=dup_last and i == n - 1), encoding="utf-8")
            except OSError as e:
                raise Setup(f"원장 준비 실패: {e}")
            out.append(led.resolve())
        for i, led in enumerate(out, 1):
            if dup_last and i == n:
                continue                                   # 계약 위반 원장은 확정하지 않는다(파싱이 거부한다)
            if i in owned:
                cmd = f'python3 "${{FZ_PLUGIN_ROOT}}/scripts/gate_check.py" --finalize {led}'
                self.cmds.append(cmd)
                rc, out_ = self.run(cmd)
            else:
                rc = GCMOD._dispatch(["--finalize", str(led)], quiet=True)
                out_ = ""
            if rc != 0:
                raise Setup(f"원장 확정 실패 {led} rc={rc} {out_[-200:]}")
        return out

    def slow_shim(self):
        """느린 판정기 — 셀 안에 훅 사본 + 위임 래퍼를 두고 이 셀의 훅을 그 사본으로 바꾼다."""
        d = self.root / "shim" / "scripts"
        try:
            d.mkdir(parents=True)
            shutil.copy2(HOOK, d / "gate_stop_hook.py")
            (d / "gate_check.py").write_text(SHIM.format(real=str(GC)), encoding="utf-8")
        except OSError as e:
            raise Setup(f"shim 준비 실패: {e}")
        self.hook_path = d / "gate_stop_hook.py"
        self.log = self.root / "judge.log"

    def run(self, cmd, extra=None):
        env = dict(self.env, **(extra or {}))
        try:
            r = subprocess.run(["bash", "-c", cmd], cwd=str(self.cwd), env=env, capture_output=True,
                               stdin=subprocess.DEVNULL, timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            raise Setup(f"명령 실행 실패: {e} · {cmd[:120]}")
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")

    def hook(self, extra=None):
        """훅 1회 → (exit, 차단 사유 | None, stderr)."""
        tp = self.root / "transcript.jsonl"
        rows = [json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": c}}]}}, ensure_ascii=False) for c in self.cmds]
        try:
            tp.write_text("\n".join(rows) + "\n", encoding="utf-8")
        except OSError as e:
            raise Setup(f"세션 기록 실패: {e}")
        payload = {"hook_event_name": "Stop", "cwd": str(self.cwd), "session_id": self.session,
                   "transcript_path": str(tp)}
        try:
            r = subprocess.run([PY, "-B", str(self.hook_path)], input=json.dumps(payload).encode(), capture_output=True,
                               env=dict(self.env, **(extra or {})), timeout=180)
        except (OSError, subprocess.SubprocessError) as e:
            raise Setup(f"훅 실행 실패: {e}")
        err = r.stderr.decode("utf-8", "replace")
        reason = None
        for line in err.splitlines():
            if line.startswith('{"decision"'):
                try:
                    reason = json.loads(line)["reason"]
                except (ValueError, KeyError) as e:
                    raise Setup(f"차단 JSON 파싱 실패: {e} · {line[:200]}")
        return r.returncode, reason, err

    def discover(self):
        """`--discover` → (exit, stdout). 요약은 stdout 끝 줄(health-check 가 tail -1 로 읽는다) — 경고 · 위반은 stderr 다."""
        try:
            r = subprocess.run([PY, "-B", str(GC), "--discover", str(self.cwd)], cwd=str(self.cwd), env=self.env,
                               capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            raise Setup(f"--discover 실행 실패: {e}")
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def summary_line(out):
    lines = [l for l in out.strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def count_cell(name, n, own):
    """원장 n 개 중 `own` 번째가 소유 · 전부 미충족 → 훅이 그 원장을 판정해 막고, `--discover` 가 n 건을 다 본다."""
    with Cell(name) as c:
        leds = c.ledgers(n, owned=(own,))
        ol = leds[own - 1]
        rc, reason, err = c.hook()
        r = reason or ""
        check(name, rc == 2 and f"미충족 게이트: {ol} — " in r,
              f"원장 {n}개 중 {own}번째 소유 미충족 원장을 판정해 막는다(exit 2)", f"rc={rc} {err[-300:]}")
        skipped = max(0, (n - 1) - FOREIGN_MAX)
        if skipped:
            check(name, f"다른 세션의 원장 {skipped}개 미판정" in r,
                  f"남의 원장 상한({FOREIGN_MAX}) 밖 {skipped}개를 수로 남긴다(말없이 자르지 않는다)", r[-300:])
        else:
            check(name, "개 미판정" not in r, "상한 안이면 미판정 진단이 없다(회귀)", r[-300:])
        drc, dout, _ = c.discover()
        last = summary_line(dout)
        unmet_lines = sum(1 for l in dout.splitlines() if l.startswith("  미충족 "))
        check(name, drc == 0 and last.startswith(f"원장 {n}건 ") and unmet_lines == n and str(ol) in dout,
              f"--discover exit 0 · 끝 줄 `원장 {n}건` · 미충족 줄 {n} · 소유 원장 경로 포함",
              f"rc={drc} 미충족 줄={unmet_lines} 끝 줄={last}")


try:
    count_cell("n1-own1", 1, 1)
    count_cell("n9-own9", 9, 9)
    count_cell("n10-own10", 10, 10)
    count_cell("n80-own80", 80, 80)
    count_cell("n8-own8", 8, 8)
    count_cell("n9-own8", 9, 8)

    # ── own4-slow — 소유 원장 먼저 · 예산 소진 시 미판정 소유 원장이 남으면 막는다(F-404) ─────────────
    with Cell("own4-slow") as c:
        leds = c.ledgers(7, owned=(4, 5, 6, 7))            # 사전순 앞 3개가 남의 원장 — 구판 순서면 그쪽을 먼저 판정한다
        own, foreign = leds[3:], leds[:3]
        c.slow_shim()
        # 예산 4초 · 판정 1회 1.5초 — 훅 시작(모듈 적재 · transcript 파싱)이 부하로 1초를 넘어도 첫 소유 원장은 판정되고,
        # 빠른 머신에서도 판정 둘(≥ 3초) 뒤 남은 예산이 1초 이하라 소유 4개 중 적어도 둘은 미판정으로 남는다
        rc, reason, err = c.hook({"FZ_DL_JUDGE_LOG": str(c.log), "FZ_DL_JUDGE_SLEEP": "1.5", BUDGET_ENV: "4"})
        r = reason or ""
        try:
            judged = [l.split()[-1] for l in c.log.read_text(encoding="utf-8").splitlines() if "--status" in l]
        except OSError:
            judged = []
        check(c.name, bool(judged) and judged[0] == str(own[0]), "판정기 첫 호출이 소유 원장이다(남의 원장보다 먼저)", judged[:3])
        check(c.name, all(j in {str(p) for p in own} for j in judged),
              "소유 원장이 미판정으로 남는 동안 남의 원장을 판정하지 않는다", judged)
        m = re.search(r"소유 원장 (\d+)개 미판정", r)
        check(c.name, rc == 2 and m is not None and int(m.group(1)) >= 1 and "예산 소진" in r,
              "예산이 다해 못 본 소유 원장이 남으면 통과하지 않는다 — 미판정 수 · 이유(예산 소진)", f"rc={rc} {err[-300:]}")
        check(c.name, m is not None and len(judged) + int(m.group(1)) >= len(own),
              "판정한 소유 원장 + 미판정 수 ≥ 소유 4", f"judged={len(judged)} · {r[-200:]}")

    # ── own4-budget0 — 예산 0: 소유 4개 전부 미판정 · 루프 방어 불변 ────────────────────────
    with Cell("own4-budget0") as c:
        leds = c.ledgers(4, owned=(1, 2, 3, 4))
        shots = [c.hook({BUDGET_ENV: "0"}) for _ in range(MAX_BLOCKS + 1)]
        r = shots[0][1] or ""
        check(c.name, shots[0][0] == 2 and "소유 원장 4개 미판정" in r and str(leds[0]) in r,
              "예산 0 → `소유 원장 4개 미판정` 차단 · 원장 경로(이름만이면 늘 plan.md)", f"rc={shots[0][0]} {r[-300:]}")
        rcs = [s[0] for s in shots]
        check(c.name, rcs == [2] * MAX_BLOCKS + [0] and "회 막았다" in shots[-1][2],
              f"루프 방어 불변 — {MAX_BLOCKS}회 막고 {MAX_BLOCKS + 1}회째 통과", rcs)

    # ── foreign-only-cap — 상한은 남의 원장에만, 넘은 수는 말한다 ───────────────────────────
    with Cell("foreign-only-cap") as c:
        c.ledgers(12)
        rc, reason, err = c.hook()
        check(c.name, rc == 0 and reason is None, "남의 원장뿐 → 통과(exit 0)", f"rc={rc} {err[-300:]}")
        check(c.name, f"다른 세션의 원장 {12 - FOREIGN_MAX}개 미판정" in err,
              f"상한({FOREIGN_MAX}) 밖 {12 - FOREIGN_MAX}개를 진단으로 남긴다", err[-300:])

    # ── discover-invalid-last — 자르면 뒤쪽 계약 위반이 안 보인다 · 종료 코드 계약 그대로 ─────────────
    with Cell("discover-invalid-last") as c:
        leds = c.ledgers(10, dup_last=True)
        drc, dout, derr = c.discover()
        last = summary_line(dout)
        check(c.name, drc == 3 and last.startswith("원장 10건 ") and "계약위반 1" in last and str(leds[-1]) in derr,
              "--discover 가 10번째 계약 위반을 본다(exit 3 · `계약위반 1`)", f"rc={drc} 끝 줄={last}")

    # ── discover-unreadable — 읽지 못한 원장은 미판정 수로(종료 코드 불변) ─────────────────────────
    with Cell("discover-unreadable") as c:
        leds = c.ledgers(9)
        leds[-1].chmod(0)
        if os.access(leds[-1], os.R_OK):
            raise Setup("chmod 000 이 읽기를 막지 못한다(root 실행?) — 미판정 셀을 만들 수 없다")
        drc, dout, _ = c.discover()
        last = summary_line(dout)
        check(c.name, drc == 0 and last.startswith("원장 9건 ") and "미판정 1" in last,
              "--discover exit 0 · `원장 9건` · 읽지 못한 1개는 `미판정 1`", f"rc={drc} 끝 줄={last}")
except Setup as e:
    print(f"SETUP {e}")
    sys.exit(3)

ran = {}
for name, n in RAN:
    ran[name] = ran.get(name, 0) + 1
empty = [name for name, n in RAN if n == 0]
check("cell-set", ran == EXPECTED_CELLS and not empty, "돈 셀 이름 · 횟수 = EXPECTED_CELLS (단언 0개인 셀 없음)",
      f"없음={sorted(set(EXPECTED_CELLS) - set(ran))} · 뜻밖={sorted(set(ran) - set(EXPECTED_CELLS))} · 빈 셀={empty}")
print()
print(f"SUMMARY fail={len(FAIL)}")
for f in FAIL:
    print(f"  FAIL {f}")
print(f"CELLS n={len(RAN)} ran={','.join(name for name, _ in RAN)}")
sys.exit(1 if FAIL else 0)
PY
