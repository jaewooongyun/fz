#!/usr/bin/env python3
"""codegraph 인덱스 신선도 검사.

인덱스가 디스크보다 뒤처지면 참조 탐색 결과가 조용히 낡는다.
`files.content_hash`(sha256)를 디스크와 대조해 판정한다.

exit 0  최신 (불일치 0)
exit 1  stale — 갱신 필요 (`codegraph sync`)
exit 2  UNRUN — 인덱스 부재 등 판정 불가. ⛔ 통과로 읽지 않는다
"""
# lint:no-root-anchor — 대상 레포를 --repo 인자로 받는 외부 검사기라 플러그인 루트를 해석하지 않는다
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sqlite3
import sys

UNRUN, OK, STALE = 2, 0, 1


def find_db(root):
    db = root / ".codegraph" / "codegraph.db"
    return db if db.is_file() else None


def check(root, limit=0):
    db = find_db(root)
    if db is None:
        return UNRUN, f"인덱스 없음: {root}/.codegraph/codegraph.db — 판정 불가(UNRUN)"
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("SELECT path, content_hash FROM files").fetchall()
    except sqlite3.Error as e:
        return UNRUN, f"DB 조회 실패: {type(e).__name__}: {e} — 판정 불가(UNRUN)"
    if not rows:
        return UNRUN, "files 테이블이 비어 있다 — 측정 실패를 먼저 의심한다(UNRUN)"

    missing, mismatch, checked = [], [], 0
    for rel, want in rows:
        if limit and checked >= limit:
            break
        p = root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        checked += 1
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != want:
            mismatch.append(rel)

    if missing or mismatch:
        head = (missing + mismatch)[:3]
        return STALE, (
            f"stale — 대조 {checked} · 삭제 {len(missing)} · 해시불일치 {len(mismatch)}"
            f" (예: {', '.join(head)}) → `codegraph sync` 필요"
        )
    return OK, f"최신 — {checked}개 파일 해시 일치, 누락 0"


def self_test():
    """양성·음성 대조를 모두 돌린다. 하나라도 어긋나면 실패한다."""
    import tempfile

    fails = []

    # 1) 인덱스 없는 디렉토리 → UNRUN (fail-open 이면 OK 로 샌다)
    with tempfile.TemporaryDirectory() as d:
        code, _ = check(pathlib.Path(d))
        if code != UNRUN:
            fails.append(f"인덱스 부재가 UNRUN 이 아니다: exit={code}")

    # 2) 해시가 맞는 인덱스 → OK
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / ".codegraph").mkdir()
        f = root / "a.txt"
        f.write_text("hello")
        con = sqlite3.connect(root / ".codegraph" / "codegraph.db")
        con.execute("CREATE TABLE files (path TEXT, content_hash TEXT)")
        con.execute(
            "INSERT INTO files VALUES (?,?)",
            ("a.txt", hashlib.sha256(b"hello").hexdigest()),
        )
        con.commit()
        con.close()
        code, msg = check(root)
        if code != OK:
            fails.append(f"일치 케이스가 OK 가 아니다: exit={code} {msg}")

        # 3) 같은 인덱스에서 파일만 바꾸면 → STALE (음성 대조)
        f.write_text("changed")
        code, _ = check(root)
        if code != STALE:
            fails.append(f"변경 케이스가 STALE 이 아니다: exit={code}")

        # 4) 파일을 지우면 → STALE
        f.unlink()
        code, _ = check(root)
        if code != STALE:
            fails.append(f"삭제 케이스가 STALE 이 아니다: exit={code}")

    if fails:
        for m in fails:
            print(f"  FAIL {m}")
        print(f"self-test {len(fails)} 실패")
        return 1
    print("self-test 4/4 통과 (UNRUN·OK·변경STALE·삭제STALE)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="codegraph 인덱스 신선도 검사")
    ap.add_argument("--repo", default=".", help="대상 레포 루트")
    ap.add_argument("--limit", type=int, default=0, help="대조 파일 수 상한(0=전수)")
    ap.add_argument("--self-test", action="store_true", help="자가 검사만 수행")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    code, msg = check(pathlib.Path(a.repo).resolve(), a.limit)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
