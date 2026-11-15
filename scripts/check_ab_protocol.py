#!/usr/bin/env python3
# lint:no-root-anchor — 검사 대상 파일 경로를 인자로 받는다. self-test 는 임시 문서만 쓴다.
"""experiment-log 의 'A/B 원장 프로토콜' 절 · 'GPT 다각도 원장 프로토콜' 절 필수 항목 검사 (S05 · R-G2 S9).

⛔ 왜: A/B 판정은 절차가 한 줄만 빠져도 조용히 틀린다 — 600s 천장을 끄지 않으면 잘린 run 이 오류 없이 빠른
   wall 을 내고(F-203), 가린 검증자 없이 채점하면 arm 을 아는 채점자가 판정한다. 절차 문서가 이 항목을
   **그 절 안에** 담고 있는지 본다(다른 절에 흩어진 문구로는 통과하지 않는다).

실행 행: 추적 작업 로그는 프로토콜(임계 · 스키마 · 기록 형식 · 빈 템플릿 · 절차)만 싣는다 — 측정 기록은 저장소 밖 로그
   `${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md` 의 같은 절에 쓴다. ⛔ 왜: 공개 저장소에 실행 기록이 쌓이면 작성자 환경의
   식별자(실행 ID · 경로 · 작업 이름)가 함께 나간다. 문서 전체의 코드 울타리 밖 표에서 ① 첫 칸이 숫자인 행 ② 첫 칸 전체가 굵은
   글씨인 행(임계 표 절 `Phase B 진입 조건` 만 허용 — 번호 행은 거기서도 실행 행) ③ 첫 칸이 sha256 인 행(동결 행 꼴 — 판정기
   gpt_ab_decide 가 절과 무관하게 읽는다) ④ 기록 전용 절(동결 행 · 결과 행 · 10. 기준선 이동 기록 · 판단 이력)의 데이터 행을 실행 행으로 보고
   `  RUN-ROW <파일>:<줄> — <사유>` 한 줄씩 낸다. 표 머리 · 구분 줄 · 칸이 모두 빈 템플릿 행은 허용한다.

GPT 절(GPT 다각도 측정 — plan R-G2 S9)은 사전등록 템플릿 · 근거 레코드 D1–D14 · 공식 문서 재조회 기준일 · 동결 행 · 판정 도구를
그 절 안에 담아야 한다. 빠진 항목은 `AB-PROTOCOL-MISSING: gpt.<id>` 한 줄씩 낸다(원장 게이트가 표지로 센다).

usage: check_ab_protocol.py EXPERIMENT_LOG | --self-test
exit: 0=충족 · 1=누락 또는 실행 행 · 2=파일을 읽지 못함(⛔ 통과 아님)
"""
import os
import re
import subprocess
import sys
import tempfile

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


GPT_HEADING = re.compile(r"^##\s+.*GPT 다각도 원장 프로토콜.*$", re.M)
GPT_REQUIRED = (
    ("gpt.prereg_template", "사전등록 템플릿 — 임계는 사용자 승인 전 requires_user_approval · 다중 frame 집계 규칙 칸",
     (r"requires_user_approval", r"n_min", r"n_max", r"arm_budget", r"daily_cap", r"arm_timeout", r"grader", r"frame_aggregation")),
    ("gpt.evidence_records", "근거 레코드 D1–D14", tuple(rf"\bD{i}\b" for i in range(1, 15))),
    ("gpt.recheck_date", "공식 문서(A1–A5 · B1) 재조회 기준일", (r"재조회 기준일: \d{4}-\d{2}-\d{2}",)),
    ("gpt.freeze_row", "동결 행 — prereg_sha256 · approved_by · time · instrument", (r"prereg_sha256", r"approved_by", r"instrument")),
    ("gpt.decide", "판정 · 동결 확인 도구", (r"gpt_ab_decide\.py decide", r"gpt_ab_decide\.py verify-freeze")),
)


