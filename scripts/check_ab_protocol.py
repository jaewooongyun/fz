#!/usr/bin/env python3
# lint:no-root-anchor — 검사 대상 파일 경로를 인자로 받는다. self-test 는 임시 문서만 쓴다.
"""experiment-log 의 'A/B 원장 프로토콜' 절 필수 항목 검사 (S05).

⛔ 왜: A/B 판정은 절차가 한 줄만 빠져도 조용히 틀린다 — 600s 천장을 끄지 않으면 잘린 run 이 오류 없이 빠른
   wall 을 내고(F-203), 가린 검증자 없이 채점하면 arm 을 아는 채점자가 판정한다. 절차 문서가 이 항목을
   **그 절 안에** 담고 있는지 본다(다른 절에 흩어진 문구로는 통과하지 않는다).

usage: check_ab_protocol.py EXPERIMENT_LOG | --self-test
exit: 0=충족 · 1=누락 · 2=파일을 읽지 못함(⛔ 통과 아님)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_section  # noqa: E402 — 형제 모듈(절 추출 공용 · F-335 ⑰)

HEADING = re.compile(r"^##\s+.*A/B 원장 프로토콜.*$", re.M)
NEXT_H2 = re.compile(r"^##\s", re.M)   # 이 절은 `##` 단위다 — `###` 소제목은 절 안에 둔다
# (id, 뜻, 모두 있어야 하는 정규식들)
REQUIRED = (
    ("arms", "B·C worktree 와 --plugin-dir", (r"FZ_BASE_TREE", r"FZ_TREE", r"--plugin-dir")),
    ("model", "모델·effort 고정과 transcript 판정", (r"claude-opus-5-5", r"--effort xhigh", r"AC-1")),
    ("autonomy", "FZ_AUTONOMY 의 실제 배선(세 스킬 미배선)", (r"FZ_AUTONOMY", r"\*\*읽지 않는다\*\*")),
    ("plugin-copy", "run 별 플러그인 사본 + --add-dir + run 전 신원 + 원본 대조 + 코드 해시", (r"플러그인 사본", r"--add-dir",
                                                                             r"--plugin-root", r"--plugin-source", r"코드 해시")),
    ("stop-hook", "검사 대상 밖 Stop hook 차단", (r"FZ_GATES_OFF=1",)),
    ("headless", "사람 대기 회피 — 티켓 브랜치·--tier 3·Build 절·표준 승인 턴",
     (r"hotfix/ABT-", r"--tier 3", r"## Build", r"표준 승인 턴")),
    ("bg-ceiling", "백그라운드 대기 600s 천장 해제", (r"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0", r"600s")),
    ("isolation", "arm×run 메모리 격리 + 시작 상태 스냅샷 + 필수 감시 3종", (r"agent-memory", r"snapshot", r"pristine", r"AC-7",
                                                                     r"user_sessions", r"정본", r"SESSION-\*_issues\.json")),
    ("input", "입력 해시", (r"입력 해시", r"input\.json")),
    ("crossover", "교차 순서", (r"B1 → C1 → B2 → C2", r"crossover-order")),
    ("wall", "wall 자 — Lead 첫 발화 → 최종 산출물, mtime 자 금지",
     (r"wall_total", r"첫 사람 발화", r"최종 산출물", r"mtime 자로 wall 을 재지 않는다")),
    ("wall-xcheck", "wall_workflow 두 자 교차 5%", (r"wall_workflow", r"5%")),
    ("oracle", "fz_wf_metrics --expect-agents 완주 오라클", (r"--expect-agents", r"미완주 run 은 \*\*0건이 아니라 무효\*\*")),
    ("blind", "가린 검증자 절차", (r"가린 검증자", r"어느 arm 의 산출물인지 알 수 없어야", r"blind-pack", r"blind-unpack",
                                     r"key\.json", r"코드로 확인한", r"JSON boolean", r"산출물 해시")),
    ("stages", "실행 모드별 필수 stage + stagesCompleted 기대", (r"stagesCompleted", r"Tier 3")),
    ("gpt-link", "GPT 배너 1:1 연결 + 실패 호출 무효", (r"1:1", r"실패한 호출")),
    ("exact-runs", "비교 run 정확히 2개", (r"\*\*정확히 2개\*\*",)),
    ("followup", "peer-review B arm 의 표준 후속 필터 턴", (r"표준 후속 필터 턴", r"고정 문구", r"followup_prompts")),
    ("instrument", "계측기 SHA 와 recollect", (r"instrument_sha", r"recollect")),
    ("sources", "원천 재대조", (r"--verify-sources",)),
    ("evidence-required", "증거 부재 = 위반(필수 증거 인자)", (r"\*\*증거 부재 = 위반\*\*", r"--state-end", r"--input-json")),
    ("fail-closed", "미구현 기준은 exit 2", (r"exit 2",)),
)


def section(text):
    return md_section.section(text, HEADING, NEXT_H2, keep_heading=True)


def check(text):
    sec = section(text)
    if sec is None:
        return ["절 없음 — '## … A/B 원장 프로토콜' 제목이 없다"]
    return [f"{rid} ({desc}) — 절 안에 없음: {[p for p in pats if not re.search(p, sec)]}"
            for rid, desc, pats in REQUIRED if not all(re.search(p, sec) for p in pats)]


def self_test():
    # 한 줄에 이어 붙인다 — '## Build' 같은 패턴이 줄 머리에 오면 새 절 제목이 되어 뒤 문구가 절 밖으로 밀린다
    full = "- " + " · ".join(p.replace("\\*", "*").replace("\\.", ".").replace("\\", "") for _, _, pats in REQUIRED for p in pats)
    doc = f"# log\n\n## §5.10 A/B 원장 프로토콜\n\n{full}\n\n## 다음 절\n"
    cases = [
        ("완비", doc, 0),
        ("항목 누락(FZ_AUTONOMY 미배선 사실)", doc.replace("**읽지 않는다**", ""), 1),
        ("절 없음", doc.replace("A/B 원장 프로토콜", "다른 제목"), 1),
        ("절 밖 문구", f"# log\n\n## §5.10 A/B 원장 프로토콜\n\n(비어 있음)\n\n## 다음 절\n{full}\n", 1),
    ]
    passed = 0
    for name, text, want in cases:
        got = 1 if check(text) else 0
        if got == want:
            passed += 1
        else:
            print(f"  FAIL {name}: {check(text)[:2]}")
    print(f"self-test {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


def main():
    if len(sys.argv) != 2:
        print(__doc__.split("\n\n")[-2])
        return 2
    if sys.argv[1] == "--self-test":
        return self_test()
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"UNRUN: {sys.argv[1]} 을 읽지 못했다 — {e}")
        return 2
    miss = check(text)
    for m in miss:
        print(f"  MISSING {m}")
    print(f"ab-protocol: 필수 {len(REQUIRED)}항목 · 누락 {len(miss)}")
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
