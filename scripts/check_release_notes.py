#!/usr/bin/env python3
"""check_release_notes.py — CHANGELOG 최상단 버전 절의 finding 표가 **요구한 ID 마다**(--ids) 또는 **표에 있는 행마다**
(--table-complete) 판정·근거·검증 절차를 적었는가.
⛔ --table-complete 는 표 밖 ID(릴리즈 노트 `Closes:` 의 F-ID 등)를 요구하지 않는다 — 닫은 finding 전부를 강제하려면
   --ids 로 넘긴다. ⛔ 지금 트리에는 --ids 로 부르는 곳이 없다 — 릴리즈 동기 검사(check_release_sync.sh)는 --table-complete 로만
   부르므로(출하 모드는 --require-table 을 더한다) 빈 칸 · 형식 오류 · 표 부재만 막는다. 노트가 `Closes:` 로 닫은 finding 이 표의 행으로
   있는지는 기계가 대조하지 않는다(표지 한 줄이 표를 대신해도 통과한다) — 릴리스 절차에서 사람이 확인한다.

왜: 릴리즈가 finding 을 닫았다고 적어도 "무엇으로 판정했고 어떻게 다시 확인하는가" 가 빠지면
다음 사람이 그 판정을 검증할 수 없다. 버전 동기(check_release_sync)는 문서가 서로를 가리키는지만 본다.

형식(⛔ 이 형식만 읽는다): 최상단 `### v{버전}` 절 안의 마크다운 표 하나 —
    | ID | 판정 | 근거 | 검증 절차 |
    |---|---|---|---|
    | A1-04 | … | … | … |
머리행에 요구 열이 있어야 하고, 요구한 ID 마다 행이 있고 요구 칸이 비어 있지 않아야 한다(`-`·`TBD` 는 빈 칸).
⛔ --table-complete 는 절에 내부 추적 번호(`F-` + 세 자리 · 코드 블록 안 포함)가 있으면 exit 1 이다 — 공개 CHANGELOG 규약(v0.57.0 · F-759).
   그래서 표의 ID 열에 finding 번호를 쓸 수 없다 — 닫은 finding 은 '닫은 finding 없음.' 표지와 관리자 메모(check_release_closes.py --note)로 넘긴다.
--require 키 ↔ 열 이름: verdict=판정 · evidence=근거 · procedure=검증 절차

usage: check_release_notes.py --ids A1-04,A2-02 [--require verdict,evidence,procedure] [--changelog F] [--version X.Y.Z]
       check_release_notes.py --table-complete [--changelog F] [--version X.Y.Z]   # 표가 있으면 모든 행의 요구 칸이 차 있어야 한다
       check_release_notes.py --table-complete --require-table [...]               # 표 필수 — 표도 '닫은 finding 없음' 표지도 없으면 1
       check_release_notes.py --judge-summary JUDGE_OUT --notes docs/releases/vX.Y.Z.md   # A/B 조건부 arm 생략 N/M 대조(F-506)
       check_release_notes.py --findings-decl NOTE   # 릴리즈 노트가 닫은 finding 을 밝혔는가(출하 게이트 ⑥ 이 부른다)
       check_release_notes.py --self-test
--judge-summary: ab_ledger.py judge 출력의 조건부 arm 줄(`처치 발동 <라벨>: 조건부 생략 N/M` · `UNRUN <라벨>: 처치 미발동 — 판정 불가
  (조건부 생략 0/M)`)마다 노트가 그 라벨과 같은 `생략 N/M` 을 한 줄에 적었는가 · 0/M arm 을 언급한 줄은 모두 `판정 불가` 로 적었는가.
  (F-506: 생략 0회였던 arm 을 노트가 '360s 느림' 으로만 적어 '교차를 건너뛰니 느렸다' 로 읽혔다) 조건부 arm 줄이 없으면 2.
--require-table: --table-complete 와 함께만 쓴다. 최상단 절에 finding 표가 없으면 1 이다 — 표를 통째로 지운 절이 통과하지 않는다. 머리행만 남긴 빈 표도 1 이다.
  닫은 finding 이 없는 릴리즈는 절에 표지 줄을 두면 표 없이 통과한다. 표지 = 줄 머리(들여쓰기 3칸까지 · 목록 기호 하나까지)에서 완결된 표지 문구로
  시작하는 줄이다 — '닫은 finding 없음' · '닫은 finding 이 없어 …'(없음 · 없다 · 없어 · 없습니다 뒤가 공백 · 줄 끝 · `. , ; : · — ( )` 가운데 하나 —
  느낌표 · 물음표 뒤는 표지가 아니다). 문장 중간의 언급 · 인용 · 코드 블록 안(울타리 · 4칸 들여쓰기) · 표지를 설명하는 문장('닫은 finding 없는 판은 …')은 표지가 아니다. 출하 진입점(check_release_sync.sh
  --release)만 이 모드로 부른다 — 기본 모드의 동작은 그대로다.
--findings-decl: 노트의 코드 블록 밖에 `Closes:` 줄(finding id 토큰 — `F-` + 숫자 3자리 · 소문자 접미와 slug 는 선택 — 이 하나 이상)이나 위 표지 줄이 있는가. 끝 줄 `FINDINGS_DECL closes|marker|none` ·
  exit 0=밝혔다 · 1=밝히지 않았다 · 2=노트를 읽지 못했다. 표지의 정의는 여기 한 벌이다 — 출하 게이트 ⑥ 은 사본 없이 이 모드를 부른다.
exit: 0=충족(--table-complete 는 finding 표가 없는 절도 0 — --require-table 이면 표지가 있을 때만) · 1=누락 ·
      2=판정 불가(파일·버전 절 부재 · --ids 모드의 표 부재 · ID 머리행의 요구 열 누락 · --require-table 을 --table-complete 없이 줌)

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
import tempfile

OK, MISSING, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import md_section  # noqa: E402 — 형제 모듈(절 추출 공용 · F-335 ⑰)

NEXT_VERSION = re.compile(r"^### v\d", re.M)
COLUMN = {"verdict": "판정", "evidence": "근거", "procedure": "검증 절차"}
EMPTY = {"", "-", "—", "tbd", "todo"}
# 닫은 finding 이 없다는 표지 — 줄 머리 고정 꼴이다: 들여쓰기(3칸까지 — 4칸부터는 마크다운의 들여쓴 코드 블록이다) · 목록 기호 하나 뒤에
#   바로 완결된 표지 문구가 온다(없음 · 없다 · 없어 · 없습니다 뒤가 공백 · 줄 끝 · `. , ; : · — ( )` 가운데 하나 — 물음표 뒤는 선언이
#   아니라 물음이라 넣지 않았다). 문장 중간의 언급 · 인용 · 표지를 '설명하는'
#   문장('닫은 finding 없는 판은 …' — 문구의 앞머리만 같다)은 선언이 아니다. 출하 게이트 ⑥(check_release_sync.sh findings_axis)도 이 정의를
#   쓴다 — 사본을 두지 않고 --findings-decl 로 이 파일을 부른다
NO_FINDING = re.compile(r"^ {0,3}(?:[-*+][ \t]+)?닫은 finding (?:이 )?없(?:음|다|어|습니다)(?=[\s.,;:·—()]|$)", re.M)
# `Closes:` 선언 — 값에 finding id 토큰이 하나는 있어야 선언이다: `F-` + 숫자 3자리 + 소문자 접미(선택) + slug(선택) — eject_findings 가
#   받는 꼴이다. 토큰은 쉼표 · 공백으로 갈린다 — 네 자리 번호 · 대문자 접미처럼 그 꼴이 아닌 값뿐이면 선언이 아니다. 빈 줄 · 자리표시 값
#   (`TBD` · `-` · '없음')도 아니다 — 닫은 것이 없으면 표지 줄로 밝힌다. ⛔ 구분 글자에 개행을 넣지 않는다 — 넣으면 빈 `Closes:` 줄의 다음
#   줄 머리가 값으로 읽힌다
# F-759 — 공개 노트 · CHANGELOG 에는 내부 추적 번호를 적지 않는다(v0.57.0 규약). Closes 와 근거는 관리자 메모(공개 저장소 밖 · `--note`)로 간다
INTERNAL_ID = re.compile(r"(?<![\w-])F-\d{3}(?!\d)")
CLOSES_DECL = re.compile(r"^Closes:(?:[^\n]*[, \t])?F-\d{3}[a-z]?(?:-[a-z0-9-]+)?(?=[, \t\r]|$)", re.M)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def outside_fences(text: str) -> str:
    """코드 울타리(``` · ~~~) 밖의 줄만 남긴다 — 울타리 안의 예시 표 · 예시 표지는 선언이 아니다. 줄 수는 그대로 둔다(빈 줄로 바꾼다).
    닫는 줄은 여는 줄과 같은 글자 · 그 이상 길이 · 뒤에 다른 글자가 없는 줄뿐이다 — 네 개 백틱 블록 안의 세 개 백틱이나 백틱 블록
    안의 물결표 줄은 블록을 닫지 않는다(닫힌 것으로 읽으면 블록 안의 예시가 선언으로 샌다). 닫히지 않은 블록은 끝까지 안이다."""
    out, fence = [], None   # fence = (여는 글자, 길이)
    for ln in text.split("\n"):
        m = FENCE.match(ln)
        if fence is not None:
            run = m.group(1) if m else ""
            if run and run[0] == fence[0] and len(run) >= fence[1] and not ln.strip()[len(run):].strip():
                fence = None
            out.append("")
        elif m:
            fence = (m.group(1)[0], len(m.group(1)))
            out.append("")
        else:
            out.append(ln)
    return "\n".join(out)


def section(text, version):
    return md_section.section(text, re.compile(rf"^### v{re.escape(version)}\b.*$", re.M), NEXT_VERSION)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


JUDGE_ARM = re.compile(r"^(?:UNRUN (?P<a>.+?): 처치 미발동 — 판정 불가 \(조건부 생략 0/(?P<m0>\d+)\)"
                       r"|\s*처치 발동 (?P<b>.+?): 조건부 생략 (?P<n>\d+)/(?P<m>\d+))", re.M)


def judge_arms(summary):
    """판정기 출력 → {arm 라벨: (생략한 run 수, 조건부 run 수)}."""
    return {m.group("a") or m.group("b"): (0, int(m.group("m0"))) if m.group("a") else (int(m.group("n")), int(m.group("m")))
            for m in JUDGE_ARM.finditer(summary)}


def skip_mismatches(notes, arms):
    bad = []
    for arm, (n, m) in arms.items():
        lines = [l for l in notes.split("\n") if arm in l]
        if not any(re.search(rf"생략 {n}/{m}(?!\d)", l) for l in lines):     # 수 쌍 전체 — `3/6` 이 `3/60` 의 앞머리로 통과하지 않는다
            got = sorted(set(re.findall(r"생략 \d+/\d+", " ".join(lines))))
            bad.append(f"{arm}: 판정기와 같은 '생략 {n}/{m}' 을 라벨과 한 줄에 적지 않았다" + (f" — 노트는 {got}" if got else ""))
        if n == 0:
            loose = [l.strip()[:80] for l in lines if "판정 불가" not in l]
            if loose:
                bad.append(f"{arm}: 처치가 한 번도 발동하지 않았는데(생략 0/{m}) '판정 불가' 없이 적은 줄 — {loose[0]}")
    return bad


def check_skips(summary_path, notes_path):
    try:
        arms = judge_arms(open(summary_path, encoding="utf-8").read())
        notes = open(notes_path, encoding="utf-8").read()
    except OSError as e:
        print(f"UNRUN: 판정기 출력 · 노트를 읽지 못했다 — {e.__class__.__name__}: {e}")
        return UNRUN
    if not arms:
        print(f"UNRUN: {summary_path} 에 조건부 arm 줄(`조건부 생략 N/M`)이 없다 — 대조할 것이 없다(⛔ 통과 아님)")
        return UNRUN
    bad = skip_mismatches(notes, arms)
    for b in bad:
        print(f"  MISSING {b}")
    print(f"release-notes: 조건부 arm {len(arms)} · 생략 표기 불일치 {len(bad)}")
    return MISSING if bad else OK


def absence_warn(text: str) -> None:
    """F-741 — 공개 노트의 대조값 없는 부재 주장('0건 · 없다 · 미발견')을 경고한다 · 종료 코드는 바꾸지 않는다(판정 한 곳: plan_integrity_check)."""
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("fz_plan_integrity", os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan_integrity_check.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        hits = mod.absence_without_control(text)
    except Exception as e:  # noqa: BLE001 — 경고 판정기의 적재 실패는 선언 판정을 바꾸지 않는다 · 판정하지 못했음을 알린다
        print(f"  NOTE 부재 주장 경고를 판정하지 못했다({type(e).__name__})")
        return
    for n, ln in hits[:3]:
        print(f"  WARN {n}행 대조값 없는 부재 주장 — `{ln[:80]}` · 같은 줄에 [대조: 양성 대조 · 저장소 전체 수](F-741)")


def findings_decl(note):
    """릴리즈 노트가 닫은 finding 을 밝혔는가 — 코드 블록 밖의 `Closes:` 줄(finding id 토큰이 하나 이상) 또는 표지 줄. 끝 줄 `FINDINGS_DECL closes|marker|none`.
    exit: 0=밝혔다 · 1=밝히지 않았다 · 2=노트를 읽지 못했다. 출하 게이트 ⑥ 이 종료 코드와 끝 줄을 함께 본다."""
    try:
        text = open(note, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"UNRUN: 노트를 읽지 못했다 — {note} ({e.__class__.__name__})")
        return UNRUN
    ids = [l.strip() for l in text.split("\n") if INTERNAL_ID.search(l)]
    if ids:
        # 코드 블록 안도 센다 — 공개 노트에 번호를 적지 않는다는 규약은 위치를 가리지 않는다
        for l in ids[:3]:
            print(f"  INTERNAL-ID {l[:120]}")
        what = "`Closes:` 줄과 근거는" if CLOSES_DECL.search(outside_fences(text)) else "번호가 필요한 설명은"
        print(f"  공개 노트에 내부 추적 번호(F- + 세 자리) {len(ids)}줄 — {what} 관리자 메모로 옮기고"
              " `check_release_closes.py --note <관리자 메모>` 로 넘긴다 · 노트에는 '닫은 finding 없음.' 표지(v0.57.0 · F-759)")
        print("FINDINGS_DECL internal-id")
        return MISSING
    kind = "marker" if NO_FINDING.search(outside_fences(text)) else "none"
    absence_warn(text)
    print(f"FINDINGS_DECL {kind}")
    return MISSING if kind == "none" else OK


def check(changelog, version, ids, require, table_complete=False, require_table=False):
    try:
        text = open(changelog, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:   # UTF-8 이 아닌 바이트도 읽기 실패다 — 예외로 죽으면 exit 1 이라 '표가 없다' 로 읽힌다
        print(f"UNRUN: CHANGELOG 를 읽지 못했다 — {changelog} ({e.__class__.__name__})")
        return UNRUN
    sec = section(text, version)
    if sec is None:
        print(f"UNRUN: CHANGELOG 에 `### v{version}` 절이 없다")
        return UNRUN
    if table_complete:
        # 공개 CHANGELOG 도 공개 문서다 — 노트 검사(findings_decl)와 같은 정의 · 코드 블록 안도 센다(v0.57.0 규약 · F-759)
        hits = [l.strip() for l in sec.split("\n") if INTERNAL_ID.search(l)]
        if hits:
            for l in hits[:3]:
                print(f"  INTERNAL-ID {l[:120]}")
            print(f"  MISSING v{version} 절에 내부 추적 번호(F- + 세 자리) {len(hits)}줄 — 공개 CHANGELOG 에는 적지 않는다 ·"
                  " '닫은 finding 없음.' 표지를 두고 Closes 와 근거는 관리자 메모로(check_release_closes.py --note <관리자 메모>)")
            print(f"release-notes: v{version} · 내부 추적 번호 {len(hits)}줄")
            return MISSING
    sec = outside_fences(sec)
    want = [COLUMN[k] for k in require]
    lines = sec.split("\n")
    head = next((i for i, l in enumerate(lines) if l.lstrip().startswith("|") and all(w in cells(l) for w in want) and "ID" in cells(l)), None)
    if head is None:
        # ⛔ `| ID |` 로 시작하는 머리행이 있는데 요구 열이 빠졌으면 '표 없음' 이 아니라 형식 오류다 — 통과시키면
        #    열 이름 오타 하나로 표 검사 전체가 조용히 빠진다(v4.40.0 GPT 리뷰)
        idh = next((l for l in lines if l.lstrip().startswith("|") and cells(l)[:1] == ["ID"]), None)
        if table_complete and idh is None:
            if require_table and not NO_FINDING.search(sec):
                # ⛔ 표 필수 모드 — 표를 통째로 지운 절이 '적지 않은 릴리즈' 로 통과하지 않는다
                print(f"  MISSING v{version} 절에 finding 표도 '닫은 finding 없음' 표지도 없다 — 닫은 것의 판정·근거·검증 절차를 표로 적거나 없음을 밝힌다")
                print(f"release-notes: v{version} · 표 필수 · 누락 1")
                return MISSING
            why = "'닫은 finding 없음' 표지가 있다" if require_table else "이 릴리즈는 finding 판정을 적지 않았다"
            print(f"release-notes: v{version} 절에 finding 표 없음 — {why}(통과)")
            return OK
        lack = [w for w in want if w not in cells(idh)] if idh else []
        print(f"UNRUN: v{version} 절에 `| ID | {' | '.join(want)} |` 머리행 표가 없다" + (f" — ID 머리행에 {lack} 열이 없다" if lack else ""))
        return UNRUN
    cols = cells(lines[head])
    j = head + 1
    if j < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[j]):
        j += 1                                   # 구분선이 있으면 건너뛴다 — 없으면 첫 행부터 읽는다(2라운드 010)
    rows, dup = {}, []
    for l in lines[j:]:
        if not l.lstrip().startswith("|"):
            break
        c = cells(l)
        if c:
            if c[0] in rows:
                dup.append(c[0])                 # ⛔ 같은 ID 두 행 — 뒤가 앞의 빈 칸을 덮는다
            rows[c[0]] = dict(zip(cols, c))
    if table_complete and require_table and not rows and not NO_FINDING.search(sec):
        # ⛔ 표 필수 모드 — 머리행만 남긴 빈 표가 '표 있음' 으로 통과하지 않는다
        print(f"  MISSING v{version} 절의 finding 표에 행이 없다 — 닫은 것을 행으로 적거나 '닫은 finding 없음' 표지를 둔다")
        print(f"release-notes: v{version} · 표 필수 · 누락 1")
        return MISSING
    if table_complete:
        ids = list(rows)   # ⛔ 표에 있는 행 전부 — 릴리즈 동기 검사가 ID 목록 없이 부른다
    bad = []
    for i in ids:
        r = rows.get(i)
        if r is None:
            bad.append(f"{i}: 행 없음")
            continue
        empty = [w for w in want if r.get(w, "").strip().lower() in EMPTY]
        if empty:
            bad.append(f"{i}: 빈 칸 {empty}")
    bad += [f"{d_}: 같은 ID 행 중복" for d_ in dup]
    for b in bad:
        print(f"  MISSING {b}")
    print(f"release-notes: v{version} · 요구 ID {len(ids)} · 열 {want} · 누락 {len(bad)}")
    return MISSING if bad else OK