# 실행 행 — 추적 작업 로그에는 프로토콜만 둔다(측정 기록은 저장소 밖 로그의 같은 절). 표는 코드 울타리 밖만 본다
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_LINE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
NUM_CELL = re.compile(r"^[0-9]+$")
BOLD_CELL = re.compile(r"^\*\*[^|]*\*\*$")
SHA256_CELL = re.compile(r"^[0-9a-f]{64}$")      # 동결 행 꼴 — gpt_ab_decide verify-freeze 는 절과 무관하게 이 꼴을 읽는다
SEPARATOR_CELL = re.compile(r"^:?-+:?$")
THRESHOLD_SECTIONS = ("Phase B 진입 조건",)      # 굵은 표지 행이 임계를 정하는 절 — 번호 행은 여기서도 실행 행이다
RECORD_SECTIONS = ("동결 행", "결과 행", "10. 기준선 이동 기록", "판단 이력")   # 형식만 두는 절 — 데이터 행은 모두 측정 기록이다


def table_cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def run_rows(text):
    """-> [(줄 번호, 사유)] — 코드 울타리 밖 표의 측정 기록 행. 표 머리 · 구분 줄 · 칸이 모두 빈 템플릿 행은 허용한다."""
    found, fence, title, level, index = [], None, "", 0, -1
    for n, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if fence is not None:
            run = m.group(1) if m else ""
            if run and run[0] == fence[0] and len(run) >= fence[1] and not line.strip()[len(run):].strip():
                fence = None
            continue
        if m:
            fence, index = (m.group(1)[0], len(m.group(1))), -1
            continue
        h = HEADING_LINE.match(line)
        if h:
            depth = len(line) - len(line.lstrip("#"))
            # 기록 전용 절의 소제목은 그 절 안이다 — 같은 깊이나 더 얕은 제목을 만날 때까지 절 이름을 유지한다
            if not (title.startswith(RECORD_SECTIONS) and depth > level):
                title, level = h.group(1), depth
            index = -1
            continue
        if not line.lstrip().startswith("|"):
            index = -1
            continue
        index += 1
        row = table_cells(line)
        if index >= 1 and all(SEPARATOR_CELL.match(c) for c in row):
            continue
        first = row[0]
        if NUM_CELL.match(first):
            found.append((n, "번호 행"))
        elif BOLD_CELL.match(first) and title not in THRESHOLD_SECTIONS:
            found.append((n, "굵은 표지 행"))
        elif SHA256_CELL.match(first):
            found.append((n, "동결 행 꼴(첫 칸 sha256)"))
        elif index >= 1 and title.startswith(RECORD_SECTIONS) and any(row):
            found.append((n, f"기록 전용 절 '{title}' 의 데이터 행"))
    return found


def section(text):
    return md_section.section(text, HEADING, NEXT_H2, keep_heading=True)


def check_gpt(text):
    """-> [(id, 뜻)] — GPT 절에 빠진 필수 항목. 절이 없으면 gpt.section 하나."""
    sec = md_section.section(text, GPT_HEADING, NEXT_H2, keep_heading=True)
    if sec is None:
        return [("gpt.section", "'## … GPT 다각도 원장 프로토콜' 제목이 없다")]
    return [(rid, desc) for rid, desc, pats in GPT_REQUIRED if not all(re.search(p, sec) for p in pats)]


def check(text):
    sec = section(text)
    if sec is None:
        return ["절 없음 — '## … A/B 원장 프로토콜' 제목이 없다"]
    return [f"{rid} ({desc}) — 절 안에 없음: {[p for p in pats if not re.search(p, sec)]}"
            for rid, desc, pats in REQUIRED if not all(re.search(p, sec) for p in pats)]


