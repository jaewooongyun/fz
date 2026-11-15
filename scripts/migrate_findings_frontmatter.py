#!/usr/bin/env python3
"""migrate_findings_frontmatter.py — 레지스트리 엔트리에 frontmatter 를 채운다 (S17).

왜: `fz-findings` 의 집계·배출·승격은 전부 frontmatter 를 읽는다. 그런데 실측 96/244 가
frontmatter 자체가 없거나 필수 필드가 빠져 있다 — 그 엔트리들은 **도구에게 보이지 않는다**.
플랜 v7 이 76건으로 적었고 89 → 96 으로 늘었다. 방치하면 증가하는 축이다.

⛔ **추측하지 않는다.** 채우는 값은 파일에서 기계적으로 유도되는 것뿐이다.

| 필드 | 유도 | 유도 불가 시 |
|---|---|---|
| `id` | 파일명 | — (파일명이 규약이면 항상 가능) |
| `title` | H1 의 `—` 뒤 | H1 전체 |
| `failure_class` | 파일명 slug 의 ID 뒤 | — |
| `status` | 항상 `open` — `entries/` 에 있다 = 미반영 (README §0 불변식) | — |
| `date` | 본문 `관측일:`·`관측:` → 없으면 첫 `YYYY-MM-DD` | **비워 둔다** |
| `class` | 본문 `분류:` 의 **동의어 표** (아래) | **비워 두고 보고** |

⛔ `class` 는 정본 5값(`hole|miss|works|retired|추가`) 뿐이고 본문은 자유 문장이다.
   "규칙 미발화"·"하네스 홀"·"게이트 미발화" 는 `hole` 의 정의를 그대로 되풀이한 말이라
   **동의어**로 본다. 그 밖은 판단이 들어가므로 채우지 않고 목록으로 남긴다.
   유도한 값에는 `# 유도: 분류 "<원문>"` 주석을 붙여 **감사 가능**하게 한다.

exit code:
  0  OK — census 통과 · 또는 마이그레이션 성공
  1  INCOMPLETE — 필수 필드가 빠진 엔트리가 남아 있다
  2  UNRUN — 디렉토리 부재·읽기 실패·빈 분모 등 판정 불가. ⛔ 통과로 읽지 않는다

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

OK, INCOMPLETE, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치해야 한다
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SLUG = re.compile(r"^(F-\d{3}[a-z]?)-([a-z0-9-]+)$")
FM = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
H1 = re.compile(r"^#\s+(?:F-\d{3}[a-z]?\s*[—–-]\s*)?(.+)$", re.M)
OBS = re.compile(r"^[-\s]*\**\s*관측일?\s*\**\s*[:：]\s*\**\s*(\d{4}-\d{2}-\d{2})", re.M)
ANYDATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
CLSLINE = re.compile(r"^[-\s]*\**\s*분류\s*\**\s*[:：]\s*(.+)$", re.M)
REQUIRED = ("id", "title", "date", "class", "failure_class", "status")
CANON_CLASS = ("hole", "miss", "works", "retired", "추가")

# ⛔ **동의어 표** — 추측이 아니라 정본 정의를 되풀이한 말만 담는다.
#    `hole` = "하네스가 잡았어야 하는데 못 잡음". 아래 말들은 전부 그 뜻이다.
#    ⛔ 새 항목을 넣기 전에 `README.md` 의 class 정의와 대조하라 — 애매하면 넣지 않는다.
CLASS_SYNONYMS = [
    (("규칙 미발화", "게이트 미발화", "하네스 홀", "게이트 홀", "수집 홀", "절차 갭",
      "지시-이행 갭", "게이트 범위 불일치", "하네스 결함", "위음성", "거짓 음성",
      "fail-silent", "Bash 함정"), "hole"),
    (("게이트가 막음", "검산이 잡았다", "게이트가 발화", "발화했고 옳았"), "works"),
    (("원리적으로 못", "원리적 한계"), "miss"),
    (("실측으로 기각", "기각됨"), "retired"),
]


def log(*a):
    print(*a, file=sys.stderr)


def derive_class(body: str):
    """본문 `분류:` → 정본 class. 확정 못 하면 (None, 원문)."""
    m = CLSLINE.search(body)
    if not m:
        return None, None
    raw = m.group(1).strip()
    # ⛔ 앞쪽 핵심만 본다 — 뒤의 "— fz를 바꾼다" 류는 처방이지 분류가 아니다
    head = re.split(r"—|--", raw)[0]
    for words, val in CLASS_SYNONYMS:
        if any(w in head for w in words):
            return val, raw
    return None, raw


def _mark(f: dict, added: list, key: str, val):
    """없을 때만 채우고 **무엇을 채웠는지 남긴다** — 이미 완전한 엔트리를 다시 쓰지 않기 위해."""
    if key not in f:
        f[key] = val
        added.append(key)


def derive(path: pathlib.Path):
    """엔트리 하나에서 채울 수 있는 필드를 뽑는다. (fields, body, unresolved)"""
    m = SLUG.match(path.stem)
    if not m:
        return None, None, ["파일명이 규약에 맞지 않는다"], []
    fid, slug = m.group(1), m.group(2)
    text = path.read_text(encoding="utf-8")
    fmm = FM.match(text)
    existing, body = ({}, text)
    if fmm:
        for line in fmm.group(1).splitlines():
            km = re.match(r"^([a-z_]+):\s*(.*)$", line)
            if km and km.group(2).split("#")[0].strip():
                existing[km.group(1)] = km.group(2).rstrip()
        body = text[fmm.end():]

    f, unresolved, added = dict(existing), [], []
    _mark(f, added, "id", fid)
    _mark(f, added, "failure_class", slug)
    _mark(f, added, "status", "open")
    if "title" not in f:
        h = H1.search(body)
        f["title"] = h.group(1).strip() if h else slug
        added.append("title")
    if "date" not in f:
        d = OBS.search(body) or ANYDATE.search(body)
        if d:
            f["date"] = d.group(1); added.append("date")
        else:
            unresolved.append("date")
    if "class" not in f:
        c, raw = derive_class(body)
        if c:
            f["class"] = f'{c}            # 유도: 분류 "{raw[:60]}" (S17 마이그레이션)'
            added.append("class")
        else:
            unresolved.append("class" + (f' (분류 원문: "{raw[:50]}")' if raw else " (분류 줄 없음)"))
    return f, body, unresolved, added


def render(f: dict, body: str) -> str:
    order = ["id", "title", "date", "class", "failure_class", "status"]
    lines = ["---"]
    for k in order:
        if k in f:
            lines.append(f"{k}: {f[k]}")
    for k in sorted(set(f) - set(order)):
        lines.append(f"{k}: {f[k]}")
    lines.append("---")
    return "\n".join(lines) + "\n" + (body if body.startswith("\n") else "\n" + body)


def entries_of(root: pathlib.Path):
    e = root / "entries"
    if not e.is_dir():
        return None
    try:
        # ⛔ `glob` 은 권한 오류에서 조용히 빈 목록을 낸다(F-271) — `iterdir` 은 던진다
        return sorted(q for q in e.iterdir() if q.suffix == ".md" and SLUG.match(q.stem))
    except OSError as ex:
        raise RuntimeError(f"entries/ 열거 실패: {type(ex).__name__}: {ex}") from ex


def census(root: pathlib.Path, verbose=True):
    """전수 census — 필수 6필드가 채워진 엔트리 비율. (rc, 미완목록)"""
    try:
        files = entries_of(root)
    except RuntimeError as e:
        log(f"UNRUN: {e}")
        return UNRUN, []
    if files is None:
        log(f"UNRUN: entries 디렉토리 없음 — {root/'entries'}")
        return UNRUN, []
    if not files:
        log("UNRUN: 엔트리가 0건 — 측정 실패를 먼저 의심한다")
        return UNRUN, []

    incomplete, nofm, badclass = [], 0, []
    for q in files:
        t = q.read_text(encoding="utf-8")
        fmm = FM.match(t)
        if not fmm:
            nofm += 1
            incomplete.append((q.name, ["frontmatter 블록 없음"]))
            continue
        fmb = fmm.group(1)
        miss = [k for k in REQUIRED if not re.search(rf"^{k}:\s*\S", fmb, re.M)]
        cm = re.search(r"^class:\s*(\S+)", fmb, re.M)
        if cm and cm.group(1).split("#")[0].strip() not in CANON_CLASS:
            badclass.append(f"{q.name}: class={cm.group(1)}")
        if miss:
            incomplete.append((q.name, miss))
    done = len(files) - len(incomplete)
    if verbose:
        print(f"census: {done}/{len(files)} 완전 ({100*done//len(files)}%)"
              f" · frontmatter 없음 {nofm} · 필드 누락 {len(incomplete)-nofm}")
        print(f"  ⛔ class 비정규(정본 {'|'.join(CANON_CLASS)} 외): {len(badclass)}")
        for b in badclass[:5]:
            print(f"      {b}")
        if len(badclass) > 5:
            print(f"      … 외 {len(badclass)-5}건")
    return (OK if not incomplete else INCOMPLETE), incomplete


def apply(root: pathlib.Path, dry: bool):
    try:
        files = entries_of(root)
    except RuntimeError as e:
        log(f"UNRUN: {e}")
        return UNRUN
    if not files:
        log("UNRUN: 엔트리가 0건 — 측정 실패를 먼저 의심한다")
        return UNRUN

    changed, left = [], []
    for q in files:
        f, body, unresolved, added = derive(q)
        if f is None:
            left.append((q.name, unresolved))
            continue
        if not added:
            # ⛔ 채울 게 없으면 **건드리지 않는다.** render() 는 필드 순서를 정규화하므로
            #    이미 완전한 엔트리도 "달라 보인다" — 그걸로 다시 쓰면 244건을 훼손 위험에 올린다
            continue
        cur = q.read_text(encoding="utf-8")
        new = render(f, body)
        if new != cur:
            if not dry:
                # ⛔ 원자 교체 — 쓰기가 끊기면 엔트리 본문이 잘린다
                tmp = q.with_suffix(".md.tmp")
                tmp.write_text(new, encoding="utf-8")
                os.replace(tmp, q)
            changed.append(q.name)
        if unresolved:
            left.append((q.name, unresolved))

    print(f"{'(dry-run) ' if dry else ''}frontmatter 기록 {len(changed)}건 · 유도 불가 잔존 {len(left)}건")
    for n in changed[:8]:
        print(f"  기록  {n}")
    if len(changed) > 8:
        print(f"  … 외 {len(changed)-8}건")
    if left:
        print("⛔ 아래는 **채우지 않았다** — 기계적으로 유도되지 않는다 (사람이 판정한다)")
        for n, u in left[:12]:
            print(f"  미해결 {n[:56]:58} {'; '.join(u)[:70]}")
        if len(left) > 12:
            print(f"  … 외 {len(left)-12}건")
    return OK


def self_test():
    """fixture — 전필드유도 · class동의어 · class불가 · date부재 · 기존보존 · 본문보존
    · 빈분모UNRUN · 디렉토리부재UNRUN · 열거실패UNRUN · dry-run무변경.
    """
    import tempfile
    passed, failed, cases = [], [], 0

    def case(name, fn):
        nonlocal cases
        cases += 1
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(pathlib.Path(tmp)); passed.append(name)
            except AssertionError as e:
                failed.append(f"{name}: {e}")
            except Exception as e:
                failed.append(f"{name}: ⛔ 예외 {type(e).__name__}: {e}")

    def mk(root, name, body):
        (root / "entries").mkdir(parents=True, exist_ok=True)
        (root / "entries" / name).write_text(body, encoding="utf-8")
        return root / "entries" / name

    def c_full_derivation(tmp):
        r = tmp / "reg"
        q = mk(r, "F-001-state-settle-time.md",
               "# F-001 — 상태 확정 시점 미확인\n\n- 관측일: 2026-08-12\n- 분류: **규칙 미발화** — fz를 바꾼다\n\n## 재현\n본문\n")
        assert apply(r, False) == OK
        t = q.read_text(encoding="utf-8")
        for want in ("id: F-001", "title: 상태 확정 시점 미확인", "date: 2026-08-12",
                     "class: hole", "failure_class: state-settle-time", "status: open"):
            assert want in t, f"⛔ '{want}' 가 없다\n{t[:220]}"
        assert "## 재현" in t and "본문" in t, "⛔ 본문이 사라졌다"

    def c_class_synonym_audited(tmp):
        r = tmp / "reg"
        q = mk(r, "F-002-gate-hole.md", "# F-002 — 제목\n\n- 관측일: 2026-08-13\n- 분류: 하네스 홀\n")
        apply(r, False)
        t = q.read_text(encoding="utf-8")
        assert "class: hole" in t, "동의어 매핑 실패"
        assert '유도: 분류 "하네스 홀"' in t, "⛔ 유도 근거 주석이 없다 — 감사 불가"

    def c_class_unmappable_left_blank(tmp):
        r = tmp / "reg"
        q = mk(r, "F-003-weird.md", "# F-003 — 제목\n\n- 관측일: 2026-08-14\n- 분류: 알 수 없는 무언가\n")
        apply(r, False)
        t = q.read_text(encoding="utf-8")
        # ⛔ 부분 문자열로 보면 `failure_class:` 가 걸린다 — **줄 시작**으로 판정한다 (규약 8·10)
        assert not re.search(r"^class:", t, re.M), f"⛔ 유도 불가인데 class 를 채웠다(추측) — {t[:180]}"
        rc, inc = census(r, verbose=False)
        assert rc == INCOMPLETE and inc, "census 가 미완을 보고하지 않았다"

    def c_missing_date_left_blank(tmp):
        r = tmp / "reg"
        q = mk(r, "F-004-nodate.md", "# F-004 — 제목\n\n- 분류: 규칙 미발화\n")
        apply(r, False)
        assert "date:" not in q.read_text(encoding="utf-8"), "⛔ 날짜가 없는데 지어냈다"

    def c_existing_fields_preserved(tmp):
        r = tmp / "reg"
        q = mk(r, "F-005-keep.md",
               "---\nid: F-005\ntitle: 원래 제목\nclass: works\n---\n\n# F-005 — 다른 제목\n\n- 관측일: 2026-08-15\n")
        apply(r, False)
        t = q.read_text(encoding="utf-8")
        assert "title: 원래 제목" in t, "⛔ 기존 값을 덮어썼다"
        assert "class: works" in t, "⛔ 기존 class 를 덮어썼다"
        assert "date: 2026-08-15" in t and "status: open" in t, "빠진 필드를 안 채웠다"

    def c_dry_run_no_write(tmp):
        r = tmp / "reg"
        q = mk(r, "F-006-dry.md", "# F-006 — 제목\n\n- 관측일: 2026-08-16\n- 분류: 규칙 미발화\n")
        before = q.read_text(encoding="utf-8")
        assert apply(r, True) == OK
        assert q.read_text(encoding="utf-8") == before, "⛔ dry-run 이 파일을 바꿨다"

    def c_census_counts(tmp):
        r = tmp / "reg"
        mk(r, "F-007-a.md", "---\nid: F-007\ntitle: t\ndate: 2026-01-01\nclass: hole\nfailure_class: a\nstatus: open\n---\n본문\n")
        mk(r, "F-008-b.md", "# F-008 — 제목\n")
        rc, inc = census(r, verbose=False)
        assert rc == INCOMPLETE, "미완이 있는데 OK"
        assert len(inc) == 1 and inc[0][0] == "F-008-b.md", f"census 오집계: {inc}"

    def c_empty_unrun(tmp):
        r = tmp / "reg"
        (r / "entries").mkdir(parents=True)
        assert census(r, verbose=False)[0] == UNRUN, "⛔ 빈 분모가 UNRUN 이 아니다"
        assert apply(r, False) == UNRUN, "⛔ 빈 분모로 마이그레이션을 돌렸다"

    def c_no_dir_unrun(tmp):
        assert census(tmp / "nope", verbose=False)[0] == UNRUN, "⛔ 디렉토리 부재가 UNRUN 이 아니다"

    def c_enumeration_failure_unrun(tmp):
        r = tmp / "reg"
        mk(r, "F-009-x.md", "# F-009 — 제목\n")
        real = pathlib.Path.iterdir
        target = (r / "entries").resolve()

        def boom(self):
            if self.resolve() == target:
                raise PermissionError("주입된 열거 실패")
            return real(self)

        import contextlib, io
        buf = io.StringIO()
        pathlib.Path.iterdir = boom
        try:
            with contextlib.redirect_stderr(buf):
                rc = census(r, verbose=False)[0]
        finally:
            pathlib.Path.iterdir = real
        err = buf.getvalue()
        assert rc == UNRUN, f"⛔ 열거 실패인데 rc={rc}"
        # ⛔ **원인 보고로 축을 격리한다** — 빈 목록으로 삼키면 빈 분모 가드가 대신 걸려
        #    같은 UNRUN 이 나므로 rc 만 보면 이 축이 검사되지 않는다(실측 헛돌이)
        assert "열거 실패" in err, f"⛔ '0건' 으로 보고됐다 — 못 세는 것과 셀 게 없는 것은 다르다: {err!r}"

    for n, f in [("full-derivation", c_full_derivation),
                 ("class-synonym-audited", c_class_synonym_audited),
                 ("class-unmappable-blank", c_class_unmappable_left_blank),
                 ("missing-date-blank", c_missing_date_left_blank),
                 ("existing-preserved", c_existing_fields_preserved),
                 ("dry-run-no-write", c_dry_run_no_write),
                 ("census-counts", c_census_counts),
                 ("empty-denominator-unrun", c_empty_unrun),
                 ("no-dir-unrun", c_no_dir_unrun),
                 ("enumeration-failure-unrun", c_enumeration_failure_unrun)]:
        case(n, f)

    print(f"self-test {len(passed)}/{cases} 통과")
    for x in passed:
        print(f"  ok   {x}")
    for x in failed:
        print(f"  FAIL {x}")
    return OK if not failed else INCOMPLETE


def main():
    ap = argparse.ArgumentParser(description="레지스트리 frontmatter 마이그레이션 (S17)")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."), help="레지스트리 루트")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--census", action="store_true", help="전수 census (기본)")
    g.add_argument("--apply", action="store_true", help="유도 가능한 필드를 기록한다")
    g.add_argument("--dry-run", action="store_true", help="무엇이 바뀔지만 인쇄")
    g.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.apply or a.dry_run:
        return apply(a.root, a.dry_run)
    return census(a.root)[0]


if __name__ == "__main__":
    sys.exit(main())
