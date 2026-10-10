#!/usr/bin/env python3
"""fz-findings 레지스트리 불변식 검사.

README §0 이 불변식을 이 폴더의 존재 이유로 못 박는다 — *"entries/ 에 있는 것 = 아직 반영되지
않은 것. 예외 없음"*. 그런데 실측(2026-09-17)에서 넷이 깨져 있었다:
`status: resolved` 3건 잔존 · 중복 ID 11쌍 · archive 번호 재사용 3건 · 등재율 33%.

⛔ 읽기 실패와 빈 분모를 **거부**한다 — 디렉토리 누락이 "위반 0건" 으로 위장되면 이 검사기가
스스로 fail-open 이 된다(F-216 계통).

기본 모드가 F-373 축까지 본다(E1-7 승격 — 전에는 `--strict` 전용) — 고아 행 · 등재율 100% · status 줄 · 대기열 절 밖 행 ·
APPLIED/live 번호 충돌 · title·H1·본문 중복 · 펜스 밖 INDEX 덤프. 축 정의는 `_strict_axes`. `--strict` 는 같은 판정의 별칭이다.
배출 감사 `eject_findings.py --audit ROOT` 가 같은 ROOT 에 이 기본 모드를 부른다(실 레지스트리 소비자).

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
# ⛔ 이름·뜻(문서 어디서든 첫 칸이 ID 인 표 행)을 바꾸지 않는다 — `eject_findings.py` 가 importlib 로 빌려
#    문서 전체에서 배출분 행을 지운다. 절 구분은 `index_rows` · `queue_rows` 가 이 위에 얹는다.
IDX_ROW = re.compile(r"^\|\s*\*{0,2}(F-\d{3}[a-z]?)\*{0,2}\s*\|", re.M)
QUEUE_HEAD = re.compile(r"^##\s+대기열(\s|$)")
SECTION_HEAD = re.compile(r"^#{1,2}\s")       # 대기열 절은 다음 `#`·`##` 제목에서 끝난다(`###` 는 안쪽)
FENCE = re.compile(r"^\s*(```|~~~)")
DUMP_LINE = re.compile(r"^(=== |\d+:\| F-\d{3})")
TITLE_LINE = re.compile(r"^title:\s*(.*?)\s*$", re.M)
H1_ID = re.compile(r"^F-\d{3}[a-z]?\s*[—·:\-]*\s*")
SHINGLE_MIN, CONTAIN_MIN = 40, 0.8            # 본문 근접 중복: 4-gram ≥40 개 · 포함도 ≥0.8 (M1 실측 오탐 0)
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


def index_rows(text: str):
    """INDEX 의 표 행(`IDX_ROW`) — 펜스 밖 줄만. 반환 [(줄 번호, ID, 속한 절 제목 | None, 대기열 절 안인가)].

    ⛔ 펜스 안 줄은 제목도 행도 아니다 — `## 다음 ID` 의 bash 예시처럼 코드 블록 속 `#`·`|` 를 읽으면 절이 갈린다.
    """
    out, sec, inq, fence = [], None, False, False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        if SECTION_HEAD.match(line):
            sec, inq = line.strip(), bool(QUEUE_HEAD.match(line))
            continue
        m = IDX_ROW.match(line)
        if m:
            out.append((n, m.group(1), sec, inq))
    return out


def queue_rows(text: str):
    """`## 대기열` 절 안 표 행의 ID 목록(문서 순서) — 등재 판정 단위."""
    return [i for _, i, _, q in index_rows(text) if q]


def _eject_module():
    """`eject_findings.py` 를 importlib 로 읽는다 — APPLIED 대장 행 규칙(`applied_records`)을 여기서 다시 짜지 않는다.

    ⛔ 모듈 최상위에서 import 하지 않는다 — 배출도 이 파일을 importlib 로 읽어서 양쪽이 최상위에서 부르면 순환이다.
    ⛔ INDEX 용 `IDX_ROW`(첫 칸 ID)로 APPLIED 를 읽으면 배출 4열 행(버전이 먼저)과 레거시 행(날짜가 먼저)이
       모두 0건이 되어 '충돌 0' 거짓 음성이 난다(EC-14).
    """
    import importlib.util
    path = pathlib.Path(__file__).resolve().parent / "eject_findings.py"
    spec = importlib.util.spec_from_file_location("fz_findings_eject", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"모듈 명세를 만들지 못했다 ({path})")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fence_free(text: str):
    """(줄 번호, 줄) — 펜스 밖 줄만."""
    fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fence = not fence
            continue
        if not fence:
            yield n, line


def _doc_keys(text: str):
    """엔트리 한 편의 (frontmatter title, 정규화 H1, 본문 4-gram 집합)."""
    m = FM.match(text)
    title = ""
    if m:
        tm = TITLE_LINE.search(m.group(1))
        if tm:
            title = tm.group(1).split("  #")[0].strip()
            if len(title) >= 2 and title[0] == title[-1] and title[0] in "\"'":
                title = title[1:-1].strip()
    body = text[m.end():] if m else text
    h1 = next((H1_ID.sub("", line[2:].strip()).strip() for _, line in _fence_free(body) if line.startswith("# ")), "")
    b2 = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    b2 = re.sub(r"^# F-\d{3}[a-z]?", "#", b2, flags=re.M)
    w = re.findall(r"\w+", b2)
    return title, h1, {tuple(w[i:i + 4]) for i in range(max(len(w) - 3, 0))}


def _same_key_pairs(keys):
    """{문서: 값} → 같은 값(빈 값 제외)을 가진 문서 쌍 목록."""
    groups = {}
    for d, k in keys.items():
        if k:
            groups.setdefault(k, []).append(d)
    return [(a, b) for v in groups.values() for i, a in enumerate(sorted(v)) for b in sorted(v)[i + 1:]]


def _strict_axes(root: pathlib.Path, texts: dict, live_slugs: set, live_ids: set, idx_rows_all, idx_text):
    """F-373 축(E1-4 에서 --strict 로 들어와 E1-7 에서 기본으로 승격). 반환 (위반 수 {축: N}, 미판정 사유 목록). 출력은 여기서 찍는다.

    ⛔ 출력의 `[--strict]` · `--strict` 표지는 이 축 묶음의 이름으로 남긴다 — 기본 모드도 같은 줄을 낸다.
       fixture(`tests/fixtures/registry/hygiene-cells/run.sh`)가 이 문자열을 고정한다.

      · 대기열 밖 — 등재는 `## 대기열` 절 안 표 행만 센다(호출자). 그 밖(다른 절 · 대기열 제목 없음)의 표 행은 위반
        (고아는 호출자가 펜스 밖 모든 표 행으로 센다 — 배출 정리 `eject_findings.py` 의 문서 전체 범위와 같다)
      · APPLIED/live 번호 충돌 — 대장 행 판정은 `eject_findings.applied_records` 를 빌린다(배출 4열 행 · 레거시
        날짜 우선 행을 둘 다 읽는다). 번호 행 ∩ live 번호 · slug 행의 번호 ∩ live 번호. APPLIED.md 부재 = 미판정
      · entries+.archive 의 frontmatter title · 번호 접두를 뗀 H1 · 본문 4-gram 포함도 중복
      · 펜스 밖 INDEX 덤프 잔재(`^=== ` · `^NN:| F-NNN`) — entries · .archive · APPLIED.md · INDEX.md
    호출자 판정: 위반이 하나라도 있으면 exit 1, 없고 미판정 축이 있으면 exit 2(줄 맨 앞 `UNRUN:`).
    texts: {"entries/<slug>": 본문} — 이미 읽은 live 엔트리. archive 본문은 여기서 읽는다.
    ⛔ 이 축들의 읽기 실패(archive 본문 · APPLIED.md)는 예외로 올리지 않고 미판정 사유로 돌려준다 — 올리면 이미 찾은
       기본 위반까지 UNRUN 으로 덮여 '가장 엄격한 모드가 가장 약한 결과' 가 된다(위반 우선).
    """
    counts, unjudged = {}, []

    def show(label, items, fmt=str, limit=10):
        print(f"  [--strict] {label}: {len(items)}")
        for x in items[:limit]:
            print(f"      {fmt(x)}")
        if len(items) > limit:
            print(f"      … 외 {len(items) - limit}건")

    # 대기열 밖 표 행
    if idx_rows_all is None:
        print("  [--strict] INDEX 대기열 밖 행: 미판정 (INDEX.md 없음)")
    else:
        outside = [r for r in idx_rows_all if not r[3]]
        if not any(QUEUE_HEAD.match(line) for _, line in _fence_free(idx_text)):
            print("  [--strict] ⛔ INDEX 에 `## 대기열` 절이 없다 — 모든 표 행이 대기열 밖이다")
        show("INDEX 대기열 밖 행(## 대기열 절 밖 표 행)", outside, lambda r: f"{r[1]} (INDEX.md:{r[0]} · 절 {r[2] or '없음'})")
        counts["대기열 밖"] = len(outside)

    # APPLIED/live 번호 충돌
    ap = root / "APPLIED.md"
    ej = ap_nums = None
    if not ap.is_file():
        print(f"  [--strict] APPLIED/live 번호 충돌: 미판정 (APPLIED.md 없음 — {ap})")
        unjudged.append(f"--strict 인데 APPLIED.md 가 없다 — APPLIED/live 번호 충돌 판정 불가 ({ap})")
    else:
        try:
            ej = _eject_module()
        except Exception as e:      # 모듈 고장은 축 미판정이다 — 위반 0 으로 읽지 않는다
            print(f"  [--strict] APPLIED/live 번호 충돌: 미판정 (eject_findings.py 를 읽지 못했다 — {type(e).__name__}: {e})")
            unjudged.append(f"APPLIED 대장 판정기(eject_findings.applied_records)를 읽지 못했다 — {type(e).__name__}: {e}")
        else:
            try:
                ap_slugs, ap_nums = ej.applied_records(ap)
            except (OSError, UnicodeDecodeError) as e:
                print(f"  [--strict] APPLIED/live 번호 충돌: 미판정 (APPLIED.md 를 읽지 못했다 — {type(e).__name__})")
                unjudged.append(f"APPLIED.md 를 읽지 못했다 — {type(e).__name__}: {e}")
                ap_slugs = ap_nums = None
        if ej is not None and ap_nums is not None:
            hits = sorted({f"{i}: APPLIED 번호 행(레거시) · live {i}" for i in ap_nums & live_ids}
                          | {f"{SLUG.match(s).group(1)}: APPLIED slug 행 {s} · "
                             + ("live 에 같은 slug 가 남아 있다" if s in live_slugs else "live 에 같은 번호 다른 엔트리")
                             for s in ap_slugs if SLUG.match(s) and SLUG.match(s).group(1) in live_ids})
            show("APPLIED/live 번호 충돌", hits)
            counts["APPLIED 충돌"] = len(hits)

    # title · H1 · 본문 중복 (entries + .archive)
    docs = dict(texts)
    arc = root / ".archive"
    try:
        arc_files = list_md(arc)
    except Unreadable as e:
        print(f"  [--strict] 중복 · 덤프 판정에서 .archive/ 를 뺐다 (열거 실패)")
        unjudged.append(f"archive 를 열거하지 못했다 — {e}")
        arc_files = []
    for p in arc_files:
        if SLUG.match(p.stem):
            try:
                docs[f".archive/{p.stem}"] = read_or_raise(p)
            except Unreadable as e:     # 그 문서만 빼고 나머지는 판정한다 — 빠진 문서는 미판정으로 남긴다
                print(f"  [--strict] 중복 · 덤프 판정에서 뺀 문서: .archive/{p.name} (읽지 못함)")
                unjudged.append(f"archive 본문을 읽지 못했다 — {e}")
    keys = {d: _doc_keys(t) for d, t in docs.items()}
    pair = lambda ab: f"{ab[0]} ⇄ {ab[1]}"
    t_pairs = _same_key_pairs({d: k[0] for d, k in keys.items()})
    h_pairs = _same_key_pairs({d: k[1] for d, k in keys.items()})
    b_pairs, names = [], sorted(keys)
    for i, a in enumerate(names):
        A = keys[a][2]
        if len(A) < SHINGLE_MIN:
            continue
        for b in names[i + 1:]:
            Bs = keys[b][2]
            if len(Bs) < SHINGLE_MIN:
                continue
            common = len(A & Bs)
            if common and common / min(len(A), len(Bs)) >= CONTAIN_MIN:
                b_pairs.append((a, b))
    show("title 중복(frontmatter)", t_pairs, pair)
    show("H1 중복(번호 접두 제거)", h_pairs, pair)
    show(f"본문 근접 중복(4-gram 포함도 ≥{CONTAIN_MIN})", b_pairs, pair)
    counts.update({"title 중복": len(t_pairs), "H1 중복": len(h_pairs), "본문 중복": len(b_pairs)})

    # 펜스 밖 INDEX 덤프 잔재
    targets = dict(docs)
    if ap.is_file():
        try:
            targets["APPLIED.md"] = read_or_raise(ap)
        except Unreadable as e:
            unjudged.append(f"APPLIED.md 덤프 판정 불가 — {e}")
    if idx_text is not None:
        targets["INDEX.md"] = idx_text
    dumps = []
    for d in sorted(targets):
        lines = [(n, line) for n, line in _fence_free(targets[d]) if DUMP_LINE.match(line)]
        if lines:
            dumps.append(f"{d}: {len(lines)}줄 · 첫 줄 :{lines[0][0]} `{lines[0][1][:60]}`")
    show("펜스 밖 INDEX 덤프(^=== · ^NN:| F-NNN)", dumps)
    counts["INDEX 덤프"] = len(dumps)
    return counts, unjudged


def check(root: pathlib.Path, strict: bool, ledger: pathlib.Path | None = None):
    """`strict` 는 판정을 바꾸지 않는다(E1-7 — 기본 모드 = 옛 `--strict`). 호출부(`--strict` · self-test) 호환용으로 받는다."""
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
    texts = {}                            # --strict 중복·덤프 축이 다시 읽지 않게 둔다
    for p in files:
        try:
            t = read_or_raise(p)          # ⛔ 디코딩 실패도 포함 (INDEX 와 같은 규칙)
        except Unreadable as e:
            unread.append(str(e))
            continue
        texts[f"entries/{p.stem}"] = t
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
    idx_text, rows_all = None, None
    if idx.is_file():
        # ⛔ 읽기 실패는 "INDEX 없음" 과 다르다 — 있는데 못 읽은 것이므로 판정 불가다.
        idx_text = read_or_raise(idx)
        # ⛔ 등재는 `## 대기열` 절 안 행만 — 절 밖에 붙은 행도 등재로 세면 '엉뚱한 곳' 을 못 본다(F-373 b).
        #    고아는 펜스 밖 모든 행 기준 — 어느 절에 있든 live 가 없는 행은 고아다.
        rows_all = index_rows(idx_text)
        idx_ids = {r[1] for r in rows_all if r[3]}
        row_ids = {r[1] for r in rows_all}
        live = set(by_id)
        listed = len(live & idx_ids)
        rate = 100 * listed // max(len(live), 1)
        # ⛔ archive 로 배출된 ID 의 INDEX 행은 **면제 대상이 아니다**. `INDEX.md:3` 이
        #    "반영·기각되면 행을 지우고 APPLIED.md 로 옮긴다" 라고 못박는다 — 남아 있으면
        #    계약 위반이다. 이전 판은 이것을 오탐 방어라고 잘못 읽었다 [외부: fz-gpt validate #7].
        orphans = sorted(row_ids - live)
        unlisted = sorted(live - idx_ids)
        idx_state = f"{listed}/{len(live)} = {rate}% (## 대기열 절 행 기준)"
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

    sx, unjudged = _strict_axes(root, texts, {p.stem for p in files}, set(by_id), rows_all, idx_text)

    violations = len(resolved) + len(dups) + len(reuse) + len(malformed) + len(bad_pid)
    if violations:
        print(f"VIOLATION: 불변식 위반 {violations}건 (status {len(resolved)} · 중복 {len(dups)} · 재사용 {len(reuse)} · 파일명 {len(malformed)} · p_id {len(bad_pid)})")
        return VIOLATION
    # ⛔ 위반이 하나라도 있으면 위반이다(exit 1) — 미판정 축이 있어도 이미 본 위반은 사실이다.
    #    위반 0 일 때만 미판정이 판정을 정한다: INDEX·APPLIED 부재는 UNRUN 이다(통과 아님).
    extra = " · ".join(f"{k} {v}" for k, v in sx.items() if v)
    if (rate is not None and (rate < 100 or orphans)) or no_status or extra:
        rs = "판정 불가" if rate is None else f"{rate}%"
        print(f"VIOLATION: --strict — 등재율 {rs} · 고아 행 {len(orphans)}건 · status 부재 {len(no_status)}건"
              + (f" · {extra}" if extra else ""))
        return VIOLATION
    # ⛔ INDEX 가 없으면 **판정 불가**다 — 이전 판은 rate=None 을 조용히 통과시켜
    #    "가장 엄격한 모드가 가장 약한 결과"를 냈다(fail-open) [외부: fz-gpt review #4].
    if rate is None:
        unjudged.insert(0, f"--strict 인데 INDEX.md 가 없다 — 등재율 판정 불가 ({idx})")
    if unjudged:
        for u in unjudged:
            print(f"UNRUN: {u}")
        return UNRUN
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
            # `## 대기열` 제목 — 이 절 안 행만 등재로 센다(없으면 모든 행이 대기열 밖 위반)
            (root / "INDEX.md").write_text("# INDEX\n\n## 대기열\n\n| ID | x |\n|---|---|\n" + idx_rows, encoding="utf-8")
        # 머리 표만 있는 APPLIED — 부재는 APPLIED/live 충돌 축 미판정(UNRUN)이라 기본 모드 정상 대조가 OK 가 되려면 있어야 한다
        (root / "APPLIED.md").write_text("# APPLIED\n\n| 날짜 | ID | 한 줄 | 처리 |\n|---|---|---|---|\n", encoding="utf-8")
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
        # ⛔ 등재 행을 넣어 등재율 100% — 없으면 기본 모드의 등재율 위반이 단언을 대신 통과시킨다(E1-7 리뷰)
        r = mk(tmp, [("F-001-a", "resolved")], idx_rows="| F-001 | x |\n")
        assert check(r, False) == VIOLATION, "resolved 잔존이 잡히지 않았다"

    def c_dup(tmp):
        r = mk(tmp, [("F-032-one", "open"), ("F-032-two", "open")], idx_rows="| F-032 | x |\n")
        assert check(r, False) == VIOLATION, "중복 ID 가 잡히지 않았다"

    def c_reuse(tmp):
        r = mk(tmp, [("F-127-live", "open")], arc=("F-127-archived",), idx_rows="| F-127 | x |\n")
        assert check(r, False) == VIOLATION, "archive 번호 재사용이 잡히지 않았다"

    def c_unrun(tmp):
        root = pathlib.Path(tmp) / "reg"
        (root / "entries").mkdir(parents=True)
        assert check(root, False) == UNRUN, "빈 분모가 UNRUN 이 아니다 (fail-open)"

    def c_strict_no_index(tmp):
        """⛔ 회귀: INDEX 부재 시 --strict 가 조용히 통과하면 안 된다 [외부: fz-gpt review #4]."""
        r = mk(tmp, [("F-001-a", "open")], idx=False)
        assert check(r, False) == UNRUN, "⛔ 기본 모드가 INDEX 없이 통과시켰다(E1-7 승격 — 부재는 판정 불가)"
        rc = check(r, True)
        assert rc == UNRUN, f"⛔ --strict 인데 rc={rc} — INDEX 없이 통과시켰다(fail-open)"

    def c_index_orphan(tmp):
        """⛔ 회귀: INDEX 에만 있고 엔트리·archive 어디에도 없는 행을 잡아야 한다 [외부: fz-gpt review #7]."""
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n| F-777 | 사라진 엔트리 |\n")
        assert check(r, False) == VIOLATION, "⛔ 기본 모드가 고아 행을 놓쳤다(E1-7 승격)"
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
        assert check(r, False) == VIOLATION, "⛔ 기본 모드가 배출된 ID 의 잔존 INDEX 행을 놓쳤다(E1-7 승격)"
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
        assert check(r, False) == VIOLATION, "⛔ 기본 모드가 status 부재를 놓쳤다(E1-7 승격)"
        assert check(r, True) == VIOLATION, "⛔ --strict 인데 status 부재를 놓쳤다"

    def c_entry_bad_utf8_unrun(tmp):
        """⛔ 회귀: 엔트리 파일의 디코딩 실패도 UNRUN 이다 (INDEX 와 같은 규칙) [외부: fz-gpt validate r3]."""
        r = mk(tmp, [("F-001-a", "open")], idx_rows="| F-001 | x |\n")
        (r / "entries" / "F-001-a.md").write_bytes(b"---\nstatus: open\n---\n\xff\xfe")
        assert check(r, True) == UNRUN, "⛔ 엔트리 디코딩 실패가 UNRUN 이 아니다"

    # ── F-373 축 (E1-4 에서 --strict 로 · E1-7 에서 기본으로) — 아래 strict() 가 두 모드를 함께 돌려 같은지 본다 ──
    import contextlib
    import io

    def body(tag, n=30):
        """4-gram 이 40 개를 넘고 다른 엔트리와 겹치지 않는 본문."""
        return "".join(f"- 관측 {k}: {tag} 고유{tag}가{k} 근거{tag}나{k} 끝\n" for k in range(n))

    def entry_text(slug, title, h1, text):
        return f"---\nid: {slug[:5]}\ntitle: {title}\nstatus: open\n---\n\n# {slug[:5]} — {h1}\n\n{text}"

    LIVE = ["F-001-alpha", "F-002-beta", "F-003-gamma"]

    def full(tmp, applied=True):
        """정상 대조 — 대기열 절 · 다른 절의 백틱 표 · 펜스 안 덤프·행 · 배출 4열 행 · 레거시 날짜 우선 행 · archive 1건."""
        root = pathlib.Path(tmp) / "reg"
        (root / "entries").mkdir(parents=True)
        (root / ".archive").mkdir()
        for s in LIVE:
            (root / "entries" / f"{s}.md").write_text(entry_text(s, f"제목 {s}", f"머리 {s}", body(s)), encoding="utf-8")
        (root / "entries" / "F-001-alpha.md").write_text(
            entry_text("F-001-alpha", "제목 F-001-alpha", "머리 F-001-alpha",
                       body("F-001-alpha") + "\n```\n=== INDEX 구조 ===\n12:| F-003 | x |\n```\n"), encoding="utf-8")
        (root / ".archive" / "F-090-gone.md").write_text(entry_text("F-090-gone", "제목 배출", "머리 배출", body("F-090-gone")),
                                                         encoding="utf-8")
        rows = "".join(f"| {s[:5]} | x | [{s[:5]}](entries/{s}.md) |\n" for s in LIVE)
        (root / "INDEX.md").write_text(
            "# INDEX\n\n## 대기열\n\n| ID | x | 문서 |\n|---|---|---|\n" + rows
            + "\n## 재번호 이력\n\n| 옛 번호 | 유지 |\n|---|---|\n| `F-032` | F-032-x |\n"
            + "\n## 다음 ID\n\n```bash\n# 주석\n| F-001 | 펜스 안 |\n=== 펜스 안 ===\n```\n", encoding="utf-8")
        if applied:
            (root / "APPLIED.md").write_text(
                "# APPLIED\n\nF-001 이 지적한 홀 같은 산문은 기록이 아니다.\n\n| 날짜 | ID | 한 줄 | 처리 |\n|---|---|---|---|\n"
                "| 2026-08-24 | F-080 | 레거시 날짜 우선 행 | `applied` |\n"
                "| 9.9.9 | F-090-gone | `v9.9.9.md` | 릴리즈 `Closes:` 로 배출 |\n", encoding="utf-8")
        return root

    def strict(root):
        """기본 모드와 --strict 를 둘 다 돌린다 — 판정·출력이 같아야 한다(E1-7: --strict 는 별칭)."""
        got = []
        for s in (False, True):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check(root, s)
            got.append((rc, buf.getvalue()))
        assert got[0] == got[1], f"⛔ 기본 모드와 --strict 가 갈렸다 rc={got[0][0]}/{got[1][0]}\n{got[0][1]}"
        return got[1]

    def edit(p, old, new):
        t = p.read_text(encoding="utf-8")
        assert old in t, f"fixture 편집 대상 없음: {old!r}"
        p.write_text(t.replace(old, new, 1), encoding="utf-8")

    def c_strict_clean(tmp):
        rc, out = strict(full(tmp))
        assert rc == OK, f"⛔ 정상 대조가 --strict 에서 rc={rc} — 펜스 안 덤프·백틱 표·산문 언급을 오탐했다\n{out}"

    def c_strict_out_of_queue(tmp):
        """⛔ 회귀(F-373 b): 대기열 절 밖에 붙은 행은 등재가 아니다 — 문서 전체를 훑으면 '엉뚱한 곳' 을 못 본다."""
        r = full(tmp)
        row = "| F-003 | x | [F-003](entries/F-003-gamma.md) |\n"
        edit(r / "INDEX.md", row, "")
        edit(r / "INDEX.md", "\n## 다음 ID", "\n" + row + "\n## 다음 ID")
        rc, out = strict(r)
        assert rc == VIOLATION and "대기열 밖 행(## 대기열 절 밖 표 행): 1" in out, f"⛔ 대기열 밖 행을 놓쳤다 rc={rc}\n{out}"
        assert "INDEX 미등재 엔트리                 : 1" in out, f"⛔ 절 밖에만 행이 있는 엔트리를 등재로 셌다\n{out}"

    def c_strict_queue_heading_missing(tmp):
        """⛔ 회귀(M1 exp-b1): `## 대기열` 제목이 바뀌면 모든 행이 대기열 밖이다 — 통과시키면 안 된다."""
        r = full(tmp)
        edit(r / "INDEX.md", "## 대기열", "## 아무거나")
        rc, out = strict(r)
        assert rc == VIOLATION and "대기열 밖 행(## 대기열 절 밖 표 행): 3" in out, f"⛔ 제목 없는 대기열을 통과시켰다 rc={rc}\n{out}"

    def c_strict_orphan_outside_queue(tmp):
        """⛔ 고아는 어느 절에 있든 고아다 — 배출 정리(문서 전체)와 같은 범위."""
        r = full(tmp)
        edit(r / "INDEX.md", "\n## 다음 ID", "\n| F-777 | 사라진 엔트리 | [F-777](entries/F-777-gone.md) |\n\n## 다음 ID")
        rc, out = strict(r)
        assert rc == VIOLATION and "INDEX 고아 행(live 엔트리 없음)      : 1" in out, f"⛔ 대기열 밖 고아를 놓쳤다 rc={rc}\n{out}"

    def c_strict_applied_legacy(tmp):
        """⛔ 회귀(EC-14): 레거시 날짜 우선 번호 행(F-050 형)과 같은 번호의 live 엔트리 = 충돌."""
        r = full(tmp)
        edit(r / "APPLIED.md", "| 2026-08-24 | F-080 |", "| 2026-08-24 | F-002 |")
        rc, out = strict(r)
        assert rc == VIOLATION and "F-002: APPLIED 번호 행(레거시)" in out, f"⛔ 레거시 번호 충돌을 놓쳤다 rc={rc}\n{out}"

    def c_strict_applied_eject_row(tmp):
        """⛔ 회귀(EC-14): 배출 4열 행(버전이 먼저)의 slug 가 아직 entries 에 있다 = 충돌."""
        r = full(tmp)
        edit(r / "APPLIED.md", "| 9.9.9 | F-090-gone |", "| 9.9.9 | F-003-gamma |")
        rc, out = strict(r)
        assert rc == VIOLATION and "F-003: APPLIED slug 행 F-003-gamma" in out, f"⛔ 배출 4열 행 충돌을 놓쳤다 rc={rc}\n{out}"

    def c_strict_applied_absent_unrun(tmp):
        """⛔ APPLIED.md 부재는 '충돌 0' 이 아니라 미판정이다 — 위반이 없으면 UNRUN."""
        rc, out = strict(full(tmp, applied=False))
        assert rc == UNRUN and any(x.startswith("UNRUN:") for x in out.splitlines()), f"⛔ APPLIED 부재인데 rc={rc}\n{out}"

    def c_strict_eject_module_unrun(tmp):
        """⛔ 대장 판정기를 못 읽으면 그 축은 미판정이다 — 위반 0 으로 읽지 않는다."""
        g = globals()
        real = g["_eject_module"]

        def boom():
            raise ImportError("주입된 모듈 고장")

        g["_eject_module"] = boom
        try:
            rc, out = strict(full(tmp))
        finally:
            g["_eject_module"] = real
        assert rc == UNRUN and "UNRUN: APPLIED 대장 판정기" in out, f"⛔ 판정기 고장인데 rc={rc}\n{out}"

    def c_strict_dup_title(tmp):
        r = full(tmp)
        edit(r / "entries" / "F-003-gamma.md", "title: 제목 F-003-gamma", "title: 제목 F-001-alpha")
        rc, out = strict(r)
        assert rc == VIOLATION and "title 중복(frontmatter): 1" in out, f"⛔ title 중복을 놓쳤다 rc={rc}\n{out}"

    def c_strict_dup_h1(tmp):
        r = full(tmp)
        edit(r / "entries" / "F-003-gamma.md", "# F-003 — 머리 F-003-gamma", "# F-003 · 머리 F-002-beta")
        rc, out = strict(r)
        assert rc == VIOLATION and "H1 중복(번호 접두 제거): 1" in out, f"⛔ H1 중복을 놓쳤다 rc={rc}\n{out}"

    def c_strict_dup_body(tmp):
        """⛔ 본문 밀림(제목·H1 은 다르고 본문이 남의 것) — archive 짝도 본다."""
        r = full(tmp)
        (r / "entries" / "F-003-gamma.md").write_text(
            entry_text("F-003-gamma", "제목 F-003-gamma", "머리 F-003-gamma", body("F-090-gone")), encoding="utf-8")
        rc, out = strict(r)
        assert rc == VIOLATION and "본문 근접 중복(4-gram 포함도 ≥0.8): 1" in out, f"⛔ 본문 중복을 놓쳤다 rc={rc}\n{out}"

    def c_strict_dump(tmp):
        """⛔ 회귀(F-022 형): 펜스 밖 INDEX 덤프 잔재 — 펜스 안 같은 줄은 정상 대조가 통과시킨다."""
        r = full(tmp)
        edit(r / "entries" / "F-002-beta.md", "끝\n", "끝\n=== INDEX 구조 ===\n12:| F-003 | x |\n")
        rc, out = strict(r)
        assert rc == VIOLATION and "펜스 밖 INDEX 덤프(^=== · ^NN:| F-NNN): 1" in out, f"⛔ 덤프 잔재를 놓쳤다 rc={rc}\n{out}"

    def c_strict_archive_bad_utf8_unrun(tmp):
        """⛔ --strict 가 읽는 archive 본문의 디코딩 실패도 UNRUN 이다 (엔트리·INDEX 와 같은 규칙)."""
        r = full(tmp)
        (r / ".archive" / "F-090-gone.md").write_bytes(b"---\nstatus: open\n---\n\xff\xfe")
        rc, out = strict(r)
        assert rc == UNRUN, f"⛔ archive 디코딩 실패인데 rc={rc}\n{out}"

    def c_strict_violation_dominates(tmp):
        """⛔ 미판정 축이 있어도 이미 본 위반은 위반이다 — UNRUN 으로 낮추지 않는다."""
        r = full(tmp, applied=False)
        edit(r / "entries" / "F-003-gamma.md", "title: 제목 F-003-gamma", "title: 제목 F-001-alpha")
        rc, out = strict(r)
        assert rc == VIOLATION, f"⛔ 위반이 있는데 rc={rc}\n{out}"

    def c_strict_violation_beats_unreadable(tmp):
        """⛔ 회귀: strict 축의 읽기 실패(archive 본문 디코딩)가 이미 본 기본 위반을 UNRUN 으로 덮지 않는다."""
        r = full(tmp)
        edit(r / "entries" / "F-003-gamma.md", "status: open", "status: resolved")
        (r / ".archive").mkdir(exist_ok=True)
        (r / ".archive" / "F-090-gone.md").write_bytes(b"---\nstatus: open\n---\n\xff\xfe")
        rc, out = strict(r)
        assert rc == VIOLATION, f"⛔ 기본 위반 + archive 디코딩 실패인데 rc={rc}\n{out}"
        assert "UNRUN" not in out.splitlines()[-1], f"⛔ 마지막 판정 줄이 UNRUN 이다\n{out}"

    def c_queue_rows_contract(tmp):
        """⛔ 계약: `IDX_ROW` 는 문서 전체 표 행(배출이 빌려 쓴다) · `queue_rows` 는 대기열 절 · 펜스 밖만."""
        t = ("# I\n\n## 대기열\n\n| F-001 | a |\n### 하위\n| F-002 | b |\n\n## 재번호 이력\n\n| F-003 | c |\n"
             "\n## 다음 ID\n\n```\n## 대기열\n| F-004 | 펜스 |\n```\n")
        assert IDX_ROW.findall(t) == ["F-001", "F-002", "F-003", "F-004"], f"IDX_ROW 뜻이 바뀌었다 {IDX_ROW.findall(t)}"
        assert queue_rows(t) == ["F-001", "F-002"], f"queue_rows={queue_rows(t)}"

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

    for n, f in [("strict-clean-ok", c_strict_clean), ("strict-out-of-queue-row", c_strict_out_of_queue),
                 ("strict-queue-heading-missing", c_strict_queue_heading_missing),
                 ("strict-orphan-outside-queue", c_strict_orphan_outside_queue),
                 ("strict-applied-legacy-conflict", c_strict_applied_legacy),
                 ("strict-applied-eject-row-conflict", c_strict_applied_eject_row),
                 ("strict-applied-absent-unrun", c_strict_applied_absent_unrun),
                 ("strict-eject-module-unrun", c_strict_eject_module_unrun),
                 ("strict-dup-title", c_strict_dup_title), ("strict-dup-h1", c_strict_dup_h1),
                 ("strict-dup-body", c_strict_dup_body), ("strict-dump-outside-fence", c_strict_dump),
                 ("strict-archive-bad-utf8-unrun", c_strict_archive_bad_utf8_unrun),
                 ("strict-violation-dominates-unjudged", c_strict_violation_dominates),
                 ("strict-violation-beats-unreadable", c_strict_violation_beats_unreadable),
                 ("queue-rows-contract", c_queue_rows_contract)]:
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