def judge(text):
    """-> (A/B 절 누락, GPT 절 누락, 실행 행) — main 의 종료 코드가 이 셋으로 정해진다(하나라도 있으면 1). self-test 도 이 함수로 잰다."""
    return check(text), check_gpt(text), run_rows(text)


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
    gfull = ("- requires_user_approval n_min n_max arm_budget daily_cap arm_timeout grader frame_aggregation · "
             + " · ".join(f"D{i}" for i in range(1, 15)) + " · prereg_sha256 approved_by instrument · "
             "gpt_ab_decide.py decide · gpt_ab_decide.py verify-freeze\n- 재조회 기준일: 2026-10-12\n")
    gdoc = f"# log\n\n## GPT 다각도 원장 프로토콜\n\n{gfull}\n## 다음 절\n"
    gcases = [("GPT 완비", gdoc, []), ("GPT 재조회일 누락", gdoc.replace("- 재조회 기준일: 2026-10-12\n", ""), ["gpt.recheck_date"]),
              ("GPT D7 누락", gdoc.replace(" · D7 ·", " ·"), ["gpt.evidence_records"]),
              ("GPT 절 없음", gdoc.replace("GPT 다각도 원장 프로토콜", "다른 제목"), ["gpt.section"]),
              ("GPT 절 밖 문구", f"# log\n\n## GPT 다각도 원장 프로토콜\n\n(비어 있음)\n\n## 다음 절\n{gfull}", [r[0] for r in GPT_REQUIRED])]
    for name, text, want in gcases:
        got = [rid for rid, _ in check_gpt(text)]
        if got == want:
            passed += 1
        else:
            print(f"  FAIL {name}: {got} (want {want})")
    # tracked-log-run-row — 프로토콜만 있는 본문은 0 · 실행 행 하나를 더한 본문은 1. main 과 같은 judge 로 잰다(검출 규칙이 빠지면 FAIL)
    fence = "```text\n| 1 | x |\n```\n"
    log = (f"# log\n\n## 기록 형식\n\n{fence}\n| # | date | 비고 |\n|---|---|---|\n| | | |\n\n"
           "### Phase B 진입 조건\n\n| 분류 | 기준 |\n|---|---|\n| **Load-bearing** | catch rate > 30% |\n\n"
           f"## §5.10 A/B 원장 프로토콜\n\n{full}\n\n### 10. 기준선 이동 기록\n\n| 시점 | 변경 |\n|---|---|\n\n"
           f"## GPT 다각도 원장 프로토콜\n\n{gfull}\n### 동결 행\n\n| prereg_sha256 | approved_by | time | instrument |\n"
           "|---|---|---|---|\n\n### 결과 행\n\n| 판정 | n_valid |\n|---|---|\n"
           "\n## 판단 이력\n\n| 날짜 | Step | 판단 | 근거 데이터 | 적용 여부 |\n|---|---|---|---|---|\n| | | | | |\n")
    blank, freeze, result, sha = "| | | |\n", "|---|---|---|---|\n", "| 판정 | n_valid |\n|---|---|\n", "0a" * 32
    tcases = [(log, 0),  # 울타리 안 번호 행 · 빈 템플릿 행 · 임계 표 절의 굵은 표지 행 · 머리만 있는 기록 전용 표는 허용
              (log.replace(blank, blank + "| 1 | 2026-01-01 | - |\n"), 1),  # ① 번호 행
              (log.replace(blank, blank + "| **C** | 2026-01-01 | - |\n"), 1),  # ② 굵은 표지 행
              (log.replace("| **Load-bearing** |", "| 7 | - |\n| **Load-bearing** |"), 1),  # 임계 표 절에서도 번호 행은 실행 행
              (log.replace(blank, blank + f"| {sha} | 2026-01-01 | - |\n"), 1),  # ③ 기록 전용 절 밖의 sha256 첫 칸
              (log.replace(freeze, freeze + f"| {sha} | user | 2026-01-01T00:00:00Z | 0000000 |\n"), 1),  # 동결 행
              (log.replace(result, result + "| ROLLBACK | 7 |\n"), 1),  # ④ 기록 전용 절의 판정 요약
              (log.replace(fence, fence + "\n| 1 | y |\n"), 1),  # 울타리가 닫힌 뒤의 번호 행
              (log.replace("| | | | | |\n", "| | | | | |\n| 2026-01-01 | S3 | KEEP | n=5 | 적용 |\n"), 1),  # ④ 판단 이력의 날짜 첫 칸 행
              # ④ 나머지 기록 전용 절 둘 — 번호 · 굵은 표지 · sha 가 아닌 첫 칸이라 ① ~ ③ 에 안 걸린다(절 목록에서 빠지면 통과로 샌다).
              #    머리행까지 묶어 그 절에만 넣는다(구분선만으로 바꾸면 칸 수가 더 많은 다른 표에도 들어간다)
              (log.replace("| prereg_sha256 | approved_by | time | instrument |\n|---|---|---|---|\n",
                           "| prereg_sha256 | approved_by | time | instrument |\n|---|---|---|---|\n| 메모 | user | - | - |\n"), 1),
              (log.replace("| 시점 | 변경 |\n|---|---|\n", "| 시점 | 변경 |\n|---|---|\n| 2026-11-01 | 변경 |\n"), 1),
              # 기록 전용 절의 소제목 아래 표도 그 절이다(소제목이 절 이름을 덮으면 그 아래 행이 샌다) · 다음 동급 절에서는 끝난다
              #   (끝나지 않으면 일반 절의 데이터 행까지 실행 행이 된다)
              (log.replace("### 결과 행\n\n| 판정 | n_valid |\n|---|---|\n", "### 결과 행\n\n| 판정 | n_valid |\n|---|---|\n" "\n#### 재측정\n\n| 판정 | n_valid |\n|---|---|\n| KEEP | 5 |\n"), 1),
              (log.replace("\n## 판단 이력", "\n### 메모\n\n| 항목 | 값 |\n|---|---|\n| 가 | 나 |\n\n## 판단 이력"), 0)]
    tgot = [1 if any(judge(text)) else 0 for text, _ in tcases]
    twant = [want for _, want in tcases]
    if tgot == twant:
        passed += 1
    else:
        print(f"  FAIL tracked-log-run-row: {tgot} (want {twant})")
    # UTF-8 이 아닌 기록 — 읽지 못한 것이다(UNRUN · exit 2). 디코드 오류가 예외로 새면 exit 1(누락)로 읽힌다
    with tempfile.TemporaryDirectory() as d:
        bad = os.path.join(d, "log.md")
        with open(bad, "wb") as fh:
            fh.write(b"\xff\xfe log\n")
        r = subprocess.run([sys.executable, "-B", os.path.abspath(__file__), bad], capture_output=True, text=True)
    if r.returncode == 2 and r.stdout.startswith("UNRUN:"):
        passed += 1
    else:
        print(f"  FAIL non-utf8-log-unrun: exit {r.returncode} {r.stdout[:120]!r} {r.stderr[-160:]!r}")
    total = len(cases) + len(gcases) + 2
    print(f"self-test {passed}/{total} passed")
    return 0 if passed == total else 1


def main():
    if len(sys.argv) != 2:
        print(__doc__.split("\n\n")[-2])
        return 2
    if sys.argv[1] == "--self-test":
        return self_test()
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"UNRUN: {sys.argv[1]} 을 읽지 못했다 — {e}")
        return 2
    miss, gmiss, rows = judge(text)
    for m in miss:
        print(f"  MISSING {m}")
    for rid, desc in gmiss:
        print(f"AB-PROTOCOL-MISSING: {rid} — {desc}")
    for n, why in rows:
        print(f"  RUN-ROW {sys.argv[1]}:{n} — {why}")
    print(f"ab-protocol: 필수 {len(REQUIRED)}항목 · 누락 {len(miss)} · GPT 절 필수 {len(GPT_REQUIRED)}항목 · 누락 {len(gmiss)} · 실행 행 {len(rows)}")
    return 1 if miss or gmiss or rows else 0


if __name__ == "__main__":
    sys.exit(main())
