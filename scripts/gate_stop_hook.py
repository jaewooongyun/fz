#!/usr/bin/env python3
"""완료 게이트 Stop hook — 미충족 원장이 있으면 세션 종료를 막는다.

이것이 게이트 계층의 **2차 계층**이다. 1차(배선 1~3)는 SKILL.md 산문이라 Lead가
건너뛰어도 아무 신호가 없다. 그 재귀를 끊는 것은 이 hook 하나뿐이다.

⛔ **자동 배선하지 않는다.** 이 파일은 실행체이고, 등록은 사용자가
`examples/hooks.json.example`을 `.claude/settings.json`으로 복사해야 발동한다.
근거: `modules/governance.md` "Claude는 훅 설치·설정 변경을 명시 합의 없이
지시·실행하지 않는다". 따라서 **기계적 차단은 설치한 머신에만 존재한다.**

## 계약 (실측 출처)

`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/plugin-dev/skills/
hook-development/` — 공식 plugin-dev 스킬.

입력 (stdin JSON):
    {"session_id": …, "transcript_path": …, "cwd": …,
     "permission_mode": …, "hook_event_name": "Stop"}

차단 출력 (`references/advanced.md:262`의 command 타입 예시):
    stderr ← {"decision": "block", "reason": "…"}
    exit 2

⛔ `hookSpecificOutput.decision` 도 `{"continue": false}` 도 아니다 — **top-level
`decision`** 이다. 세 후보 중 어느 것인지는 공식 스킬 문서로 확정했다(probe 불요).

## 설계 결정

**원장 발견 = `cwd` 하위 glob (깊이 0~3).** `session_id`가 입력에 오므로
`~/.fz/sessions/<id>.json` 바인딩도 가능하지만 쓰지 않는다 — 바인딩은 **쓰는 쪽
배선**이 필요하고, 그 배선이 빠지면 hook이 원장을 못 찾아 조용히 무력화된다(이
작업에서 다섯 번 만난 실패 모드다). glob은 배선이 0이고, 여러 원장을 전부 보므로
다른 미완 작업을 놓치지 않는다. `STATE: closed`는 판정기가 no-op으로 걸러낸다.

⛔ **깊이 한계와 그 밖.** 깊이 4 이상, 그리고 `cwd` **밖**(워크트리에서 작업하고
원장이 리포 루트에 있는 경우)은 어떤 glob으로도 찾지 못한다 — hook은 `cwd`만
받으므로 설계 한계다. `FZ_GATES_LEDGER`(경로 목록, `os.pathsep` 구분)로 명시
지정할 수 있다.

⛔ **"찾지 못함"은 조용하지 않다.** `gates/` 디렉토리가 아예 없으면 게이트 미사용
세션이므로 조용히 통과하지만, `gates/`는 있는데 확정 원장이 없으면 그 사실을
stderr로 남긴다. 미사용과 미발견이 같은 침묵이면 놓친 원장이 통과로 보인다.

**판정 = 재실행 없음.** `CHECK`를 다시 돌리면 게이트당 기본 120초여서 hook에
부적합하다. 기록된 증거를 읽어 판정한다 — 증거는 서명으로 oracle에 묶여 있어
"CHECK를 안 돌리고 통과 텍스트만 쓴" 경로를 이미 막는다.

**전면 fail-open.** 어떤 오류든 exit 0이다. `modules/gates.md`의 exit 계약이
"세션 감금이 게이트 누락보다 나쁘다"를 이미 정했고, hook은 그 원칙이 가장
날카롭게 적용되는 자리다 — 여기서 실수하면 사용자가 세션을 끝낼 수 없다.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scripts/ → 플러그인 루트

HOOK_EVENTS = ("Stop", "SubagentStop")
# ⛔ 원장 발견(glob 깊이·SKIP_DIRS·상한)과 `FZ_GATES_LEDGER` 는 **판정기가 소유한다** —
#    `gate_check.py`의 `find_ledgers`. 여기에 복제하면 두 구현이 갈린다.
LEDGER_ENV = "FZ_GATES_LEDGER"
CHECK_TIMEOUT_S = 20                   # 판정기 1회 호출 상한
TOTAL_BUDGET_S = 45                    # 전체 예산 — 넘으면 통과(진단만)
MAX_BLOCKS = 2                         # 같은 상태로 이 횟수까지만 막는다
STATE_FILE = Path.home() / ".fz" / "stop-hook-state.json"

EXIT_PASS, EXIT_BLOCK = 0, 2


def _pass(diagnostic: str = "") -> int:
    """통과. 진단은 stderr로만 — Claude에게 피드백되지만 차단은 아니다."""
    if diagnostic:
        print(f"[gate-stop-hook] {diagnostic}", file=sys.stderr)
    return EXIT_PASS


def _block(reason: str) -> int:
    """차단. ⛔ JSON 은 **stderr** 로, exit 는 **2** — 공식 command 타입 계약."""
    print(json.dumps({"decision": "block", "reason": reason},
                     ensure_ascii=False), file=sys.stderr)
    return EXIT_BLOCK


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


def find_checker() -> Path | None:
    """같은 `scripts/` 디렉토리의 판정기."""
    cand = ROOT / "scripts" / "gate_check.py"
    return cand if cand.is_file() else None


def load_checker_module():
    """판정기를 모듈로 불러온다 — **원장 발견 함수를 빌려 쓰기 위해서**.

    ⛔ 자체 구현을 두지 않는다. 두 곳이 각자 원장을 찾으면 한쪽이 놓치는 배치가
       생긴다 — 깊이 2만 보던 결함이 정확히 그것이었다. 린터의 선례와 같은 원칙이다
       (`lint_contracts.py:804` "chk_N6 와 self-test 가 **같은 함수**를 쓴다").

    ⛔ 판정은 여전히 subprocess 다(격리). import 는 부작용 없는 **탐색 함수** 하나만
       빌리기 위한 것이고, 실패하면 통과한다 — hook 은 어떤 오류로도 세션을 감금하지
       않는다.
    """
    checker = find_checker()
    if checker is None:
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fz_gate_check", checker)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:                                  # noqa: BLE001
        return None


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> bool:
    """⛔ 실패하면 False. 루프 방어를 못 하므로 호출부는 **통과**를 택한다 —
    상태를 못 쓰는데 막으면 무한 block 이 된다."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
        return True
    except OSError:
        return False


