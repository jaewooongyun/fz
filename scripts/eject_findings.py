#!/usr/bin/env python3
"""릴리즈 노트의 `Closes:` 를 읽어 fz-findings 엔트리를 배출한다.

릴리즈가 finding 을 닫아도 레지스트리로 돌아오는 길이 없었다 — `docs/releases/` 네 문서에
`F-\\d{3}` 인용이 0건이었고, 그것이 배출률 5.8%(15/258)의 직접 원인이다.

배출 = `entries/{slug}.md` → `.archive/{slug}.md` 이동 + `APPLIED.md` 1행 추가 + `INDEX.md` 대기열 행 제거.
⛔ 삭제하지 않는다. 이동과 기록만 하며, 무엇을 닫았는지는 릴리즈 저자가 `Closes:` 로 적는다.
⛔ 셋은 한 번에 원자적으로 바뀌지 않는다 — 이동·대장은 manifest 선기록으로, INDEX 행은 실행 끝의
   재계산(`index_sync`)으로 같은 노트 재실행(또는 `--prune-index`)이 맞춘다. 남은 어긋남은 `--audit` 이 보여 준다.

exit 0  배출 성공 (또는 --audit 대조 일치 · 위생 검사 기본 모드 통과)
exit 1  거부 — 모호한 ID · 없는 엔트리 · 대장 불일치 · INDEX 정리 실패(읽은 뒤 바뀜 · 쓰기 실패 · 교체 뒤 대조 불일치) · --audit 의 위생 위반
exit 2  UNRUN — 레지스트리·릴리즈 노트 부재 · 레지스트리 잠금 대기 상한 초과 등 판정 불가. ⛔ 통과로 읽지 않는다
"""
# lint:no-root-anchor — 대상 레지스트리를 --root 인자로 받는 외부 검사기다
from __future__ import annotations

import argparse
import collections
import contextlib
import fcntl
import functools
import hashlib
import json
import math
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import time

OK, REJECT, UNRUN = 0, 1, 2
# ⛔ `\s*` 는 개행을 먹는다 — `Closes:` 다음 줄의 제목이 토큰으로 읽혔다(exit 1).
#    수평 공백만 허용해 **빈 선언**이 빈 선언으로 남게 한다 [외부: fz-gpt review #8].
CLOSES = re.compile(r"^Closes:[^\S\n]*(.*)$", re.M)
ID = re.compile(r"^F-\d{3}[a-z]?$")
SLUG = re.compile(r"^(F-\d{3}[a-z]?)-[a-z0-9-]+$")


def log(*a):
    print(*a, file=sys.stderr)


def parse_closes(note: pathlib.Path):
    """릴리즈 노트에서 Closes: 토큰을 뽑는다. 여러 줄·쉼표 구분 허용."""
    if not note.is_file():
        return None, f"릴리즈 노트 없음: {note}"
    toks = []
    for m in CLOSES.finditer(note.read_text(encoding="utf-8")):
        for t in re.split(r"[,\s]+", m.group(1).strip()):
            if t:
                toks.append(t)
    return toks, None


def index_entries(entries: pathlib.Path):
    """slug -> path, id -> [slug...] 두 색인. id 가 여럿이면 모호하다."""
    by_slug, by_id = {}, {}
    for p in sorted(entries.glob("*.md")):
        stem = p.stem
        m = SLUG.match(stem)
        if not m:
            continue
        by_slug[stem] = p
        by_id.setdefault(m.group(1), []).append(stem)
    return by_slug, by_id


# resolve 실패 종류 — ⛔ AMBIGUOUS 는 "이미 배출됨" 으로 skip 할 수 없다.
# 모호한 ID 는 어느 파일을 가리키는지 모르므로 대장에 같은 번호가 있어도 안전하지 않다.
NOT_FOUND, AMBIGUOUS, MALFORMED = "not_found", "ambiguous", "malformed"


def resolve(tok, by_slug, by_id):
    """토큰 하나를 slug 로 확정한다. 반환 (slug, kind, message)."""
    if tok in by_slug:
        return tok, None, None
    # ⛔ slug 형식인데 entries 에 없다 = 이미 배출됐을 수 있다(NOT_FOUND).
    # 이 분기가 없으면 full slug 로 적은 Closes: 가 재실행에서 MALFORMED 로 떨어져 거부된다.
    if SLUG.match(tok):
        return None, NOT_FOUND, f"{tok}: 엔트리 없음 (이미 배출됐거나 오타)"
    if ID.match(tok):
        cands = by_id.get(tok, [])
        if len(cands) == 1:
            return cands[0], None, None
        if not cands:
            return None, NOT_FOUND, f"{tok}: 엔트리 없음 (이미 배출됐거나 오타)"
        return None, AMBIGUOUS, f"{tok}: ID 가 {len(cands)}개 파일에 걸려 모호하다 — full slug 로 적어라: {', '.join(cands)}"
    return None, MALFORMED, f"{tok}: slug 도 ID 도 아니다"


# 대장 표 행: `| <무엇> | F-xxx | ...` 또는 `| F-xxx | ...` — ⛔ 산문 속 언급은 제외한다.
# APPLIED.md 본문에는 "F-032 이 지적한 홀" 같은 설명 문장이 있고, 그것을 배출 기록으로
# 읽으면 아직 큐에 있는 엔트리가 "이미 배출됨" 으로 조용히 skip 된다 (실측 오탐 1건).
ROW_ID = re.compile(r"^\|[^|\n]*\|\s*\*{0,2}(F-\d{3}[a-z]?)\*{0,2}[^|\n]*\|", re.M)
ROW_ID_FIRST = re.compile(r"^\|\s*\*{0,2}(F-\d{3}[a-z]?)\*{0,2}[^|\n]*\|", re.M)


ROW_SLUG = re.compile(r"^\|[^|\n]*\|\s*\*{0,2}(F-\d{3}[a-z]?-[a-z0-9-]+)\*{0,2}[^|\n]*\|", re.M)
ROW_SLUG_FIRST = re.compile(r"^\|\s*\*{0,2}(F-\d{3}[a-z]?-[a-z0-9-]+)\*{0,2}[^|\n]*\|", re.M)


def applied_records(applied: pathlib.Path):
    """APPLIED.md 대장의 **표 행**에서 (full slug 집합, **번호만 적힌** 행의 번호 집합) 을 읽는다.

    ⛔ 번호 집합은 slug 행에서 파생시키지 않는다 — `F-032-one` 행의 번호 `F-032` 를 번호 집합에
    넣으면 그것이 **레거시 번호 행처럼 보여서** `F-032-two` 까지 배출된 것으로 읽힌다
    (2차 검증에서 audit 이 실제로 통과시켰다). 행 단위로 갈라야 한다(규약 8).

    산문 언급은 제외한다 — APPLIED 본문의 "F-032 이 지적한 홀" 같은 문장을 배출 기록으로
    읽으면 아직 큐에 있는 엔트리가 조용히 skip 된다 (실측 오탐 1건).
    """
    if not applied.is_file():
        return set(), set()
    slugs, nums_only = set(), set()
    for line in applied.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        row = line + "\n"
        got_slug = set(ROW_SLUG.findall(row)) | set(ROW_SLUG_FIRST.findall(row))
        if got_slug:
            slugs |= got_slug
            continue                      # 이 행은 slug 를 밝혔다 — 번호 집합에 넣지 않는다
        nums_only |= set(ROW_ID.findall(row)) | set(ROW_ID_FIRST.findall(row))
    return slugs, nums_only


def archive_slugs(archive: pathlib.Path):
    """archive 에 실재하는 엔트리 slug 집합.

    ⛔ `glob` 은 권한 없는 디렉토리에서 **예외 없이 빈 목록**을 낸다(실측 Python 3.9.6).
    빈 archive 와 못 읽는 archive 를 구별하지 못하면 "배출 안 됐다" 로 오판한다.
    """
    if not archive.is_dir():
        return set()
    return {q.stem for q in archive.iterdir() if q.suffix == ".md"}


def ejected_slug(tok, ap_slugs, ap_nums, arc):
    """토큰이 **이미 배출됐다면** 그 full slug, 아니면 None.

    ⛔ 판정은 **번호별**로 한다. 전역 플래그(`archive 디렉토리가 있는가`)로 레거시 여부를
    정하면 두 방향으로 다 틀린다 — 빈 디렉토리가 생기면 멀쩡한 레거시 기록이 거부되고,
    배출 후 archive 를 비우면 거꾸로 레거시로 오인된다(둘 다 실측)
    [외부: fz-gpt validate r3·r4].

    ⛔ full slug 경로와 번호 경로는 **같은 답**을 내야 한다. 갈리면 같은 배출을 한쪽은 skip,
    한쪽은 거부한다.

    번호 `N` 에 대한 archive 후보 수로 갈린다.
    - 후보 **1개** : 그 slug 가 배출분이다 (두 경로 모두 그것을 돌려준다)
    - 후보 **0개** : archive 도입 이전에 삭제된 레거시다 — 대장 기록만으로 인정
    - 후보 **2개+**: 어느 것인지 모른다 — 배출됨으로 치지 않는다(거부 경로로)
    """
    m = SLUG.match(tok)
    num = m.group(1) if m else (tok if ID.match(tok) else None)
    if num is None:
        return None
    cands = sorted(x for x in arc if x.startswith(num + "-"))
    if len(cands) > 1:
        return None                       # 같은 번호의 archive 파일이 여럿 — 판정 불가
    if m:                                 # full slug 토큰
        if tok in ap_slugs:
            # 후보가 있으면 그것과 일치해야 한다. 없으면 레거시 삭제로 본다.
            return tok if (not cands or cands[0] == tok) else None
        if num in ap_nums:                # 번호만 적힌 레거시 행
            return tok if (not cands or cands[0] == tok) else None
        return None
    # 번호 토큰
    same = sorted(x for x in ap_slugs if x.startswith(num + "-"))
    if len(same) > 1:
        return None                       # 대장에 같은 번호 full slug 가 여럿 — 모호
    if len(same) == 1:
        return same[0] if (not cands or cands[0] == same[0]) else None
    if num in ap_nums:
        return cands[0] if cands else num
    return None


MANI_NAME = ".eject-manifest.json"


def write_manifest(mani: pathlib.Path, hist):
    """⛔ **원자 교체**로 쓴다. 직접 쓰면 중간에 끊겼을 때 *기존 이력까지* 손상된다
    (2차 검증에서 잘림 주입으로 재현됐다) [외부: fz-gpt validate r2 #1].
    """
    tmp = mani.with_name(mani.name + ".tmp")
    try:
        tmp.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, mani)
    except BaseException:
        # ⛔ 실패하면 잘린 .tmp 를 남기지 않는다 — 남으면 다음 사람이 그것을 원장으로 착각한다
        tmp.unlink(missing_ok=True)
        raise


LOCK_NAME = ".fz-registry.lock"
LOCK_WAIT_ENV = "FZ_REGISTRY_LOCK_WAIT"
LOCK_WAIT_DEFAULT = 30.0


