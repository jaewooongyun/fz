#!/bin/bash
# Stop 훅 차단 사유 fixture (F-360 · EC-07) — 사유가 미충족 id 목록을 싣고, 반복 차단 지문은 그대로인지 동작으로 본다.
#   two-unmet     소유 원장 미충족 2개 → 사유에 두 id · `UNMET: 2` · 지문 = sha12("<원장>:unmet")
#   over-cap      미충족 11개 → 표시 id ≤ 8 · 표시 id 수 + `…외 N건` = 11
#   long-ids      긴 id 11개 → 요약 ≤ 400자로 줄어도 표시 + 생략 = 11
#   churn         같은 세션 · 같은 원장이 2개 → 11개로 바뀌어도 지문 1개 · 2회 막고 3회째 통과(MAX_BLOCKS=2)
#   foreign-k     남의 원장 3개(= 접기 한도 k) → 원장별 경고 3줄 · 통과(비소유 notes 회귀)
#   foreign-fold  남의 원장 5개(미충족 4 · 계약 위반 1) + 소유 1개 → 경고는 건수 한 줄 · 원장 경로 0
#   length-cap    소유 원장 8개 × 긴 요약 → 사유 ≤ 4000자 · 안내 줄 보존 · 표시 줄 + `…외 N줄` = 8 · 지문 8항
#   invalid       소유 원장 계약 위반(중복 id) → `⛔ 원장 계약 위반` 사유 · 지문 = sha12("<원장>:invalid")(exit 3 사유 경로)
#   infra         소유 원장 읽기 불가(chmod 000) → 판정기 exit 2 · `인프라` 진단 · 통과(인프라 실패 회귀)
# 지문은 기준 공식(`gate_stop_hook.py` 지문 블록 — 원장 경로:판정 종류의 sha12)을 여기서 따로 계산해 상태 파일 키와 맞춘다.
# 기준 트리는 끝 줄만 실어 two-unmet · over-cap · long-ids 에서 앞 id 를 놓치고, 남의 원장을 접지 않는다 → exit 1.
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 스크립트 · 임시 폴더 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 스크립트 exit 1' 게이트가 결함 재현 없이 통과한다 — 그래서 3 이다(미처리 예외도 3).
#   ⛔ 기능 부재(목록 없음 · 접기 없음)는 단언 실패(1)다. 훅의 새 상수를 import 하지 않는다 — 계약 값은 아래에 고정한다.
# ⛔ 중첩 가드: 이 러너가 도는 동안 FZ_STOP_REASON_MULTI_FIXTURE=1 이다. 안에서 다시 불리면 `UNRUN:` 을 내고 exit 2.
# ⛔ 셀마다 임시 cwd · 임시 HOME(루프 방어 상태 파일) · 고유 session_id 를 쓴다. 바깥 FZ_GATES_LEDGER · FZ_GATES_OFF ·
#    FZ_GATES_TRACE 는 자식에게 넘기지 않는다 — 넘기면 바깥 원장을 판정하거나 판정을 통째로 건너뛴다.
# usage: run.sh [--scripts <scripts 폴더>]   (기본: 이 fixture 가 든 트리의 scripts/)
set -u
if [ -n "${FZ_STOP_REASON_MULTI_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 stop-reason-multi 가 도는 중"
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

FZ_STOP_REASON_MULTI_FIXTURE=1 PYTHONDONTWRITEBYTECODE=1 python3 -B - "$S" <<'PY'
import hashlib, json, os, pathlib, re, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

HOOK = pathlib.Path(sys.argv[1]) / "gate_stop_hook.py"
PY = sys.executable
IDS_SHOWN, SUMMARY_MAX, FOLD_K, REASON_MAX, MAX_BLOCKS = 8, 400, 3, 4000, 2   # 사유 계약 값(F-360 · EC-07)
FAIL = []


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def fp(entries):
    """기준 지문 공식 — `sha12("|".join(sorted(["<원장>:unmet" | "<원장>:invalid", …])))`."""
    return hashlib.sha256("|".join(sorted(entries)).encode("utf-8", "replace")).hexdigest()[:12]


def gate(gid):
    return (f"- [ ] {gid}: 판정 대상 {gid}\n  CRITERION: 사람이 읽는 합격 조건\n  CHECK: echo ok\n"
            "  EXPECT: ok\n  CWD: /usr\n  EVIDENCE: pending\n")


def ledger(cwd, rel, ids, dup=False):
    """`cwd/rel/gates/plan.md` 에 미충족 원장을 쓴다 — 반환은 훅이 쓰는 꼴(resolve 한 경로)."""
    g = cwd / rel / "gates"
    try:
        g.mkdir(parents=True, exist_ok=True)
        body = (f"# Gates: stop-reason-multi\nROOT: {g.parent}\nSTATE: active\nScope: 사유 계약\n\n"
                + "\n".join(gate(i) for i in ids) + ("\n" + gate(ids[0]) if dup else ""))
        (g / "plan.md").write_text(body, encoding="utf-8")
    except OSError as e:
        raise Setup(f"원장 기록 실패: {e}")
    return (g / "plan.md").resolve()


def transcript(cwd, owned):
    """이 세션이 `owned` 원장만 `Write` 로 쓴 세션 기록. 다른 원장은 남의 원장이 된다."""
    rows = [json.dumps({"type": "user", "message": {"content": "stop-reason-multi gates"}})]
    rows += [json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "input": {"file_path": str(p), "content": "x"}}]}})
        for p in owned]
    tp = cwd / "transcript.jsonl"
    try:
        tp.write_text("\n".join(rows) + "\n", encoding="utf-8")
    except OSError as e:
        raise Setup(f"세션 기록 실패: {e}")
    return tp


