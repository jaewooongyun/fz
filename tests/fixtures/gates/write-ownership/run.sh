#!/bin/bash
# Stop 훅 소유 판정 fixture (F-377 · F-422) — 원장을 **실제로 쓰는** 판정기 호출만 한 세션은 그 원장의 소유자이고, 읽기 전용
# 호출은 소유로 승격되지 않는지 동작으로 본다. 셀마다 명령을 진짜로 실행해 원장 바이트가 바뀌는지(쓰기의 정답)를 먼저 재고,
# 같은 명령 문자열을 Bash tool_use 로 transcript 에 넣어 훅을 돌린다.
#   write   only-literal · reverify-literal · set-state-literal · default-literal · only-var-abs(`$L` 같은 명령 대입) ·
#           only-var-sourced(env 파일이 G · L 을 준다 — 명령 줄에 'gates' · 'plan.md' · 판정기 이름이 없다, F-422) ·
#           default-var-sourced(플래그 없는 기본 실행 + source) · set-state-cd(`cd …/gates` 뒤 상대명) ·
#           set-state-abbrev(`--set active` — argparse 축약 = `--set-state`)
#           → 원장이 바뀌고 훅이 막는다(exit 2 · 사유에 `미충족 게이트: <원장>`)
#   read    status-literal · status-only(`--status --only`) · status-only-sourced · discover · cat-args(판정기 이름이 인자로만 지나감) ·
#           status-abbrev(`--stat` — argparse 축약 = `--status`) ·
#           source-missing-unrelated(못 읽은 source 뒤 판정기와 무관한 스크립트 — 어휘 밖 옵션) ·
#           stdin-script-args(`python3 -` 의 stdin 스크립트에 판정기 경로 · 변수를 인자로 넘김 — 판정기 호출이 아니다)
#           → 원장 불변 · 훅 통과(exit 0 · `다른 세션의 원장(막지 않음): <원장>`)
#   tilde   tilde-source-owned — `. ~/env.sh`(셀 HOME 에 실재) 뒤 `"$G" --only S1 "$L"` → 소유로 막되 '대상 미상 쓰기' 가 아니다
#   unknown only-profile-var — 원장 인자가 이 명령 · source 밖(셸 프로필)에서 온 쓰기 → 훅이 '대상 미상 쓰기' 로 전 원장 판정(차단)
#           only-sourced-gone — source 한 env 파일이 훅 전에 지워진 쓰기(`"$G"` · `"$L"` 를 못 푼다) → 같은 '대상 미상 쓰기'
#   control control-finalize — `--finalize <원장>` 리터럴(기준 훅도 소유로 본다 — 하네스가 소유를 읽는다는 대조)
#   pair    own-and-foreign — 한 세션이 원장 A 는 `--only` 로 쓰고 B 는 `--status` 로 읽기만 → A 만 막고 B 는 경고
#   loop    loop-guard — 소유 원장 미충족은 MAX_BLOCKS(2)회 막고 3회째 루프 방어로 통과(불변)
# 기준 트리(4.44.0)는 판정기 쓰기 플래그 · 기본 실행 · 변수 경로 · source 를 쓰기로 보지 않아 write 셀이 '다른 세션의 원장' 으로
#   통과한다 → exit 1.
# ⛔ 셀 집합 대조(F-408): 실제로 돈 셀(단언 1개 이상)의 이름 · 횟수가 EXPECTED_CELLS 와 다르면 FAIL — 끝 줄 `CELLS n=<수> ran=<…>`.
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 스크립트 · 임시 폴더 · 원장 준비 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 스크립트 exit 1' 게이트가 결함 재현 없이 통과한다 — 그래서 3 이다(미처리 예외도 3).
# ⛔ 셀마다 임시 cwd · 임시 HOME(루프 방어 상태 파일) · 고유 session_id. 바깥 FZ_GATES_LEDGER · FZ_GATES_OFF · FZ_GATES_TRACE ·
#    FZ_GATES_HOOK_BUDGET_S 는 자식에게 넘기지 않는다 — 넘기면 바깥 원장을 판정하거나 판정을 통째로 건너뛴다.
# usage: run.sh [--scripts <scripts 폴더>]   (기본: 이 fixture 가 든 트리의 scripts/ — health-check 글롭이 인자 없이 부른다)
set -u
if [ -n "${FZ_WRITE_OWNERSHIP_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 write-ownership 이 도는 중"
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

FZ_WRITE_OWNERSHIP_FIXTURE=1 PYTHONDONTWRITEBYTECODE=1 python3 -B - "$S" <<'PY'
import hashlib, json, os, pathlib, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

SCRIPTS = pathlib.Path(sys.argv[1])
GC, HOOK = SCRIPTS / "gate_check.py", SCRIPTS / "gate_stop_hook.py"
PY = sys.executable
MAX_BLOCKS = 2                    # 훅 루프 방어 계약 값 — 훅 상수를 import 하지 않는다
DROP_ENV = ("FZ_GATES_LEDGER", "FZ_GATES_OFF", "FZ_GATES_TRACE", "FZ_GATES_HOOK_BUDGET_S")
G_LINE = 'G="${FZ_PLUGIN_ROOT}/scripts/gate_check.py"'   # fz-code 6.4 블록과 같은 꼴
FAIL, CHECKS, RAN = [], [], []
EXPECTED_CELLS = {
    "only-literal": 1, "reverify-literal": 1, "set-state-literal": 1, "default-literal": 1, "only-var-abs": 1,
    "only-var-sourced": 1, "default-var-sourced": 1, "set-state-cd": 1, "set-state-abbrev": 1,
    "status-literal": 1, "status-only": 1, "status-only-sourced": 1, "discover": 1, "cat-args": 1,
    "status-abbrev": 1, "source-missing-unrelated": 1, "stdin-script-args": 1, "tilde-source-owned": 1,
    "only-profile-var": 1, "only-sourced-gone": 1, "control-finalize": 1, "own-and-foreign": 1, "loop-guard": 1,
}


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    CHECKS.append(cell)
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def ledger_text(r):
    def gate(gid, check):
        return (f"- [ ] {gid}: [Step] {gid} 구현\n  CRITERION: {gid} 완료\n  CHECK: {check}\n  EXPECT: ok\n"
                f"  CWD: {r}\n  EVIDENCE: pending\n")
    return (f"# Gates: write-ownership fixture\nROOT: {r}\nSTATE: active\nScope: 판정기 쓰기 호출의 소유\n\n"
            + gate("S1", "echo ok") + "\n" + gate("S2", "test -f impl-S2.done && echo ok") + "\n"
            + gate("S3", "test -f impl-S3.done && echo ok"))


def sha(p):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError as e:
        raise Setup(f"원장 읽기 실패: {e}")


class Cell:
    """셀 하나 = 임시 cwd + 임시 HOME + 고유 세션 + 그 세션이 친 Bash 명령(transcript)."""
    n = 0

    def __init__(self, name):
        Cell.n += 1
        self.name, self.session, self.cmds = name, f"wo-{Cell.n}-{name}", []

    def __enter__(self):
        try:
            self.td = tempfile.TemporaryDirectory(prefix="fz-wo-")
            root = pathlib.Path(self.td.name).resolve()
            self.root, self.cwd, self.home, plug = root, root / "w", root / "home", root / "plugin"
            for d in (self.cwd, self.home, plug):
                d.mkdir()
            (plug / "scripts").symlink_to(SCRIPTS, target_is_directory=True)   # ${FZ_PLUGIN_ROOT}/scripts = --scripts
        except OSError as e:
            raise Setup(f"셀 준비 실패: {e}")
        self.env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
        self.env.update(HOME=str(self.home), FZ_PLUGIN_ROOT=str(plug), PYTHONDONTWRITEBYTECODE="1")
        self.k0 = len(CHECKS)
        return self

    def __exit__(self, *exc):
        RAN.append((self.name, sum(1 for x in CHECKS[self.k0:] if x == self.name)))
        self.td.cleanup()

    def ledger(self, rel="TICKET-0000", seed="finalized"):
        """`cwd/rel/gates/plan.md` — seed: finalized(앞선 plan 세션이 확정) · rfr(확정 뒤 ready_for_review) · draft."""
        r = self.cwd / rel
        led = r / "gates" / "plan.md"
        try:
            led.parent.mkdir(parents=True)
            led.write_text(ledger_text(r), encoding="utf-8")
        except OSError as e:
            raise Setup(f"원장 준비 실패: {e}")
        if seed != "draft":
            rc, out = self.run(f"python3 -B '{GC}' --finalize '{led}'", record=False)
            if rc != 0:
                raise Setup(f"원장 확정 실패 rc={rc} {out[-200:]}")
        if seed == "rfr":
            t = led.read_text(encoding="utf-8")
            if "\nSTATE: active\n" not in t:
                raise Setup("STATE 줄 없음")
            led.write_text(t.replace("\nSTATE: active\n", "\nSTATE: ready_for_review\n", 1), encoding="utf-8")
        return led.resolve()

    def envfile(self, led, name="cell-env.sh", where=None):
        """원장 · 판정기 경로를 주는 env 파일(`. env.sh && …` 꼴) — 명령 줄에는 그 경로가 없다. where: 놓을 폴더(기본 셀 루트)."""
        p = (where or self.root) / name
        try:
            p.write_text(f"{G_LINE}\nexport L={led}\n", encoding="utf-8")
        except OSError as e:
            raise Setup(f"env 파일 기록 실패: {e}")
        return p

    def run(self, cmd, record=True, extra=None):
        """세션의 Bash 명령 하나 — 실제로 실행하고(record 면) transcript 에 남긴다. → (exit, 결합 출력)"""
        if record:
            self.cmds.append(cmd)
        env = dict(self.env, **(extra or {}))
        try:
            r = subprocess.run(["bash", "-c", cmd], cwd=str(self.cwd), env=env, capture_output=True,
                               stdin=subprocess.DEVNULL, timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            raise Setup(f"명령 실행 실패: {e} · {cmd[:120]}")
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")

    def hook(self):
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
            r = subprocess.run([PY, "-B", str(HOOK)], input=json.dumps(payload).encode(), capture_output=True,
                               env=self.env, timeout=120)
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


def write_cell(name, seed, make_cmds):
    """원장을 실제로 쓰는 명령만 한 세션 → 원장이 바뀌고 훅이 그 원장으로 막는다."""
    with Cell(name) as c:
        led = c.ledger(seed=seed)
        before = sha(led)
        for cmd in make_cmds(c, led):
            c.run(cmd)
        check(name, sha(led) != before, "명령이 원장을 실제로 쓴다(바이트 변화 — 쓰기의 정답)", "")
        rc, reason, err = c.hook()
        check(name, rc == 2 and f"미충족 게이트: {led} — " in (reason or ""),
              "훅이 이 원장의 소유를 읽고 막는다(exit 2 · `미충족 게이트: <원장>`)", f"rc={rc} {err[-300:]}")


def read_cell(name, make_cmds):
    """읽기 전용 호출만 한 세션 → 원장 불변 · 소유가 아니다(훅 통과 · 남의 원장 경고)."""
    with Cell(name) as c:
        led = c.ledger()
        before = sha(led)
        for cmd in make_cmds(c, led):
            c.run(cmd)
        check(name, sha(led) == before, "명령이 원장을 쓰지 않는다(바이트 불변)", "")
        rc, reason, err = c.hook()
        check(name, rc == 0 and reason is None and f"다른 세션의 원장(막지 않음): {led} — " in err,
              "읽기는 소유가 아니다(exit 0 · `다른 세션의 원장(막지 않음): <원장>`)", f"rc={rc} {err[-300:]}")


try:
    # ── write — 원장을 쓰는 판정기 호출(F-377) ───────────────────────────────────────
    write_cell("only-literal", "finalized", lambda c, L: [f'{G_LINE}\npython3 "$G" --only S1 {L}'])
    write_cell("reverify-literal", "finalized", lambda c, L: [f'{G_LINE}\npython3 "$G" --reverify {L}'])
    write_cell("set-state-literal", "rfr", lambda c, L: [f'{G_LINE}\npython3 "$G" --set-state active {L}'])
    write_cell("default-literal", "finalized", lambda c, L: [f'{G_LINE}\npython3 "$G" {L}'])
    write_cell("only-var-abs", "finalized", lambda c, L: [f'{G_LINE}\nL={L}\npython3 "$G" --only S1 "$L"'])
    write_cell("only-var-sourced", "finalized", lambda c, L: [f'. {c.envfile(L)} && python3 "$G" --only S1 "$L"'])
    write_cell("default-var-sourced", "finalized", lambda c, L: [f'. {c.envfile(L)} && python3 "$G" "$L"'])
    write_cell("set-state-cd", "rfr",
               lambda c, L: [f'cd {L.parent} && python3 "${{FZ_PLUGIN_ROOT}}/scripts/gate_check.py" --set-state active plan.md'])
    write_cell("set-state-abbrev", "rfr", lambda c, L: [f'{G_LINE}\npython3 "$G" --set active {L}'])

    # ── read — 읽기 전용 호출은 소유로 승격되지 않는다 ─────────────────────────────────
    read_cell("status-literal", lambda c, L: [f'{G_LINE}\npython3 "$G" --status {L}'])
    read_cell("status-only", lambda c, L: [f'{G_LINE}\npython3 "$G" --status --only S1 {L}'])
    read_cell("status-only-sourced", lambda c, L: [f'. {c.envfile(L)} && python3 "$G" --status --only S1 "$L"'])
    read_cell("discover", lambda c, L: [f'{G_LINE}\npython3 "$G" --discover {c.cwd}'])
    read_cell("cat-args", lambda c, L: [f'cat "${{FZ_PLUGIN_ROOT}}/scripts/gate_check.py" {L} >/dev/null'])
    read_cell("status-abbrev", lambda c, L: [f'{G_LINE}\npython3 "$G" --stat {L}'])
    # 못 읽은 source(`~/nope.sh` 는 셀 HOME 에 없다) 뒤의 무관한 스크립트 — 옵션이 판정기 어휘 밖이라 argparse 가 거부할 꼴이다
    read_cell("source-missing-unrelated",
              lambda c, L: ['. ~/nope.sh && python3 $X/tool.py --arm B --ledger $X/l.jsonl'])
    # `python3 -` 는 stdin 의 스크립트를 돌린다 — 뒤의 판정기 경로 · `$T` 는 그 스크립트의 sys.argv 다
    read_cell("stdin-script-args",
              lambda c, L: ["P=/opt/plug; python3 - $P/scripts/gate_check.py $T <<'PY'\nimport sys\nprint(len(sys.argv))\nPY"])

    # ── tilde — `~` 로 source 한 env 파일이 실재하면 그 대입으로 푼다(소유 · '대상 미상' 아님) ───────────
    with Cell("tilde-source-owned") as c:
        led = c.ledger()
        before = sha(led)
        c.envfile(led, where=c.home)
        c.run('. ~/cell-env.sh && python3 "$G" --only S1 "$L"')
        check(c.name, sha(led) != before, "명령이 원장을 실제로 쓴다(env 파일은 셀 HOME 의 `~/cell-env.sh`)", "")
        rc, reason, err = c.hook()
        r = reason or ""
        check(c.name, rc == 2 and f"미충족 게이트: {led} — " in r, "훅이 이 원장의 소유를 읽고 막는다(exit 2 · `미충족 게이트: <원장>`)",
              f"rc={rc} {err[-300:]}")
        check(c.name, "대상 미상 쓰기" not in err, "`~` source 를 풀었으므로 '대상 미상 쓰기' 가 아니다", err[-300:])

    # ── unknown — 원장 인자를 풀 수 없는 쓰기 → 전 원장 판정(fail-closed) ───────────────────
    with Cell("only-profile-var") as c:
        led = c.ledger()
        before = sha(led)
        c.run(f'{G_LINE}\npython3 "$G" --only S1 "$LEDGER_FROM_PROFILE"', extra={"LEDGER_FROM_PROFILE": str(led)})
        check(c.name, sha(led) != before, "명령이 원장을 실제로 쓴다(값은 셸 프로필 변수 — 명령 · source 밖)", "")
        rc, reason, err = c.hook()
        r = reason or ""
        check(c.name, rc == 2 and "대상 미상 쓰기" in r and f"미충족 게이트: {led} — " in r,
              "원장 인자를 못 푼 쓰기는 '다른 세션의 원장' 이 아니다 — '대상 미상 쓰기' 로 전 원장 판정 · 차단",
              f"rc={rc} {err[-300:]}")
        check(c.name, "FZ_GATES_LEDGER" in r, "사유에 범위를 좁히는 출구(FZ_GATES_LEDGER)", r[-300:])

    with Cell("only-sourced-gone") as c:
        led = c.ledger()
        before = sha(led)
        envf = c.envfile(led)
        c.run(f'. {envf} && python3 "$G" --only S1 "$L"')
        check(c.name, sha(led) != before, "명령이 원장을 실제로 쓴다(env 파일이 G · L 을 준다)", "")
        try:
            envf.unlink()                                  # 세션이 끝나기 전에 임시 env 파일을 지웠다
        except OSError as e:
            raise Setup(f"env 파일 삭제 실패: {e}")
        rc, reason, err = c.hook()
        r = reason or ""
        check(c.name, rc == 2 and "대상 미상 쓰기" in r and f"미충족 게이트: {led} — " in r,
              "source 한 파일이 사라져 못 푼 쓰기도 '다른 세션의 원장' 이 아니다 — '대상 미상 쓰기' · 차단", f"rc={rc} {err[-300:]}")

    # ── control — 기준 훅도 소유로 보는 꼴(하네스가 소유를 읽는다는 대조) ─────────────────────
    with Cell("control-finalize") as c:
        led = c.ledger(seed="draft")
        before = sha(led)
        c.run(f'{G_LINE}\npython3 "$G" --finalize {led}')
        check(c.name, sha(led) != before, "--finalize 가 원장을 쓴다", "")
        rc, reason, err = c.hook()
        check(c.name, rc == 2 and f"미충족 게이트: {led} — " in (reason or ""), "`--finalize <원장>` 리터럴 → 차단",
              f"rc={rc} {err[-300:]}")

    # ── pair — 한 세션 안에서 쓴 원장만 소유, 읽은 원장은 남의 원장 ───────────────────────
    with Cell("own-and-foreign") as c:
        a = c.ledger("A-own")
        b = c.ledger("B-read")
        c.run(f'{G_LINE}\npython3 "$G" --only S1 {a}')
        c.run(f'{G_LINE}\npython3 "$G" --status --only S1 {b}')
        rc, reason, err = c.hook()
        r = reason or ""
        check(c.name, rc == 2 and f"미충족 게이트: {a} — " in r, "쓴 원장 A 로 막는다", f"rc={rc} {err[-300:]}")
        check(c.name, f"미충족 게이트: {b} — " not in r and f"다른 세션의 원장(막지 않음): {b} — " in r,
              "읽기만 한 원장 B 는 소유가 아니다(경고만)", r[-300:])

    # ── loop — 루프 방어 불변 ───────────────────────────────────────────────────────────
    with Cell("loop-guard") as c:
        led = c.ledger()
        c.run(f'{G_LINE}\npython3 "$G" --only S1 {led}')
        shots = [c.hook() for _ in range(MAX_BLOCKS + 1)]
        rcs = [s[0] for s in shots]
        check(c.name, rcs == [2] * MAX_BLOCKS + [0], f"{MAX_BLOCKS}회 막고 {MAX_BLOCKS + 1}회째 루프 방어 통과", rcs)
        check(c.name, "회 막았다" in shots[-1][2], "마지막 통과는 루프 방어 진단", shots[-1][2][-200:])
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
