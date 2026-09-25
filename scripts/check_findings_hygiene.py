#!/usr/bin/env python3
"""fz-findings 레지스트리 불변식 검사.

README §0 이 불변식을 이 폴더의 존재 이유로 못 박는다 — *"entries/ 에 있는 것 = 아직 반영되지
않은 것. 예외 없음"*. 그런데 실측(2026-09-17)에서 넷이 깨져 있었다:
`status: resolved` 3건 잔존 · 중복 ID 11쌍 · archive 번호 재사용 3건 · 등재율 33%.

⛔ 읽기 실패와 빈 분모를 **거부**한다 — 디렉토리 누락이 "위반 0건" 으로 위장되면 이 검사기가
스스로 fail-open 이 된다(F-216 계통).

exit 0  불변식 충족
exit 1  위반 — 건수는 출력 참조
exit 2  UNRUN — 레지스트리 부재·빈 분모 등 판정 불가. ⛔ 통과로 읽지 않는다
"""
# lint:no-root-anchor — 대상 레지스트리를 --root 인자로 받는 외부 검사기다
from __future__ import annotations

import argparse
import pathlib
import re
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ 캡처에 접미 문자를 포함한다 — `F-123a` 를 `F-123` 으로 접으면 서로 다른 발견이 중복으로
#    보이고, INDEX 대조에서도 키가 어긋난다(이전 판은 `i[:5]` 로 잘라 맞추고 있었다).
SLUG = re.compile(r"^(F-\d{3}[a-z]?)-[a-z0-9-]+$")
FM = re.compile(r"\A---\n(.*?)\n---", re.S)
STATUS = re.compile(r"^status:\s*(\S+)", re.M)
# INDEX 등재 판정 단위 = 표 행(규약 8). 산문 언급은 등재가 아니다.
IDX_ROW = re.compile(r"^\|\s*\*{0,2}(F-\d{3}[a-z]?)\*{0,2}\s*\|", re.M)
CANON_STATUS = {"open", "proposed"}
# ⛔ `p_id` 는 **선택** 필드다(A5 계약) — 없는 것은 위반이 아니라 *미분류* 다.
#    형식은 실측 규약 `P{tier}-{letter}` 를 따른다(`P1-B`·`P2-A` — slug 가 아니다).
P_ID_LINE = re.compile(r"^p_id:\s*(\S+)", re.M)
P_ID_OK = re.compile(r"^P[0-9]-[A-Z]$")



class Unreadable(Exception):
    """파일을 읽지 못했다 — **없는 것과 다른 축**이므로 UNRUN 으로 올린다."""