def hook(cwd, home, session, tp):
    """훅 1회 → (exit, 차단 사유 | None, stderr 전체)."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("FZ_GATES_LEDGER", "FZ_GATES_OFF", "FZ_GATES_TRACE")}
    env.update(HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    payload = {"hook_event_name": "Stop", "cwd": str(cwd), "session_id": session, "transcript_path": str(tp)}
    try:
        r = subprocess.run([PY, "-B", str(HOOK)], input=json.dumps(payload).encode(),
                           capture_output=True, env=env, timeout=120)
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


def state(home):
    p = home / ".fz" / "stop-hook-state.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError) as e:
        raise Setup(f"상태 파일 읽기 실패: {e}")


def summary_of(reason, prefix, led):
    """사유에서 `<prefix><원장> — ` 줄의 요약 부분. 없으면 None."""
    head = f"{prefix}{led} — "
    for line in (reason or "").split("\n"):
        if line.startswith(head):
            return line[len(head):]
    return None


def shown_ids(summ, ids):
    return [i for i in ids if re.search(r"(?<![\w.-])" + re.escape(i) + r"(?![\w.-])", summ or "")]


def omitted(summ):
    m = re.search(r"…외 (\d+)건", summ or "")
    return int(m.group(1)) if m else 0


class Cell:
    """셀 하나 = 임시 cwd + 임시 HOME + 고유 세션."""
    n = 0

    def __init__(self, name):
        Cell.n += 1
        self.name, self.session = name, f"srm-{Cell.n}-{name}"

    def __enter__(self):
        try:
            self.td = tempfile.TemporaryDirectory(prefix="fz-srm-")
        except OSError as e:
            raise Setup(f"임시 폴더 생성 실패: {e}")
        root = pathlib.Path(self.td.name).resolve()
        self.cwd, self.home = root / "w", root / "home"
        self.cwd.mkdir()
        self.home.mkdir()
        return self

    def __exit__(self, *exc):
        for p in self.cwd.rglob("plan.md"):
            try:
                p.chmod(0o644)
            except OSError:
                pass
        self.td.cleanup()


def summary_cell(name, ids, want_ids_all):
    """소유 원장 하나 · 미충족 `ids` → 차단 · 요약의 id 산술 · 지문."""
    with Cell(name) as c:
        led = ledger(c.cwd, "T-0001", ids)
        rc, reason, err = hook(c.cwd, c.home, c.session, transcript(c.cwd, [led]))
        check(name, rc == 2 and reason is not None, "소유 원장 미충족 → 차단(exit 2)", f"rc={rc} {err[-300:]}")
        summ = summary_of(reason, "미충족 게이트: ", led)
        check(name, summ is not None, "사유에 `미충족 게이트: <원장> — ` 줄", (reason or "")[:300])
        got, rest = shown_ids(summ, ids), omitted(summ)
        check(name, f"UNMET: {len(ids)} (" in (summ or ""), f"요약에 `UNMET: {len(ids)}` 줄", summ)
        if want_ids_all:
            check(name, got == ids and rest == 0, f"미충족 id {len(ids)}개가 모두 보인다", summ)
        else:
            check(name, 1 <= len(got) <= IDS_SHOWN and got == ids[:len(got)], f"표시 id 는 앞에서부터 1~{IDS_SHOWN}개", summ)
            check(name, len(got) + rest == len(ids), f"표시 id 수 + 생략 수 = {len(ids)}", f"표시 {len(got)} · 생략 {rest} · {summ}")
        check(name, len(summ or "") <= SUMMARY_MAX, f"요약 ≤ {SUMMARY_MAX}자", f"{len(summ or '')}자")
        st = state(c.home)
        check(name, st == {f"{c.session}|{fp([f'{led}:unmet'])}": 1},
              "지문 = 기준 공식 sha12(<원장>:unmet) · 카운트 1", st)


try:
    # ── two-unmet · over-cap · long-ids — 사유의 미충족 목록(F-360) ──────────────
    summary_cell("two-unmet", ["S36", "S28d"], True)
    summary_cell("over-cap", [f"U{i:02d}" for i in range(1, 12)], False)
    summary_cell("long-ids", [f"L{i:02d}-" + "x" * 56 for i in range(1, 12)], False)

    # ── churn — 사유가 바뀌어도 지문 · MAX_BLOCKS 는 그대로 ───────────────────────
    with Cell("churn") as c:
        led = ledger(c.cwd, "T-0001", ["S36", "S28d"])
        tp = transcript(c.cwd, [led])
        shots = [hook(c.cwd, c.home, c.session, tp)]
        ledger(c.cwd, "T-0001", [f"U{i:02d}" for i in range(1, 12)])          # 옆 편집 — 내용 · 요약이 바뀐다
        shots += [hook(c.cwd, c.home, c.session, tp) for _ in range(MAX_BLOCKS)]
        rcs = [s[0] for s in shots]
        check("churn", rcs == [2] * MAX_BLOCKS + [0], f"{MAX_BLOCKS}회 막고 {MAX_BLOCKS + 1}회째 통과", rcs)
        check("churn", "회 막았다" in shots[-1][2], "마지막 통과는 루프 방어 진단", shots[-1][2][-200:])
        check("churn", shots[0][1] != shots[1][1], "두 차단의 사유는 다르다(요약이 바뀐 셀)", "")
        st = state(c.home)
        check("churn", st == {f"{c.session}|{fp([f'{led}:unmet'])}": MAX_BLOCKS + 1},
              "지문 1개 · 카운트 3 — 요약 변화가 카운터를 리셋하지 않는다", st)

    # ── foreign-k — 남의 원장 k 개는 원장별 경고(비소유 notes 회귀) ────────────────
    with Cell("foreign-k") as c:
        leds = [ledger(c.cwd, f"F-{i}", ["S36", "S28d"]) for i in range(FOLD_K)]
        rc, reason, err = hook(c.cwd, c.home, c.session, transcript(c.cwd, []))
        check("foreign-k", rc == 0 and reason is None, "남의 원장만 → 통과(exit 0)", f"rc={rc} {err[-300:]}")
        for led in leds:
            check("foreign-k", f"다른 세션의 원장(막지 않음): {led} — " in err, f"원장별 경고 줄: {led.parent.parent.name}", err[-300:])
        check("foreign-k", state(c.home) == {}, "통과는 상태 파일을 쓰지 않는다", state(c.home))

    # ── foreign-fold — 남의 원장 k+2 개는 건수 한 줄(EC-07) ──────────────────────
    with Cell("foreign-fold") as c:
        own = ledger(c.cwd, "A-own", ["S36", "S28d"])
        leds = [ledger(c.cwd, f"F-{i}", ["S36", "S28d"]) for i in range(FOLD_K + 1)]
        leds.append(ledger(c.cwd, "F-bad", ["S36"], dup=True))
        n = len(leds)
        rc, reason, err = hook(c.cwd, c.home, c.session, transcript(c.cwd, [own]))
        check("foreign-fold", rc == 2 and reason is not None, "소유 원장 미충족 → 차단", f"rc={rc} {err[-300:]}")
        lines = [l for l in (reason or "").split("\n") if "다른 세션의 원장" in l]
        check("foreign-fold", len(lines) == 1, f"남의 원장 {n}개 → 경고 한 줄", lines)
        fold = lines[0] if lines else ""
        check("foreign-fold", f"{n}개" in fold and f"미충족 {n - 1}" in fold and "계약 위반 1" in fold,
              f"접은 줄에 건수 {n} · 미충족 {n - 1} · 계약 위반 1", fold)
        check("foreign-fold", "--discover" in fold, "접은 줄에 원장별 목록 명령", fold)
        check("foreign-fold", not any(str(l) in (reason or "") for l in leds), "사유에 남의 원장 경로 0", "")
        check("foreign-fold", summary_of(reason, "미충족 게이트: ", own) is not None, "소유 원장 줄은 그대로", "")
        check("foreign-fold", state(c.home) == {f"{c.session}|{fp([f'{own}:unmet'])}": 1},
              "지문 = 소유 원장만(남의 원장 수와 무관)", state(c.home))

    # ── length-cap — 사유 전체 상한 ──────────────────────────────────────────────
    with Cell("length-cap") as c:
        deep = "d" * 120
        ids = [f"L{i:02d}-" + "x" * 56 for i in range(1, 12)]
        leds = [ledger(c.cwd, f"T-{i}{deep}/{deep}", ids) for i in range(8)]
        rc, reason, err = hook(c.cwd, c.home, c.session, transcript(c.cwd, leds))
        check("length-cap", rc == 2 and reason is not None, "소유 원장 8개 → 차단", f"rc={rc} {err[-300:]}")
        r = reason or ""
        shown = sum(1 for l in leds if summary_of(r, "미충족 게이트: ", l) is not None)
        m = re.search(r"…외 (\d+)줄 생략", r)
        cut = int(m.group(1)) if m else 0
        check("length-cap", len(r) <= REASON_MAX, f"사유 ≤ {REASON_MAX}자", f"{len(r)}자")
        check("length-cap", cut > 0 and shown + cut == len(leds), f"표시 줄 + 생략 줄 = {len(leds)}", f"표시 {shown} · 생략 {cut}")
        check("length-cap", "`ABANDON: <게이트ID> <이유>`" in r and "--status <원장>" in r, "안내 줄(ABANDON 출구 · 판정 명령) 보존", r[-300:])
        check("length-cap", state(c.home) == {f"{c.session}|{fp([f'{l}:unmet' for l in leds])}": 1},
              "지문 = 원장 8개 path:unmet 의 정렬 결합", state(c.home))

    # ── invalid — exit 3 사유 경로 ───────────────────────────────────────────────
    with Cell("invalid") as c:
        led = ledger(c.cwd, "T-0001", ["S36"], dup=True)
        rc, reason, err = hook(c.cwd, c.home, c.session, transcript(c.cwd, [led]))
        summ = summary_of(reason, "⛔ 원장 계약 위반: ", led)
        check("invalid", rc == 2 and summ is not None, "계약 위반 → 차단 · `⛔ 원장 계약 위반: <원장> — ` 줄", f"rc={rc} {err[-300:]}")
        check("invalid", "INVALID LEDGER" in (summ or "") and "중복 게이트 id" in (summ or ""), "요약 = 판정기 stderr 끝 줄", summ)
        check("invalid", state(c.home) == {f"{c.session}|{fp([f'{led}:invalid'])}": 1},
              "지문 = 기준 공식 sha12(<원장>:invalid)", state(c.home))

    # ── infra — 판정기 exit 2 는 막지 않고 진단만 ─────────────────────────────────
    with Cell("infra") as c:
        led = ledger(c.cwd, "T-0001", ["S36", "S28d"])
        tp = transcript(c.cwd, [led])
        led.chmod(0)
        if os.access(led, os.R_OK):
            raise Setup("chmod 000 이 읽기를 막지 못한다(root 실행?) — 인프라 셀을 만들 수 없다")
        rc, reason, err = hook(c.cwd, c.home, c.session, tp)
        check("infra", rc == 0 and reason is None, "판정기 인프라 실패 → 통과(exit 0)", f"rc={rc} {err[-300:]}")
        check("infra", f"{led}: 인프라 — INFRA:" in err, "진단에 `<원장>: 인프라 — INFRA:` 줄", err[-300:])
        check("infra", state(c.home) == {}, "통과는 상태 파일을 쓰지 않는다", state(c.home))
except Setup as e:
    print(f"SETUP {e}")
    sys.exit(3)

print()
print(f"SUMMARY fail={len(FAIL)}")
for f in FAIL:
    print(f"  FAIL {f}")
sys.exit(1 if FAIL else 0)
PY