def self_test():
    head = "| ID | 판정 | 근거 | 검증 절차 |\n|---|---|---|---|\n"
    full = "# Changelog\n\n### v9.9.0 (2026-01-01) — t\n\n" + head + "| A1 | 해결 | 실측 | `bash x` |\n| A2 | 해결 | 실측 | `bash y` |\n\n### v9.8.0\n| A3 | x |\n"
    cases = [
        ("전부 있음 → 0", full, "9.9.0", ["A1", "A2"], OK),
        ("ID 행 없음 → 1", full, "9.9.0", ["A1", "A9"], MISSING),
        ("빈 칸(-) → 1", full.replace("| 실측 | `bash y` |", "| - | `bash y` |"), "9.9.0", ["A2"], MISSING),
        ("버전 절 없음 → 2", full, "1.0.0", ["A1"], UNRUN),
        ("요구 열 없는 표 → 2", full.replace("검증 절차", "절차"), "9.9.0", ["A1"], UNRUN),
        ("아래 버전 절의 행은 세지 않는다 → 1", full, "9.9.0", ["A3"], MISSING),
    ]
    tc = [("표 전 행 완전 → 0", full, OK), ("표 한 행 빈 칸 → 1", full.replace("| 실측 | `bash y` |", "| 실측 | TBD |"), MISSING),
          ("표 없는 절 → 0(적지 않은 릴리즈)", "# Changelog\n\n### v9.9.0 (2026-01-01) — t\n\n본문만\n", OK),
          ("구분선 없는 표의 빈 첫 행 → 1", "# Changelog\n\n### v9.9.0 — t\n\n| ID | 판정 | 근거 | 검증 절차 |\n| A1 | 해결 | - | x |\n", MISSING),
          ("같은 ID 빈 행 뒤 완성 행 → 1", full.replace("| A2 | 해결 | 실측 | `bash y` |", "| A2 | 해결 | - | - |\n| A2 | 해결 | 실측 | `bash y` |"), MISSING),
          ("ID 머리행에 요구 열 누락 → 2", full.replace("검증 절차", "절차"), UNRUN),
          # 공개 CHANGELOG 의 내부 추적 번호 — 칸이 다 찬 표여도 거부한다(F-759 · 노트와 같은 규약)
          ("표 ID 가 내부 추적 번호 → 1", full.replace("| A1 |", "| F-123 |"), MISSING)]
    bare = "# Changelog\n\n### v9.9.0 (2026-01-01) — t\n\n본문만\n"
    # 표 필수 모드(--require-table) — (셀 이름, CHANGELOG, 기대). 셀 이름은 FZ_SELFTEST_LIST=1 일 때 `PASS <이름>` 으로 낸다
    rt = [("require-table-absent-exit1", bare, MISSING),
          ("require-table-marker-with-internal-id-exit1", bare + "\n닫은 finding 없음.\n\n- F-123 의 꼴을 막았다\n", MISSING),
          ("require-table-marker-ok", bare + "\n닫은 finding 이 없어 표를 쓰지 않는다.\n", OK),
          ("require-table-marker-bullet-ok", bare + "\n- 닫은 finding 없음 — 문서만 고쳤다\n", OK),
          # 표지는 줄 머리 꼴이다 — 문장 중간의 언급은 선언이 아니다
          ("require-table-marker-midline-exit1", bare + "\n이 릴리즈는 " + "닫은 finding 이 없어 표를 쓰지 않는다.\n", MISSING),
          # 표지를 설명하는 문장 · 문구 뒤에 낱말이 이어지는 줄 · 4칸 들여쓴 코드 블록은 표지가 아니다. 3칸 들여쓰기까지는 표지다
          ("require-table-explaining-bullet-exit1", bare + "\n- 닫은 finding 없는 판은 표지 한 줄로 표를 대신한다\n", MISSING),
          ("require-table-marker-suffix-exit1", bare + "\n- 닫은 finding 이 없다면 표를 쓰지 않는다\n", MISSING),
          ("require-table-indented-block-exit1", bare + "\n    닫은 finding 없음\n", MISSING),
          ("require-table-marker-indent3-ok", bare + "\n   - 닫은 finding 없음\n", OK),
          ("require-table-marker-question-exit1", bare + "\n닫은 finding 이 없다?\n", MISSING),   # 물음은 선언이 아니다
          ("require-table-quoted-marker-exit1", bare + "\n- 닫은 것이 없으면 '닫은 finding 이 없어 …' 표지를 둔다\n", MISSING),
          ("require-table-backtick-marker-exit1", bare + "\n- 닫은 것이 없으면 `닫은 finding 이 없어 …` 표지를 둔다\n", MISSING),
          ("require-table-curly-marker-exit1", bare + "\n- 닫은 것이 없으면 ‘닫은 finding 이 없어 …’ 표지를 둔다\n", MISSING),
          ("require-table-fenced-example-exit1", bare + "\n```\n| ID | 판정 | 근거 | 검증 절차 |\n|---|---|---|---|\n"
           "| A1 | 해결 | 실측 | x |\n닫은 finding 이 없어 표를 쓰지 않는다.\n```\n", MISSING),
          # 안쪽의 짧은 울타리 · 다른 글자의 울타리는 블록을 닫지 않는다 — 닫힌 것으로 읽으면 예시 표지가 선언이 된다
          ("require-table-nested-fence-exit1", bare + "\n````\n```\n닫은 finding 이 없어 표를 쓰지 않는다.\n```\n````\n", MISSING),
          ("require-table-tilde-in-backtick-exit1", bare + "\n```\n~~~\n닫은 finding 이 없어 표를 쓰지 않는다.\n~~~\n```\n", MISSING),
          # 뒤에 글자가 붙은 울타리 줄(안쪽 예시의 여는 줄)은 닫는 줄이 아니다
          ("require-table-info-string-not-close-exit1", bare + "\n```\n```text\n닫은 finding 이 없어 표를 쓰지 않는다.\n```\n", MISSING),
          ("require-table-complete-ok", full, OK),
          ("require-table-blank-cell-exit1", full.replace("| 실측 | `bash y` |", "| 실측 | TBD |"), MISSING),
          ("require-table-header-only-exit1", bare + "\n" + head, MISSING)]
    # --findings-decl — (셀 이름, 노트 본문 | None = 파일 없음, 기대)
    fd = [("findings-decl-closes-internal-id-exit1", "# v9.9.9\n\nCloses: F-001\n", MISSING),
          ("findings-decl-prose-id-with-marker-exit1", "# v9.9.9\n\n닫은 finding 없음.\n\n- F-123 의 꼴을 막았다\n", MISSING),
          ("findings-decl-fenced-id-with-marker-exit1", "# v9.9.9\n\n닫은 finding 없음.\n\n```\nF-123\n```\n", MISSING),
          ("findings-decl-marker-four-digit-ok", "# v9.9.9\n\n닫은 finding 없음.\n\n- 이슈 X-1000 · F-1000 은 번호 꼴이 아니다\n", OK),
          ("findings-decl-marker-ok", "# v9.9.9\n\n- 닫은 finding 없음 — 문서만 고쳤다\n", OK),
          ("findings-decl-none-exit1", "# v9.9.9\n\n본문만 있다\n", MISSING),
          ("findings-decl-midline-marker-exit1", "# v9.9.9\n\n이 릴리즈는 " + "닫은 finding 이 없다.\n", MISSING),
          ("findings-decl-fenced-marker-exit1", "# v9.9.9\n\n```\n닫은 finding 없음\n```\n", MISSING),
          ("findings-decl-fenced-closes-exit1", "# v9.9.9\n\n```\nCloses: F-001\n```\n", MISSING),
          ("findings-decl-empty-closes-exit1", "# v9.9.9\n\nCloses:\n", MISSING),
          # 자리표시 값은 선언이 아니다 — finding 번호가 하나는 있어야 한다(slug 가 붙은 꼴 · 쉼표로 이은 꼴은 선언이다)
          ("findings-decl-closes-placeholder-exit1", "# v9.9.9\n\nCloses: TBD\n", MISSING),
          ("findings-decl-closes-dash-exit1", "# v9.9.9\n\nCloses: -\n", MISSING),
          ("findings-decl-closes-slug-internal-id-exit1", "# v9.9.9\n\nCloses: note, F-123-some-entry\n", MISSING),
          # id 토큰의 꼴 — 네 자리 번호 · 대문자 접미는 id 가 아니다. 소문자 접미는 id 다. 빈 `Closes:` 줄의 다음 줄은 값이 아니다
          ("findings-decl-closes-four-digit-exit1", "# v9.9.9\n\nCloses: F-1000\n", MISSING),
          ("findings-decl-closes-upper-suffix-exit1", "# v9.9.9\n\nCloses: F-001A\n", MISSING),
          ("findings-decl-closes-letter-suffix-internal-id-exit1", "# v9.9.9\n\nCloses: F-001a\n", MISSING),
          ("findings-decl-closes-next-line-exit1", "# v9.9.9\n\nCloses:\nF-001 은 다음 줄이다\n", MISSING),
          ("findings-decl-explaining-bullet-exit1", "# v9.9.9\n\n- 닫은 finding 없는 판은 표지 한 줄로 표를 대신한다\n", MISSING),
          ("findings-decl-indented-block-exit1", "# v9.9.9\n\n본문\n\n    닫은 finding 없음\n", MISSING),
          ("findings-decl-unreadable-exit2", None, UNRUN)]
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []
    with tempfile.TemporaryDirectory() as d:
        for name, text, ver, ids, want in cases:
            p = os.path.join(d, "CHANGELOG.md")
            open(p, "w", encoding="utf-8").write(text)
            stdout = sys.stdout
            sys.stdout = open(os.devnull, "w")
            try:
                got = check(p, ver, ids, ["verdict", "evidence", "procedure"])
            finally:
                sys.stdout.close()
                sys.stdout = stdout
            if got == want:
                passed += 1
            else:
                fails.append(f"{name}: got {got}")
        for name, text, want in tc:
            p = os.path.join(d, "CHANGELOG.md")
            open(p, "w", encoding="utf-8").write(text)
            stdout = sys.stdout
            sys.stdout = open(os.devnull, "w")
            try:
                got = check(p, "9.9.0", [], ["verdict", "evidence", "procedure"], table_complete=True)
            finally:
                sys.stdout.close()
                sys.stdout = stdout
            if got == want:
                passed += 1
            else:
                fails.append(f"{name}: got {got}")
        for name, text, want in rt:
            p = os.path.join(d, "CHANGELOG.md")
            open(p, "w", encoding="utf-8").write(text)
            stdout = sys.stdout
            sys.stdout = open(os.devnull, "w")
            try:
                got = check(p, "9.9.0", [], ["verdict", "evidence", "procedure"], table_complete=True, require_table=True)
            finally:
                sys.stdout.close()
                sys.stdout = stdout
            if got == want:
                passed += 1
                if listing:
                    print(f"PASS {name}")
            else:
                fails.append(f"{name}: got {got}")
        for name, text, want in fd:
            p = os.path.join(d, "note.md" if text is not None else "absent.md")
            if text is not None:
                open(p, "w", encoding="utf-8").write(text)
            stdout = sys.stdout
            sys.stdout = open(os.devnull, "w")
            try:
                got = findings_decl(p)
            finally:
                sys.stdout.close()
                sys.stdout = stdout
            if got == want:
                passed += 1
                if listing:
                    print(f"PASS {name}")
            else:
                fails.append(f"{name}: got {got}")
        # F-741 — 부재 주장 경고는 종료 코드를 바꾸지 않고 줄만 낸다
        for name, text, want_warn in (("findings-decl-absence-warns", "# v9.9.9\n\n닫은 finding 없음.\n\n- 남은 오탐 0건\n", True),
                                      ("findings-decl-absence-with-control-quiet",
                                       "# v9.9.9\n\n닫은 finding 없음.\n\n- 남은 오탐 0건 [대조: 같은 검사가 심은 꼴 4건]\n", False)):
            p = os.path.join(d, "note.md")
            open(p, "w", encoding="utf-8").write(text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                got = findings_decl(p)
            if got == OK and ("대조값 없는 부재 주장" in buf.getvalue()) == want_warn:
                passed += 1
                if listing:
                    print(f"PASS {name}")
            else:
                fails.append(f"{name}: got {got} warn={'대조값 없는 부재 주장' in buf.getvalue()}")
        # UTF-8 이 아닌 CHANGELOG — 판정 불가(2)다. 예외로 죽으면 exit 1 이라 게이트가 '표가 없다' 로 읽는다
        p = os.path.join(d, "CHANGELOG.md")
        with open(p, "wb") as fh:
            fh.write("# Changelog\n\n### v9.9.0 — t\n\ncaf".encode("utf-8") + b"\xe9\n")
        stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            got = check(p, "9.9.0", [], ["verdict", "evidence", "procedure"], table_complete=True)
        except UnicodeDecodeError:
            got = "UnicodeDecodeError"
        finally:
            sys.stdout.close()
            sys.stdout = stdout
        if got == UNRUN:
            passed += 1
            if listing:
                print("PASS changelog-not-utf8-exit2")
        else:
            fails.append(f"changelog-not-utf8-exit2: got {got}")
    judge = ("UNRUN fz-review[pr-a]: 처치 미발동 — 판정 불가 (조건부 생략 0/6) — 생략이 일어난 run 이 없다\n"
             "  INVALID r9 — 입력 해시 불일치\n  처치 발동 fz-plan[feature]: 조건부 생략 3/6\n")
    arms = judge_arms(judge)
    good = "- fz-review[pr-a] C′: 생략 0/6 — 처치 미발동이라 효과 판정 불가\n- fz-plan[feature]: 생략 3/6 · 품질 게이트 통과\n"
    bads = [good.replace("생략 0/6 — 처치 미발동이라 효과 판정 불가", "360s 느렸다"),                 # 생략 표기 없음
            good.replace("생략 0/6 — 처치 미발동이라 효과 판정 불가", "생략 0/6 · 360s 느렸다"),       # 0/M 을 효과로 적음
            good.replace("생략 3/6", "생략 2/6"),                                                  # 판정기와 다른 수
            good.replace("생략 3/6", "생략 3/60"),                                                 # 판정기 수가 앞머리일 뿐인 다른 수
            good + "- fz-review[pr-a] 는 271s 느렸다\n"]                                         # 0/M arm 의 다른 줄이 효과를 말함
    ok = arms == {"fz-review[pr-a]": (0, 6), "fz-plan[feature]": (3, 6)} and not skip_mismatches(good, arms) \
        and all(skip_mismatches(b, arms) for b in bads)
    print(("PASS  " if ok else "FAIL  ") + "r3-f506-notes-match-judge-summary — 노트의 '생략 N/M' 이 판정기 요약과 같고 0/M arm 은 판정 불가로만 쓴다"
          + ("" if ok else f" — arms {arms} · 통과본 {skip_mismatches(good, arms)} · 거부 {[bool(skip_mismatches(b, arms)) for b in bads]}"))
    if not ok:
        fails.append("r3-f506-notes-match-judge-summary")
    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed + ok}/{len(cases) + len(tc) + len(rt) + len(fd) + 2 + 2} passed")   # + 2 = 부재 주장 경고 셀(F-741)
    return OK if not fails else MISSING


