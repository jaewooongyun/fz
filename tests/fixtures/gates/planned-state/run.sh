#!/bin/bash
# 승인·미착수(planned) fixture (F-190 · F-159) — 두 SKILL 의 실제 호출 줄을 SKILL.md 에서 뽑아 착수 전 → 착수 후 순서로
# 재생하고, 판정기 전이표와 Stop 훅이 그 흐름에서 어떻게 판정하는지 동작으로 본다.
#   approved-unstarted   fz-plan 4.5 줄 재생(cp → 판정기 호출 span 순서대로) → 확정 · planned · ABANDON 0 · 훅 통과(차단 0회)
#   fz-code-start        같은 세션이 fz-code Phase 0.4 줄로 active → 훅이 막고 사유에 셋째 선택지 · 6.4 `--only` 줄로 S1 PASS
#   work-recorded        진행 기록 5종(PASS 증거 · reverify 강등 · --confirm · 위조 증거 · 재승인 뒤 FAIL 의 강등) 원장의 planned 역행 거부 · 바이트 불변
#   refinalize           진행 기록 있는 active 원장을 다시 확정(--finalize --only · 헤더 지우고 --finalize)해도 STATE active · 훅 차단
#   unmet-active         미충족 active 원장은 계속 막힌다 — MAX_BLOCKS 회 막고 그다음 루프 방어로 통과
#   planned-refuses      planned 원장: 실행 · --only · --reverify · --confirm · 6.4 줄 exit 3 · 바이트 불변 · --status 0 · 표 밖 간선 거부 · active 는 증명 불요
#   one-path             생성(--from-plan) STATE active · --finalize 는 STATE 를 쓰지 않는다(contract) / planned 를 쓴다(plan)
#   residual-no-record   ⛔ 잔존 위험 고정 — 게이트를 안 돌렸거나 실패만 한 세션은 진행 기록 0 이라 planned 로 갈 수 있다(contract).
#   residual-replan      ⛔ 잔존 위험 고정 — 진행 중 원장에서 fz-plan 4.5 를 다시 재생하면 cp 가 기록을 판정기 밖에서 덮어 planned · 훅 통과.
#                        두 셀은 그 우회가 **지금 열려 있음**을 PASS 로 기록한다 — 막히면 문서(modules/gates.md STATE 절)와 함께 바꾼다
# --variant contract(기본) | plan — 계획이 열어 둔 두 분기. 차이: one-path(--finalize 가 planned 를 쓰는가) ·
#   work-recorded 의 거부 토큰 · residual-no-record(contract 는 허용 고정, plan 은 거부). 트리는 contract 만 구현한다.
# 기준 트리(4.44.0)는 두 층에서 각각 실패해 exit 1 이다 — 판정기는 planned 를 거부하고(`--set-state planned` exit 2 · planned
#   원장 exit 3), 기준 SKILL 에는 착수 전·착수 호출 줄이 없다(4.5 의 `--finalize` 는 굵은 토큰이라 호출로 뽑히지 않고, Phase 0.4 에는
#   판정기 호출이 0개다). 기준 scripts + 기준 skills 조합에서는 추출 층이 먼저 드러나고, 기준 scripts + 후보 skills 도 판정기 층만으로 exit 1.
# ⛔ 셀 집합 대조(F-408): 실제로 돈 셀(단언 1개 이상)의 이름 · 횟수가 EXPECTED_CELLS 와 다르면 FAIL 이다 — 셀 하나를 지워도
#   기준이 다른 셀에서 실패해 '후보 0 · 기준 1' 이 그대로 서는 구조를 막는다. 끝 줄 `CELLS n=<수> ran=<이름,…>`.
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 파일 · 임시 폴더 · pty · 추출 · 단언기 고장)
#   ⛔ 추출 실패 = SKILL.md 부재 · 4.5 `원장 확정` 줄 부재 · `## Phase 0.4` 절 부재 · 6.4 bash 블록 부재 · 판정기 호출 0건 → 3.
#      특정 호출 줄(`--set-state planned` · `--set-state active`)의 부재는 그 셀이 재는 대상이라 단언 실패(1)다.
#   ⛔ 호출 줄을 이 파일에 복사해 두지 않는다 — 복사본은 SKILL 이 바뀌어도 초록이다.
# ⛔ 셀마다 임시 cwd · 임시 HOME(루프 방어 상태 파일) · 고유 session_id. 바깥 FZ_GATES_LEDGER · FZ_GATES_OFF · FZ_GATES_TRACE 는
#    자식에게 넘기지 않는다 — 넘기면 바깥 원장을 판정하거나 판정을 통째로 건너뛴다.
# usage: run.sh [--scripts <scripts 폴더>] [--skills <skills 폴더>] [--variant contract|plan]
#        (기본: 이 fixture 가 든 트리의 scripts/ · skills/ · contract — health-check 글롭이 인자 없이 부른다)
set -u
if [ -n "${FZ_PLANNED_STATE_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 planned-state 가 도는 중"
  exit 2
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
S="$(cd "$HERE/../../../../scripts" 2>/dev/null && pwd)"
K="$(cd "$HERE/../../../../skills" 2>/dev/null && pwd)"
V=contract
while [ $# -gt 0 ]; do
  case "$1" in
    --scripts) [ $# -ge 2 ] || { echo "SETUP --scripts 에 경로가 없다"; exit 3; }
               S="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --scripts 경로 없음: $2"; exit 3; }; shift 2 ;;
    --skills)  [ $# -ge 2 ] || { echo "SETUP --skills 에 경로가 없다"; exit 3; }
               K="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --skills 경로 없음: $2"; exit 3; }; shift 2 ;;
    --variant) [ $# -ge 2 ] || { echo "SETUP --variant 에 값이 없다"; exit 3; }
               case "$2" in contract|plan) V="$2" ;; *) echo "SETUP --variant 는 contract|plan — 받은 값 $2"; exit 3 ;; esac
               shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -n "$S" ] && [ -f "$S/gate_check.py" ] && [ -f "$S/gate_stop_hook.py" ] \
  || { echo "SETUP gate_check.py · gate_stop_hook.py 없음: ${S:-?}"; exit 3; }
