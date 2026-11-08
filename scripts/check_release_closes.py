#!/usr/bin/env python3
# lint:no-root-anchor — 대상 레지스트리를 --findings-root 인자로 받는 외부 검사기다
"""릴리스 노트 `Closes:` 와 레지스트리 반영 기록(applied) 대조 — 고쳤는데 닫히지 않는 경로를 막는다.

배출의 자동 출구는 릴리스 노트 `Closes:` 하나다. 그런데 고친 엔트리를 노트에 적을지는 저자의 기억에 달려 있었다
(실측 F-550 — v4.52.0 에서 고쳤는데 Closes 누락). 이 검사기는 기대 집합을 **실행 때** live 엔트리의
`applied: full` 에서 계산해 노트와 대조한다 — 해시로 고정한 표가 없다(F-401: 판 중간에 생긴 엔트리를 놓친다).

위반 일곱:
  (a) applied: full 인데 Closes 에 없다
  (b) Closes 토큰의 엔트리가 applied: partial 이다(applied 가 없으면 WARN)
  (c) applied full|partial 인데 applied_ref 가 없음 · pending · 없는 커밋 · HEAD 비조상
  (d) 원장 승격 완료 절의 관측 엔트리가 live 인데 applied: full 이 아니다(D-2 — check_findings_hygiene 함수)
  (e) 원장 미등재 트랙 D 후보가 노트 `Track-D-Review:` 줄(그 failure_class 또는 묶음 F-ID)에 없다
  (f) Closes 줄에 ID · slug 가 아닌 토큰(산문 · 괄호 주석 · 부분 표기)
  (g) 판정 재료가 규약 밖 — applied 값이 full · partial · 없음 밖(오타 · 따옴표 · 빈 값) · `F-*.md` 이름이 `F-NNN-slug` 밖
      (조용히 건너뛰면 그 엔트리가 기대 집합에서 사라진다 · ID 는 eject · hygiene 과 같은 세 자리 — 넓히면 검사만 통과하고 배출이 거부한다)
같은 ID 의 live 엔트리가 둘 이상이면 판정 불가(2) — slug 를 ID 로 접으면 하나만 닫아도 형제가 통과한다.
`## 반영` 머리만 있고 applied 가 없는 엔트리는 기대 집합에 넣지 않고 NOTE 로만 보인다.

exit 0 통과 · 1 위반 · 2 판정 불가(레지스트리 · 노트 · git · 원장 부재 — 사유 한 줄, ⛔ 통과로 읽지 않는다)
⛔ 레지스트리를 쓰지 않는다(잠금 파일도 만들지 않는다). 배출은 eject_findings.py 가 한다.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
HERE = pathlib.Path(__file__).resolve().parent
SLUG = re.compile(r"^(F-\d{3}[a-z]?)-[a-z0-9-]+$")
ID = re.compile(r"^F-\d{3}[a-z]?$")
APPLIED_VALUES = (None, "full", "partial")
FM = re.compile(r"\A---\n(.*?)\n---", re.S)
APPLIED = re.compile(r"^applied:[ \t]*([^\s#]*)", re.M)
APPLIED_REF = re.compile(r"^applied_ref:[ \t]*([^\s#]*)", re.M)
CLOSES = re.compile(r"^Closes:[^\S\n]*(.*)$", re.M)
TRACK_D = re.compile(r"^Track-D-Review:[^\S\n]*(.*)$", re.M)
REFLECT = re.compile(r"^## 반영", re.M)
GIT = "git"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"_fz_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_entries(entries: pathlib.Path):
    """live 엔트리 → [{id, slug, applied, ref, reflect}]. 읽기 실패는 예외로 올린다(빈 목록으로 위장하지 않는다)."""
    rows = []
    for p in sorted(entries.iterdir()):
        m = SLUG.match(p.stem)
        if p.suffix != ".md" or not m:
            continue
        text = p.read_text(encoding="utf-8")
        fm = FM.match(text)
        fm = fm.group(1) if fm else ""
        a, r = APPLIED.search(fm), APPLIED_REF.search(fm)
        rows.append({"id": m.group(1), "slug": p.stem, "applied": a.group(1) if a else None,
                     "ref": r.group(1) if r and r.group(1) else None, "reflect": bool(REFLECT.search(text))})
    return rows


def odd_names(entries: pathlib.Path) -> list:
    """`F-*.md` 인데 `F-NNN-slug` 꼴이 아닌 파일 — read_entries 가 건너뛰는 것을 드러낸다."""
    return sorted(p.name for p in entries.glob("F-*.md") if not SLUG.match(p.stem))


def closes_tokens(note_text: str):
    """(정상 토큰, 거부 토큰). ⛔ eject 의 parse_closes 를 완화하지 않는다 — ID · slug 가 아니면 사유와 함께 거부한다."""
    good, bad = [], []
    for m in CLOSES.finditer(note_text):
        for t in re.split(r"[,\s]+", m.group(1).strip()):
            if t:
                (good if ID.match(t) or SLUG.match(t) else bad).append(t)
    return good, bad


def _git(repo: pathlib.Path, *args):
    return subprocess.run([GIT, "-C", str(repo), *args], capture_output=True, text=True)


def ref_problem(repo: pathlib.Path, ref):
    if not ref:
        return "applied_ref 가 없다"
    if ref == "pending":
        return "applied_ref 가 pending 이다 — 커밋 SHA 로 바꾼 뒤 릴리스한다"
    if not re.match(r"^[0-9a-f]{7,40}$", ref):
        return f"applied_ref {ref!r} 는 7~40자 hex 가 아니다"
    if _git(repo, "cat-file", "-e", f"{ref}^{{commit}}").returncode != 0:
        return f"applied_ref {ref} 커밋이 없다"
    if _git(repo, "merge-base", "--is-ancestor", ref, "HEAD").returncode != 0:
        return f"applied_ref {ref} 가 HEAD 의 조상이 아니다"
    return None


def check(root: pathlib.Path, note: pathlib.Path, repo: pathlib.Path, ledger: pathlib.Path | None = None) -> int:
    entries = root / "entries"
    ledger = ledger or repo / "modules" / "promotion-ledger.md"
    for what, ok in (("레지스트리 entries/", entries.is_dir()), ("릴리스 노트", note.is_file()), ("원장", ledger.is_file())):
        if not ok:
            print(f"UNRUN: {what} 없음 — 판정 불가 ({entries if 'entries' in what else note if '노트' in what else ledger})")
            return UNRUN
    try:
        head = _git(repo, "rev-parse", "HEAD")
    except OSError as e:
        print(f"UNRUN: git 을 실행하지 못했다 — {type(e).__name__} (판정 불가)")
        return UNRUN
    if head.returncode != 0:
        print(f"UNRUN: {repo} 가 git 저장소가 아니다 — 판정 불가")
        return UNRUN
    try:
        rows = read_entries(entries)
        note_text, ledger_text = note.read_text(encoding="utf-8"), ledger.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"UNRUN: 읽기 실패 — {e} (판정 불가)")
        return UNRUN
    if not rows:
        print(f"UNRUN: entries 에 엔트리가 0건 — 측정 실패를 먼저 의심한다 ({entries})")
        return UNRUN
    seen = {}
    for r in rows:
        seen.setdefault(r["id"], []).append(r["slug"])
    dup = {i: s for i, s in seen.items() if len(s) > 1}
    if dup:
        print(f"UNRUN: 같은 ID 의 live 엔트리 {len(dup)}쌍 — slug 를 ID 로 접으면 형제가 숨는다(판정 불가): "
              + " · ".join(f"{i}={','.join(s)}" for i, s in sorted(dup.items())))
        return UNRUN
    by_id = {r["id"]: r for r in rows}
    try:
        unreg, why = _load("fz_telemetry_report").track_d_unregistered(str(entries), str(ledger))
        promoted = None if why else _load("check_findings_hygiene").promoted_evidence_ids(ledger_text)
    except Exception as e:          # noqa: BLE001 — 의존 검사기를 못 부르면 판정 불가다(exit 1 = 위반과 겹치지 않게)
        print(f"UNRUN: 의존 검사기를 불러오지 못했다 — {type(e).__name__}: {e}")
        return UNRUN
    if why:
        print(f"UNRUN: 트랙 D 후보를 재지 못했다 — {why}")
        return UNRUN

    viol, warn, note_lines = [], [], []
    good, bad = closes_tokens(note_text)
    viol += [f"(f) Closes 토큰 {t!r} — ID · slug 만 적는다(산문 · 괄호 주석 · 부분 표기는 노트 본문으로)" for t in bad]
    viol += [f"(g) {r['id']}: applied 값 {r['applied']!r} 를 모른다(full · partial · 없음) — 고친 뒤 대조한다 ({r['slug']})"
             for r in rows if r["applied"] not in APPLIED_VALUES]
    viol += [f"(g) {n}: 엔트리 이름이 F-NNN-slug 꼴이 아니다 — 대조에서 빠진다" for n in odd_names(entries)]
    closed = {SLUG.match(t).group(1) if SLUG.match(t) else t for t in good}
    for r in rows:
        if r["applied"] == "full" and r["id"] not in closed:
            viol.append(f"(a) {r['id']}: applied: full 인데 Closes 에 없다 ({r['slug']})")
        if r["applied"] in ("full", "partial"):
            p = ref_problem(repo, r["ref"])
            if p:
                viol.append(f"(c) {r['id']}: {p}")
        if r["reflect"] and r["applied"] is None:
            note_lines.append(f"NOTE {r['id']}: `## 반영` 절만 있고 applied 가 없다 — 기대 집합 밖")
    for i in sorted(closed):
        r = by_id.get(i)
        if r and r["applied"] == "partial":
            viol.append(f"(b) {i}: Closes 에 있는데 applied: partial — 남은 축을 새 엔트리로 쪼갠 뒤 full 만 닫는다")
        elif r and r["applied"] is None:
            warn.append(f"WARN {i}: Closes 에 있는데 applied 기록이 없다")
    for i in sorted(promoted):
        if i in by_id and by_id[i]["applied"] != "full":
            viol.append(f"(d) {i}: 원장 승격 완료 절의 관측인데 live · applied: full 아님")
    declared = set()
    for m in TRACK_D.finditer(note_text):
        declared.update(t.strip("`") for t in re.split(r"[,\s]+", m.group(1)) if t)
    for c in unreg:
        if c["class"] not in declared and not any(mm["id"] in declared for mm in c["members"]):
            viol.append(f"(e) 트랙 D 후보 `{c['class']}`({' · '.join(mm['id'] for mm in c['members'])}) 원장 미등재 — "
                        "노트 `Track-D-Review:` 줄에 클래스나 묶음 ID 를 적는다")
    for line in warn + note_lines + viol:
        print(f"  {line}")
    if viol:
        print(f"VIOLATION: {len(viol)}건 (기대 applied: full {sum(r['applied'] == 'full' for r in rows)} · Closes {len(closed)})")
        return VIOLATION
    print(f"RELEASE_CLOSES_OK (applied: full {sum(r['applied'] == 'full' for r in rows)} · Closes {len(closed)} · 트랙 D 미등재 {len(unreg)} 선언)")
    return OK


def list_applied(root: pathlib.Path) -> int:
    entries = root / "entries"
    if not entries.is_dir():
        print(f"UNRUN: entries 디렉토리 없음 — {entries}")
        return UNRUN
    for r in read_entries(entries):
        if r["applied"] is not None:
            print(f"{r['id']} {r['applied'] or '-'} {r['ref'] or '-'} {r['slug']}")
    return OK


def self_test() -> int:
    import tempfile

    results = []

    def case(name, fn):
        try:
            fn()
            results.append((name, None))
        except AssertionError as e:
            results.append((name, str(e)))
        except Exception as e:      # 한 셀이 터져도 나머지가 돈다
            results.append((name, f"예외 {type(e).__name__}: {e}"))

    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        repo = base / "repo"
        (repo / "modules").mkdir(parents=True)

        def git(*a):
            subprocess.run([GIT, "-C", str(repo), *a], check=True, capture_output=True,
                           env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                                "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})

        git("init", "-q", "-b", "main")
        (repo / "a.txt").write_text("a")
        git("add", "."); git("commit", "-qm", "a")
        anc = _git(repo, "rev-parse", "HEAD").stdout.strip()
        git("checkout", "-qb", "side"); (repo / "b.txt").write_text("b"); git("add", "."); git("commit", "-qm", "b")
        side = _git(repo, "rev-parse", "HEAD").stdout.strip()
        git("checkout", "-q", "main")
        ledger = repo / "modules" / "promotion-ledger.md"
        LEDGER0 = "# 원장\n\n### D-1: x (트랙 D 관측 #1)\n\n- 관측 #1: **F-050**\n- ✅ **승격 완료 (2026-01-01)**: x\n"
        seq = [0]

        def reg(entries, note, ledger_text=LEDGER0):
            seq[0] += 1
            root = base / f"r{seq[0]}"
            (root / "entries").mkdir(parents=True)
            for fid, extra in entries:
                (root / "entries" / f"{fid}-x.md").write_text(f"---\nid: {fid}\nstatus: open\n{extra}---\n\n# {fid}\n", encoding="utf-8")
            n = base / f"n{seq[0]}.md"
            n.write_text(note, encoding="utf-8")
            ledger.write_text(ledger_text, encoding="utf-8")
            return root, n

        def run(root, n):
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check(root, n, repo, ledger)
            return rc, buf.getvalue()

        full = f"applied: full\napplied_ref: {anc[:7]}\n"
        base_rows = [("F-050", full), ("F-051", "")]

        def expect(rc_want, needle, entries, note, ledger_text=LEDGER0):
            root, n = reg(entries, note, ledger_text)
            rc, out = run(root, n)
            assert rc == rc_want and needle in out, f"rc={rc} want={rc_want} · {needle!r} 없음\n{out}"

        case("applied-full-not-closed", lambda: expect(VIOLATION, "(a) F-050", base_rows, "# v\n\nCloses: F-051\n"))
        case("partial-in-closes", lambda: expect(VIOLATION, "(b) F-052", base_rows + [("F-052", f"applied: partial\napplied_ref: {anc[:7]}\n")],
                                                 "Closes: F-050, F-052\n"))
        case("applied-ref-pending-at-release", lambda: expect(VIOLATION, "(c) F-053: applied_ref 가 pending",
                                                              base_rows + [("F-053", "applied: partial\napplied_ref: pending\n")], "Closes: F-050\n"))
        case("applied-ref-nonexistent", lambda: expect(VIOLATION, "커밋이 없다",
                                                       [("F-050", "applied: full\napplied_ref: deadbee\n")], "Closes: F-050\n"))
        case("applied-ref-not-ancestor", lambda: expect(VIOLATION, "HEAD 의 조상이 아니다",
                                                        [("F-050", f"applied: full\napplied_ref: {side[:9]}\n")], "Closes: F-050\n"))
        case("promoted-evidence-live", lambda: expect(VIOLATION, "(d) F-050", [("F-050", ""), ("F-051", "")], "Closes: F-051\n"))
        TD = "date: 2026-10-0{d}\nfailure_class: td-x\n"
        td_rows = base_rows + [("F-060", TD.format(d=1)), ("F-061", TD.format(d=2))]
        case("track-d-undeclared", lambda: expect(VIOLATION, "(e) 트랙 D 후보 `td-x`", td_rows, "Closes: F-050\n"))
        case("track-d-unrelated-declaration-fails", lambda: expect(VIOLATION, "(e) 트랙 D 후보 `td-x`", td_rows,
                                                                    "Closes: F-050\nTrack-D-Review: other-class, F-099 — 무관\n"))
        case("track-d-declared-ok", lambda: expect(OK, "RELEASE_CLOSES_OK", td_rows, "Closes: F-050\nTrack-D-Review: td-x — 다음 판 판정\n"))

        def mid_version():
            root, n = reg(base_rows, "Closes: F-050\n")
            assert run(root, n)[0] == OK, "정상 노트가 통과하지 않았다"
            (root / "entries" / "F-070-x.md").write_text(f"---\nid: F-070\nstatus: open\n{full}---\n# F-070\n", encoding="utf-8")
            rc, out = run(root, n)
            assert rc == VIOLATION and "(a) F-070" in out, f"판 중간에 생긴 full 엔트리를 기대 집합에 넣지 않았다\n{out}"
        case("mid-version-entry-expected", mid_version)
        case("closes-prose-rejected", lambda: expect(VIOLATION, "(f) Closes 토큰 '(부분)'", base_rows, "Closes: F-050 (부분)\n"))

        def reflect_note():
            root, n = reg(base_rows, "Closes: F-050\n")
            p = root / "entries" / "F-051-x.md"
            p.write_text(p.read_text(encoding="utf-8") + "\n## 반영 (x)\n- 일부\n", encoding="utf-8")
            rc, out = run(root, n)
            assert rc == OK and "NOTE F-051" in out and "(a) F-051" not in out, f"반영 머리만 있는 엔트리 처리 rc={rc}\n{out}"
        case("reflect-heading-note-only", reflect_note)

        def unrun(kind):
            def fn():
                root, n = reg(base_rows, "Closes: F-050\n")
                if kind == "root":
                    root = base / "absent"
                elif kind == "note":
                    n = base / "absent.md"
                rc, out = run(root, n)
                assert rc == UNRUN and "UNRUN" in out and "RELEASE_CLOSES_OK" not in out, f"{kind} 부재인데 rc={rc}\n{out}"
            return fn
        case("registry-root-missing-unrun", unrun("root"))
        case("note-missing-unrun", unrun("note"))

        def git_missing():
            global GIT
            root, n = reg(base_rows, "Closes: F-050\n")
            old, GIT = GIT, str(base / "no-git")
            try:
                rc, out = run(root, n)
            finally:
                GIT = old
            assert rc == UNRUN and "git" in out, f"git 부재인데 rc={rc}\n{out}"
        case("git-missing-unrun", git_missing)

        def never_writes():
            root, n = reg(td_rows + [("F-052", "applied: partial\napplied_ref: pending\n")], "Closes: F-052 (x)\n")
            before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            run(root, n)
            after = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            assert before == after, "검사기가 레지스트리를 바꿨다(잠금 파일 포함)"
        case("checker-never-writes-registry", never_writes)
        case("clean-release-ok", lambda: expect(OK, "RELEASE_CLOSES_OK", base_rows, "# v\n\nCloses: F-050\n"))

    bad = [(n, e) for n, e in results if e]
    for n, e in results:
        print(f"{'PASS' if not e else 'FAIL'} {n}" + (f" — {e}" if e else ""))
    print(f"self-test {len(results) - len(bad)}/{len(results)} 통과")
    return OK if not bad else VIOLATION


def main() -> int:
    ap = argparse.ArgumentParser(description="릴리스 노트 Closes ↔ 레지스트리 applied 대조")
    ap.add_argument("--findings-root", type=pathlib.Path, help="레지스트리 루트 (entries/ 보유)")
    ap.add_argument("--note", type=pathlib.Path, help="릴리스 노트")
    ap.add_argument("--repo", type=pathlib.Path, default=HERE.parent, help="applied_ref 를 대조할 플러그인 저장소(기본: 이 트리)")
    ap.add_argument("--ledger", type=pathlib.Path, help="promotion-ledger.md (기본: --repo/modules)")
    ap.add_argument("--list-applied", action="store_true", help="applied 가 있는 엔트리를 'F-NNN 값 ref slug' 로 낸다")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.findings_root:
        ap.error("--findings-root 가 필요하다 (또는 --self-test)")
    if a.list_applied:
        return list_applied(a.findings_root)
    if not a.note:
        ap.error("--note 가 필요하다 (또는 --list-applied)")
    return check(a.findings_root, a.note, a.repo, a.ledger)


if __name__ == "__main__":
    sys.exit(main())
