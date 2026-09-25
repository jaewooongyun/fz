#!/usr/bin/env python3
# lint:no-root-anchor — 파일시스템 루트를 쓰지 않는다(순수 판정 함수 + 환경변수 읽기만).
"""자율 세션 모드의 행동 판정 (S18).

`FZ_AUTONOMY` 로 세션 모드를 받아 **이 행동을 지금 해도 되는가**를 판정한다.
⛔ 왜 플래그가 아니라 환경변수인가: 모드는 **워커까지 전파돼야** 한다. 플래그는
   `/fz` 호출 1회에만 붙고 하위 실행에 전달되지 않는다. kill-switch(`FZ_GATES_OFF`)가
   이미 같은 이유로 환경변수다 (`modules/governance.md` § Kill-Switch).

판정 3값 — 섞으면 "자율이니까 했다"가 금지 행동까지 덮는다.

  PROCEED  자동 진행
  ASK      사람에게 묻는다 (판정 불가·범위 밖·비가역 포함)
  BLOCK    모드와 무관하게 막는다

규칙 (위에서부터, 먼저 맞는 것이 이긴다):

  ① 금지 행동이면 **BLOCK**. ⛔ 자율 모드가 금지를 풀지 않는다 — 커밋·push·외부 발신·삭제는
     되돌리는 비용이 사람 확인 비용보다 크다. "자율이면 진행"만으로는 기존 승인과의 충돌을
     판정할 수 없다.
  ② 모드를 모르면 **ASK**. ⛔ fail-closed — 미지 값을 자율로 읽으면 오타 하나가 승인을 없앤다.
  ③ 대화형이면 **ASK**.
  ④ 자율이면 — **범위 안 + 가역**일 때만 PROCEED. 둘 중 하나라도 아니면 ASK.

복합 작업은 **가장 보수적인 판정이 이긴다** (BLOCK > ASK > PROCEED). 평균이나 다수결이
아니다 — 한 부분이 금지면 묶음 전체가 금지다.

exit: 0=PROCEED · 1=ASK · 3=BLOCK · 2=측정 실패(⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import os
import sys

PROCEED, ASK, BLOCK = "PROCEED", "ASK", "BLOCK"
EXIT = {PROCEED: 0, ASK: 1, BLOCK: 3}
UNRUN = 2

MODE_ENV = "FZ_AUTONOMY"
AUTONOMOUS, INTERACTIVE = "autonomous", "interactive"
KNOWN_MODES = (AUTONOMOUS, INTERACTIVE)
DEFAULT_MODE = INTERACTIVE   # ⛔ 미설정의 기본값은 **대화형**이다. 자율이 기본이면 설정 누락이 승인을 없앤다

# ⛔ 이름이 아니라 **되돌리는 비용**으로 고른 집합이다. 외부로 나간 것과 지운 것은 돌아오지 않는다.
FORBIDDEN = {
    "commit": "이력을 만든다 — 되돌리려면 이력을 다시 쓴다",
    "push": "남의 눈에 닿는다 — 회수가 불가능하다",
    "external_send": "외부 서비스로 나간다 — 캐시·인덱스에 남는다",
    "delete": "지운 것은 돌아오지 않는다",
    "pr_create": "외부 발신이다 — `push` 와 같은 축",
    "pr_edit": "외부 발신이다 — 게시된 내용을 바꾼다",
}

PRECEDENCE = {BLOCK: 0, ASK: 1, PROCEED: 2}   # 작을수록 보수적


def normalize_mode(raw) -> str:
    """빈 값·미설정은 기본값(대화형). 그 외 미지 값은 **그대로** 돌려준다(② 가 잡는다)."""
    if raw is None:
        return DEFAULT_MODE
    v = raw.strip().lower()
    if v == "":
        return DEFAULT_MODE
    return v


def decide_one(mode: str, action: str, in_scope: bool, reversible: bool) -> tuple:
    """(판정, 사유). ⛔ 순서를 바꾸면 자율 모드가 금지를 덮는다."""
    if action in FORBIDDEN:
        return BLOCK, f"금지 행동 `{action}` — {FORBIDDEN[action]} (⛔ 모드 무관)"
    if mode not in KNOWN_MODES:
        return ASK, f"모드 `{mode}` 를 모른다 — fail-closed 로 묻는다 (아는 값: {'·'.join(KNOWN_MODES)})"
    if mode == INTERACTIVE:
        return ASK, "대화형 모드 — 진행 전에 묻는다"
    if not in_scope:
        return ASK, "원래 요청 범위 밖 — 자율이라도 범위를 넓히지 않는다"
    if not reversible:
        return ASK, "비가역 작업 — 자율은 **범위 내 가역**까지만이다"
    return PROCEED, "자율 · 범위 내 · 가역"


def decide(mode: str, actions) -> tuple:
    """복합 작업 — 가장 보수적인 판정이 이긴다. 반환 (판정, [(행동, 판정, 사유)…])."""
    if not actions:
        return None, []          # ⛔ 빈 입력은 PROCEED 가 아니다 — 호출부가 UNRUN 으로 다룬다
    rows = [(a["action"],) + decide_one(mode, a["action"],
                                        bool(a.get("in_scope", False)),
                                        bool(a.get("reversible", False)))
            for a in actions]
    worst = min((r[1] for r in rows), key=lambda v: PRECEDENCE[v])
    return worst, rows


def main() -> int:
    ap = argparse.ArgumentParser(description="자율 모드 행동 판정")
    ap.add_argument("--action", action="append", default=[],
                    help="행동 이름. 여러 번 주면 복합 작업 (가장 보수적 판정이 이긴다)")
    ap.add_argument("--mode", help=f"모드 (기본: ${MODE_ENV} 또는 {DEFAULT_MODE})")
    ap.add_argument("--in-scope", action="store_true", help="원래 요청 범위 안인가")
    ap.add_argument("--reversible", action="store_true", help="되돌릴 수 있는가")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.action:
        print("UNRUN: --action 이 없다 — 판정할 대상이 없으면 통과가 아니다", file=sys.stderr)
        return UNRUN

    mode = normalize_mode(args.mode if args.mode is not None else os.environ.get(MODE_ENV))
    acts = [{"action": a, "in_scope": args.in_scope, "reversible": args.reversible}
            for a in args.action]
    verdict, rows = decide(mode, acts)
    print(f"mode={mode} · 행동 {len(rows)}건")
    for name, v, why in rows:
        print(f"  {v:<8} {name} — {why}")
    print(f"{verdict}")
    return EXIT[verdict]


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    passed, fails = 0, []

    def case(name, mode, acts, want):
        nonlocal passed
        try:
            got, _ = decide(mode, acts)
        except Exception as e:      # noqa: BLE001 — 크래시를 FAIL 로 (요약 줄 보존)
            fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
            return
        if got == want:
            passed += 1
        else:
            fails.append(f"{name}: {got} (기대 {want})")

    A = lambda a, s=True, r=True: {"action": a, "in_scope": s, "reversible": r}  # noqa: E731

    # ① 자율 = 진행 (범위 안 + 가역)
    case("autonomous-proceeds", AUTONOMOUS, [A("edit_file")], PROCEED)
    # ② 대화형 = 질문
    case("interactive-asks", INTERACTIVE, [A("edit_file")], ASK)
    # ③ ⛔ 금지 행동은 **자율에서도** 차단
    case("forbidden-blocked-in-autonomous", AUTONOMOUS, [A("commit")], BLOCK)
    case("forbidden-blocked-push", AUTONOMOUS, [A("push")], BLOCK)
    case("forbidden-blocked-delete", AUTONOMOUS, [A("delete")], BLOCK)
    case("forbidden-blocked-external", AUTONOMOUS, [A("external_send")], BLOCK)
    # ④ ⛔ 미지 모드 = 질문 (fail-closed). 오타 하나가 승인을 없애지 않는다
    case("unknown-mode-asks", "auto", [A("edit_file")], ASK)
    case("empty-mode-defaults-interactive", normalize_mode(""), [A("edit_file")], ASK)
    case("unset-mode-defaults-interactive", normalize_mode(None), [A("edit_file")], ASK)
    # ⑤ ⛔ 범위 밖·비가역은 자율에서도 질문
    case("out-of-scope-asks", AUTONOMOUS, [A("edit_file", s=False)], ASK)
    case("irreversible-asks", AUTONOMOUS, [A("edit_file", r=False)], ASK)
    # ⑥ ⛔ 복합 작업 — 가장 보수적인 판정이 이긴다 (다수결이 아니다)
    case("compound-worst-wins-block", AUTONOMOUS,
         [A("edit_file"), A("edit_file"), A("commit")], BLOCK)
    case("compound-worst-wins-ask", AUTONOMOUS,
         [A("edit_file"), A("edit_file"), A("edit_file", s=False)], ASK)
    case("compound-all-clear", AUTONOMOUS, [A("edit_file"), A("read_file")], PROCEED)
    # ⑦ ⛔ 빈 입력은 PROCEED 가 아니다
    case("empty-is-not-proceed", AUTONOMOUS, [], None)

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
