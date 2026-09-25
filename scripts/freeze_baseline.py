#!/usr/bin/env python3
"""freeze_baseline.py — Wave B 의 비교 기준을 동결한다 (B15).

왜: Wave B·D 는 하네스를 **감량·측정**한다. 그런데 "무엇과 비교해서 줄었나" 의 그 *무엇*이
없으면 나중에 어떤 수치를 내도 해석할 수 없다. 이 스크립트는 그 기준점 하나를 만든다.

동결 대상 두 가지 (플랜 v9 B15):
  1. **트리 manifest** — 파일 경로 → sha256. 어떤 파일이 어떤 내용이었는지
  2. **`--refs` 근거 스냅샷** — `measure_constraint_load.py --refs <skill>` 의 판정 근거.
     floor/ceiling 수치만 남기면 *왜 그 수치인지* 를 6주 뒤 재구성할 수 없다

⛔ 파일 목록은 직접 걷지 않고 `git ls-files --cached --others --exclude-standard` 를 쓴다 —
   git 이 이미 "이 트리에 속한 파일" 을 권위 있게 정의하고 `.gitignore` 도 해석한다.
   직접 walk 하면 제외 규칙을 재구현하게 되고, 그 재구현이 어긋나는 순간 baseline 이
   비결정적이 된다.

exit code:
  0  PASS — 동결 성공 · 또는 재계산이 manifest 와 일치
  1  MISMATCH — 재계산이 manifest 와 다르다 (그것이 이 도구의 목적이다)
  2  UNRUN — git 부재·manifest 부재·읽기 실패 등 **판정 불가**. ⛔ 통과로 읽지 않는다

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys

OK, MISMATCH, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — `lint_contracts.py` ANCHOR_LINES 의 **허용 형태와 정확히 일치**해야 한다.
#    `pathlib.Path(__file__)…` 는 화이트리스트에 없다(bare `Path` 만). fail-closed 이므로
#    "동작은 같다" 로는 통과하지 않는다 — 형태를 맞춘다.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = pathlib.Path(SCRIPT_DIR).parent
DEFAULT_OUT = "tests/fixtures/baseline-manifest.json"
DEFAULT_REFS = "tests/fixtures/baseline-refs.txt"


def log(*a):
    print(*a, file=sys.stderr)


def git(root: pathlib.Path, *args):
    """git 호출. 실패는 None — 호출부가 UNRUN 으로 올린다."""
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def tree_files(root: pathlib.Path, exclude=()):
    """git 이 보는 트리 파일 목록 (추적 + 미추적 비무시).

    ⛔ `exclude` 로 **baseline 산출물 자신을 뺀다.** manifest 는 자기 해시를 담을 수 없고
    (닭과 달걀), 산출물을 포함하면 동결 직후 검증이 곧바로 "파일 2개 추가" 로 불일치한다.
    refs 파일은 `files` 대신 `refs_sha256` 이 별도로 보호한다 — 두 방어는 독립이다.
    """
    out = git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    if out is None:
        return None
    ex = set(exclude)
    return sorted(set(l for l in out.splitlines() if l.strip() and l not in ex))


def hash_file(p: pathlib.Path):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_hashes(root: pathlib.Path, files):
    """경로 → sha256. 읽기 실패는 **따로 돌려준다** — 조용히 빼면 분모가 줄어든다."""
    got, unread = {}, []
    for rel in files:
        fp = root / rel
        try:
            got[rel] = hash_file(fp)
        except OSError as e:
            unread.append(f"{rel}: {type(e).__name__}")
    return got, unread


def collect_refs(root: pathlib.Path, skills_dir="skills"):
    """`--refs` 근거를 스킬별로 모은다. 실패한 스킬은 목록으로 돌려준다."""
    sd = root / skills_dir
    if not sd.is_dir():
        return None, [f"{skills_dir}/ 디렉토리 없음"]
    script = root / "scripts" / "measure_constraint_load.py"
    if not script.is_file():
        return None, ["scripts/measure_constraint_load.py 없음"]
    chunks, failed = [], []
    for skill in sorted(q.name for q in sd.iterdir() if q.is_dir()):
        try:
            r = subprocess.run([sys.executable, str(script), "--refs", skill],
                               capture_output=True, text=True, timeout=120, cwd=str(root))
        except (OSError, subprocess.SubprocessError) as e:
            failed.append(f"{skill}: {type(e).__name__}")
            continue
        if r.returncode != 0:
            failed.append(f"{skill}: exit {r.returncode}")
            continue
        chunks.append(f"===== {skill} =====\n{r.stdout.rstrip()}\n")
    return "\n".join(chunks), failed


def freeze(root: pathlib.Path, out_rel: str, refs_rel: str, date: str):
    files = tree_files(root, exclude=(out_rel, refs_rel))
    if files is None:
        log(f"UNRUN: git 호출 실패 — {root} 가 git 저장소가 아니거나 git 이 없다")
        return UNRUN
    if not files:
        log("UNRUN: 트리 파일이 0건 — 측정 실패를 먼저 의심한다")
        return UNRUN

    got, unread = collect_hashes(root, files)
    if unread:
        log(f"UNRUN: 읽기 실패 {len(unread)}건 — 부분 manifest 를 만들지 않는다")
        for u in unread[:5]:
            log(f"  {u}")
        return UNRUN

    refs, refs_failed = collect_refs(root)
    if refs is None:
        log(f"UNRUN: --refs 근거를 수집할 수 없다 — {refs_failed}")
        return UNRUN
    if refs_failed:
        # ⛔ 일부 스킬 실패는 **동결 실패**다. 반쪽 근거를 기준점으로 삼으면
        #    나중 비교가 "줄어든 것" 인지 "안 재진 것" 인지 구별되지 않는다.
        log(f"UNRUN: --refs 수집이 {len(refs_failed)}개 스킬에서 실패 — 부분 근거로 동결하지 않는다")
        for f in refs_failed[:5]:
            log(f"  {f}")
        return UNRUN

    refs_path = root / refs_rel
    refs_path.parent.mkdir(parents=True, exist_ok=True)
    refs_path.write_text(refs, encoding="utf-8")
    refs_hash = hashlib.sha256(refs.encode("utf-8")).hexdigest()

    head = (git(root, "rev-parse", "HEAD") or "").strip() or None
    dirty = git(root, "status", "--porcelain", "--untracked-files=all") or ""
    manifest = {
        "schema": 1,
        "date": date,
        "git_head": head,
        # ⛔ 동결 시점에 미커밋이 있었는지 남긴다 — 나중에 "어느 커밋과 같은가" 를
        #    물으면 답이 '어느 커밋과도 같지 않다' 일 수 있다
        "uncommitted_at_freeze": len([l for l in dirty.splitlines() if l.strip()]),
        "file_count": len(got),
        "refs_file": refs_rel,
        "refs_sha256": refs_hash,
        "files": got,
    }
    out_path = root / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"동결 완료 — 파일 {len(got)}건 · refs {len(refs.splitlines())}줄 · HEAD {head[:8] if head else '?'}"
          + (f" · 미커밋 {manifest['uncommitted_at_freeze']}건" if manifest["uncommitted_at_freeze"] else ""))
    print(f"  manifest: {out_rel}")
    print(f"  refs    : {refs_rel} (sha256 {refs_hash[:12]}…)")
    return OK


def verify(root: pathlib.Path, out_rel: str):
    mp = root / out_rel
    if not mp.is_file():
        log(f"UNRUN: manifest 없음 — {mp} (먼저 --freeze)")
        return UNRUN
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log(f"UNRUN: manifest 를 읽을 수 없다 — {e}")
        return UNRUN
    want = man.get("files")
    if not isinstance(want, dict) or not want:
        log("UNRUN: manifest 에 files 가 없거나 비었다 — 측정 실패를 먼저 의심한다")
        return UNRUN

    files = tree_files(root, exclude=(out_rel, man.get("refs_file") or DEFAULT_REFS))
    if files is None:
        log("UNRUN: git 호출 실패")
        return UNRUN
    got, unread = collect_hashes(root, files)
    if unread:
        log(f"UNRUN: 읽기 실패 {len(unread)}건 — 판정 불가")
        return UNRUN

    added = sorted(set(got) - set(want))
    removed = sorted(set(want) - set(got))
    changed = sorted(k for k in set(got) & set(want) if got[k] != want[k])

    refs_rel = man.get("refs_file")
    refs_state = "—"
    if refs_rel:
        rp = root / refs_rel
        if not rp.is_file():
            refs_state = "⛔ 부재"
        else:
            try:
                cur = hashlib.sha256(rp.read_bytes()).hexdigest()
                refs_state = "일치" if cur == man.get("refs_sha256") else "⛔ 불일치"
            except OSError as e:
                log(f"UNRUN: refs 파일 읽기 실패 — {e}")
                return UNRUN

    print(f"기준: {man.get('date')} · 파일 {len(want)}건 · HEAD {str(man.get('git_head'))[:8]}")
    print(f"현재: 파일 {len(got)}건 · 추가 {len(added)} · 삭제 {len(removed)} · 변경 {len(changed)} · refs {refs_state}")
    for k in added[:10]:
        print(f"  + {k}")
    for k in removed[:10]:
        print(f"  - {k}")
    for k in changed[:10]:
        print(f"  ~ {k}")
    n = len(added) + len(removed) + len(changed)
    if n > 30:
        print(f"  … 외 {n - 30}건")
    if n or refs_state.startswith("⛔"):
        log(f"MISMATCH: 기준과 다르다 (추가 {len(added)} · 삭제 {len(removed)} · 변경 {len(changed)} · refs {refs_state})")
        return MISMATCH
    print("PASS: 재계산이 manifest 와 일치한다")
    return OK


def self_test():
    """fixture — 동결·일치·변경·추가·삭제·refs변조·manifest부재·빈트리·읽기실패.

    ⛔ 각 fixture 는 **해당 방어를 제거하면 실패**해야 한다(ablation). 통과만으로는 증거가 아니다.
    """
    import os
    import tempfile

    passed, failed, cases = [], [], 0

    def case(name, fn):
        nonlocal cases
        cases += 1
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(pathlib.Path(tmp))
                passed.append(name)
            except AssertionError as e:
                failed.append(f"{name}: {e}")
            except Exception as e:
                # ⛔ AssertionError 만 잡으면 fixture 하나가 터질 때 뒤가 전부 안 돈다
                failed.append(f"{name}: ⛔ 예외 {type(e).__name__}: {e}")

    def mkrepo(root, files=None, with_measure=True, skills=("a",)):
        root.mkdir(parents=True, exist_ok=True)
        for a in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(root), *a], capture_output=True)
        (root / "scripts").mkdir(exist_ok=True)
        for sk in skills:
            d = root / "skills" / sk
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(f"# {sk}\n", encoding="utf-8")
        if with_measure:
            (root / "scripts" / "measure_constraint_load.py").write_text(
                "import sys\nprint('refs', sys.argv[-1])\n", encoding="utf-8")
        for rel, body in (files or {"a.md": "A\n"}).items():
            fp = root / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(body, encoding="utf-8")
        return root

    def c_freeze_then_verify(tmp):
        r = mkrepo(tmp / "r")
        assert freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01") == OK, "동결 실패"
        assert (r / DEFAULT_OUT).is_file() and (r / DEFAULT_REFS).is_file(), "산출물 부재"
        assert verify(r, DEFAULT_OUT) == OK, "동결 직후 검증이 불일치"

    def c_content_change_detected(tmp):
        r = mkrepo(tmp / "r")
        assert freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01") == OK
        (r / "a.md").write_text("A CHANGED\n", encoding="utf-8")
        assert verify(r, DEFAULT_OUT) == MISMATCH, "⛔ 내용 변경을 못 잡았다"

    def c_file_added_detected(tmp):
        r = mkrepo(tmp / "r")
        assert freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01") == OK
        (r / "b.md").write_text("B\n", encoding="utf-8")
        assert verify(r, DEFAULT_OUT) == MISMATCH, "⛔ 파일 추가를 못 잡았다"

    def c_file_removed_detected(tmp):
        r = mkrepo(tmp / "r")
        assert freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01") == OK
        (r / "a.md").unlink()
        assert verify(r, DEFAULT_OUT) == MISMATCH, "⛔ 파일 삭제를 못 잡았다"

    def c_refs_tamper_detected(tmp):
        r = mkrepo(tmp / "r")
        assert freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01") == OK
        # ⛔ refs 는 `files` 에서 제외돼 있다(자기 참조 회피). 그러면 **무엇이 지키는가** —
        #    `refs_sha256` 하나뿐이다. 그것이 실제로 잡는지 본다.
        rp = r / DEFAULT_REFS
        rp.write_text(rp.read_text(encoding="utf-8") + "TAMPER\n", encoding="utf-8")
        man = json.loads((r / DEFAULT_OUT).read_text(encoding="utf-8"))
        assert DEFAULT_REFS not in man["files"], "refs 가 files 에 있다 — 자기 참조 회피가 안 됐다"
        assert verify(r, DEFAULT_OUT) == MISMATCH, "⛔ refs 변조를 refs_sha256 이 못 잡았다"

    def c_missing_manifest_unrun(tmp):
        r = mkrepo(tmp / "r")
        rc = verify(r, DEFAULT_OUT)
        assert rc == UNRUN, f"⛔ manifest 부재인데 rc={rc} (UNRUN 이어야 한다)"

    def c_not_a_git_repo_unrun(tmp):
        r = tmp / "plain"
        (r / "scripts").mkdir(parents=True)
        (r / "a.md").write_text("A\n", encoding="utf-8")
        rc = freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01")
        assert rc == UNRUN, f"⛔ git 저장소가 아닌데 rc={rc}"

    def c_empty_tree_unrun(tmp):
        """⛔ 0건은 측정 실패를 먼저 의심한다.

        ⛔ **가드를 격리한다** — 이전 판은 `skills/` 가 없어서 refs 수집 실패로 UNRUN 이 났고,
        빈 트리 가드를 제거해도 통과했다(헛돌이). 여기서는 refs 가 정상 동작하도록 파일을
        두되 `.gitignore: *` 로 **git 이 보는 목록만 0건**으로 만든다.
        """
        r = mkrepo(tmp / "r")
        (r / ".gitignore").write_text("*\n", encoding="utf-8")   # .gitignore 자신도 `*` 에 걸린다
        assert tree_files(r) == [], f"전제 불성립 — 트리가 비지 않았다: {tree_files(r)[:3]}"
        rc = freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01")
        assert rc == UNRUN, f"⛔ 빈 트리인데 rc={rc}"

    def c_partial_refs_refuses_freeze(tmp):
        """⛔ 일부 스킬의 --refs 가 실패하면 **반쪽 근거로 동결하지 않는다**."""
        r = mkrepo(tmp / "r", skills=("a", "b"))
        (r / "scripts" / "measure_constraint_load.py").write_text(
            "import sys\n"
            "sys.exit(3) if sys.argv[-1] == 'b' else print('refs', sys.argv[-1])\n", encoding="utf-8")
        rc = freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01")
        assert rc == UNRUN, f"⛔ refs 부분 실패인데 rc={rc} — 반쪽 기준점이 만들어졌다"
        assert not (r / DEFAULT_OUT).exists(), "실패인데 manifest 를 남겼다"

    def c_unreadable_file_unrun(tmp):
        r = mkrepo(tmp / "r")
        real = hash_file

        def boom(p):
            if p.name == "a.md":
                raise PermissionError("주입")
            return real(p)

        g = globals()
        g["hash_file"] = boom
        try:
            rc = freeze(r, DEFAULT_OUT, DEFAULT_REFS, "2026-01-01")
        finally:
            g["hash_file"] = real
        assert rc == UNRUN, f"⛔ 읽기 실패인데 rc={rc} — 부분 manifest 를 만들면 안 된다"

    for n, f in [("freeze-then-verify", c_freeze_then_verify),
                 ("content-change", c_content_change_detected),
                 ("file-added", c_file_added_detected),
                 ("file-removed", c_file_removed_detected),
                 ("refs-tamper", c_refs_tamper_detected),
                 ("missing-manifest-unrun", c_missing_manifest_unrun),
                 ("not-git-repo-unrun", c_not_a_git_repo_unrun),
                 ("empty-tree-unrun", c_empty_tree_unrun),
                 ("partial-refs-refuses", c_partial_refs_refuses_freeze),
                 ("unreadable-file-unrun", c_unreadable_file_unrun)]:
        case(n, f)

    print(f"self-test {len(passed)}/{cases} 통과")
    for x in passed:
        print(f"  ok   {x}")
    for x in failed:
        print(f"  FAIL {x}")
    return OK if not failed else MISMATCH


def main():
    ap = argparse.ArgumentParser(description="Wave B 비교 기준 동결 (B15)")
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT, help="플러그인 루트")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"manifest 경로 (기본 {DEFAULT_OUT})")
    ap.add_argument("--refs-out", default=DEFAULT_REFS, help=f"refs 근거 경로 (기본 {DEFAULT_REFS})")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--freeze", action="store_true", help="현재 트리를 기준으로 동결")
    g.add_argument("--verify", action="store_true", help="재계산이 manifest 와 일치하는지")
    g.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.freeze:
        return freeze(a.root, a.out, a.refs_out, a.date)
    return verify(a.root, a.out)


if __name__ == "__main__":
    sys.exit(main())
