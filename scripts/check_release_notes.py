#!/usr/bin/env python3
"""check_release_notes.py — CHANGELOG 최상단 버전 절의 finding 표가 **요구한 ID 마다**(--ids) 또는 **표에 있는 행마다**
(--table-complete) 판정·근거·검증 절차를 적었는가.
⛔ --table-complete 는 표 밖 ID(릴리즈 노트 `Closes:` 의 F-ID 등)를 요구하지 않는다 — 닫은 finding 전부를 강제하려면
   --ids 로 넘긴다(릴리즈 게이트 CHECK 가 그렇게 부른다). 릴리즈 동기 검사는 빈 칸·형식 오류만 막는다.

왜: 릴리즈가 finding 을 닫았다고 적어도 "무엇으로 판정했고 어떻게 다시 확인하는가" 가 빠지면
다음 사람이 그 판정을 검증할 수 없다. 버전 동기(check_release_sync)는 문서가 서로를 가리키는지만 본다.

형식(⛔ 이 형식만 읽는다): 최상단 `### v{버전}` 절 안의 마크다운 표 하나 —
    | ID | 판정 | 근거 | 검증 절차 |
    |---|---|---|---|
    | A1-04 | … | … | … |
머리행에 요구 열이 있어야 하고, 요구한 ID 마다 행이 있고 요구 칸이 비어 있지 않아야 한다(`-`·`TBD` 는 빈 칸).
--require 키 ↔ 열 이름: verdict=판정 · evidence=근거 · procedure=검증 절차

usage: check_release_notes.py --ids A1-04,A2-02 [--require verdict,evidence,procedure] [--changelog F] [--version X.Y.Z]
       check_release_notes.py --table-complete [--changelog F] [--version X.Y.Z]   # 표가 있으면 모든 행의 요구 칸이 차 있어야 한다
       check_release_notes.py --self-test
exit: 0=충족(--table-complete 는 finding 표가 없는 절도 0) · 1=누락 · 2=판정 불가(파일·버전 절 부재 · --ids 모드의 표 부재 ·
      ID 머리행의 요구 열 누락)

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile

OK, MISSING, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COLUMN = {"verdict": "판정", "evidence": "근거", "procedure": "검증 절차"}
EMPTY = {"", "-", "—", "tbd", "todo"}


def section(text, version):
    m = re.search(rf"^### v{re.escape(version)}\b.*$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^### v\d", text[m.end():], re.M)
    return text[m.end(): m.end() + nxt.start()] if nxt else text[m.end():]


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def check(changelog, version, ids, require, table_complete=False):
    try:
        text = open(changelog, encoding="utf-8").read()
    except OSError as e:
        print(f"UNRUN: CHANGELOG 를 읽지 못했다 — {changelog} ({e.__class__.__name__})")
        return UNRUN
    sec = section(text, version)
    if sec is None:
        print(f"UNRUN: CHANGELOG 에 `### v{version}` 절이 없다")
        return UNRUN
    want = [COLUMN[k] for k in require]
    lines = sec.split("\n")
    head = next((i for i, l in enumerate(lines) if l.lstrip().startswith("|") and all(w in cells(l) for w in want) and "ID" in cells(l)), None)
    if head is None:
        # ⛔ `| ID |` 로 시작하는 머리행이 있는데 요구 열이 빠졌으면 '표 없음' 이 아니라 형식 오류다 — 통과시키면
        #    열 이름 오타 하나로 표 검사 전체가 조용히 빠진다(v4.40.0 GPT 리뷰)
        idh = next((l for l in lines if l.lstrip().startswith("|") and cells(l)[:1] == ["ID"]), None)
        if table_complete and idh is None:
            print(f"release-notes: v{version} 절에 finding 표 없음 — 이 릴리즈는 finding 판정을 적지 않았다(통과)")
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
          ("ID 머리행에 요구 열 누락 → 2", full.replace("검증 절차", "절차"), UNRUN)]
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
    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{len(cases) + len(tc)} passed")
    return OK if not fails else MISSING


def main():
    ap = argparse.ArgumentParser(description="릴리즈 노트 finding 판정 기록 검사")
    ap.add_argument("--ids")
    ap.add_argument("--require", default="verdict,evidence,procedure")
    ap.add_argument("--changelog", default=os.path.join(os.path.dirname(SCRIPT_DIR), "CHANGELOG.md"))
    ap.add_argument("--version")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--table-complete", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
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
    return check(a.changelog, ver, [x for x in (a.ids or "").split(",") if x], req, table_complete=a.table_complete)


if __name__ == "__main__":
    sys.exit(main())