def main():
    ap = argparse.ArgumentParser(description="릴리즈 노트 finding 판정 기록 검사")
    ap.add_argument("--ids")
    ap.add_argument("--require", default="verdict,evidence,procedure")
    ap.add_argument("--changelog", default=os.path.join(os.path.dirname(SCRIPT_DIR), "CHANGELOG.md"))
    ap.add_argument("--version")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--table-complete", action="store_true")
    ap.add_argument("--require-table", action="store_true")
    ap.add_argument("--judge-summary")
    ap.add_argument("--notes")
    ap.add_argument("--findings-decl", metavar="NOTE")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.findings_decl:
        return findings_decl(a.findings_decl)
    if a.judge_summary or a.notes:
        if not (a.judge_summary and a.notes):
            print("UNRUN: --judge-summary 와 --notes 를 함께 준다")
            return UNRUN
        return check_skips(a.judge_summary, a.notes)
    if a.require_table and not a.table_complete:
        print("UNRUN: --require-table 은 --table-complete 와 함께 준다")
        return UNRUN
    if not a.ids and not a.table_complete:
        print("UNRUN: --ids 가 필요하다")
        return UNRUN
    req = [x for x in a.require.split(",") if x]
    unknown = [x for x in req if x not in COLUMN]
    if unknown:
        print(f"UNRUN: 알 수 없는 --require 키 {unknown} — {sorted(COLUMN)}")
        return UNRUN
    ver = a.version
    if not ver:
        try:
            ver = json.load(open(os.path.join(os.path.dirname(SCRIPT_DIR), ".claude-plugin", "plugin.json"), encoding="utf-8"))["version"]
        except (OSError, ValueError, KeyError) as e:
            print(f"UNRUN: plugin.json 버전을 읽지 못했다 — {e.__class__.__name__}")
            return UNRUN
    return check(a.changelog, ver, [x for x in (a.ids or "").split(",") if x], req, table_complete=a.table_complete,
                 require_table=a.require_table)


if __name__ == "__main__":
    sys.exit(main())