@contextlib.contextmanager
def registry_lock(root: pathlib.Path):
    """협조 writer 끼리의 배타 구간 — `{root}/.fz-registry.lock` 에 `fcntl.flock(LOCK_EX)` 를 상한 안에서 재시도한다.

    ⛔ 잠금은 **프로세스가 쥔다** — 프로세스가 끝나면(SIGKILL 포함) 커널이 푼다. 그래서 이 파일은 지우지
       않고, 파일이 있다는 것을 잠김으로 읽지 않는다. 존재로 판정하는 잠금 파일은 보유자가 강제 종료되면
       그대로 남아 다음 writer 를 영영 막는다.
    ⛔ 같은 규칙을 따르는 writer(이 스크립트 · 이 파일에 flock 을 잡는 도구)끼리만 막는다. 에디터 Edit ·
       `cat >` 처럼 잠금을 모르는 쓰기는 막지 못한다 — INDEX 는 교체 직전 재확인만 한다(`index_sync`).

    yield: 잡았으면 True. 상한(`FZ_REGISTRY_LOCK_WAIT` 초, 기본 30)을 넘기거나 파일을 못 열면 False.
    """
    raw = os.environ.get(LOCK_WAIT_ENV, "")
    try:
        wait = float(raw) if raw else LOCK_WAIT_DEFAULT
    except ValueError:
        wait = None
    # ⛔ float() 는 'nan' · 'inf' 를 받아들인다 — 그러면 마감이 영영 오지 않아 '상한 안 재시도' 가 무한 대기가 된다
    if wait is None or not math.isfinite(wait) or wait < 0:
        log(f"UNRUN: {LOCK_WAIT_ENV}={raw!r} 는 0 이상의 유한한 초가 아니다 — 아무것도 바꾸지 않았다")
        yield False
        return
    path = root / LOCK_NAME
    try:
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as e:
        log(f"UNRUN: 레지스트리 잠금 파일을 열 수 없다 — {path}: {e} (아무것도 바꾸지 않았다)")
        yield False
        return
    try:
        deadline = time.monotonic() + wait
        got = False
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                got = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    break
            time.sleep(0.1)
        if not got:
            log(f"UNRUN: 레지스트리 잠금을 {wait:g}초 안에 얻지 못했다 — 다른 협조 writer 가 쓰는 중이다 ({path}). "
                "아무것도 바꾸지 않았다. ⛔ 잠금 파일을 지우지 마라 — 파일이 있는 것은 잠김이 아니고, "
                "보유자가 끝나면 커널이 푼다")
        yield got
    finally:
        os.close(fd)                      # 닫으면 flock 이 풀린다 — 파일은 남긴다


INDEX_NAME = "INDEX.md"
# INDEX 행이 가리키는 엔트리 — `](entries/<slug>.md)` 와 `](./entries/<slug>.md)` 는 같은 파일이다.
INDEX_LINK = re.compile(r"\]\((\./)?entries/([^)\s/]+)\.md\)")
TEST_HOOK_ENV = "FZ_REGISTRY_TEST_HOOK"