[ -n "$K" ] && [ -f "$K/fz-plan/SKILL.md" ] && [ -f "$K/fz-code/SKILL.md" ] \
  || { echo "SETUP fz-plan · fz-code SKILL.md 없음: ${K:-?}"; exit 3; }

FZ_PLANNED_STATE_FIXTURE=1 PYTHONDONTWRITEBYTECODE=1 python3 -B - "$S" "$K" "$V" <<'PY'
import hashlib, json, os, pathlib, re, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

SCRIPTS, SKILLS, VARIANT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
GC, HOOK = SCRIPTS / "gate_check.py", SCRIPTS / "gate_stop_hook.py"
PY = sys.executable
MAX_BLOCKS = 2                    # 훅 루프 방어 계약 값 — 훅 상수를 import 하지 않는다
FAIL = []
CHECKS = []                       # 단언 기록 — 셀마다 몇 개가 돌았는지 센다
RAN = []                          # (셀 이름, 그 셀에서 돈 단언 수)
# 기대 셀 이름 → 도는 횟수. 셀을 더하거나 빼면 여기도 바꾼다 — 다르면 FAIL(셀을 지워도 초록인 구조를 막는다)
EXPECTED_CELLS = {
    "approved-unstarted": 1, "fz-code-start": 1, "work-recorded": 1, "work-recorded-demoted": 1,
    "work-recorded-confirm": 1, "work-recorded-forged": 1, "work-recorded-reapproved": 1, "refinalize": 1,
    "unmet-active": 1, "planned-refuses": 1, "one-path": 1, "residual-no-record": 2, "residual-replan": 1,
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


# ── SKILL.md 호출 줄 추출 ──────────────────────────────────────────────────────
SPAN_RE = re.compile(r"`([^`\n]+)`")


def _read(name):
    p = SKILLS / name / "SKILL.md"
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        raise Setup(f"{p} 읽기 실패: {e}")


def _calls(text):
    """`python3 "…/gate_check.py" …` 꼴 백틱 span — 문서 안의 판정기 호출 줄."""
    return [s.strip() for s in SPAN_RE.findall(text)
            if "gate_check.py" in s and s.strip().startswith("python3 ")]


def _section(text, heading):
    """`heading` 으로 시작하는 `## ` 제목부터 다음 `## ` 제목 앞까지."""
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if l.startswith(heading):
            body = [l]
            for m in lines[i + 1:]:
                if re.match(r"^##? ", m):
                    break
                body.append(m)
            return "\n".join(body)
    return None


def extract():
    plan, code = _read("fz-plan"), _read("fz-code")
    # positive control — 추출기가 각 문서에서 판정기 호출을 하나라도 보는가. 0 이면 추출기 고장이거나 문서 형식이 바뀌었다
    for name, text in (("fz-plan", plan), ("fz-code", code)):
        if not _calls(text) and '"$G"' not in text:
            raise Setup(f"{name}/SKILL.md 에서 판정기 호출 span 0건 — 추출기 고장 또는 문서 형식 변경")
    rows = [l for l in plan.split("\n") if re.match(r"^4\.5\. ", l) and "원장 확정" in l]
    if len(rows) != 1:
        raise Setup(f"fz-plan 4.5 `원장 확정` 줄 {len(rows)}개 — 추출 불가")
    plan_calls = _calls(rows[0])
    if not plan_calls:
        raise Setup("fz-plan 4.5 줄에 판정기 호출 span 0건 — 추출 불가")
    p04 = _section(code, "## Phase 0.4")
    if p04 is None:
        raise Setup("fz-code `## Phase 0.4` 절 없음 — 추출 불가")
    start_calls = _calls(p04)          # 0 건일 수 있다 — 착수 전환 줄 부재는 단언 대상
    m = re.search(r"^6\.4\. .*?^\s*```bash\n(.*?)^\s*```", code, re.S | re.M)
    if m is None:
        raise Setup("fz-code 6.4 bash 블록 없음 — 추출 불가")
    block = m.group(1)
    g = re.search(r'^\s*G="([^"]+)"', block, re.M)
    only = [l for l in block.split("\n") if "--only" in l and '"$G"' in l]
    if g is None or len(only) != 1:
        raise Setup(f"fz-code 6.4 블록에서 G= 대입 · `--only` 줄을 못 뽑았다 (G={bool(g)} · only={len(only)})")
    step_call = re.sub(r"\s+#.*$", "", only[0].strip()).replace('"$G"', f'"{g.group(1)}"')
    return plan_calls, start_calls, step_call


def materialize(cmd, work, step="S1"):
    out = cmd.replace("{WORK_DIR}", str(work)).replace("{StepID}", step)
    left = re.findall(r"\{[^}]*\}", out.replace("${FZ_PLUGIN_ROOT}", ""))
    if left:
        raise Setup(f"치환 못 한 자리표시 {left} — {cmd}")
    return out


# ── 셀 ─────────────────────────────────────────────────────────────────────────
def gate(gid, title, body):
    return f"- [ ] {gid}: {title}\n{body}  EVIDENCE: pending\n"


def ledger_text(r):
    crit = "S3 화면을 눈으로 확인"
    return (f"# Gates: planned-state fixture\nROOT: {r}\nSTATE: active\nScope: 승인·미착수 재생\n\n"
            + gate("S1", "첫 구현", f"  CRITERION: S1 산출물이 있다\n  CHECK: test -f impl-S1.done && echo s1 ok\n"
                                    f"  EXPECT: s1 ok\n  CWD: {r}\n") + "\n"
            + gate("S2", "둘째 구현", f"  CRITERION: S2 산출물이 있다\n  CHECK: test -f impl-S2.done && echo s2 ok\n"
                                     f"  EXPECT: s2 ok\n  CWD: {r}\n") + "\n"
            + gate("S3", "화면 확인", f"  MANUAL: {crit}\n  CRITERION_HASH: {hashlib.sha256(crit.encode()).hexdigest()[:12]}\n"))


class Cell:
    """셀 하나 = 임시 cwd + 임시 HOME + 고유 세션 + 그 세션의 Bash 기록(transcript)."""
    n = 0

    def __init__(self, name):
        Cell.n += 1
        self.name, self.session, self.cmds = name, f"pst-{Cell.n}-{name}", []

    def __enter__(self):
        try:
            self.td = tempfile.TemporaryDirectory(prefix="fz-pst-")
        except OSError as e:
            raise Setup(f"임시 폴더 생성 실패: {e}")
        root = pathlib.Path(self.td.name).resolve()
        self.cwd, self.home, plug = root / "w", root / "home", root / "plugin"
        try:
            self.cwd.mkdir()
            self.home.mkdir()
            plug.mkdir()
            (plug / "scripts").symlink_to(SCRIPTS, target_is_directory=True)   # ${FZ_PLUGIN_ROOT}/scripts = --scripts
        except OSError as e:
            raise Setup(f"셀 준비 실패: {e}")
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("FZ_GATES_LEDGER", "FZ_GATES_OFF", "FZ_GATES_TRACE")}
        self.env.update(HOME=str(self.home), FZ_PLUGIN_ROOT=str(plug), PYTHONDONTWRITEBYTECODE="1")
        self.r = self.cwd / "TICKET-0000"
        self.led = self.r / "gates" / "plan.md"
        self.k0 = len(CHECKS)
        return self

    def __exit__(self, *exc):
        RAN.append((self.name, sum(1 for x in CHECKS[self.k0:] if x == self.name)))
        self.td.cleanup()

    def bash(self, cmd, record=True):
        """세션이 Bash 로 친 명령 하나 — transcript 에 남기고 실행한다. → (exit, 결합 출력)"""
        if record:
            self.cmds.append(cmd)
        try:
            r = subprocess.run(["bash", "-c", cmd], cwd=str(self.cwd), env=self.env, capture_output=True,
                               stdin=subprocess.DEVNULL, timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            raise Setup(f"명령 실행 실패: {e} · {cmd[:120]}")
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")

    def gc(self, *args, record=True):
        """판정기 직접 호출(fixture 의 단언용 — SKILL 줄이 아니다)."""
        q = " ".join("'" + a.replace("'", "'\\''") + "'" for a in (str(GC),) + args)
        return self.bash(f"python3 -B {q}", record=record)

    def confirm(self, gid):
        """`--confirm` 은 대화형 stdin 을 요구한다 — pty 를 붙이고 `y` 를 보낸다(MANUAL 확인 기록을 진짜로 만든다)."""
        import pty
        try:
            master, slave = pty.openpty()
        except OSError as e:
            raise Setup(f"pty 를 열 수 없다 — --confirm 셀을 만들 수 없다: {e}")
        self.cmds.append(f"python3 {GC} --confirm {gid} {self.led}")
        try:
            p = subprocess.Popen([PY, "-B", str(GC), "--confirm", gid, str(self.led)], stdin=slave,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, cwd=str(self.cwd))
            os.close(slave)
            os.write(master, b"y\n")
            out, err = p.communicate(timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            raise Setup(f"--confirm 실행 실패: {e}")
        finally:
            os.close(master)
        return p.returncode, (out + err).decode("utf-8", "replace")

    def hook(self):
        """훅 1회 → (exit, 차단 사유 | None, stderr). transcript = 이 세션이 친 Bash 명령 전부."""
        tp = self.cwd / "transcript.jsonl"
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

    def blocks(self):
        p = self.home / ".fz" / "stop-hook-state.json"
        try:
            st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except (OSError, ValueError) as e:
            raise Setup(f"상태 파일 읽기 실패: {e}")
        return {k: v for k, v in st.items() if k.startswith(self.session + "|")}

    def text(self):
        try:
            return self.led.read_text(encoding="utf-8") if self.led.exists() else ""
        except OSError as e:
            raise Setup(f"원장 읽기 실패: {e}")

    def state(self):
        m = re.search(r"^STATE: (\S+)$", self.text(), re.M)
        return m.group(1) if m else None

    def write(self, body):
        try:
            self.led.write_text(body, encoding="utf-8")
        except OSError as e:
            raise Setup(f"원장 편집 실패: {e}")

    def touch(self, name):
        try:
            (self.r / name).write_text("x\n", encoding="utf-8")
        except OSError as e:
            raise Setup(f"산출물 생성 실패: {e}")

    def plan_session(self):
        """fz-plan 4.5 — draft → plan.md 복사(산문 단계, 고정) 뒤 4.5 줄의 판정기 호출을 적힌 순서대로 재생한다."""
        try:
            (self.r / "gates").mkdir(parents=True, exist_ok=True)      # 재계획(residual-replan)은 같은 폴더에 다시 쓴다
            (self.r / "gates" / "plan.draft.md").write_text(ledger_text(self.r), encoding="utf-8")
        except OSError as e:
            raise Setup(f"draft 준비 실패: {e}")
        self.bash(f"cp {self.r}/gates/plan.draft.md {self.led}")
        return [(c, *self.bash(materialize(c, self.r))) for c in PLAN_CALLS]

    def code_start(self):
        """fz-code Phase 0.4 — 그 절의 판정기 호출(착수 전환)을 재생한다."""
        return [(c, *self.bash(materialize(c, self.r))) for c in START_CALLS]

    def step(self, sid):
        """fz-code 6.4 — `--only {StepID}` 줄 재생."""
        return self.bash(materialize(STEP_CALL, self.r, sid))


def has(calls, flag):
    return [c for c in calls if re.search(re.escape(flag) + r"(\s|$)", c)]


def refuse_planned(cell, c, label):
    """진행 기록이 있는 active 원장에 `--set-state planned` → 거부 · STATE active · 바이트 불변."""
    before = c.text()
    rc, out = c.gc("--set-state", "planned", str(c.led))
    check(cell, rc == 1, f"{label}: --set-state planned 거부(exit 1)", f"rc={rc} {out[-300:]}")
    if VARIANT == "contract":
        check(cell, "REJECT: work-recorded" in out, f"{label}: 사유 `REJECT: work-recorded`", out[-300:])
    check(cell, c.text() == before and c.state() == "active", f"{label}: 원장 바이트 불변 · STATE active", c.state())


try:
    PLAN_CALLS, START_CALLS, STEP_CALL = extract()
    print(f"EXTRACT fz-plan 4.5 호출 {len(PLAN_CALLS)} · fz-code Phase 0.4 호출 {len(START_CALLS)} · 6.4 `--only` 1 · variant={VARIANT}")

    # ── approved-unstarted — 승인·미착수 원장이 ABANDON 없이 Stop 을 통과한다 ─────────────
    with Cell("approved-unstarted") as c:
        fin, pl = has(PLAN_CALLS, "--finalize"), has(PLAN_CALLS, "--set-state planned")
        check(c.name, len(fin) == 1, "fz-plan 4.5 줄에 `--finalize` 호출 1개", PLAN_CALLS)
        check(c.name, len(pl) == 1, "fz-plan 4.5 줄에 `--set-state planned` 호출 1개", PLAN_CALLS)
        check(c.name, bool(fin and pl) and PLAN_CALLS.index(fin[0]) < PLAN_CALLS.index(pl[0]),
              "`--set-state planned` 는 `--finalize` 뒤", PLAN_CALLS)
        replay = c.plan_session()
        check(c.name, all(rc == 0 for _, rc, _ in replay), "4.5 재생 호출 전부 exit 0",
              [(x[:60], rc, out[-120:]) for x, rc, out in replay if rc != 0])
        t = c.text()
        check(c.name, "\nAPPROVED: yes" in t and t.count("APPROVED_ORACLE_HASH: ") == 2, "확정 — APPROVED · 실행 게이트 도장 2", t[:300])
        check(c.name, c.state() == "planned", "STATE planned", c.state())
        check(c.name, "ABANDON:" not in t, "ABANDON 0 — 거짓 포기 기록 없음", "")
        rc, out = c.gc("--status", str(c.led), record=False)
        check(c.name, rc == 0, "--status exit 0(착수 전 no-op)", f"rc={rc} {out[-300:]}")
        rc, reason, err = c.hook()
        check(c.name, rc == 0 and reason is None, "Stop 훅 통과(exit 0 · 차단 사유 없음)", f"rc={rc} {err[-300:]}")
        check(c.name, c.blocks() == {}, "차단 0회 — 루프 방어로 빠져나간 것이 아니다", c.blocks())
        rc, out = c.gc("--discover", str(c.cwd), record=False)
        check(c.name, rc == 0 and "착수 전 1" in out, "--discover 가 착수 전 원장을 센다(숨기지 않는다)", out[-200:])

    # ── fz-code-start — 같은 세션이 fz-code 줄로 착수 → 미충족 active 는 막힌다 ────────────
    with Cell("fz-code-start") as c:
        check(c.name, len(has(START_CALLS, "--set-state active")) == 1,
              "fz-code Phase 0.4 에 `--set-state active` 호출 1개", START_CALLS)
        c.plan_session()
        started = c.code_start()
        check(c.name, bool(started) and all(rc == 0 for _, rc, _ in started), "Phase 0.4 재생 exit 0",
              [(x[:60], rc, out[-120:]) for x, rc, out in started])
        check(c.name, c.state() == "active", "STATE active — 착수는 증명 불요", c.state())
        rc, reason, err = c.hook()
        check(c.name, rc == 2 and reason is not None, "미충족 active → 훅 차단(exit 2)", f"rc={rc} {err[-300:]}")
        r = reason or ""
        check(c.name, "`ABANDON: <게이트ID> <이유>`" in r and "--set-state planned" in r and "착수 전" in r,
              "사유에 셋째 선택지 — 착수 전이면 ABANDON 아님 · `--set-state planned`", r[-400:])
        c.touch("impl-S1.done")
        rc, out = c.step("S1")
        check(c.name, rc == 0 and "PASS  S1" in out, "fz-code 6.4 `--only S1` 줄로 S1 PASS", f"rc={rc} {out[-300:]}")
        check(c.name, re.search(r"^- \[x\] S1:", c.text(), re.M) is not None and "sig=" in c.text(), "S1 [x] · 서명 증거", "")

    # ── work-recorded — 진행 기록 있는 원장의 planned 역행 거부 ───────────────────────────
    with Cell("work-recorded") as c:
        c.plan_session()
        c.code_start()
        c.touch("impl-S1.done")
        c.step("S1")
        refuse_planned(c.name, c, "PASS 증거")
        rc, reason, err = c.hook()
        check(c.name, rc == 2, "거부 뒤에도 훅 차단(S2 미충족)", f"rc={rc} {err[-200:]}")
    with Cell("work-recorded-demoted") as c:
        c.plan_session()
        c.code_start()
        c.touch("impl-S1.done")
        c.step("S1")
        try:
            (c.r / "impl-S1.done").unlink()
        except OSError as e:
            raise Setup(f"산출물 삭제 실패: {e}")
        rc, out = c.gc("--reverify", str(c.led))
        t = c.text()
        check(c.name, rc == 1 and re.search(r"^- \[ \] S1:", t, re.M) is not None, "--reverify 가 S1 을 강등(exit 1 · [ ])",
              f"rc={rc} {out[-200:]}")
        check(c.name, "EVIDENCE: pending; demoted" in t and "sig=" not in t,
              "강등 기록 `pending; demoted` 만 남는다(서명 증거 0) — reverify 이력", t[-400:])
        refuse_planned(c.name, c, "강등 기록")
    with Cell("work-recorded-confirm") as c:
        c.plan_session()
        c.code_start()
        rc, out = c.confirm("S3")
        check(c.name, rc == 0 and "CONFIRMED: " in c.text(), "--confirm S3(pty · y) 가 확인을 기록", f"rc={rc} {out[-200:]}")
        refuse_planned(c.name, c, "--confirm 기록")
    with Cell("work-recorded-reapproved") as c:
        # 기록은 있지만 지금 unmet 인 게이트(재승인으로 옛 PASS 서명이 새 oracle 과 안 맞는다)가 재실행에서 떨어져도 흔적이 남는가
        c.plan_session()
        c.code_start()
        c.touch("impl-S1.done")
        c.step("S1")
        t = c.text()
        changed = t.replace("CHECK: test -f impl-S1.done && echo s1 ok", "CHECK: test -f impl-S1b.done && echo s1 ok", 1)
        if changed == t:
            raise Setup("S1 CHECK 편집 실패")
        c.write(changed)
        rc, out = c.gc("--finalize", "--only", "S1", str(c.led))
        check(c.name, rc == 0, "S1 CHECK 수정 뒤 `--finalize --only S1` 재승인 exit 0", f"rc={rc} {out[-200:]}")
        rc, out = c.gc("--status", str(c.led), record=False)
        check(c.name, rc == 1 and "UNMET S1" in out and "sig=" in c.text(),
              "재승인 뒤 S1 은 unmet 이지만 옛 기록([x] · 서명 증거)은 남는다", f"rc={rc} {out[-200:]}")
        rc, out = c.step("S1")
        t = c.text()
        check(c.name, rc == 1 and re.search(r"^- \[ \] S1:", t, re.M) is not None and "EVIDENCE: pending; demoted" in t,
              "재승인 뒤 S1 FAIL → `pending; demoted`(직전 met 이 아니어도 흔적이 있으면 강등 기록)", f"rc={rc} {out[-200:]}")
        refuse_planned(c.name, c, "재승인 뒤 FAIL 의 강등 기록")
    with Cell("work-recorded-forged") as c:
        c.plan_session()
        c.code_start()
        t = c.text()
        forged = t.replace("- [ ] S2: 둘째 구현", "- [x] S2: 둘째 구현", 1)
        forged = re.sub(r"(- \[x\] S2: 둘째 구현\n(?:  .*\n)*?)  EVIDENCE: pending",
                        r"\1  EVIDENCE: sig=000000000000; exit=0; cwd=/; env=forged; output=s2 ok", forged, count=1)
        if forged == t or "sig=000000000000" not in forged:
            raise Setup("위조 증거 편집 실패")
        c.write(forged)
        rc, out = c.gc("--status", str(c.led), record=False)
        check(c.name, rc == 1 and "UNMET S2" in out, "위조 증거는 met 이 아니다(--status exit 1 · S2 UNMET)", f"rc={rc} {out[-200:]}")
        refuse_planned(c.name, c, "위조 증거(흔적도 기록이다)")
        c.write(forged.replace("STATE: active", "STATE: planned", 1))
        rc, out = c.gc("--status", str(c.led), record=False)
        check(c.name, rc == 1, "손으로 STATE planned 를 쓴 기록 있는 원장은 no-op 이 아니다(--status exit 1)", f"rc={rc} {out[-200:]}")
        rc, reason, err = c.hook()
        check(c.name, rc == 2, "그 원장도 훅이 막는다", f"rc={rc} {err[-200:]}")

    # ── refinalize — 진행 기록 있는 active 원장을 다시 확정해도 planned 가 되지 않는다 ─────────
    with Cell("refinalize") as c:
        c.plan_session()
        c.code_start()
        c.touch("impl-S1.done")
        c.step("S1")
        rc, out = c.gc("--finalize", "--only", "S1", str(c.led))
        check(c.name, rc == 0 and c.state() == "active", "`--finalize --only S1` 뒤 STATE active", f"rc={rc} {c.state()} {out[-200:]}")
        c.write(c.text().replace("APPROVED: yes\n", "", 1))
        rc, out = c.gc("--finalize", str(c.led))
        t = c.text()
        check(c.name, rc == 0 and c.state() == "active", "헤더를 지우고 `--finalize` 해도 STATE active", f"rc={rc} {c.state()} {out[-200:]}")
        check(c.name, t.count("sig=") == 1 and re.search(r"^- \[x\] S1:", t, re.M) is not None, "재확정이 진행 기록을 지우지 않는다", "")
        refuse_planned(c.name, c, "재확정 뒤")
        rc, reason, err = c.hook()
        check(c.name, rc == 2, "재확정 뒤에도 훅 차단", f"rc={rc} {err[-200:]}")

    # ── unmet-active — 미충족 active 는 계속 막힌다 ────────────────────────────────────────
    with Cell("unmet-active") as c:
        c.plan_session()
        c.code_start()
        shots = [c.hook() for _ in range(MAX_BLOCKS + 1)]
        rcs = [s[0] for s in shots]
        check(c.name, rcs == [2] * MAX_BLOCKS + [0], f"{MAX_BLOCKS}회 막고 {MAX_BLOCKS + 1}회째 루프 방어 통과", rcs)
        check(c.name, "회 막았다" in shots[-1][2], "마지막 통과는 루프 방어 진단", shots[-1][2][-200:])
        check(c.name, c.state() == "active" and "ABANDON:" not in c.text(), "원장은 그대로(STATE active · ABANDON 0)", c.state())

    # ── planned-refuses — 착수 전 원장은 판정만 no-op, 실행은 exit 3 ──────────────────────
    with Cell("planned-refuses") as c:
        c.plan_session()
        check(c.name, c.state() == "planned", "준비: STATE planned", c.state())
        before = c.text()
        for label, args in (("기본 실행", ()), ("--only S1", ("--only", "S1")), ("--reverify", ("--reverify",))):
            rc, out = c.gc(*args, str(c.led))
            check(c.name, rc == 3 and "--set-state active" in out, f"{label} → exit 3 · 착수 안내", f"rc={rc} {out[-200:]}")
        rc, out = c.step("S1")
        check(c.name, rc == 3, "fz-code 6.4 `--only` 줄도 exit 3 — Phase 0.4 를 건너뛰면 멈춘다", f"rc={rc} {out[-200:]}")
        rc, out = c.confirm("S3")
        check(c.name, rc == 3, "--confirm → exit 3(확인도 진행 기록)", f"rc={rc} {out[-200:]}")
        check(c.name, c.text() == before, "원장 바이트 불변", "")
        for tgt in ("ready_for_review", "closed"):
            rc, out = c.gc("--set-state", tgt, str(c.led))
            check(c.name, rc == 1 and c.state() == "planned", f"planned → {tgt} 거부(표 밖 간선)", f"rc={rc} {out[-200:]}")
        rc, out = c.gc("--set-state", "active", str(c.led))
        check(c.name, rc == 0 and c.state() == "active", "planned → active 증명 불요(미충족 3 그대로)", f"rc={rc} {out[-200:]}")

    # ── one-path — 생성 · 확정 · planned 의 진입 경로 ─────────────────────────────────────
    with Cell("one-path") as c:
        try:
            (c.r / "gates").mkdir(parents=True)
            pj = c.cwd / "p.json"
            pj.write_text(json.dumps({"title": "t", "steps": [{"id": "G1", "title": "t", "verify": {
                "kind": "command", "criterion": "c", "command": "echo ok", "expect": "ok"}}]}), encoding="utf-8")
        except OSError as e:
            raise Setup(f"plan JSON 준비 실패: {e}")
        rc, out = c.gc("--from-plan", str(pj), "--root", str(c.r), "--out", str(c.led))
        check(c.name, rc == 0 and c.state() == "active", "생성(--from-plan) STATE active", f"rc={rc} {c.state()} {out[-200:]}")
        rc, out = c.gc("--finalize", str(c.led))
        want = "active" if VARIANT == "contract" else "planned"
        check(c.name, rc == 0 and c.state() == want, f"--finalize 뒤 STATE {want}", f"rc={rc} {c.state()} {out[-200:]}")
        rc, out = c.gc("--set-state", "planned", str(c.led))
        check(c.name, rc == 0 and c.state() == "planned", "확정 · 진행 기록 0 → --set-state planned exit 0", f"rc={rc} {out[-200:]}")

    # ── residual-no-record — ⛔ 잔존 위험 고정: 기록 0 인 착수 세션의 planned 역행 ─────────────────
    for label, run_gate in (("게이트 0회", False), ("실패만 1회", True)):
        with Cell("residual-no-record") as c:
            c.plan_session()
            c.code_start()
            c.touch("impl-code.changed")                 # 코드는 고쳤다 — 게이트는 안 돌렸거나 실패만 했다
            if run_gate:
                rc, out = c.step("S1")
                check(c.name, rc == 1 and "EVIDENCE: pending; demoted" not in c.text(),
                      f"{label}: S1 FAIL 은 `pending` 그대로(통과한 적이 없다)", f"rc={rc} {out[-200:]}")
            rc, out = c.gc("--set-state", "planned", str(c.led))
            hrc, reason, err = c.hook()
            if VARIANT == "contract":
                check(c.name, rc == 0 and c.state() == "planned" and hrc == 0,
                      f"RESIDUAL {label}: 진행 기록 0 → planned 허용 · 훅 통과 (계약이 남긴 우회 — 지금 열려 있음을 기록)",
                      f"set-state rc={rc} · hook rc={hrc} · {out[-200:]}")
            else:
                check(c.name, rc == 1 and c.state() == "active" and hrc == 2,
                      f"{label}: active → planned 무조건 거부 · 훅 차단", f"set-state rc={rc} · hook rc={hrc}")

    # ── residual-replan — ⛔ 잔존 위험 고정: 진행 중 원장에서 4.5 재생(재계획) ─────────────────────
    #    cp(산문 단계)가 판정기 밖에서 기록을 먼저 덮으므로 두 분기 모두 같은 결과다 — 판정기 전제는 덮인 원장만 본다
    with Cell("residual-replan") as c:
        c.plan_session()
        c.code_start()
        c.touch("impl-S1.done")
        rc, out = c.step("S1")
        check(c.name, rc == 0 and "sig=" in c.text(), "준비: 착수 뒤 S1 PASS 기록", f"rc={rc} {out[-200:]}")
        c.plan_session()
        t = c.text()
        hrc, reason, err = c.hook()
        check(c.name, c.state() == "planned" and "sig=" not in t and hrc == 0,
              "RESIDUAL 재계획: 4.5 재생의 cp 가 진행 기록을 덮어 planned · 훅 통과 (판정기 밖 우회 — 지금 열려 있음을 기록)",
              f"STATE={c.state()} · sig={'sig=' in t} · hook rc={hrc} · {err[-200:]}")
except Setup as e:
    print(f"SETUP {e}")
    sys.exit(3)

ran = {}
for name, n in RAN:
    ran[name] = ran.get(name, 0) + 1
empty = [name for name, n in RAN if n == 0]
check("cell-set", ran == EXPECTED_CELLS and not empty, "돈 셀 이름 · 횟수 = EXPECTED_CELLS (단언 0개인 셀 없음)",
      f"없음={sorted(set(EXPECTED_CELLS) - set(ran))} · 뜻밖={sorted(set(ran) - set(EXPECTED_CELLS))} · "
      f"횟수 차={[k for k in EXPECTED_CELLS if k in ran and ran[k] != EXPECTED_CELLS[k]]} · 빈 셀={empty}")
print()
print(f"SUMMARY variant={VARIANT} fail={len(FAIL)}")
for f in FAIL:
    print(f"  FAIL {f}")
print(f"CELLS n={len(RAN)} ran={','.join(name for name, _ in RAN)}")
sys.exit(1 if FAIL else 0)
PY