def judge(checker: Path, ledger: Path, budget_left: float):
    """판정기를 `--status` 로 부른다 — CHECK 재실행 없음.

    반환: (exit_code, 요약 한 줄). exit 는 판정기 계약을 그대로 쓴다
    (0 충족 · 1 미충족 · 2 인프라 · 3 원장 계약 위반).
    """
    timeout = min(CHECK_TIMEOUT_S, max(1.0, budget_left))
    try:
        proc = subprocess.run(
            [sys.executable, str(checker), "--status", str(ledger)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None, "판정기 호출 실패"
    out = (proc.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    tail = (out[-1] if out else "") or (err[-1] if err else "")
    return proc.returncode, tail[:200]


def main() -> int:
    started = time.monotonic()
    try:
        raw = sys.stdin.read()
    except OSError:
        return _pass("stdin 읽기 실패")
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return _pass("입력이 JSON 이 아니다")
    if not isinstance(payload, dict):
        return _pass("입력이 객체가 아니다")

    event = payload.get("hook_event_name")
    if event is not None and event not in HOOK_EVENTS:
        return _pass()          # 다른 이벤트에 잘못 배선됐다 — 조용히 통과

    if os.environ.get("FZ_GATES_OFF") == "1":
        return _pass("FZ_GATES_OFF=1 — 판정 생략")

    checker = find_checker()
    if checker is None:
        return _pass("판정기를 찾지 못했다 (설치 손상?)")

    cwd_raw = payload.get("cwd") or os.getcwd()
    try:
        cwd = Path(cwd_raw).resolve()
    except (OSError, RuntimeError):
        return _pass(f"cwd 해석 실패: {cwd_raw!r}")
    if not cwd.is_dir():
        return _pass(f"cwd 가 디렉토리가 아니다: {cwd}")

    gcmod = load_checker_module()
    if gcmod is None or not hasattr(gcmod, "find_ledgers"):
        return _pass("판정기 모듈을 불러올 수 없어 원장 탐색을 건너뛴다")
    ledgers, discovery_note = gcmod.find_ledgers(cwd, os.environ.get(LEDGER_ENV, ""))
    if not ledgers:
        # 진단이 있으면 남긴다 — "찾지 못함"이 조용한 통과로 보이면 안 된다.
        return _pass(discovery_note)

    unmet, invalid, notes = [], [], ([discovery_note] if discovery_note else [])
    for led in ledgers:
        left = TOTAL_BUDGET_S - (time.monotonic() - started)
        if left <= 1.0:
            notes.append(f"예산 소진 — {led.name} 미판정")
            break
        code, tail = judge(checker, led, left)
        if code is None or code == 2:
            notes.append(f"{led}: 인프라 — {tail}")
        elif code == 1:
            unmet.append((led, tail))
        elif code == 3:
            invalid.append((led, tail))

    if not unmet and not invalid:
        return _pass("; ".join(notes) if notes else "")

    # ── 무한 루프 방어 ──
    # Stop 을 막으면 Claude 가 계속하고 다시 Stop 에 도달한다. 원장 상태가 그대로면
    # 같은 이유로 또 막히므로 세션이 끝나지 않는다. ⛔ 문서에 `stop_hook_active`
    # 같은 필드가 없어(실측 grep 0건) 스크립트가 직접 방어한다.
    fingerprint = sha12("|".join(
        f"{p}:{sha12(p.read_text(encoding='utf-8', errors='replace'))}"
        if p.is_file() else str(p)
        for p, _ in unmet + invalid
    ))
    session = str(payload.get("session_id") or "no-session")
    key = f"{session}|{fingerprint}"
    state = load_state()
    count = int(state.get(key) or 0) + 1

    # 오래된 항목 정리 — 상태 파일이 무한히 자라지 않게
    if len(state) > 200:
        state = {}
    state[key] = count
    if not save_state(state):
        return _pass("루프 방어 상태를 쓸 수 없어 통과 — 무한 block 을 만들지 않는다")

    if count > MAX_BLOCKS:
        return _pass(
            f"같은 상태로 {MAX_BLOCKS}회 막았다 — 통과시킨다. "
            f"미충족 {len(unmet)}건 · 계약 위반 {len(invalid)}건 (수동 확인 필요)")

    lines = []
    for led, tail in invalid:
        lines.append(f"⛔ 원장 계약 위반: {led} — {tail}")
    for led, tail in unmet:
        lines.append(f"미충족 게이트: {led} — {tail}")
    lines += notes
    lines.append("")
    lines.append("게이트를 충족시키거나, 할 수 없으면 원장에 "
                 "`ABANDON: <게이트ID> <이유>` 를 남긴다 (포기 사실이 원장에 보존된다).")
    lines.append(f"판정: python3 {checker} --status <원장>")
    return _block("\n".join(lines))


# ── self-test ───────────────────────────────────────────────────────────
# ⛔ hook 은 등록해야 발동하지만, 계약(stdin JSON → exit + stderr)은 **등록 없이**
#    검증할 수 있다. 등록 자체는 사용자 소관이므로 여기까지가 우리가 닫을 수 있는
#    경계다 — 그 경계를 실행 가능한 형태로 남긴다(F-040: 1회 실행이 완료 조건).
# (이름, 원장 배치, payload 덮어쓰기, env, 기대 exit, 기대 stderr 조각)
#
# ⛔ **깊이 케이스가 핵심이다.** glob 을 `*/gates/plan.md` 하나로 두면 깊이 1·3·4 를
#    놓치고 **조용히 통과**한다 (2026-08-25 실측: 4종 중 1종만 발견). fixture 가
#    정확히 깊이 2 로만 원장을 만들면 그 결함이 관측되지 않는다 — 이 작업에서
#    "fixture 가 자기 이름의 축을 못 본다"를 여덟 번 만났다.
SELF_TEST_CASES = (
    ("no-gates-dir",   None,               {}, {}, 0, None),
    ("depth1",         "d1:unmet",         {}, {}, 2, '"decision": "block"'),
    ("depth2",         "unmet",            {}, {}, 2, '"decision": "block"'),
    ("depth3",         "d3:unmet",         {}, {}, 2, '"decision": "block"'),
    ("depth4",         "d4:unmet",         {}, {}, 2, '"decision": "block"'),
    ("draft-only",     "draft",            {}, {}, 0, "확정 원장(plan.md)이 없다"),
    ("skip-git",       "git:unmet",        {}, {}, 0, None),
    ("closed-passes",  "closed",           {}, {}, 0, None),
    ("approved-unmet", "approved",         {}, {}, 2, '"decision": "block"'),
    ("kill-switch",    "unmet",            {}, {"FZ_GATES_OFF": "1"}, 0, "FZ_GATES_OFF"),
    ("wrong-event",    "unmet",            {"hook_event_name": "PreToolUse"}, {}, 0, None),
    ("bad-cwd",        "unmet",            {"cwd": "/nonexistent/xyz"}, {}, 0, "디렉토리가 아니다"),
    ("env-missing",    None,               {}, {"FZ_GATES_LEDGER": "/nonexistent/x.md"},
                                              0, "찾을 수 없다"),
    # ⛔ 무한 루프 방어 — 같은 상태로 MAX_BLOCKS 회까지 막고 그 다음엔 통과한다.
    #    `repeat` 은 같은 session_id·같은 원장으로 N 회 발사한 뒤 **마지막** 결과를 본다.
    #    이 케이스가 없으면 방어를 제거해도 self-test 가 통과한다(2026-08-25 실측).
    ("loop-guard",     "unmet",            {}, {}, 0, "회 막았다"),
)
# 반복 발사가 필요한 케이스 — 이름 → 발사 횟수
REPEAT_CASES = {"loop-guard": MAX_BLOCKS + 1}


PROBE_LAYOUT = {
    "d1": "gates", "d3": "a/b/gates", "d4": "a/b/c/gates", "git": ".git/gates",
}


def _write_probe_ledger(root, spec):
    """`spec` = `[배치:]종류`. 배치 미지정이면 깊이 2(`ASD-0000/gates`)."""
    layout, _, kind = spec.rpartition(":")
    rel = PROBE_LAYOUT.get(layout, "ASD-0000/gates")
    gates = root / rel
    gates.mkdir(parents=True, exist_ok=True)
    name = "plan.draft.md" if kind == "draft" else "plan.md"
    state = "closed" if kind == "closed" else "active"
    approved = "APPROVED: yes\n" if kind == "approved" else ""
    body = ("# Gates: self-test\n"
            f"ROOT: {gates.parent}\n"
            f"STATE: {state}\n"
            f"{approved}"
            "Scope: hook 계약 검증\n\n"
            "- [ ] G1: 판정 대상\n"
            "  CRITERION: 사람이 읽는 합격 조건\n"
            "  CHECK: echo ok\n"
            "  EXPECT: ok\n"
            "  CWD: /usr\n"
            "  EVIDENCE: pending\n")
    target = gates / name
    target.write_text(body, encoding="utf-8")
    if kind == "approved":
        # ⛔ 닭-달걀: 도장을 계산하려면 파싱해야 하는데 `APPROVED: yes` 면 파싱이
        #    전수 도장을 요구한다. `--finalize` 가 정확히 그 순서를 아는 유일한 경로다
        #    — draft 로 쓰고 확정을 맡긴다. (직접 계산하려다 LedgerError 를 봤다)
        target.write_text(body.replace("APPROVED: yes\n", ""), encoding="utf-8")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "gate_check.py"),
             "--finalize", str(target)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, timeout=30, check=False)


def self_test() -> int:
    import shutil
    import tempfile
    me = str(Path(__file__).resolve())
    # ⛔ 상태 파일을 격리한다 — 사용자 실 상태를 오염시키면 안 되고,
    #    이전 회차 카운트가 남으면 unmet-blocks 가 통과로 뒤집힌다.
    home = Path(tempfile.mkdtemp(prefix="fz-hook-home-"))
    passed, failed = 0, []
    for name, kind, override, env, want_exit, want_err in SELF_TEST_CASES:
        d = Path(tempfile.mkdtemp(prefix="fz-hook-cwd-"))
        try:
            if kind is not None:
                _write_probe_ledger(d, kind)
            payload = {"hook_event_name": "Stop", "cwd": str(d),
                       "session_id": f"selftest-{name}"}
            payload.update(override)
            child = dict(os.environ)
            child["HOME"] = str(home)
            child.pop("FZ_GATES_OFF", None)
            child.update(env)
            shots = REPEAT_CASES.get(name, 1)
            for _ in range(shots):
                proc = subprocess.run(
                    [sys.executable, me], input=json.dumps(payload).encode(),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=child, timeout=60)
            err = (proc.stderr or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_err and want_err not in err:
                why.append(f"stderr 에 {want_err!r} 없음")
            if why:
                failed.append(f"{name}: {'; '.join(why)}")
            else:
                passed += 1
        finally:
            shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(home, ignore_errors=True)

    for f in failed:
        print(f"  FAIL {f}", file=sys.stderr)
    total = len(SELF_TEST_CASES)
    print(f"stop-hook self-test {passed}/{total} passed")
    return EXIT_PASS if not failed else 1


if __name__ == "__main__":
    # ⛔ `sys.exit()` 를 try 안에 두면 안 된다. `SystemExit` 은 `BaseException` 이라
    #    최후 방어가 그것을 잡아 exit 0 으로 바꾼다 — **차단이 영원히 발화하지 않는다.**
    #    실측(2026-08-25): `decision=block` JSON 은 stderr 로 나갔는데 exit 은 0 이었다.
    #    차단 코드가 있는데 발화하지 않는 것, 이 작업에서 다섯 번째로 만난 축이다.
    if "--self-test" in sys.argv[1:]:
        sys.exit(self_test())
    try:
        _code = main()
    except Exception as exc:                           # noqa: BLE001
        # 최후 방어 — 예상 외 오류로 세션을 감금하지 않는다. `SystemExit` 은 여기 안 온다.
        print(f"[gate-stop-hook] 예상 외 오류로 통과: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        _code = EXIT_PASS
    sys.exit(_code)