def read_or_raise(path: pathlib.Path) -> str:
    """⛔ `OSError` 만 잡으면 안 된다 — 깨진 바이트는 `UnicodeDecodeError`(ValueError 계열)로
    나오고 그대로 전파돼 UNRUN 조차 내지 못한다 [외부: fz-gpt validate r2 #4].
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Unreadable(f"{path.name}: {type(e).__name__}: {e}") from e


def list_md(d: pathlib.Path):
    """디렉토리의 `*.md` 목록. ⛔ 열거 실패를 **빈 목록과 구분**한다 — 못 세는 것과
    셀 게 없는 것은 다르다. 구분하지 않으면 권한 오류가 '위반 0건' 으로 둔갑한다
    [외부: fz-gpt validate r2 새 이슈 major].
    """
    if not d.is_dir():
        return []
    try:
        # ⛔ `glob` 을 쓰지 않는다 — 실측: 권한 없는 디렉토리에서 **예외 없이 빈 목록**을 낸다
        #    (Python 3.9.6 확인). `iterdir`·`listdir`·`scandir` 는 PermissionError 를 던진다.
        #    glob 로 열거하면 이 함수의 try/except 는 영원히 발동하지 않는다
        #    [외부: fz-gpt validate r3 — 내 fixture 가 glob 을 갈아끼워 없는 경로를 검사했다].
        return sorted(q for q in d.iterdir() if q.suffix == ".md")
    except OSError as e:
        raise Unreadable(f"{d.name}/ 열거 실패: {type(e).__name__}: {e}") from e


def check(root: pathlib.Path, strict: bool, ledger: pathlib.Path | None = None):
    try:
        return _check(root, strict, ledger)
    except Unreadable as e:
        print(f"UNRUN: 읽기/열거 실패 — {e} (⛔ 통과가 아니다)")
        return UNRUN


def _check(root: pathlib.Path, strict: bool, ledger: pathlib.Path | None = None):
    ent, arc, idx = root / "entries", root / ".archive", root / "INDEX.md"
    if not ent.is_dir():
        print(f"UNRUN: entries 디렉토리 없음 — {ent}")
        return UNRUN
    files = sorted(p for p in ent.glob("*.md") if SLUG.match(p.stem))
    if not files:
        print(f"UNRUN: entries 에 F-NNN 엔트리가 0건 — 측정 실패를 먼저 의심한다 ({ent})")
        return UNRUN

    resolved, unread, by_id = [], [], {}
    p_ids, bad_pid = {}, []
    no_status = []
    for p in files:
        try:
            t = read_or_raise(p)          # ⛔ 디코딩 실패도 포함 (INDEX 와 같은 규칙)
        except Unreadable as e:
            unread.append(str(e))
            continue
        m = FM.match(t)
        if m:
            sm = STATUS.search(m.group(1))
            if sm:
                val = sm.group(1).split("#")[0].strip()
                if val not in CANON_STATUS:
                    resolved.append(f"{p.name}: status={val}")
            else:
                # ⛔ frontmatter 는 있는데 status 줄이 없다 — 이전 판은 여기서 조용히 빠져나갔고,
                #    "status 비정규 4건" 이라는 인쇄가 **나머지는 정상**이라는 거짓 함의를 줬다.
                no_status.append(f"{p.name}: frontmatter 에 status 줄 없음")
        else:
            no_status.append(f"{p.name}: frontmatter 블록 자체가 없음")
        if m:
            pm = P_ID_LINE.search(m.group(1))
            if pm:
                v = pm.group(1).split("#")[0].strip()
                if P_ID_OK.match(v):
                    p_ids.setdefault(v, []).append(p.name)
                else:
                    bad_pid.append(f"{p.name}: p_id={v} (형식 `P{{tier}}-{{letter}}` 아님)")
        by_id.setdefault(SLUG.match(p.stem).group(1), []).append(p.name)

    if unread:
        print(f"UNRUN: 읽기 실패 {len(unread)}건 — 판정 불가")
        for u in unread:
            print(f"  {u}")
        return UNRUN

    dups = {k: v for k, v in by_id.items() if len(v) > 1}
    # archive 번호 재사용: 살아 있는 엔트리와 같은 번호가 .archive 에도 있다
    reuse = []
    if arc.is_dir():
        arc_ids = {}
        for p in list_md(arc):
            m = SLUG.match(p.stem)
            if m:
                arc_ids.setdefault(m.group(1), []).append(p.name)
        for i in sorted(set(arc_ids) & set(by_id)):
            reuse.append(f"{i}: entries={by_id[i]} archive={arc_ids[i]}")
    arc_state = "없음" if not arc.is_dir() else f"{len(list_md(arc))}건"

    # 등재율
    # ⛔ 양방향으로 센다 — 교집합만 보면 "INDEX 에는 있는데 엔트리가 사라진" 행(고아)이
    #    등재율에 전혀 나타나지 않는다. 두 방향은 다른 고장이다 [외부: fz-gpt review #7].
    orphans, unlisted = [], []
    if idx.is_file():
        # ⛔ 읽기 실패는 "INDEX 없음" 과 다르다 — 있는데 못 읽은 것이므로 판정 불가다.
        idx_text = read_or_raise(idx)
        idx_ids = set(IDX_ROW.findall(idx_text))
        live = set(by_id)
        listed = len(live & idx_ids)
        rate = 100 * listed // max(len(live), 1)
        # ⛔ archive 로 배출된 ID 의 INDEX 행은 **면제 대상이 아니다**. `INDEX.md:3` 이
        #    "반영·기각되면 행을 지우고 APPLIED.md 로 옮긴다" 라고 못박는다 — 남아 있으면
        #    계약 위반이다. 이전 판은 이것을 오탐 방어라고 잘못 읽었다 [외부: fz-gpt validate #7].
        orphans = sorted(idx_ids - live)
        unlisted = sorted(live - idx_ids)
        idx_state = f"{listed}/{len(live)} = {rate}%"
    else:
        idx_ids, rate, idx_state = set(), None, "INDEX.md 없음"

    # ⛔ 규약에 안 맞는 파일명은 **조용히 제외되지 않는다** — 실측에서 slug 에 대문자가 하나 섞인
    #    엔트리가 세 도구 모두에게 보이지 않은 채 남아 있었다. 안 보이는 것은 관리되지 않는다.
    malformed = sorted(q.name for q in list_md(ent)
                       if not q.name.startswith("_") and not SLUG.match(q.stem))

    print(f"분모: entries {len(files)}건 · 고유 ID {len(by_id)} · archive {arc_state}")
    print(f"  status 비정규({'|'.join(sorted(CANON_STATUS))} 외) : {len(resolved)}")
    for r in resolved:
        print(f"      {r}")
    print(f"  중복 ID                            : {len(dups)}")
    for k in sorted(dups):
        print(f"      {k}: {', '.join(dups[k])}")
    print(f"  archive 번호 재사용                 : {len(reuse)}")
    for r in reuse:
        print(f"      {r}")
    print(f"  INDEX 등재율                        : {idx_state}")
    print(f"  status 줄 부재(판정 자체가 불가)     : {len(no_status)}")
    for n in no_status[:5]:
        print(f"      {n}")
    if len(no_status) > 5:
        print(f"      … 외 {len(no_status) - 5}건")
    print(f"  파일명 규약 불일치(도구 사각지대)    : {len(malformed)}")
    for m in malformed:
        print(f"      {m}")
    print(f"  INDEX 고아 행(live 엔트리 없음)      : {len(orphans)}")
    for o in orphans:
        print(f"      {o}")
    print(f"  INDEX 미등재 엔트리                 : {len(unlisted)}")
    for u in unlisted[:5]:
        print(f"      {u}")
    if len(unlisted) > 5:
        print(f"      … 외 {len(unlisted) - 5}건")

    print(f"  p_id 형식 위반                      : {len(bad_pid)}")
    for b in bad_pid:
        print(f"      {b}")
    if ledger is None:
        # ⛔ 원장을 안 받았으면 **소속 검사는 미판정**이다 — 통과로 세지 않는다.
        print(f"  p_id 소속(원장 대조)                 : 미판정 (--ledger 미지정) · 부여 {sum(len(v) for v in p_ids.values())}건/{len(p_ids)}종")
    else:
        try:
            lt = read_or_raise(ledger)
        except Unreadable as e:
            print(f"UNRUN: 원장을 읽지 못했다 — {e}")
            return UNRUN
        known = set(re.findall(r"`(P[0-9]-[A-Z])`", lt)) | set(re.findall(r"^###\s*(P[0-9]-[A-Z])\b", lt, re.M))
        unknown = sorted(k for k in p_ids if k not in known)
        print(f"  p_id 소속(원장 미등재)               : {len(unknown)}")
        for u in unknown:
            print(f"      {u}: {', '.join(p_ids[u][:3])}")
        bad_pid += [f"원장 미등재 p_id {u}" for u in unknown]

    violations = len(resolved) + len(dups) + len(reuse) + len(malformed) + len(bad_pid)
    if violations:
        print(f"VIOLATION: 불변식 위반 {violations}건 (status {len(resolved)} · 중복 {len(dups)} · 재사용 {len(reuse)} · 파일명 {len(malformed)} · p_id {len(bad_pid)})")
        return VIOLATION
    if strict:
        # ⛔ INDEX 가 없으면 --strict 는 **판정 불가**다 — 이전 판은 rate=None 을 조용히 통과시켜
        #    "가장 엄격한 모드가 가장 약한 결과"를 냈다(fail-open) [외부: fz-gpt review #4].
        if rate is None:
            print(f"UNRUN: --strict 인데 INDEX.md 가 없다 — 등재율 판정 불가 ({idx})")
            return UNRUN
        if rate < 100 or orphans or no_status:
            print(f"VIOLATION: --strict — 등재율 {rate}% · 고아 행 {len(orphans)}건 · status 부재 {len(no_status)}건")
            return VIOLATION
    print("OK: 불변식 충족")
    return OK


def self_test():
    """fixture — 정상·resolved잔존·중복ID·archive재사용·빈분모UNRUN
    + strict무INDEX·INDEX고아·배출건오탐방어 (뒤 3종 = fz-gpt review #4/#7 회귀)."""
    import tempfile

    passed, failed, cases = [], [], 0

    def mk(tmp, entries, arc=(), idx_rows="", idx=True):
        root = pathlib.Path(tmp) / "reg"
        (root / "entries").mkdir(parents=True)
        for slug, status in entries:
            body = f"---\nid: {slug[:5]}\nstatus: {status}\n---\n\n# {slug}\n" if status else f"# {slug}\n"
            (root / "entries" / f"{slug}.md").write_text(body, encoding="utf-8")
        if arc:
            (root / ".archive").mkdir()
            for slug in arc:
                (root / ".archive" / f"{slug}.md").write_text("x\n", encoding="utf-8")
        if idx:
            (root / "INDEX.md").write_text("# INDEX\n\n| ID | x |\n|---|---|\n" + idx_rows, encoding="utf-8")
        return root

    def case(name, fn):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(tmp)
                passed.append(name)
            except AssertionError as e:
                failed.append(f"{name}: {e}")
            except Exception as e:
                # ⛔ AssertionError 만 잡으면 fixture 하나가 터질 때 **뒤의 전부가 안 돈다** —
                #    그리고 self-test 는 "N/N 통과" 를 인쇄하지 못한 채 죽어서, 통과도 실패도
                #    아닌 침묵이 된다(실측: ablation 이 이것을 '헛돌이' 로 오독했다).
                failed.append(f"{name}: ⛔ 예외 {type(e).__name__}: {e}")

    def c_ok(tmp):
        r = mk(tmp, [("F-001-a", "open"), ("F-002-b", "proposed")], idx_rows="| F-001 | x |\n| F-002 | x |\n")
        assert check(r, False) == OK, "정상인데 OK 가 아니다"

    def c_resolved(tmp):
        r = mk(tmp, [("F-001-a", "resolved")])
        assert check(r, False) == VIOLATION, "resolved 잔존이 잡히지 않았다"

    def c_dup(tmp):
        r = mk(tmp, [("F-032-one", "open"), ("F-032-two", "open")])
        assert check(r, False) == VIOLATION, "중복 ID 가 잡히지 않았다"

    def c_reuse(tmp):
        r = mk(tmp, [("F-127-live", "open")], arc=("F-127-archived",))
        assert check(r, False) == VIOLATION, "archive 번호 재사용이 잡히지 않았다"

    def c_unrun(tmp):
        root = pathlib.Path(tmp) / "reg"
        (root / "entries").mkdir(parents=True)
        assert check(root, False) == UNRUN, "빈 분모가 UNRUN 이 아니다 (fail-open)"

    def c_strict_no_index(tmp):
        """⛔ 회귀: INDEX 부재 시 --strict 가 조용히 통과하면 안 된다 [외부: fz-gpt review #4]."""
        r = mk(tmp, [("F-001-a", "open")], idx=False)
        assert check(r, False) == OK, "비-strict 는 통과해야 한다"
        rc = check(r, True)
        assert rc == UNRUN, f"⛔ --strict 인데 rc={rc} — INDEX 없이 통과시켰다(fail-open)"

    def c_index_orphan(tmp):
        """⛔ 회귀: INDEX 에만 있고 엔트리·archive 어디에도 없는 행을 잡아야 한다 [외부: fz-gpt review #7]."""
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n| F-777 | 사라진 엔트리 |\n")
        assert check(r, False) == OK, "고아는 비-strict 를 막지 않는다"
        assert check(r, True) == VIOLATION, "⛔ 등재율 100% 라서 고아 행을 놓쳤다"

    def c_archived_row_is_stale(tmp):
        """⛔ 회귀: 배출된 ID 의 INDEX 행은 **지워져야 한다** — 면제가 아니다.

        근거는 레지스트리 자신의 계약이다 — `INDEX.md:3`
        "반영·기각되면 행을 지우고 APPLIED.md 로 옮긴다".
        이전 판은 이 행을 '오탐 방어' 로 면제했는데, 그것이 계약 위반을 고정하고 있었다
        [외부: fz-gpt validate #7].
        """
        r = mk(tmp, [("F-001-a", "open")], arc=("F-300-done",),
               idx_rows="| F-001 | x |\n| F-300 | 배출됐는데 행이 남음 |\n")
        assert check(r, False) == OK, "비-strict 는 통과해야 한다"
        assert check(r, True) == VIOLATION, \
            "⛔ 배출된 ID 의 잔존 INDEX 행을 면제했다 (INDEX.md:3 계약 위반)"

    def c_index_unreadable_unrun(tmp):
        """⛔ 회귀: INDEX 가 있는데 못 읽으면 UNRUN 이다 (없는 것과 다른 축).

        ⛔ 이전 판은 `chmod 000` 을 썼는데, **root 에서는 권한이 무시돼** 분기에 닿지 못한 채
        통과로 집계됐다 — 그 환경에선 ablation 도 무효였다 [외부: fz-gpt validate r2 minor].
        환경에 기대지 않도록 **오류를 직접 주입**한다.
        """
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n")
        real = pathlib.Path.read_text
        target = (r / "INDEX.md").resolve()

        def boom(self, *a, **k):
            if self.resolve() == target:
                raise PermissionError("주입된 읽기 실패")
            return real(self, *a, **k)

        pathlib.Path.read_text = boom
        try:
            rc = check(r, False)
        finally:
            pathlib.Path.read_text = real
        assert rc == UNRUN, f"⛔ 읽기 실패인데 rc={rc} (UNRUN 이어야 한다)"

    def c_index_bad_utf8_unrun(tmp):
        """⛔ 회귀: 깨진 바이트는 `UnicodeDecodeError` 로 나온다 — OSError 만 잡으면 샌다
        [외부: fz-gpt validate r2 #4]."""
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n")
        (r / "INDEX.md").write_bytes(b"# I\n\n| ID |\n|---|\n| F-001 | \xff\xfe |\n")
        rc = check(r, False)
        assert rc == UNRUN, f"⛔ 디코딩 실패인데 rc={rc}"

    def c_archive_enumeration_failure_unrun(tmp):
        """⛔ 회귀: archive 를 **못 세는 것**과 **셀 게 없는 것**은 다르다.

        구분하지 않으면 권한 오류가 '재사용 0건' 으로 둔갑해 위반이 정상으로 바뀐다
        [외부: fz-gpt validate r2 새 이슈 major].
        """
        r = mk(tmp, [("F-001-a", "open")], arc=("F-001-old",), idx_rows="| F-001 | x |\n")
        assert check(r, False) == VIOLATION, "정상 열거면 번호 재사용 위반이어야 한다"
        # ⛔ **실제 호출 경로**에 주입한다. 이전 판은 `glob` 을 갈아끼웠는데 코드가 `glob` 을
        #    쓰던 시절에도 진짜 권한 오류는 glob 이 삼켜서, 그 fixture 는 실재하지 않는 경로를
        #    검사하고 있었다 [외부: fz-gpt validate r3].
        real = pathlib.Path.iterdir
        arc_dir = (r / ".archive").resolve()

        def boom(self):
            if self.resolve() == arc_dir:
                raise PermissionError("주입된 열거 실패")
            return real(self)

        pathlib.Path.iterdir = boom
        try:
            rc = check(r, True)
        finally:
            pathlib.Path.iterdir = real
        assert rc == UNRUN, f"⛔ 열거 실패인데 rc={rc} — 위반이 정상으로 바뀌었다"

    def c_malformed_filename(tmp):
        """⛔ 회귀: 규약에 안 맞는 파일명(대문자 등)을 조용히 제외하면 안 된다 (실측 1건)."""
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n")
        (r / "entries" / "F-077-zsh-colon-A-modifier.md").write_text("---\nstatus: open\n---\n", encoding="utf-8")
        assert check(r, False) == VIOLATION, "⛔ 대문자 섞인 파일명이 침묵 제외됐다"

    def c_underscore_not_flagged(tmp):
        """⛔ 오탐 방어: `_TEMPLATE.md` 같은 밑줄 파일은 엔트리가 아니다."""
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n")
        (r / "entries" / "_TEMPLATE.md").write_text("템플릿\n", encoding="utf-8")
        assert check(r, False) == OK, "템플릿을 불일치로 오탐했다"

    def c_missing_status(tmp):
        """⛔ 회귀: status 줄이 없는 엔트리를 조용히 건너뛰면 안 된다 (실측 96건).

        판정 축이 다르다 — 비정규 값은 *틀린 답*이고, 줄 부재는 *답이 없는 것*이다.
        후자를 안 세면 "비정규 N건" 이 나머지는 정상이라는 거짓 함의를 준다.
        """
        r = mk(tmp, [("F-001-a", "open"), ("F-002-b", None)], idx_rows="| F-001 | x |\n| F-002 | x |\n")
        assert check(r, False) == OK, "비-strict 는 통과해야 한다 (기존 상태 보존)"
        assert check(r, True) == VIOLATION, "⛔ --strict 인데 status 부재를 놓쳤다"

    def c_entry_bad_utf8_unrun(tmp):
        """⛔ 회귀: 엔트리 파일의 디코딩 실패도 UNRUN 이다 (INDEX 와 같은 규칙) [외부: fz-gpt validate r3]."""
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n")
        (r / "entries" / "F-001-a.md").write_bytes(b"---\nstatus: open\n---\n\xff\xfe")
        assert check(r, True) == UNRUN, "⛔ 엔트리 디코딩 실패가 UNRUN 이 아니다"

    for n, f in [("ok", c_ok), ("resolved-remains", c_resolved), ("dup-id", c_dup),
                 ("archive-id-reuse", c_reuse), ("empty-denominator-unrun", c_unrun),
                 ("strict-no-index-unrun", c_strict_no_index),
                 ("index-orphan-row", c_index_orphan),
                 ("archived-row-is-stale", c_archived_row_is_stale),
                 ("index-unreadable-unrun", c_index_unreadable_unrun),
                 ("index-bad-utf8-unrun", c_index_bad_utf8_unrun),
                 ("archive-enumeration-failure-unrun", c_archive_enumeration_failure_unrun),
                 ("entry-bad-utf8-unrun", c_entry_bad_utf8_unrun),
                 ("malformed-filename", c_malformed_filename),
                 ("underscore-not-entry", c_underscore_not_flagged),
                 ("missing-status-line", c_missing_status)]:
        cases += 1
        case(n, f)

    # ⛔ 분모는 세어서 인쇄한다 (상수로 적으면 케이스 증설 시 거짓이 된다)
    print(f"self-test {len(passed)}/{cases} 통과")
    for p in passed:
        print(f"  ok   {p}")
    for f in failed:
        print(f"  FAIL {f}")
    return OK if not failed else VIOLATION


def main():
    ap = argparse.ArgumentParser(description="fz-findings 불변식 검사")
    ap.add_argument("--root", type=pathlib.Path)
    ap.add_argument("--strict", action="store_true", help="등재율 100% 미달도 위반으로 본다")
    ap.add_argument("--ledger", type=pathlib.Path,
                    help="promotion-ledger.md — p_id 소속 대조 (미지정 시 그 축은 **미판정**)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.root:
        ap.error("--root 가 필요하다 (또는 --self-test)")
    return check(a.root, a.strict, ledger=a.ledger)


if __name__ == "__main__":
    sys.exit(main())
