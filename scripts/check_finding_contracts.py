#!/usr/bin/env python3
"""check_finding_contracts.py — 문서로 고친 finding 의 계약(문구 있음 · 없음 · 정확한 횟수)을 표로 대조한다.

왜: 문서 결함을 고쳐도 그 문장이 다음 편집에서 조용히 사라지거나 옛 문구가 함께 남으면 아무 검사도 말하지 않았다
(F-025 — 새 문구 존재만 재고 옛 문구 잔존을 놓쳤다). 고친 자리마다 되돌리면 실패하는 셀이 있어야 한다.

표: tests/fixtures/docs/finding-contracts.tsv — 열 `id  path  kind  text` (탭 구분 · `#` 줄은 주석)
  kind = has      — path 에 text 가 1번 이상 있다
         lacks    — path 에 text 가 없다(대체 변경의 옛 문구)
         count=N  — path 에 text 가 정확히 N번 있다(사본 수 고정)
  path 는 플러그인 루트 기준 상대 경로

사용:
  check_finding_contracts.py [--root DIR] [--table TSV] [--ids F-NNN[:k],…]
    --ids 를 주면 그 ID 들만 본다. ID 마다 행이 k 개(기본 1) 이상이고 전부 충족해야 통과다.
    --ids 가 없으면 표의 모든 행을 본다.
  check_finding_contracts.py --self-test

exit: 0 충족 · 1 위반(문구 부재 · 잔존 · 횟수 · 행 부족 · 모르는 ID) · 2 UNRUN(표 · 대상 파일 부재 · 형식 오류 — ⛔ 통과 아님)
출력: ID 마다 `ok F-NNN rows=k` 또는 `FAIL F-NNN: <사유>` · self-test 는 케이스마다 `PASS <셀>`
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

OK, VIOLATION, UNRUN = 0, 1, 2
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TABLE = "tests/fixtures/docs/finding-contracts.tsv"
ID_RE = re.compile(r"F-\d{3}[a-z]?\Z")
KIND_RE = re.compile(r"(has|lacks|count=(\d+))\Z")


class Unrun(Exception):
    pass


def load(table: Path):
    if not table.is_file():
        raise Unrun(f"표가 없다: {table}")
    rows = []
    for n, line in enumerate(table.read_text(encoding="utf-8").split("\n"), 1):
        if not line.strip() or line.startswith("#") or line.startswith("id\t"):
            continue
        cells = line.split("\t")
        if len(cells) != 4:
            raise Unrun(f"{table.name}:{n} 열이 4개가 아니다({len(cells)})")
        fid, path, kind, text = cells
        if not ID_RE.match(fid) or not KIND_RE.match(kind) or not path or not text:
            raise Unrun(f"{table.name}:{n} 형식 오류 — id={fid!r} kind={kind!r}")
        rows.append((n, fid, path, kind, text))
    return rows


def check_row(root: Path, path: str, kind: str, text: str):
    p = root / path
    if not p.is_file():
        raise Unrun(f"대상 파일이 없다: {path}")
    n = p.read_text(encoding="utf-8").count(text)
    if kind == "has":
        return None if n >= 1 else f"{path}: 문구 없음 — {text[:60]!r}"
    if kind == "lacks":
        return None if n == 0 else f"{path}: 옛 문구 {n}회 남음 — {text[:60]!r}"
    want = int(KIND_RE.match(kind).group(2))
    return None if n == want else f"{path}: {n}회(기대 {want}) — {text[:60]!r}"


def run(root: Path, table: Path, ids_spec: str | None) -> int:
    try:
        rows = load(table)
        want = {}
        if ids_spec:
            for tok in ids_spec.split(","):
                tok = tok.strip()
                if not tok:
                    continue
                fid, _, k = tok.partition(":")
                if not ID_RE.match(fid) or (k and not k.isdigit()):
                    raise Unrun(f"--ids 형식 오류: {tok!r}")
                want[fid] = int(k or 1)
        else:
            for _, fid, *_ in rows:
                want.setdefault(fid, 1)
        bad = 0
        for fid, k in want.items():
            mine = [r for r in rows if r[1] == fid]
            why = []
            if len(mine) < k:
                why.append(f"행 {len(mine)}개 < 요구 {k}개" if mine else "표에 행이 없다(모르는 ID)")
            for _, _, path, kind, text in mine:
                w = check_row(root, path, kind, text)
                if w:
                    why.append(w)
            if why:
                bad += 1
                print(f"FAIL {fid}: " + " · ".join(why))
            else:
                print(f"ok {fid} rows={len(mine)}")
    except Unrun as e:
        print(f"UNRUN: {e}")
        return UNRUN
    return VIOLATION if bad else OK


def self_test() -> int:
    cases = []

    def case(name, files, table, ids, want_rc, want_out=None):
        cases.append((name, files, table, ids, want_rc, want_out))

    doc = {"docs/a.md": "새 규칙 한 줄\n사본 X\n사본 X\n"}
    case("fc-has-pass", doc, "F-001\tdocs/a.md\thas\t새 규칙", "F-001", OK, "ok F-001 rows=1")
    case("fc-has-missing-fails", doc, "F-001\tdocs/a.md\thas\t없는 문구", "F-001", VIOLATION, "FAIL F-001")
    case("fc-lacks-present-fails", doc, "F-002\tdocs/a.md\tlacks\t새 규칙", "F-002", VIOLATION, "옛 문구 1회")
    case("fc-count-mismatch-fails", doc, "F-003\tdocs/a.md\tcount=3\t사본 X", "F-003", VIOLATION, "2회(기대 3)")
    case("fc-missing-file-unrun", doc, "F-004\tdocs/none.md\thas\tx", "F-004", UNRUN, "UNRUN")
    case("fc-bad-row-unrun", doc, "F-005\tdocs/a.md\tmaybe\tx", "F-005", UNRUN, "형식 오류")
    case("fc-unknown-id-fails", doc, "F-001\tdocs/a.md\thas\t새 규칙", "F-009", VIOLATION, "모르는 ID")
    case("fc-min-rows-short-fails", doc, "F-001\tdocs/a.md\thas\t새 규칙", "F-001:2", VIOLATION, "행 1개 < 요구 2개")
    case("fc-all-rows-default", doc, "F-001\tdocs/a.md\thas\t새 규칙\nF-003\tdocs/a.md\tcount=2\t사본 X", None, OK, "ok F-003 rows=1")

    import contextlib
    import io
    passed, failed = 0, []
    for name, files, table, ids, want_rc, want_out in cases:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rel, txt in files.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(txt, encoding="utf-8")
            t = root / "contracts.tsv"
            t.write_text("id\tpath\tkind\ttext\n" + table + "\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = run(root, t, ids)
            out = buf.getvalue()
            if rc == want_rc and (want_out is None or want_out in out):
                passed += 1
                print(f"PASS {name}")
            else:
                failed.append(f"{name}: rc={rc}(기대 {want_rc}) 출력={out.strip()[:120]!r}")
    for f in failed:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{len(cases)} passed")
    return OK if not failed else VIOLATION


def main() -> int:
    ap = argparse.ArgumentParser(description="finding 문서 계약 대조")
    ap.add_argument("--root", default=os.path.dirname(SCRIPT_DIR))
    ap.add_argument("--table", default=None)
    ap.add_argument("--ids", default=None, metavar="F-NNN[:k],…")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    root = Path(a.root)
    return run(root, Path(a.table) if a.table else root / DEFAULT_TABLE, a.ids)


if __name__ == "__main__":
    sys.exit(main())
