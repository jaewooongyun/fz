#!/usr/bin/env python3
# lint:no-root-anchor — 보고서 파일을 인자로 받는 검사기라 플러그인 루트를 해석하지 않는다
"""보고 수치의 재생성 명령 검사 (F-493).

보고서의 수치를 원천에서 다시 내지 않고 손으로 옮기면, 부분합이 보존되는 분류 오류는 "합 = 전체" 검산을
통과한다(F-493: 5건이 틀렸는데 검산은 통과). 그래서 수치 표는 행마다 **원천에서 그 값을 다시 내는 명령**을
같이 적는다 — 읽는 사람이 돌려 보면 같은 값이 나와야 한다.

규칙
  · 머리줄에 `수치` · `값` · `건수` · `count` 칸이 있는 표 = 수치 표
  · 수치 표에는 `재생성` (또는 `regen`) 칸이 있어야 한다
  · 그 칸은 행마다 백틱으로 감싼 명령을 담는다 — 빈 칸 · `-` · 산문만은 위반

usage: check_report_regen.py REPORT.md [REPORT2.md …]  ·  --self-test
exit: 0 위반 0 · 1 위반 있음 · 2 입력 오류(파일 없음 · 수치 표 0개도 판정 불가로 보고만 한다)
"""
from __future__ import annotations

import os
import re
import sys
import tempfile

NUMERIC_HEAD = re.compile(r"^(수치|값|건수|count)$", re.I)
REGEN_HEAD = re.compile(r"^(재생성|regen)$", re.I)
SEP = re.compile(r"^\|?[\s:|-]+\|?$")
CMD = re.compile(r"`[^`]+`")
CELL_SPLIT = re.compile(r"(?<!\\)\|")   # `\|` inside a cell (e.g. a piped command) is not a column break


def cells_of(line):
    return [c.strip() for c in CELL_SPLIT.split(line.strip().strip("|"))]


def tables(text):
    """-> [(start line, header cells, [(line no, cells)])] — GFM 표만."""
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and SEP.match(lines[i + 1].strip()):
            head = cells_of(lines[i])
            rows, j = [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, cells_of(lines[j])))
                j += 1
            out.append((i + 1, head, rows))
            i = j
        else:
            i += 1
    return out


def check(text, name="report"):
    """-> (violations, numeric tables seen)."""
    v, seen = [], 0
    for start, head, rows in tables(text):
        if not any(NUMERIC_HEAD.match(h) for h in head):
            continue
        seen += 1
        rc = next((k for k, h in enumerate(head) if REGEN_HEAD.match(h)), None)
        if rc is None:
            v.append(f"{name}:{start}: 수치 표에 재생성 칸이 없다 — 행마다 원천에서 다시 내는 명령을 적는다")
            continue
        for ln, cells in rows:
            cell = cells[rc] if rc < len(cells) else ""
            if not CMD.search(cell):
                v.append(f"{name}:{ln}: 재생성 칸에 명령(백틱)이 없다 — {cell[:40] or '(빈 칸)'}")
    return v, seen


def self_test():
    cases = [
        ("ok", "| 항목 | 수치 | 재생성 |\n|---|---|---|\n| 파일 | 12 | `git ls-files \\| wc -l` |\n", 0, 1),
        ("no-regen-column", "| 항목 | 수치 |\n|---|---|\n| 파일 | 12 |\n", 1, 1),
        ("empty-regen-cell", "| 항목 | 건수 | 재생성 |\n|---|---|---|\n| a | 3 | - |\n| b | 4 | `grep -c x f` |\n", 1, 1),
        ("prose-only-cell", "| 항목 | count | regen |\n|---|---|---|\n| a | 3 | 손으로 셌다 |\n", 1, 1),
        ("non-numeric-table-ignored", "| 이름 | 설명 |\n|---|---|\n| a | b |\n", 0, 0),
    ]
    fails = []
    for name, text, want_v, want_seen in cases:
        v, seen = check(text, name)
        if len(v) != want_v or seen != want_seen:
            fails.append(f"{name}: violations {len(v)} (want {want_v}) · numeric tables {seen} (want {want_seen})")
    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {len(cases) - len(fails)}/{len(cases)} passed")
    return 0 if not fails else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    if not argv:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    total_v, total_seen = [], 0
    for path in argv:
        if not os.path.isfile(path):
            print(f"report-regen: 파일 없음 — {path}", file=sys.stderr)
            return 2
        v, seen = check(open(path, encoding="utf-8", errors="replace").read(), os.path.basename(path))
        total_v += v
        total_seen += seen
    for x in total_v:
        print(x)
    if total_seen == 0:
        print("report-regen: 수치 표 0개 — 판정 불가(⛔ 통과 아님)")
        return 2
    print(f"report-regen: {'OK' if not total_v else 'FAIL'} (numeric tables={total_seen} violations={len(total_v)})")
    return 0 if not total_v else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