@functools.lru_cache(maxsize=None)
def _hygiene_module():
    """`check_findings_hygiene.py` 를 importlib 로 읽는다 — 행 규칙(`IDX_ROW`)과 `--audit` 의 위생 검사(`check`)가 쓴다.

    ⛔ 모듈 최상위에서 import 하지 않는다 — 위생 검사도 이 파일을 importlib 로 읽어서(`applied_records`) 양쪽이
       최상위에서 서로를 부르면 순환이 된다. 쓰는 순간에만 올린다.
    """
    import importlib.util
    path = pathlib.Path(__file__).resolve().parent / "check_findings_hygiene.py"
    spec = importlib.util.spec_from_file_location("fz_findings_hygiene", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@functools.lru_cache(maxsize=None)
def _queue_row():
    """INDEX 대기열 행 판정 정규식 — `check_findings_hygiene.py` 의 `IDX_ROW` 를 그대로 빌린다.

    ⛔ 행 규칙을 여기서 다시 짜지 않는다. 위생 검사가 '등재' 로 세는 행과 배출이 지우는 행이 갈리면
       한쪽이 지운 행을 다른 쪽이 고아로 세거나, 지우지 않은 행을 등재로 센다.
    ⛔ 절을 가리지 않고 문서 전체에 쓴다 — 위생 검사의 등재(`queue_rows`, `## 대기열` 절만)보다 넓은 것이
       의도다. 절 밖에 잘못 붙은 행(위생 검사의 `대기열 밖` 위반)도 배출되면 고아이고, 좁히면 `--prune-index` 가 못 지운다.
    """
    return _hygiene_module().IDX_ROW


def _test_hook(point: str, idx: pathlib.Path):
    """⛔ 시험 전용 틈 — `FZ_REGISTRY_TEST_HOOK` 이 비어 있으면 아무것도 하지 않는다(운영 경로 무동작).

    값은 명령(shlex 분할)이고 `<지점> <INDEX 경로>` 를 덧붙여 실행한다. 지점:
      read     — 처음 읽은 뒤 · 교체 직전 재확인 전 (읽기~교체 사이 변경 재현)
      replace  — 재확인 뒤 · os.replace 직전, 잠금을 쥔 채 (협조 writer 가 기다리는지 재현)
      replaced — 교체 뒤 · 비대상 행 대조 전 (대조 실패와 백업 경로 재현)
    소비자: tests/fixtures/registry/eject-index/run.sh
    """
    cmd = os.environ.get(TEST_HOOK_ENV, "")
    if cmd:
        # ⛔ env 가 셸에 남아 있으면 운영 경로에서도 돈다 — 돌 때마다 알린다(조용히 임의 명령을 실행하지 않는다)
        log(f"WARN: {TEST_HOOK_ENV} 활성 — 시험 전용 훅을 '{point}' 지점에서 실행한다")
        subprocess.run(shlex.split(cmd) + [point, str(idx)], check=False)


def _row_counter(text: str):
    """표 행(`|` 로 시작하는 줄)의 다중집합."""
    return collections.Counter(line.rstrip("\r") for line in text.split("\n") if line.startswith("|"))


def _index_plan(text: str, targets: set, live_ids: set):
    """INDEX 본문을 (남길 본문, 지울 행 [(slug, 줄)], WARN 목록) 으로 가른다.

    지울 행 = 대기열 행(위생 검사 `IDX_ROW`)이면서 **full slug 링크**가 targets 의 slug 를 가리키고
    그 slug 의 번호가 행 ID 와 같은 것.
    ⛔ ID 만으로 지우지 않는다 — 같은 번호를 다른 slug 가 쓰고 있을 수 있다(현재 수는 위생 검사의 `중복 ID` 줄).
    ⛔ 못 지운 의심 행을 말없이 넘기지 않는다 — archive slug 를 가리키는데 행 ID 가 다르거나, 행 ID 가
       live 에는 없고 archive 에만 있는데 링크가 다른 slug(옛 이름 · 오타)면 WARN 으로 남긴다.
    """
    row_re = _queue_row()
    tids = {SLUG.match(s).group(1) for s in targets}
    keep, removed, warns = [], [], []
    for line in text.splitlines(keepends=True):
        m = row_re.match(line)
        if not m:
            keep.append(line)
            continue
        rid = m.group(1)
        links = INDEX_LINK.findall(line)
        hit = [s for _, s in links if s in targets and SLUG.match(s).group(1) == rid]
        if hit:
            removed.append((hit[0], line.rstrip("\r\n")))
            if any(dot for dot, s in links if s == hit[0]):
                warns.append(f"{rid}: `./entries/` 형태 링크 — 같은 파일로 보고 지웠다 ({hit[0]})")
            continue
        keep.append(line)
        stale = sorted({s for _, s in links if s in targets})
        if stale or (rid not in live_ids and rid in tids):
            arc_same = sorted(s for s in targets if s.startswith(rid + "-")) or stale
            got = ", ".join(s for _, s in links) or "링크 없음"
            warns.append(f"{rid}: slug 변형 의심 — 지우지 않았다 (행 링크 {got} · archive {', '.join(arc_same)})")
    return "".join(keep), removed, warns


def _live(root: pathlib.Path):
    """entries 의 (slug 집합, 번호 집합)."""
    ent = root / "entries"
    slugs = {q.stem for q in ent.iterdir() if q.suffix == ".md" and SLUG.match(q.stem)} if ent.is_dir() else set()
    return slugs, {SLUG.match(s).group(1) for s in slugs}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def index_sync(root: pathlib.Path, slugs) -> int:
    """INDEX.md 에서 **archive 에 있는 slug** 의 대기열 행을 0 으로 다시 계산한다 — 배출·복구·정리의 공통 끝 단계.

    호출자(잠금을 쥔 채): eject(이번 실행이 옮긴 것 · 이미 배출돼 skip 한 것 · reconcile 이 복구한 것) ·
    `--resolve-pending`(확정한 레코드의 archive 분) · `--prune-index`(archive 전부 − keep).
    ⛔ 대상은 넘겨받은 slug 중 **실제로 archive 에 있고 entries 에 없는 것**뿐이다 — 넘겨받았다는 것만으로
       지우지 않는다. 이동이 실패한 slug 의 행을 지우면 live 엔트리가 색인에서 사라진다.
    ⛔ 원자적 비교-교체가 아니다. 순서: 읽기·해시 → 새 본문을 `.tmp` 에 → **교체 직전 재읽기** 해시가 다르면
       교체하지 않고 거부 → `os.replace` → 다시 읽어 비대상 행 다중집합 대조. 재확인과 교체 사이에 잠금
       없는 쓰기(에디터 Edit 등)가 끼면 그 쓰기는 잃는다 — 보장 밖이다. 교체 뒤 대조는 경합 탐지가 아니라
       이 변환이 비대상 행을 건드리지 않았는지의 검산이다(다르면 원본을 백업하고 경로를 알린다).
    ⛔ 지울 행이 0 이면 파일을 다시 쓰지 않는다 — 재실행은 바이트·mtime 을 바꾸지 않는다.
    ⛔ INDEX 가 없으면 배출을 막지 않고 NOTE 만 남긴다 — 잘못된 루트를 조용히 넘기지 않도록 경로를 찍는다.
    """
    idx = root / INDEX_NAME
    if not idx.is_file():
        print(f"NOTE: {INDEX_NAME} 없음 — 대기열 행 정리를 건너뛴다 ({idx}) · ⛔ 레지스트리 루트가 맞는지 확인하라")
        return OK
    try:
        raw0 = idx.read_bytes()
        text0 = raw0.decode("utf-8")
        arc = archive_slugs(root / ".archive")
        live, live_ids = _live(root)
        targets = {s for s in set(slugs) & arc if SLUG.match(s)} - live
        new_text, removed, warns = _index_plan(text0, targets, live_ids)
    except (OSError, UnicodeDecodeError, AttributeError) as e:
        log(f"UNRUN: {INDEX_NAME} 대기열 행을 판정하지 못했다 — {type(e).__name__}: {e} (INDEX 는 그대로다)")
        return UNRUN
    for w in warns:
        print(f"  WARN   {w}")
    _test_hook("read", idx)
    if not removed:
        print(f"{INDEX_NAME} -0행 (archive slug 의 대기열 행 재계산 — 지울 행 없음)")
        return OK
    tmp = idx.with_name(idx.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
        shutil.copymode(idx, tmp)
    except OSError as e:
        if tmp.is_file():
            tmp.unlink()
        log(f"REJECT: {INDEX_NAME} 정리 실패 — {type(e).__name__}: {e} (원본 그대로 · 이동·대장 기록은 남았다 — "
            f"다시 실행하거나 `--prune-index {root}` 로 맞춘다)")
        return REJECT
    if _sha(idx.read_bytes()) != _sha(raw0):
        tmp.unlink()
        log(f"REJECT: {INDEX_NAME} 가 읽은 뒤 바뀌었다 — 교체하지 않았다 (잠금 밖 writer). "
            "다시 실행하면 바뀐 내용 기준으로 다시 계산한다")
        return REJECT
    _test_hook("replace", idx)
    try:
        os.replace(tmp, idx)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        log(f"REJECT: {INDEX_NAME} 교체 실패 — {type(e).__name__}: {e} (원본 그대로)")
        return REJECT
    _test_hook("replaced", idx)
    after = idx.read_bytes().decode("utf-8", errors="replace")
    want = _row_counter(text0) - collections.Counter(line for _, line in removed)
    if _row_counter(after) != want:
        bak = root / f"{INDEX_NAME}.bak-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
        try:
            bak.write_bytes(raw0)
            where = f"원본 백업: {bak}"
        except OSError as e:
            where = f"⛔ 원본 백업도 실패했다 — {e}"
        log(f"REJECT: 교체 뒤 {INDEX_NAME} 의 비대상 행이 지운 행만큼만 달라지지 않았다 — {where}")
        return REJECT
    print(f"{INDEX_NAME} -{len(removed)}행 (archive slug 의 대기열 행 재계산)")
    for slug, _ in removed:
        print(f"  INDEX  -  {slug}")
    print("NOTE: 잠금은 협조 writer 끼리만 막는다 — 잠금 없이 INDEX 를 고친 쓰기(에디터 Edit 등)는 교체 직전 "
          "재확인 뒤로는 보장되지 않는다. 레지스트리 정리 중에는 다른 세션이 쓰지 않는다(README §1)")
    return OK


def reconcile(root: pathlib.Path, hist, applied: pathlib.Path, mani: pathlib.Path, landed_out: set | None = None):
    """중단된 배출(`state: pending`)을 재실행에서 **복구**한다.

    ⛔ 이동은 됐는데 대장·manifest 기록 전에 끊기면, 이전 판은 그 상태를 영영 복구하지 못했다 —
    재실행은 "엔트리 없음" 으로 거부하고 audit 은 manifest 에 기록이 없어 0 을 냈다
    [외부: fz-gpt validate r2 #1]. 그래서 **이동 전에 계획을 먼저 적는다**(선기록).

    복구 규칙: pending 레코드의 계획 slug 중 archive 에 실재하고 대장에 없는 것을 대장에 적고,
    레코드를 done 으로 확정한다. 이미 적힌 것은 건드리지 않는다(멱등).
    landed_out: archive 에 도착한 slug 를 모은다 — 호출자(eject)가 마지막 `index_sync` 에 넘겨
    INDEX 대기열 행을 지운다(대장만 복구하고 INDEX 행을 남기면 고아가 된다).
    """
    pend = [r for r in hist if r.get("state") == "pending"]
    if not pend:
        return hist, 0, []
    arc = archive_slugs(root / ".archive")
    ap_slugs, _ = applied_records(applied)
    ent_have = {q.stem for q in (root / "entries").iterdir() if q.suffix == ".md"} \
        if (root / "entries").is_dir() else set()
    fixed, unresolved = 0, []
    for rec in pend:
        planned = rec.get("planned", [])
        landed = [x for x in planned if x in arc]
        if landed_out is not None:
            landed_out.update(landed)
        add = [x for x in landed if x not in ap_slugs]
        if add:
            rows = [f"| {rec.get('version', '?')} | {x} | `{rec.get('note', '?')}` | 중단 복구 |" for x in add]
            with applied.open("a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(rows) + "\n")
            print(f"  복구   중단된 배출 {len(add)}건을 대장에 기록: {', '.join(add)}")
            fixed += len(add)
            # ⛔ 루프 안에서 갱신한다 — 안 하면 같은 slug 를 담은 pending 이 둘일 때 **두 번 적힌다**
            ap_slugs = ap_slugs | set(add)
        # ⛔ **확인된 것만 확정한다.** planned 중 archive 에도 entries 에도 없는 것이 있으면
        #    이 배출은 아직 설명되지 않았다 — done 으로 덮으면 증거가 사라져 영영 복구 못 한다
        #    (실측: archive 열거가 비면 ejected=[] 인 채 done 이 됐다) [외부: fz-gpt validate r3].
        missing = [x for x in planned if x not in arc and x not in ent_have]
        if missing:
            unresolved.append(f"{rec.get('version', '?')}: {', '.join(missing)}")
            continue                      # pending 유지
        rec["state"] = "done"
        rec["ejected"] = landed
    write_manifest(mani, hist)
    if unresolved:
        log("REJECT: 중단된 배출을 설명하지 못했다 — archive 에도 entries 에도 없다: "
            + " · ".join(unresolved) + " (pending 유지)")
        log("   ⛔ 이 상태에서는 새 배출도 막힌다. 파일이 실제로 유실됐다면 "
            "`--resolve-pending` 으로 **사람이 명시적으로** 손실을 확정하라 (자동 무시하지 않는다)")
    return hist, fixed, unresolved


def resolve_pending(root: pathlib.Path):
    """⛔ 설명되지 않은 중단을 **사람의 판정으로** 닫는다 — 잠금을 쥐고 본체(`_resolve_pending`)를 돌린 뒤
    확정한 레코드의 archive 분 INDEX 대기열 행을 지운다(`index_sync`)."""
    # ⛔ 잠금 파일은 manifest 가 있는 레지스트리 루트에만 만든다 — 잘못된 루트에 흔적을 남기지 않는다
    if not (root / MANI_NAME).is_file():
        return _resolve_pending(root, set())
    landed: set = set()
    with registry_lock(root) as held:
        if not held:
            return UNRUN
        rc = _resolve_pending(root, landed)
        if rc != OK:
            return rc
        return index_sync(root, landed)


def _resolve_pending(root: pathlib.Path, landed_out: set):
    """⛔ 설명되지 않은 중단을 **사람의 판정으로** 닫는다.

    보수적 reconcile 은 planned 를 설명하지 못하면 pending 을 유지하고 모든 배출을 막는다 —
    그것이 안전하지만, 파일이 실제로 유실됐다면 **영구 교착**이 된다(실측 확인).
    자동으로 풀지 않는 이유: 유실 판정은 사람만 할 수 있고, 조용히 넘기면 증거가 사라진다.
    닫을 때도 지우지 않고 `lost` 로 **남긴다**.
    """
    mani = root / MANI_NAME
    if not mani.is_file():
        log(f"UNRUN: manifest 없음 — {mani}")
        return UNRUN
    try:
        hist = json.loads(mani.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log(f"UNRUN: manifest 를 읽을 수 없다 — {e}")
        return UNRUN
    arc = archive_slugs(root / ".archive")
    ent = {q.stem for q in (root / "entries").iterdir() if q.suffix == ".md"} \
        if (root / "entries").is_dir() else set()
    applied = root / "APPLIED.md"
    ap_slugs, _ = applied_records(applied)
    closed, recovered = 0, 0
    for rec in hist:
        if rec.get("state") != "pending":
            continue
        planned = rec.get("planned", [])
        landed = [x for x in planned if x in arc]
        # ⛔ 확정 **전에** 대장을 복구한다. 안 하면 파일은 archive 에 있고 대장엔 없는 채로
        #    done 이 찍혀 reconcile 이 다시 볼 일이 없어진다 — 고아가 영구화된다
        #    [외부: fz-gpt validate r4 major].
        add = [x for x in landed if x not in ap_slugs]
        if add:
            rows = [f"| {rec.get('version', '?')} | {x} | `{rec.get('note', '?')}` | 수동 확정 복구 |" for x in add]
            with applied.open("a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(rows) + "\n")
            ap_slugs = ap_slugs | set(add)
            recovered += len(add)
            print(f"  복구   대장 기록 {len(add)}건: {', '.join(add)}")
        landed_out.update(landed)
        rec["ejected"] = landed
        rec["lost"] = [x for x in planned if x not in arc and x not in ent]
        rec["state"] = "done"
        closed += 1
        print(f"  확정   {rec.get('version', '?')}: 배출 {rec['ejected']} · 유실 {rec['lost']}")
    if not closed:
        print("pending 레코드가 없다 — 할 일 없음")
        return OK
    write_manifest(mani, hist)
    print(f"pending {closed}건을 done 으로 확정했다 · 대장 복구 {recovered}건 (유실분은 `lost` 로 남는다)")
    return OK


def eject(root: pathlib.Path, note: pathlib.Path, version: str, dry: bool):
    """잠금을 쥐고 배출(`_eject`)한 뒤, 이번 실행이 건드린 slug 의 INDEX 대기열 행을 지운다(`index_sync`).

    ⛔ INDEX 정리는 **이번 실행분**(옮긴 것 · 이미 배출돼 skip 한 것 · reconcile 이 복구한 것)만이다.
       예전 배출분이 남긴 행은 `--prune-index` 가 맡는다 — 배출 하나가 무관한 행을 한꺼번에 지우지 않는다.
    ⛔ dry-run 은 읽기만 하므로 잠금도 INDEX 정리도 하지 않는다.
    """
    # ⛔ 잠금 파일은 레지스트리로 확인된 루트에만 만든다 — 잘못된 --root 에 흔적을 남기지 않는다
    if dry or not (root / "entries").is_dir():
        return _eject(root, note, version, dry, set())
    touched: set = set()
    with registry_lock(root) as held:
        if not held:
            return UNRUN
        rc = _eject(root, note, version, dry, touched)
        if rc == UNRUN or (rc == REJECT and not touched):
            return rc                     # 노트 부재 · 이동 전 거부 — 아무것도 바꾸지 않았다(INDEX 포함)
        rc_idx = index_sync(root, touched)
    return rc if rc != OK else rc_idx


def _eject(root: pathlib.Path, note: pathlib.Path, version: str, dry: bool, touched: set):
    entries, archive, applied = root / "entries", root / ".archive", root / "APPLIED.md"
    if not entries.is_dir():
        log(f"UNRUN: entries 디렉토리 없음 — {entries}")
        return UNRUN
    toks, err = parse_closes(note)
    if err:
        log(f"UNRUN: {err}")
        return UNRUN
    if not toks:
        log(f"UNRUN: `Closes:` 줄이 없다 — {note} (배출 대상 미지정)")
        return UNRUN

    # ⛔ 중단 복구를 **계획보다 먼저** 한다 — 복구가 대장을 바꾸므로 skip 판정의 입력이 달라진다.
    mani = root / MANI_NAME
    try:
        hist = json.loads(mani.read_text(encoding="utf-8")) if mani.is_file() else []
    except (json.JSONDecodeError, OSError) as e:
        log(f"REJECT: 기존 manifest 를 읽을 수 없다 — {e} (하나도 이동하지 않았다)")
        return REJECT
    if not isinstance(hist, list):
        log(f"REJECT: manifest 최상위가 배열이 아니다 — {mani} (하나도 이동하지 않았다)")
        return REJECT
    if not dry:
        hist, _, unresolved = reconcile(root, hist, applied, mani, landed_out=touched)
        if unresolved:
            touched.clear()      # ⛔ 거부는 전무 — INDEX 도 건드리지 않는다(README 규칙 2)
            return REJECT        # ⛔ 설명 안 된 중단 위에 새 배출을 얹지 않는다

    by_slug, by_id = index_entries(entries)
    ap_slugs, ap_nums = applied_records(applied)
    arc_have = archive_slugs(archive)
    mani_ejected = {x for r in hist for x in r.get("ejected", [])}
    plan, rejects, skipped, seen_tok = [], [], [], set()
    for t in toks:
        if t in seen_tok:            # ⛔ 같은 토큰 반복은 조용히 넘긴다 (중복 이동 방지)
            continue
        seen_tok.add(t)
        slug, kind, e = resolve(t, by_slug, by_id)
        if e:
            # ⛔ 모호·형식오류는 skip 하지 않는다 — 어느 파일인지 모르는 채 통과시키면 안 된다.
            if kind == NOT_FOUND:
                done = ejected_slug(t, ap_slugs, ap_nums, arc_have)
                if done:
                    note_ = ""
                    if done in mani_ejected and done not in arc_have:
                        # ⛔ 대장은 배출됐다고 하는데 archive 에 파일이 없다 — 상태 불일치다.
                        #    멱등을 위해 skip 하되 **말없이 넘기지 않는다**. 차단은 audit 소관.
                        # ⛔ manifest 가 배출했다고 기록한 것이 archive 에 없다 — 사람이 지웠거나 옮겼다
                        note_ = " ⚠️ manifest 는 배출됐다는데 archive 에 파일이 없다 — `--audit` 으로 확인하라"
                    skipped.append(f"{t}: 이미 배출됨 (대장 {done}){note_}")
                    if SLUG.match(done):
                        touched.add(done)      # 행이 남았으면 이번 실행 끝에 지운다(중단 뒤 재실행 복구)
                    continue
            rejects.append(e)
            continue
        if slug not in plan:
            plan.append(slug)

    print(f"대상 {len(toks)} · 배출 {len(plan)} · skip {len(skipped)} · 거부 {len(rejects)}")
    for s in skipped:
        print(f"  skip   {s}")
    for r in rejects:
        print(f"  거부   {r}")
    if rejects:
        log("REJECT: 모호하거나 없는 토큰이 있다 — 하나도 이동하지 않았다")
        touched.clear()
        return REJECT
    if dry:
        for s in plan:
            print(f"  (dry)  {s}")
        return OK

    if not plan:
        return OK            # ⛔ 옮길 게 없으면 archive 디렉토리조차 만들지 않는다 (위 arc_known 참조)
    archive.mkdir(exist_ok=True)
    # ⛔ **이동 전에 전건 검증한다** — 중간에 거부하면 앞선 파일은 이미 이동했는데 대장·manifest
    #    기록은 없어서 재실행도 "엔트리 없음" 으로 거부된다(원자성 파괴) [외부: fz-gpt review #1].
    conflicts = [s for s in plan if (archive / f"{s}.md").exists()]
    if conflicts:
        log(f"REJECT: archive 에 같은 이름이 이미 있다 — {', '.join(conflicts)} (하나도 이동하지 않았다)")
        touched.clear()
        return REJECT
    # ⛔ **선기록**: 옮기기 전에 계획을 manifest 에 pending 으로 적는다. 이동 뒤 기록 전에
    #    끊겨도 다음 실행의 reconcile() 이 이 레코드를 보고 복구한다 [외부: fz-gpt validate r2 #1].
    rec = {"version": version, "note": note.name, "planned": list(plan), "state": "pending", "ejected": []}
    hist.append(rec)
    write_manifest(mani, hist)
    moved, move_err = [], None
    for slug in plan:
        src, dst = by_slug[slug], archive / f"{slug}.md"
        try:
            shutil.move(str(src), str(dst))
        except OSError as e:
            # ⛔ 여기서 멈추고 **성공을 반환하지 않는다**. 이전 판은 break 후 OK 를 냈고,
            #    그래서 "절반만 배출" 이 조용히 통과했다 — 게다가 이 삼킴이 중복 이동 오류까지
            #    가려서 duplicate-token fixture 를 헛돌게 만들었다 [외부: fz-gpt validate #1].
            move_err = f"{slug}: {e}"
            log(f"⛔ 이동 실패 {move_err} — 이미 이동한 {len(moved)}건은 기록에 남긴다")
            break
        moved.append(slug)
        print(f"  이동   {slug}")
    touched.update(moved)

    # ⛔ full slug 로 적는다 — 번호만 적으면 같은 번호의 다른 slug 와 구분되지 않는다(#3)
    rows = [f"| {version} | {s} | `{note.name}` | 릴리즈 `Closes:` 로 배출 |" for s in moved]
    if rows:
        with applied.open("a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(rows) + "\n")
        print(f"APPLIED.md +{len(rows)}행")
    # ⛔ 선기록한 레코드를 **확정**한다 (append 가 아니다 — append 하면 pending 이 영원히 남는다)
    rec["state"] = "done"
    rec["ejected"] = moved
    write_manifest(mani, hist)
    if move_err:
        # ⛔ 기록은 남겼다(복구 가능). 그러나 계획한 전부를 옮기지 못했으므로 **성공이 아니다**.
        log(f"REJECT: 이동 중단 — 계획 {len(plan)} 중 {len(moved)}건만 배출됐다 ({move_err}). "
            f"`--audit {root}` 로 대장·archive 정합을 확인하라")
        return REJECT
    return OK


def prune_index(root: pathlib.Path, keep=frozenset()):
    """`--prune-index ROOT` — archive 에 있는 slug **전부**의 INDEX 대기열 행을 0 으로 다시 계산한다(일괄 정리).

    맡는 것: INDEX 를 지우기 전의 배출분 · 중단된 정리. 수동 기각·흡수는 `entries/` 에서 지우므로(archive 없음)
    대상이 아니다 — 그 행은 손으로 지운다(레지스트리 README §1).
    keep: 지우지 않을 ID 또는 full slug(결정 대기 엔트리처럼 행을 남겨야 하는 것).
    ⛔ INDEX.md 만 바꾼다 — manifest·APPLIED·엔트리는 건드리지 않는다.
    ⛔ 이 명령의 일이 INDEX 뿐이라 INDEX 가 없으면 UNRUN 이다(배출의 NOTE 와 다르다 — 잘못된 루트 의심).
    """
    if not (root / "entries").is_dir():
        log(f"UNRUN: entries 디렉토리 없음 — {root / 'entries'} (레지스트리 루트가 아니다)")
        return UNRUN
    if not (root / INDEX_NAME).is_file():
        log(f"UNRUN: {INDEX_NAME} 없음 — {root / INDEX_NAME} (정리할 대상이 없다 · 루트 확인)")
        return UNRUN
    with registry_lock(root) as held:
        if not held:
            return UNRUN
        arc = archive_slugs(root / ".archive")
        kept = sorted(s for s in arc if s in keep or (SLUG.match(s) and SLUG.match(s).group(1) in keep))
        # ⛔ archive 와 하나도 맞지 않는 keep 토큰(오타 · 형식 틀림)은 남기려던 행을 지운다 — 바꾸기 전에 멈춘다
        hit = set(kept) | {SLUG.match(s).group(1) for s in kept if SLUG.match(s)}
        miss = sorted(k for k in keep if k not in hit)
        if miss:
            log(f"UNRUN: --keep 토큰이 archive 의 어느 엔트리와도 맞지 않는다 — {', '.join(miss)} "
                "(ID F-NNN 또는 full slug · 아무것도 바꾸지 않았다)")
            return UNRUN
        for s in kept:
            print(f"  keep   {s} (지우지 않는다)")
        return index_sync(root, arc - set(kept))


def index_residual(root: pathlib.Path, slugs):
    """읽기 전용 — slugs 중 entries 에 없는 것의 INDEX 대기열 행이 남았는가. 반환 (잔존 [(slug, 줄)], WARN, 대조 불가 사유)."""
    idx = root / INDEX_NAME
    if not idx.is_file():
        return [], [], f"{INDEX_NAME} 없음 ({idx})"
    try:
        live, live_ids = _live(root)
        targets = {s for s in slugs if SLUG.match(s)} - live
        _, residual, warns = _index_plan(idx.read_text(encoding="utf-8"), targets, live_ids)
    except (OSError, UnicodeDecodeError, AttributeError) as e:
        return [], [], f"{INDEX_NAME} 대기열 행을 판정하지 못했다 — {type(e).__name__}: {e}"
    return residual, warns, None


def audit(root: pathlib.Path, mani_path: pathlib.Path):
    """A3 verify — manifest 의 배출 ID 집합이 APPLIED 에 전건 있는지 대조 + 배출분·archive 의 INDEX 대기열 잔존 대조.

    ⛔ INDEX 잔존은 **보고만** 하고 exit 를 바꾸지 않는다 — INDEX 를 지우기 전의 배출분(레거시)이 남아
       있어서 여기서 거부하면 일괄 정리(`--prune-index`) 전의 레지스트리가 감사를 통과하지 못한다.
       고아 행을 위반으로 세는 것은 위생 검사 쪽이다.
    """
    if not mani_path.is_file():
        log(f"UNRUN: manifest 없음 — {mani_path}")
        return UNRUN
    try:
        hist = json.loads(mani_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log(f"UNRUN: manifest 파싱 실패 — {e}")
        return UNRUN
    # ⛔ pending 레코드는 **중단 증거**다 — 빼고 세면 WAL 에 흔적이 있는데도 감사가 통과한다
    #    [외부: fz-gpt validate r3].
    pending = [r for r in hist if r.get("state") == "pending"]
    want = {s for rec in hist for s in rec.get("ejected", [])}
    want |= {s for rec in pending for s in rec.get("planned", [])}
    if not want:
        log("UNRUN: manifest 에 배출 기록이 0건 — 측정 실패를 먼저 의심한다")
        return UNRUN
    # ⛔ eject 와 **같은 식별 규칙**을 쓴다. 이전 판은 여기서 full slug 를 번호로 축약해
    #    APPLIED=F-032-one · manifest=F-032-two 가 누락 0 으로 통과했다 [외부: fz-gpt validate #3].
    ap_slugs, ap_nums = applied_records(root / "APPLIED.md")
    arc = archive_slugs(root / ".archive")
    missing = [s for s in sorted(want) if ejected_slug(s, ap_slugs, ap_nums, arc) != s]
    arch_missing = [s for s in sorted(want) if not (root / ".archive" / f"{s}.md").is_file()]
    print(f"manifest 배출 {len(want)} · APPLIED 누락 {len(missing)} · archive 누락 {len(arch_missing)}"
          + (f" · ⛔ 미완료(pending) 레코드 {len(pending)}건" if pending else ""))
    for s in missing:
        print(f"  APPLIED 누락  {s}")
    for s in arch_missing:
        print(f"  archive 누락  {s}")
    for r in pending:
        print(f"  미완료 레코드  {r.get('version', '?')} planned={r.get('planned', [])}")
    residual, warns, why = index_residual(root, want | arc)
    if why:
        print(f"NOTE: INDEX 잔존 대조 생략 — {why}")
    else:
        print(f"INDEX 잔존 {len(residual)} (배출분·archive slug 의 대기열 행)")
        for slug, _ in residual:
            print(f"  INDEX 잔존  {slug}")
        for w in warns:
            print(f"  WARN   {w}")
        if residual:
            print(f"    → `--prune-index {root}` 가 지운다 (⛔ 잔존은 대장 대조의 exit 를 바꾸지 않는다 — 고아 판정은 `--audit` 의 위생 검사)")
    return REJECT if (missing or arch_missing or pending) else OK


def audit_cli(root: pathlib.Path, mani_path: pathlib.Path):
    """`--audit ROOT` — 대장 대조(`audit`) 뒤 같은 ROOT 에 위생 검사 기본 모드(`check_findings_hygiene.check`)를 돌린다.

    실 레지스트리 소비자(SC-3 · G27): 릴리스마다 배출 뒤 이 진입점을 부른다. `audit()` 의 대조 규칙·self-test 는 그대로다.
    판정(위반 우선): 대조 거부 또는 위생 위반이 하나라도 있으면 1 · 아니고 어느 쪽이 UNRUN 이면 2 · 둘 다 통과면 0.
    ⛔ 위생 검사기를 읽지 못하거나 검사 중 예외가 나면 UNRUN 이다 — 통과로 읽지 않고, traceback 으로 죽지도 않는다.
       모듈은 대장 대조보다 **먼저** 읽는다 — 대조의 INDEX 잔존 판정도 같은 모듈(`_queue_row`)을 쓰므로, 뒤에서 읽으면
       적재 실패가 대조 단계의 traceback 으로 새어 나간다.
    """
    try:
        hmod = _hygiene_module()
    except Exception as e:      # 적재 실패 = 판정 불가 — 대장 대조도 이 모듈에 기대므로 돌리지 않는다
        print(f"UNRUN: 위생 검사기를 읽지 못했다 — {type(e).__name__}: {e} (대장 대조도 돌리지 않았다)")
        print(f"AUDIT: 대장 대조 미실행 · 위생 검사 미실행 → exit {UNRUN}")
        return UNRUN
    rc = audit(root, mani_path)
    print("── 위생 검사 (check_findings_hygiene.py 기본 모드 · 같은 ROOT) ──")
    try:
        hy = hmod.check(root, False)
    except Exception as e:      # 모듈 고장·예상 밖 예외 = 판정 불가
        print(f"UNRUN: 위생 검사를 돌리지 못했다 — {type(e).__name__}: {e}")
        hy = UNRUN
    final = REJECT if REJECT in (rc, hy) else (UNRUN if UNRUN in (rc, hy) else OK)
    print(f"AUDIT: 대장 대조 exit {rc} · 위생 검사 exit {hy} → exit {final}")
    return final


def self_test():
    """fixture — 정상·없는ID·이미배출·ID충돌거부·중단후재실행·산문언급·모호비skip
    + 중복토큰·충돌시전무이동·같은번호다른slug·빈Closes (뒤 4종 = fz-gpt review #1/#3/#8 회귀)
    + INDEX 대기열 행 정리·잠금·감사 잔존(index-* · prune-index-keep · lock-busy-unrun · audit-reports-index-residual)."""
    import tempfile

    passed, failed, cases = [], [], 0

    def mk(tmp, entries, applied_rows=""):
        root = pathlib.Path(tmp) / "reg"
        (root / "entries").mkdir(parents=True)
        for slug in entries:
            (root / "entries" / f"{slug}.md").write_text(f"# {slug}\n", encoding="utf-8")
        (root / "APPLIED.md").write_text("# APPLIED\n\n| 날짜 | ID | 노트 | 처리 |\n|---|---|---|---|\n" + applied_rows, encoding="utf-8")
        note = pathlib.Path(tmp) / "v9.9.9.md"
        return root, note

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

    def c_normal(tmp):
        root, note = mk(tmp, ["F-001-alpha", "F-002-beta"])
        note.write_text("# v9.9.9\n\nCloses: F-001-alpha, F-002-beta\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == OK, "정상 배출이 OK 가 아니다"
        assert (root / ".archive" / "F-001-alpha.md").is_file(), "archive 로 이동되지 않았다"
        assert not (root / "entries" / "F-001-alpha.md").exists(), "entries 에 남아 있다"
        assert "F-001" in (root / "APPLIED.md").read_text(encoding="utf-8"), "APPLIED 행이 없다"

    def c_absent(tmp):
        root, note = mk(tmp, ["F-001-alpha"])
        note.write_text("Closes: F-999\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == REJECT, "없는 ID 가 거부되지 않았다"
        assert (root / "entries" / "F-001-alpha.md").is_file(), "거부인데 다른 엔트리가 움직였다"

    def c_already(tmp):
        root, note = mk(tmp, ["F-001-alpha"], "| 2026-01-01 | F-002 | x | applied |\n")
        note.write_text("Closes: F-002, F-001-alpha\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == OK, "이미 배출분 skip 이 OK 가 아니다"
        assert (root / ".archive" / "F-001-alpha.md").is_file(), "나머지가 배출되지 않았다"

    def c_ambiguous(tmp):
        root, note = mk(tmp, ["F-032-one", "F-032-two"])
        note.write_text("Closes: F-032\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == REJECT, "모호한 ID 가 거부되지 않았다"
        assert (root / "entries" / "F-032-one.md").is_file(), "거부인데 이동됐다"

    def c_rerun(tmp):
        root, note = mk(tmp, ["F-001-alpha"])
        note.write_text("Closes: F-001-alpha\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == OK, "1회차가 실패했다"
        assert eject(root, note, "9.9.9", False) == OK, "재실행이 실패했다 (멱등이어야 한다)"
        assert len(list((root / ".archive").glob("*.md"))) == 1, "재실행이 중복 이동했다"
        assert audit(root, root / MANI_NAME) == OK, "audit 이 통과하지 않았다"
        # ⛔ 무변화 재실행이 manifest 를 불리면 안 된다
        hist = json.loads((root / MANI_NAME).read_text(encoding="utf-8"))
        assert len(hist) == 1, f"⛔ 재실행이 빈 레코드를 쌓았다 ({len(hist)}개)"
        assert (root / "APPLIED.md").read_text(encoding="utf-8").count("F-001-alpha") == 1, \
            "재실행이 대장에 중복 기록했다"

    def c_prose_not_row(tmp):
        """⛔ 회귀: APPLIED **산문** 속 ID 언급은 배출 기록이 아니다 (실측 오탐).

        ⛔ 대상을 entries 에 두면 resolve 가 성공해 skip 분기에 닿지 않는다 — 이전 판이 그래서
        헛돌았다. 분기를 타려면 대상이 **없어야** 하고, 그때 산문 언급만으로 skip 되면 안 된다
        (없는 ID 를 '이미 배출됨' 으로 통과시키는 것이므로 거부가 맞다).
        """
        root, note = mk(tmp, ["F-900-unrelated"])
        ap = root / "APPLIED.md"
        ap.write_text(ap.read_text(encoding="utf-8") + "\n- 주의: F-077 이 지적한 홀이 재발했다 (산문 언급)\n", encoding="utf-8")
        note.write_text("Closes: F-077\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == REJECT, f"⛔ 산문 언급을 배출 기록으로 읽어 skip 했다 (rc={rc})"

    def c_ambiguous_not_skipped(tmp):
        """⛔ 회귀: 모호한 ID 는 대장에 같은 번호가 있어도 거부해야 한다."""
        root, note = mk(tmp, ["F-032-one", "F-032-two"],
                        "| 2026-01-01 | F-032 | x | applied |\n")
        note.write_text("Closes: F-032\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == REJECT, "모호한 ID 가 skip 으로 통과했다"
        assert (root / "entries" / "F-032-one.md").is_file(), "거부인데 이동됐다"

    def c_duplicate_token(tmp):
        """⛔ 회귀: 같은 엔트리를 두 토큰으로 가리켜도 한 번만 이동해야 한다 [외부: fz-gpt review #1]."""
        root, note = mk(tmp, ["F-050-dup"])
        note.write_text("Closes: F-050-dup, F-050-dup, F-050\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        # ⛔ 반환 코드를 본다 — 중복 제거가 없으면 두 번째 이동이 OSError 로 터져 REJECT 가 된다.
        #    파일·행 상태만 보던 이전 판은 그 오류가 OK 로 삼켜져 헛돌았다 [외부: fz-gpt validate #1].
        assert rc == OK, f"중복 토큰 처리가 실패했다 (rc={rc})"
        assert (root / ".archive" / "F-050-dup.md").is_file(), "이동되지 않았다"
        rows = [l for l in (root / "APPLIED.md").read_text(encoding="utf-8").splitlines()
                if "F-050-dup" in l]
        assert len(rows) == 1, f"대장에 중복 행이 {len(rows)}개 쌓였다"

    def c_conflict_no_partial_move(tmp):
        """⛔ 회귀: 뒤쪽 토큰이 충돌하면 **앞쪽도 이동하지 않아야** 한다 (원자성) [외부: fz-gpt review #1]."""
        root, note = mk(tmp, ["F-060-first", "F-061-second"])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-061-second.md").write_text("선점\n", encoding="utf-8")
        note.write_text("Closes: F-060-first, F-061-second\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == REJECT, "충돌인데 거부하지 않았다"
        assert (root / "entries" / "F-060-first.md").is_file(), \
            "⛔ 앞 파일이 이미 이동했다 — 대장 기록 없이 절반만 배출된 상태"

    def c_same_number_other_slug(tmp):
        """⛔ 회귀: 대장에 F-070-one 이 있어도 F-070-two 는 skip 되면 안 된다 [외부: fz-gpt review #3].

        ⛔ 이전 판은 `F-070-two` 를 **entries 에 둬서** resolve 가 성공했고, 그래서 NOT_FOUND
        skip 분기에 애초에 들어가지 않았다 — 구판 로직을 복원해도 통과하는 헛돌이였다
        [외부: fz-gpt validate #3]. 분기에 닿으려면 대상이 entries 에 **없어야** 한다.
        """
        root, note = mk(tmp, ["F-900-unrelated"], "| 2026-01-01 | F-070-one | x | applied |\n")
        note.write_text("Closes: F-070-two\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == REJECT, \
            f"⛔ 같은 번호의 다른 slug 를 '이미 배출됨' 으로 착각해 skip 했다 (rc={rc}, REJECT 여야 한다)"

    def c_closes_newline_not_eaten(tmp):
        """⛔ 회귀: 빈 `Closes:` 다음 줄의 제목을 토큰으로 읽으면 안 된다 [외부: fz-gpt review #8]."""
        root, note = mk(tmp, ["F-080-x"])
        note.write_text("Closes:\n\n## 변경 요약\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == UNRUN, f"빈 선언인데 rc={rc} (UNRUN 이어야 한다)"
        assert (root / "entries" / "F-080-x.md").is_file(), "빈 선언인데 엔트리가 움직였다"

    def c_bold_id_in_ledger(tmp):
        """⛔ 회귀: 대장 ID 가 `**F-002**` 로 굵게 적힌 행도 배출 기록으로 읽어야 한다 (실재 1건).

        ⛔ 판정 조건에 주의 — 대장 기록은 **엔트리가 이미 없을 때만** skip 근거다. 파일이 살아 있으면
        같은 번호를 재사용한 새 발견이므로 배출이 맞다(번호 재사용은 위생 검사의 축이다).
        따라서 굵은 ID 파싱은 이 NOT_FOUND 경로에서만 관측된다.
        """
        root, note = mk(tmp, ["F-900-other"], "| 2026-08-24 | **F-002** | `x` | 설명 | `applied` | 비고 |\n")
        note.write_text("Closes: F-002\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == OK, f"⛔ 굵은 ID 를 못 읽어 '없는 ID' 로 거부했다 (rc={rc})"
        assert (root / "entries" / "F-900-other.md").is_file(), "무관한 엔트리가 움직였다"

    def c_note_cell_mention_not_record(tmp):
        """⛔ 회귀: **비고 칸**에 언급된 ID 는 배출 기록이 아니다 (실재 3행이 이 형태)."""
        root, note = mk(tmp, ["F-900-unrelated"],
                        "| 2026-08-24 | F-002 | `x` | 설명 | `applied` | 참고: F-300 도 같은 축이다 |\n")
        note.write_text("Closes: F-300\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        # ⛔ 대상을 entries 에 두면 skip 분기에 닿지 않는다(이전 판 헛돌이). 없는 상태로 둬야
        #    "비고 칸 언급을 배출 기록으로 읽는가" 를 실제로 잰다 [외부: fz-gpt validate].
        assert rc == REJECT, f"⛔ 비고 칸 언급을 배출 기록으로 읽어 skip 했다 (rc={rc})"

    def c_partial_move_not_ok(tmp):
        """⛔ 회귀: 이동 도중 실패하면 **성공을 반환하지 않는다** [외부: fz-gpt validate #1]."""
        root, note = mk(tmp, ["F-410-first", "F-411-second"])
        note.write_text("Closes: F-410-first, F-411-second\n", encoding="utf-8")
        real_move, calls = shutil.move, {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("주입된 이동 실패")
            return real_move(src, dst)

        shutil.move = flaky
        try:
            rc = eject(root, note, "9.9.9", False)
        finally:
            shutil.move = real_move
        assert calls["n"] == 2, f"이동이 2회 시도되지 않았다 ({calls['n']}회)"
        assert rc == REJECT, f"⛔ 절반만 배출했는데 rc={rc} — 성공으로 삼켰다"
        assert "F-410-first" in (root / "APPLIED.md").read_text(encoding="utf-8"), \
            "이동한 건이 대장에 없다 — 복구 불가 상태"

    def c_corrupt_manifest_rejects_before_move(tmp):
        """⛔ 회귀: 손상된 manifest 는 **이동 전에** 걸러야 한다 [외부: fz-gpt validate #1]."""
        root, note = mk(tmp, ["F-420-x"])
        (root / ".eject-manifest.json").write_text("{ 이건 JSON 이 아니다", encoding="utf-8")
        note.write_text("Closes: F-420-x\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == REJECT, f"손상 manifest 인데 rc={rc}"
        assert (root / "entries" / "F-420-x.md").is_file(), \
            "⛔ manifest 를 이동 뒤에 읽어서 기록 없는 배출이 남았다"

    def c_audit_detects_slug_mismatch(tmp):
        """⛔ 회귀: audit 이 full slug 를 번호로 축약하면 안 된다 [외부: fz-gpt validate #3]."""
        root, _ = mk(tmp, [], "| 2026-01-01 | F-032-one | x | applied |\n")
        (root / ".archive").mkdir()
        (root / ".archive" / "F-032-two.md").write_text("x\n", encoding="utf-8")
        mani = root / ".eject-manifest.json"
        mani.write_text(json.dumps([{"version": "1", "ejected": ["F-032-two"]}]), encoding="utf-8")
        rc = audit(root, mani)
        assert rc == REJECT, \
            f"⛔ APPLIED=F-032-one 인데 manifest=F-032-two 를 누락 0 으로 통과시켰다 (rc={rc})"

    def c_malformed_token_rejected(tmp):
        """⛔ 회귀: slug 도 ID 도 아닌 토큰은 거부한다 — 조용히 넘기면 오타가 무시된다."""
        root, note = mk(tmp, ["F-430-x"])
        note.write_text("Closes: F-430-x, 오타난토큰\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == REJECT, f"형식 오류 토큰인데 rc={rc}"
        assert (root / "entries" / "F-430-x.md").is_file(), "거부인데 정상 토큰이 이동했다"

    def c_recover_applied_write_failure(tmp):
        """⛔ 회귀: 이동은 됐는데 **대장 기록 전에** 끊겨도 재실행이 복구한다 [외부: fz-gpt validate r2 #1]."""
        root, note = mk(tmp, ["F-500-a", "F-501-b"])
        note.write_text("Closes: F-500-a, F-501-b\n", encoding="utf-8")
        real_open = pathlib.Path.open

        def boom(self, *a, **k):
            if self.name == "APPLIED.md" and "a" in (a[0] if a else k.get("mode", "r")):
                raise OSError("주입: 대장 기록 실패")
            return real_open(self, *a, **k)

        pathlib.Path.open = boom
        try:
            try:
                eject(root, note, "9.9.9", False)
            except OSError:
                pass                      # 기록 단계에서 터진 상태를 만든다
        finally:
            pathlib.Path.open = real_open
        assert (root / ".archive" / "F-500-a.md").is_file(), "이동 자체가 안 됐다 — 전제 불성립"
        ap_before = (root / "APPLIED.md").read_text(encoding="utf-8")
        assert "F-500-a" not in ap_before, "대장에 이미 적혔다 — 전제 불성립"

        rc = eject(root, note, "9.9.9", False)      # 재실행 = 복구
        ap = (root / "APPLIED.md").read_text(encoding="utf-8")
        assert "F-500-a" in ap and "F-501-b" in ap, \
            "⛔ 중단된 배출이 대장에 복구되지 않았다 (파일만 archive 에 남는 고아 상태)"
        assert rc == OK, f"복구 후 재실행이 실패했다 (rc={rc})"
        assert audit(root, root / MANI_NAME) == OK, "복구 후 audit 이 통과하지 않았다"

    def c_manifest_atomic_no_truncation(tmp):
        """⛔ 회귀: manifest 쓰기가 **중간에 잘려도** 기존 이력이 손상되지 않는다 (원자 교체).

        ⛔ `os.replace` 실패를 주입하던 이전 판은 헛돌았다 — 직접 쓰기 판에는 `os.replace` 가
        아예 없어 주입이 발동하지 않는다. **잘림 자체**를 주입해야 두 판이 갈린다.
        """
        root, note = mk(tmp, ["F-510-a"])
        note.write_text("Closes: F-510-a\n", encoding="utf-8")
        mani = root / MANI_NAME
        mani.write_text(json.dumps([{"version": "old", "note": "n", "ejected": ["F-000-x"], "state": "done"}]),
                        encoding="utf-8")
        real_write = pathlib.Path.write_text

        def half(self, data, *a, **k):
            if MANI_NAME in self.name:            # manifest 본체와 .tmp 모두
                real_write(self, data[: len(data) // 2], *a, **k)
                raise OSError("주입: 쓰기 중 끊김")
            return real_write(self, data, *a, **k)

        pathlib.Path.write_text = half
        try:
            try:
                eject(root, note, "9.9.9", False)
            except OSError:
                pass
        finally:
            pathlib.Path.write_text = real_write
        # ⛔ 원자 교체면 잘린 내용은 .tmp 에만 남고 본체는 그대로다
        try:
            hist = json.loads(mani.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise AssertionError(f"⛔ 쓰기 중단이 기존 manifest 를 손상시켰다 — {e}")
        assert isinstance(hist, list) and hist and hist[0].get("version") == "old", \
            f"⛔ 기존 이력이 사라졌다 — {hist}"

    def c_pending_record_written_before_move(tmp):
        """⛔ 회귀: 계획은 **이동 전에** 적혀야 복구가 가능하다 (선기록)."""
        root, note = mk(tmp, ["F-520-a"])
        note.write_text("Closes: F-520-a\n", encoding="utf-8")
        real_move, seen = shutil.move, {}

        def spy(src, dst):
            hist = json.loads((root / MANI_NAME).read_text(encoding="utf-8"))
            seen["pending"] = [r for r in hist if r.get("state") == "pending"]
            return real_move(src, dst)

        shutil.move = spy
        try:
            eject(root, note, "9.9.9", False)
        finally:
            shutil.move = real_move
        assert seen.get("pending"), "⛔ 이동 시점에 pending 레코드가 없다 — 중단되면 복구 불가"
        assert "F-520-a" in seen["pending"][0]["planned"], "계획이 기록되지 않았다"
        hist = json.loads((root / MANI_NAME).read_text(encoding="utf-8"))
        assert all(r.get("state") == "done" for r in hist), "완료 후에도 pending 이 남았다"

    def c_ejected_slug_boundaries(tmp):
        """⛔ 회귀: 식별 경계 — **번호 경로와 full slug 경로가 같은 답**을 내야 한다.

        판정은 번호별 archive 후보 수로 갈린다(0=레거시 · 1=그것 · 2+=판정 불가).
        전역 플래그로 하면 빈 디렉토리·비워진 archive 양쪽으로 다 틀린다
        [외부: fz-gpt validate r3·r4].
        """
        A, N = {"F-001-a", "F-001-b"}, {"F-001"}
        cases = [
            # (토큰, ap_slugs, ap_nums, arc, 기대)
            # 레거시 번호 행 + archive 후보 다건 → 두 경로 모두 판정 불가
            ("F-001",     set(), N,     A,            None),
            ("F-001-a",   set(), N,     A,            None),
            # 레거시 번호 행 + 후보 유일 → 두 경로 모두 그 slug
            ("F-001",     set(), N,     {"F-001-a"},  "F-001-a"),
            ("F-001-a",   set(), N,     {"F-001-a"},  "F-001-a"),
            # 레거시 번호 행 + 후보 0 (archive 이전 삭제) → 두 경로 모두 인정
            ("F-001",     set(), N,     set(),        "F-001"),
            ("F-001-a",   set(), N,     set(),        "F-001-a"),
            # 명시 full slug 행 + 후보 0 (배출 후 사람이 archive 를 비움) → 대장 기록을 존중
            ("F-002-x",   {"F-002-x"}, set(), set(),  "F-002-x"),
            # 명시 full slug 행인데 archive 후보가 **다른** slug → 불일치
            ("F-002-x",   {"F-002-x"}, set(), {"F-002-y"}, None),
            # 대장에 같은 번호 full slug 가 둘 → 모호
            ("F-032",     {"F-032-one", "F-032-two"}, set(), set(), None),
            # 대장에 없는 slug 는 배출 아님
            ("F-032-two", {"F-032-one"}, set(), {"F-032-two"}, None),
            ("오타",       {"F-001-a"},   set(), set(), None),
        ]
        bad = []
        for tok, aps, apn, arc, want in cases:
            got = ejected_slug(tok, aps, apn, arc)
            if got != want:
                bad.append(f"{tok} arc={sorted(arc)} → {got!r} 기대 {want!r}")
        assert not bad, "⛔ 식별 경계 불일치: " + " · ".join(bad)

    def c_legacy_skip_idempotent_across_runs(tmp):
        """⛔ 회귀: 레거시 번호 행 skip 이 **2회차에도** 같은 답이어야 한다.

        1회차가 빈 `.archive/` 를 만들면 `arc_known` 이 뒤집혀 같은 입력이 거부됐다
        (실측 rc 0 → 1, 멱등 파괴) [외부: fz-gpt validate r3].
        """
        root, note = mk(tmp, ["F-900-other"], "| 2026-01-01 | F-001 | x | applied |\n")
        note.write_text("Closes: F-001\n", encoding="utf-8")
        rc1 = eject(root, note, "9.9.9", False)
        rc2 = eject(root, note, "9.9.9", False)
        assert rc1 == OK and rc2 == OK, f"⛔ 같은 입력인데 1회차={rc1} 2회차={rc2} (멱등 파괴)"

    def c_reconcile_keeps_pending_when_unexplained(tmp):
        """⛔ 회귀: 복구를 **확인하지 못하면** pending 을 done 으로 덮지 않는다.

        덮으면 증거가 사라져 오류가 걷힌 뒤에도 영영 복구하지 못한다 [외부: fz-gpt validate r3].
        """
        root, note = mk(tmp, ["F-950-z"])
        (root / ".archive").mkdir()
        mani = root / MANI_NAME
        mani.write_text(json.dumps([{"version": "1", "note": "n",
                                     "planned": ["F-001-a"], "state": "pending", "ejected": []}]),
                        encoding="utf-8")
        note.write_text("Closes: F-950-z\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        hist = json.loads(mani.read_text(encoding="utf-8"))
        assert hist[0]["state"] == "pending", \
            "⛔ 설명하지 못한 중단을 done 으로 확정했다 — 복구 경로가 사라졌다"
        assert rc == REJECT, f"설명 안 된 중단 위에 새 배출을 얹었다 (rc={rc})"
        assert (root / "entries" / "F-950-z.md").is_file(), "거부인데 새 배출이 진행됐다"

    def c_reconcile_no_duplicate_across_pendings(tmp):
        """⛔ 회귀: 같은 slug 를 담은 pending 이 둘이면 대장에 **한 번만** 적는다."""
        root, note = mk(tmp, ["F-960-y"])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        mani = root / MANI_NAME
        rec = {"note": "n", "planned": ["F-001-a"], "state": "pending", "ejected": []}
        mani.write_text(json.dumps([dict(rec, version="1"), dict(rec, version="2")]), encoding="utf-8")
        note.write_text("Closes: F-960-y\n", encoding="utf-8")
        eject(root, note, "9.9.9", False)
        cnt = (root / "APPLIED.md").read_text(encoding="utf-8").count("F-001-a")
        assert cnt == 1, f"⛔ 대장에 {cnt}회 적혔다 (pending 간 중복)"

    def c_audit_pending_missing_ledger(tmp):
        """⛔ 회귀 축1: pending 의 planned 를 **분모에 넣어야** 대장 누락이 잡힌다.

        ⛔ 이전 판은 두 보호(분모 포함 · 최종 pending 거부)를 한 fixture 로 묶어서, 하나만
        제거해도 통과했다 — 축을 갈라야 각각이 고정된다 [외부: fz-gpt validate r4 minor].
        """
        root, _ = mk(tmp, [], "| 2026-01-01 | F-000-old | x | applied |\n")
        (root / ".archive").mkdir()
        for f in ("F-000-old", "F-001-a"):
            (root / ".archive" / f"{f}.md").write_text("x\n", encoding="utf-8")
        mani = root / MANI_NAME
        mani.write_text(json.dumps([
            {"version": "1", "note": "n", "planned": ["F-000-old"], "state": "done", "ejected": ["F-000-old"]},
            # F-001-a 는 archive 에 있으나 **대장에 없다** — 분모에 넣어야 '누락' 으로 잡힌다
            {"version": "2", "note": "n", "planned": ["F-001-a"], "state": "pending", "ejected": []},
        ]), encoding="utf-8")
        # ⛔ 반환 코드만 보면 '최종 pending 거부' 가 대신 걸려서 이 축이 격리되지 않는다.
        #    **누락으로 지목했는가**를 출력으로 확인한다 [외부: fz-gpt validate r4 minor].
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = audit(root, mani)
        out = buf.getvalue()
        assert rc == REJECT, f"rc={rc}"
        assert "APPLIED 누락  F-001-a" in out, \
            f"⛔ pending 의 planned 가 분모에서 빠져 대장 누락으로 지목되지 않았다 — {out!r}"

    def c_audit_pending_complete_but_unfinalized(tmp):
        """⛔ 회귀 축2: 파일·대장이 다 갖춰졌어도 **확정 전 pending** 은 거부한다.

        이 입력에서는 '분모 포함' 만으로는 못 잡는다 — 누락이 0이기 때문이다.
        최종 pending 거부 조건이 있어야 걸린다.
        """
        root, _ = mk(tmp, [], "| 2026-01-01 | F-001-a | x | applied |\n")
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        mani = root / MANI_NAME
        mani.write_text(json.dumps([
            {"version": "1", "note": "n", "planned": ["F-001-a"], "state": "pending", "ejected": []},
        ]), encoding="utf-8")
        assert audit(root, mani) == REJECT, \
            "⛔ 대장·archive 는 갖춰졌지만 확정되지 않은 pending 을 통과시켰다"

    def c_resolve_pending_recovers_ledger(tmp):
        """⛔ 회귀: `--resolve-pending` 도 **확정 전에 대장을 복구**해야 한다.

        안 하면 파일은 archive 에 있고 대장엔 없는 채로 done 이 찍혀, reconcile 이 다시 볼
        일이 없어진다 — 고아가 영구화된다 [외부: fz-gpt validate r4 major].
        """
        root, _ = mk(tmp, [])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        mani = root / MANI_NAME
        mani.write_text(json.dumps([{"version": "1", "note": "n",
                                     "planned": ["F-001-a"], "state": "pending", "ejected": []}]),
                        encoding="utf-8")
        assert resolve_pending(root) == OK
        ap = (root / "APPLIED.md").read_text(encoding="utf-8")
        assert "F-001-a" in ap, "⛔ 확정했는데 대장이 비어 있다 — 고아 영구화"
        assert audit(root, mani) == OK, "확정 후 audit 이 통과하지 않는다"

    def c_empty_archive_is_not_evidence(tmp):
        """⛔ 회귀: **빈** `.archive/` 는 "배출 이력 있음" 이 아니다.

        디렉토리 유무로 판정하면, 어쩌다 빈 디렉토리가 생긴 것만으로 레거시 대장 기록이
        전부 거부된다. 기준은 **실제 배출물이 있는가** 다 [외부: fz-gpt validate r3].
        """
        root, note = mk(tmp, ["F-900-other"], "| 2026-01-01 | F-001 | x | applied |\n")
        (root / ".archive").mkdir()          # 비어 있는 채로 존재
        note.write_text("Closes: F-001\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == OK, f"⛔ 빈 archive 디렉토리 때문에 레거시 기록이 거부됐다 (rc={rc})"

    def c_archive_enumeration_failure_not_silent(tmp):
        """⛔ 회귀: archive 를 **못 세는 것**을 "비어 있음" 으로 읽으면 안 된다.

        `glob` 은 권한 오류에서 예외 없이 빈 목록을 낸다(실측 Python 3.9.6) — 그러면
        "아직 배출 안 됨" 으로 오판해 이미 배출된 것을 다시 옮기려 든다. `iterdir` 은 던진다.
        """
        root, note = mk(tmp, ["F-970-w"])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        note.write_text("Closes: F-970-w\n", encoding="utf-8")
        real = pathlib.Path.iterdir
        arc_dir = (root / ".archive").resolve()
        seen = {"raised": False}

        def boom(self):
            if self.resolve() == arc_dir:
                seen["raised"] = True
                raise PermissionError("주입된 열거 실패")
            return real(self)

        pathlib.Path.iterdir = boom
        try:
            try:
                eject(root, note, "9.9.9", False)
                silent = True
            except PermissionError:
                silent = False
        finally:
            pathlib.Path.iterdir = real
        assert seen["raised"], "주입이 열거 경로에 닿지 않았다 — fixture 전제 불성립"
        assert not silent, "⛔ 열거 실패를 빈 archive 로 읽고 그대로 진행했다"

    def c_resolve_pending_breaks_deadlock(tmp):
        """⛔ 회귀: 설명 안 된 중단이 **영구 교착**이 되지 않아야 한다 (탈출구 실재).

        보수적 reconcile 은 안전하지만, planned 파일이 실제로 유실되면 무관한 새 배출까지
        영원히 막힌다(실측 3회 연속 REJECT). 자동으로 풀면 안 되고 — 유실 판정은 사람 몫이다 —
        **명시적 명령**이 있어야 한다. 그리고 닫을 때도 지우지 않고 `lost` 로 남긴다.
        """
        root, note = mk(tmp, ["F-990-new"])
        (root / ".archive").mkdir()
        mani = root / MANI_NAME
        mani.write_text(json.dumps([{"version": "1", "note": "n",
                                     "planned": ["F-001-lost"], "state": "pending", "ejected": []}]),
                        encoding="utf-8")
        note.write_text("Closes: F-990-new\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == REJECT, "교착 전제가 성립하지 않는다"
        assert resolve_pending(root) == OK, "탈출구가 동작하지 않는다"
        rec = json.loads(mani.read_text(encoding="utf-8"))[0]
        assert rec["state"] == "done" and rec["lost"] == ["F-001-lost"], \
            f"⛔ 유실 증거가 기록에 남지 않았다 — {rec}"
        rc = eject(root, note, "9.9.9", False)
        assert rc == OK, f"⛔ 확정 후에도 새 배출이 막힌다 (rc={rc})"
        assert (root / ".archive" / "F-990-new.md").is_file(), "새 배출이 진행되지 않았다"

    def row(slug):
        return f"| {slug[:5]} | x | [{slug[:5]}](entries/{slug}.md) |\n"

    def ix(root, slugs, extra=""):
        """INDEX.md — `## 대기열` 아래 표에 slug 마다 한 행 + 다른 절의 산문 링크(행이 아니다)."""
        text = ("# INDEX\n\n> 반영되면 행을 지운다\n\n## 대기열\n\n| ID | 한 줄 | 문서 |\n|---|---|---|\n"
                + "".join(row(s) for s in slugs) + extra
                + "\n## 다음 ID\n\n산문 속 링크 [F-001](entries/F-001-alpha.md) 는 대기열 행이 아니다\n")
        (root / "INDEX.md").write_text(text, encoding="utf-8")
        return text

    def c_index_row_pruned_on_eject(tmp):
        """⛔ 회귀: 배출은 그 slug 의 INDEX 대기열 행을 지운다 — 이동·대장만 하고 행을 남기면 고아가 된다."""
        root, note = mk(tmp, ["F-001-alpha", "F-002-beta"])
        before = ix(root, ["F-001-alpha", "F-002-beta"])
        note.write_text("Closes: F-001-alpha\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == OK, "배출이 OK 가 아니다"
        after = (root / "INDEX.md").read_text(encoding="utf-8")
        assert row("F-001-alpha") not in after, "⛔ 배출한 slug 의 대기열 행이 남았다"
        assert after == before.replace(row("F-001-alpha"), ""), "⛔ 대상 행 밖의 줄이 바뀌었다"
        assert eject(root, note, "9.9.9", False) == OK, "재실행이 실패했다"
        assert (root / "INDEX.md").read_text(encoding="utf-8") == after, "⛔ 재실행이 INDEX 를 바꿨다"
        assert (root / LOCK_NAME).is_file(), "잠금 파일이 없다 — 잠금을 잡지 않았다"

    def c_index_same_number_other_slug(tmp):
        """⛔ 회귀: 같은 번호의 다른 slug 행은 지우지 않는다 — 행 식별은 ID 가 아니라 full slug 링크다.

        배출은 이번 실행분만 지우고, 예전 배출분은 `--prune-index` 가 지운다.
        """
        root, note = mk(tmp, ["F-070-two", "F-071-x"])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-070-one.md").write_text("x\n", encoding="utf-8")
        ix(root, ["F-070-one", "F-070-two", "F-071-x"])
        note.write_text("Closes: F-071-x\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == OK, "배출이 OK 가 아니다"
        t = (root / "INDEX.md").read_text(encoding="utf-8")
        assert row("F-071-x") not in t, "배출 행이 남았다"
        assert row("F-070-two") in t, "⛔ 같은 번호의 live 행을 지웠다"
        assert row("F-070-one") in t, "⛔ 이번 배출과 무관한 예전 배출 행까지 지웠다"
        assert prune_index(root) == OK, "--prune-index 실패"
        t = (root / "INDEX.md").read_text(encoding="utf-8")
        assert row("F-070-one") not in t and row("F-070-two") in t, "⛔ --prune-index 가 slug 로 가르지 못했다"

    def c_index_absent_note(tmp):
        """⛔ 회귀: INDEX 가 없어도 배출은 성공하되 **말없이 넘기지 않는다**(NOTE). `--prune-index` 는 UNRUN."""
        import io
        root, note = mk(tmp, ["F-001-alpha"])
        note.write_text("Closes: F-001-alpha\n", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = eject(root, note, "9.9.9", False)
        assert rc == OK, f"INDEX 부재가 배출을 막았다 (rc={rc})"
        assert "NOTE: INDEX.md 없음" in buf.getvalue(), "⛔ INDEX 부재를 조용히 넘겼다"
        assert not (root / "INDEX.md").exists(), "없던 INDEX 를 만들었다"
        assert prune_index(root) == UNRUN, "⛔ --prune-index 가 INDEX 없이 통과했다"

    def c_index_reconcile_prunes(tmp):
        """⛔ 회귀: 중단 복구(reconcile)도 INDEX 대기열 행을 지운다 — 대장만 복구하면 고아가 남는다."""
        root, note = mk(tmp, ["F-960-y"])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        (root / MANI_NAME).write_text(json.dumps([{"version": "1", "note": "n", "planned": ["F-001-a"],
                                                  "state": "pending", "ejected": []}]), encoding="utf-8")
        ix(root, ["F-001-a", "F-960-y"])
        note.write_text("Closes: F-960-y\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == OK, "복구 뒤 배출이 OK 가 아니다"
        t = (root / "INDEX.md").read_text(encoding="utf-8")
        assert row("F-001-a") not in t, "⛔ reconcile 이 복구한 slug 의 행이 남았다"
        assert row("F-960-y") not in t, "배출 행이 남았다"

    def c_index_resolve_pending_prunes(tmp):
        """⛔ 회귀: `--resolve-pending` 도 확정한 레코드의 archive 분 행을 지운다."""
        root, _ = mk(tmp, [])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        (root / MANI_NAME).write_text(json.dumps([{"version": "1", "note": "n", "planned": ["F-001-a", "F-002-lost"],
                                                  "state": "pending", "ejected": []}]), encoding="utf-8")
        ix(root, ["F-001-a"])
        assert resolve_pending(root) == OK, "확정이 OK 가 아니다"
        assert row("F-001-a") not in (root / "INDEX.md").read_text(encoding="utf-8"), "⛔ 확정 뒤에도 행이 남았다"

    def c_index_changed_after_read_rejects(tmp):
        """⛔ 회귀: 처음 읽은 뒤 INDEX 가 바뀌면 교체하지 않고 거부한다 — 덮으면 남의 행을 잃는다."""
        root, note = mk(tmp, ["F-001-alpha"])
        ix(root, ["F-001-alpha"])
        note.write_text("Closes: F-001-alpha\n", encoding="utf-8")
        foreign = "| F-990 | 다른 세션 | [F-990](entries/F-990-foreign.md) |\n"

        def fake(point, idx):
            if point == "read":
                with open(idx, "a", encoding="utf-8") as f:
                    f.write(foreign)

        g = globals()
        real = g["_test_hook"]
        g["_test_hook"] = fake
        try:
            rc = eject(root, note, "9.9.9", False)
        finally:
            g["_test_hook"] = real
        t = (root / "INDEX.md").read_text(encoding="utf-8")
        assert rc == REJECT, f"⛔ 읽은 뒤 바뀐 INDEX 를 그대로 덮었다 (rc={rc})"
        assert foreign in t, "⛔ 다른 writer 의 행을 잃었다"
        assert row("F-001-alpha") in t, "거부인데 교체했다"
        assert not (root / "INDEX.md.tmp").exists(), ".tmp 를 남겼다"
        assert eject(root, note, "9.9.9", False) == OK, "재실행이 맞추지 못했다"
        t = (root / "INDEX.md").read_text(encoding="utf-8")
        assert foreign in t and row("F-001-alpha") not in t, "재실행 결과가 틀렸다"

    def c_index_write_failure_rejects(tmp):
        """⛔ 회귀: INDEX 쓰기가 실패하면 성공을 반환하지 않고 원본을 그대로 둔다(배출 기록은 남는다)."""
        root, note = mk(tmp, ["F-001-alpha"])
        before = ix(root, ["F-001-alpha"])
        (root / "INDEX.md.tmp").mkdir()        # .tmp 자리를 디렉토리로 막아 쓰기를 실패시킨다
        note.write_text("Closes: F-001-alpha\n", encoding="utf-8")
        rc = eject(root, note, "9.9.9", False)
        assert rc == REJECT, f"⛔ INDEX 쓰기 실패인데 rc={rc}"
        assert (root / "INDEX.md").read_text(encoding="utf-8") == before, "⛔ 실패했는데 원본이 바뀌었다"
        assert (root / ".archive" / "F-001-alpha.md").is_file(), "배출 자체가 안 됐다 — 전제 불성립"
        assert "F-001-alpha" in (root / "APPLIED.md").read_text(encoding="utf-8"), "대장 기록이 없다"
        (root / "INDEX.md.tmp").rmdir()
        assert eject(root, note, "9.9.9", False) == OK, "막힘이 풀린 뒤 재실행이 맞추지 못했다"
        assert row("F-001-alpha") not in (root / "INDEX.md").read_text(encoding="utf-8"), "재실행 뒤에도 행이 남았다"

    def c_index_link_variants(tmp):
        """⛔ 회귀: `./entries/` 링크도 같은 파일로 지우고, 다른 slug 링크(옛 이름)는 지우지 않되 WARN 한다."""
        import io
        root, _ = mk(tmp, [])
        (root / ".archive").mkdir()
        for s in ("F-001-a", "F-002-b"):
            (root / ".archive" / f"{s}.md").write_text("x\n", encoding="utf-8")
        dot = "| F-001 | x | [F-001](./entries/F-001-a.md) |\n"
        old = "| F-002 | x | [F-002](entries/F-002-old-name.md) |\n"
        ix(root, [], dot + old)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = prune_index(root)
        t = (root / "INDEX.md").read_text(encoding="utf-8")
        out = buf.getvalue()
        assert rc == OK, f"rc={rc}"
        assert dot not in t, "⛔ `./entries/` 링크 행을 놓쳤다 (0건을 지우고 OK)"
        assert old in t, "⛔ slug 가 다른 행을 번호만 보고 지웠다"
        assert "slug 변형" in out and "./entries/" in out, f"⛔ 변형을 말없이 넘겼다 — {out!r}"

    def c_prune_index_keep(tmp):
        """`--prune-index` 의 keep 은 결정 대기 엔트리의 행을 남긴다(ID 또는 full slug)."""
        root, _ = mk(tmp, [])
        (root / ".archive").mkdir()
        for s in ("F-001-a", "F-002-b", "F-003-c"):
            (root / ".archive" / f"{s}.md").write_text("x\n", encoding="utf-8")
        ix(root, ["F-001-a", "F-002-b", "F-003-c"])
        assert prune_index(root, frozenset({"F-002", "F-003-c"})) == OK, "--prune-index 실패"
        t = (root / "INDEX.md").read_text(encoding="utf-8")
        assert row("F-001-a") not in t, "keep 밖 행이 남았다"
        assert row("F-002-b") in t and row("F-003-c") in t, "⛔ keep 한 행을 지웠다"

    def c_lock_busy_unrun(tmp):
        """⛔ 회귀: 다른 협조 writer 가 잠금을 쥐고 있으면 상한까지 기다린 뒤 아무것도 바꾸지 않고 UNRUN.

        ⛔ 판정은 잠금 파일의 존재가 아니라 flock 보유다 — 보유자가 놓으면 파일이 남아 있어도 바로 잡힌다.
        """
        root, note = mk(tmp, ["F-001-alpha"])
        before = ix(root, ["F-001-alpha"])
        note.write_text("Closes: F-001-alpha\n", encoding="utf-8")
        old = os.environ.get(LOCK_WAIT_ENV)
        os.environ[LOCK_WAIT_ENV] = "0.3"
        fd = os.open(str(root / LOCK_NAME), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            t0 = time.monotonic()
            rc = eject(root, note, "9.9.9", False)
            waited = time.monotonic() - t0
        finally:
            os.close(fd)
            if old is None:
                os.environ.pop(LOCK_WAIT_ENV, None)
            else:
                os.environ[LOCK_WAIT_ENV] = old
        assert rc == UNRUN, f"⛔ 잠금이 잡혀 있는데 rc={rc}"
        assert waited >= 0.25, f"⛔ 상한까지 기다리지 않았다 ({waited:.2f}s)"
        assert (root / "entries" / "F-001-alpha.md").is_file(), "⛔ 잠금 없이 이동했다"
        assert (root / "INDEX.md").read_text(encoding="utf-8") == before, "⛔ 잠금 없이 INDEX 를 바꿨다"
        assert (root / LOCK_NAME).is_file(), "⛔ 잠금 파일을 지웠다"

    def c_reject_leaves_index(tmp):
        """⛔ 회귀: 거부(모호·없는 토큰)는 전무다 — 이미 배출된 slug 가 섞여 있어도 INDEX 를 바꾸지 않는다."""
        root, note = mk(tmp, [], "| 9.9.8 | F-001-a | `old.md` | 릴리즈 `Closes:` 로 배출 |\n")
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        before = ix(root, ["F-001-a"])
        note.write_text("Closes: F-001-a, F-009-typo\n", encoding="utf-8")
        assert eject(root, note, "9.9.9", False) == REJECT, "없는 토큰인데 거부하지 않았다"
        assert (root / "INDEX.md").read_text(encoding="utf-8") == before, "⛔ 거부한 실행이 INDEX 를 바꿨다"

    def c_prune_index_keep_miss(tmp):
        """⛔ 회귀: archive 와 맞지 않는 keep 토큰(오타)은 바꾸기 전에 UNRUN — 남기려던 행을 지우지 않는다."""
        root, _ = mk(tmp, [])
        (root / ".archive").mkdir()
        (root / ".archive" / "F-348-a.md").write_text("x\n", encoding="utf-8")
        before = ix(root, ["F-348-a"])
        assert prune_index(root, frozenset({"F348"})) == UNRUN, "오타 keep 을 받아들였다"
        assert (root / "INDEX.md").read_text(encoding="utf-8") == before, "⛔ 오타 keep 으로 행을 지웠다"

    def c_lock_wait_nonfinite_unrun(tmp):
        """⛔ 회귀: 잠금 대기 상한이 nan · inf · 음수면 기다리지 않고 UNRUN — float() 가 받아들여 무한 대기가 되던 경로."""
        root, note = mk(tmp, ["F-001-alpha"])
        note.write_text("Closes: F-001-alpha\n", encoding="utf-8")
        old = os.environ.get(LOCK_WAIT_ENV)
        try:
            for v in ("nan", "inf", "-1"):
                os.environ[LOCK_WAIT_ENV] = v
                t0 = time.monotonic()
                rc = eject(root, note, "9.9.9", False)
                assert rc == UNRUN and time.monotonic() - t0 < 1.0, f"⛔ {v}: rc={rc}"
        finally:
            if old is None:
                os.environ.pop(LOCK_WAIT_ENV, None)
            else:
                os.environ[LOCK_WAIT_ENV] = old
        assert (root / "entries" / "F-001-alpha.md").is_file(), "⛔ 상한이 틀렸는데 이동했다"
        assert eject(root, note, "9.9.9", False) == OK, "⛔ 보유자가 놓았는데 파일이 남았다는 이유로 막혔다"

    def c_audit_reports_index_residual(tmp):
        """⛔ 회귀: --audit 은 배출분의 INDEX 잔존 행을 보여 준다 — INDEX 를 안 보면 고아가 감사를 그대로 통과한다."""
        import io
        root, _ = mk(tmp, [], "| 9.9.9 | F-001-a | `n` | 릴리즈 `Closes:` 로 배출 |\n")
        (root / ".archive").mkdir()
        (root / ".archive" / "F-001-a.md").write_text("x\n", encoding="utf-8")
        mani = root / MANI_NAME
        mani.write_text(json.dumps([{"version": "9.9.9", "note": "n", "planned": ["F-001-a"],
                                     "state": "done", "ejected": ["F-001-a"]}]), encoding="utf-8")
        ix(root, ["F-001-a"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            audit(root, mani)
        assert "INDEX 잔존  F-001-a" in buf.getvalue(), f"⛔ 잔존 행을 보고하지 않았다 — {buf.getvalue()!r}"

    for n, f in [("normal", c_normal), ("absent-id", c_absent), ("already-ejected", c_already),
                 ("ambiguous-id-reject", c_ambiguous), ("rerun-idempotent", c_rerun),
                 ("prose-mention-not-row", c_prose_not_row),
                 ("ambiguous-not-skipped", c_ambiguous_not_skipped),
                 ("duplicate-token", c_duplicate_token),
                 ("conflict-no-partial-move", c_conflict_no_partial_move),
                 ("same-number-other-slug", c_same_number_other_slug),
                 ("closes-newline-not-eaten", c_closes_newline_not_eaten),
                 ("bold-id-in-ledger", c_bold_id_in_ledger),
                 ("note-cell-mention-not-record", c_note_cell_mention_not_record),
                 ("partial-move-not-ok", c_partial_move_not_ok),
                 ("corrupt-manifest-before-move", c_corrupt_manifest_rejects_before_move),
                 ("audit-slug-mismatch", c_audit_detects_slug_mismatch),
                 ("malformed-token-rejected", c_malformed_token_rejected),
                 ("recover-applied-write-failure", c_recover_applied_write_failure),
                 ("manifest-atomic-no-truncation", c_manifest_atomic_no_truncation),
                 ("pending-record-before-move", c_pending_record_written_before_move),
                 ("ejected-slug-boundaries", c_ejected_slug_boundaries),
                 ("legacy-skip-idempotent", c_legacy_skip_idempotent_across_runs),
                 ("empty-archive-not-evidence", c_empty_archive_is_not_evidence),
                 ("archive-enum-failure-not-silent", c_archive_enumeration_failure_not_silent),
                 ("reconcile-keeps-unexplained-pending", c_reconcile_keeps_pending_when_unexplained),
                 ("reconcile-no-duplicate-pendings", c_reconcile_no_duplicate_across_pendings),
                 ("audit-pending-missing-ledger", c_audit_pending_missing_ledger),
                 ("audit-pending-unfinalized", c_audit_pending_complete_but_unfinalized),
                 ("resolve-pending-recovers-ledger", c_resolve_pending_recovers_ledger),
                 ("resolve-pending-breaks-deadlock", c_resolve_pending_breaks_deadlock),
                 ("index-row-pruned-on-eject", c_index_row_pruned_on_eject),
                 ("index-same-number-other-slug", c_index_same_number_other_slug),
                 ("index-absent-note", c_index_absent_note),
                 ("index-reconcile-prunes", c_index_reconcile_prunes),
                 ("index-resolve-pending-prunes", c_index_resolve_pending_prunes),
                 ("index-changed-after-read-rejects", c_index_changed_after_read_rejects),
                 ("index-write-failure-rejects", c_index_write_failure_rejects),
                 ("index-link-variants", c_index_link_variants),
                 ("prune-index-keep", c_prune_index_keep),
                 ("lock-busy-unrun", c_lock_busy_unrun),
                 ("reject-leaves-index", c_reject_leaves_index),
                 ("prune-index-keep-miss", c_prune_index_keep_miss),
                 ("lock-wait-nonfinite-unrun", c_lock_wait_nonfinite_unrun),
                 ("audit-reports-index-residual", c_audit_reports_index_residual)]:
        cases += 1
        case(n, f)

    # ⛔ 분모를 세어서 인쇄한다 — 상수로 적으면 케이스를 늘렸을 때 문구가 거짓이 된다
    print(f"self-test {len(passed)}/{cases} 통과")
    for p in passed:
        print(f"  ok   {p}")
    for f in failed:
        print(f"  FAIL {f}")
    return OK if not failed else REJECT


def main():
    ap = argparse.ArgumentParser(description="릴리즈 Closes: → fz-findings 배출")
    ap.add_argument("--root", type=pathlib.Path, help="레지스트리 루트 (entries/·APPLIED.md 보유)")
    ap.add_argument("--note", type=pathlib.Path, help="릴리즈 노트 경로")
    ap.add_argument("--version", default="", help="APPLIED 행에 적을 버전/날짜")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit", type=pathlib.Path, metavar="ROOT", help="manifest ↔ APPLIED 대조 + 위생 검사 기본 모드")
    ap.add_argument("--resolve-pending", type=pathlib.Path, metavar="ROOT",
                    help="⛔ 설명되지 않은 중단(pending)을 사람 판정으로 확정한다 — 유실분은 `lost` 로 남긴다")
    ap.add_argument("--prune-index", type=pathlib.Path, metavar="ROOT",
                    help="archive 에 있는 slug 의 INDEX 대기열 행을 전부 지운다 (일괄 정리 — INDEX.md 만 바꾼다)")
    ap.add_argument("--keep", default="", metavar="ID,...",
                    help="--prune-index 에서 지우지 않을 ID 또는 full slug (쉼표 구분)")
    ap.add_argument("--manifest", type=pathlib.Path)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.keep and not a.prune_index:
        ap.error("--keep 은 --prune-index 와 함께만 쓴다")
    if a.self_test:
        return self_test()
    if a.audit:
        mani = a.manifest or (a.audit / ".eject-manifest.json")
        return audit_cli(a.audit, mani)
    if a.resolve_pending:
        return resolve_pending(a.resolve_pending)
    if a.prune_index:
        return prune_index(a.prune_index, frozenset(t for t in re.split(r"[,\s]+", a.keep) if t))
    if not a.root or not a.note:
        ap.error("--root 와 --note 가 필요하다 (또는 --self-test / --audit)")
    return eject(a.root, a.note, a.version or "unversioned", a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
