#!/usr/bin/env python3
"""check_asset_census.py — 자산이 **어디에서도 참조되지 않는가**(고아) (B13 / v7 S21).

왜: 모듈·에이전트·워크플로는 다른 문서가 `참조:` 로 부를 때만 로드된다. 참조가 끊기면
그 파일은 남아 있지만 **아무도 읽지 않는다** — 삭제된 것과 같은데 트리에는 보인다.
플랜 v9 §1-1 이 이 census 를 손으로 한 번 돌려 `51/51 참조 · 고아 0` 을 기록했는데,
**그 조사를 고정하는 검사가 없어서** 다음에 끊기면 아무도 모른다.

⛔ **모집단·추출 규약을 먼저 고정한다** (플랜 D3 verify #15 의 같은 원칙):
   스스로 고른 행 수와 합계를 맞추면 누락이 통과한다. 여기서는 glob 이 모집단이고,
   그 수를 **분모로 함께 인쇄**한다.

⛔ **참조 판정은 경로 문자열이다** — 파일 stem 만으로 grep 하면 산문의 같은 단어가 걸린다
   (실측: `adversarial` stem 은 32곳, 실제 경로 참조는 2곳).

exit code:
  0  PASS — 고아 0
  1  VIOLATION — 고아가 있다 (참조를 잇거나 파일을 지운다)
  2  UNRUN — 모집단 0건·읽기 실패 등 판정 불가. ⛔ 통과로 읽지 않는다

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 모집단 — 「참조돼야 비로소 작동하는」 자산만. 진입점(SKILL.md·CLAUDE.md)은 제외한다.
POPULATION = ("modules/**/*.md", "agents/*.md", "workflows/*.js", "templates/*.md")
# 참조를 찾을 곳
SEARCH = ("*.md", "*.js", "*.py", "*.sh", "*.json")
# ⛔ 자기 자신·사료는 참조 근거로 세지 않는다 — 사료가 사료를 가리키면 둘 다 고아인데 살아 보인다
NOT_A_REFERRER = ("docs/releases/", "CHANGELOG.md", ".fz-work/")


def log(*a):
    print(*a, file=sys.stderr)


def corpus(root: pathlib.Path):
    """참조를 찾을 파일 목록. ⛔ `iterdir` 계열로 읽어 열거 실패를 삼키지 않는다."""
    out = []
    for pat in SEARCH:
        out.extend(root.rglob(pat))
    keep = []
    for q in out:
        rel = q.relative_to(root).as_posix()
        if rel.startswith((".git/", "node_modules/")):
            continue
        if any(rel.startswith(x) or x in rel for x in NOT_A_REFERRER):
            continue
        keep.append(q)
    return keep


def census(root: pathlib.Path):
    assets = []
    for pat in POPULATION:
        assets.extend(sorted(root.glob(pat)))
    assets = sorted({q for q in assets if q.is_file()})
    if not assets:
        log(f"UNRUN: 모집단이 0건 — {root} (측정 실패를 먼저 의심한다)")
        return UNRUN

    files = corpus(root)
    if not files:
        log("UNRUN: 참조를 찾을 파일이 0건 — 스캔 실패를 의심한다")
        return UNRUN

    try:
        blobs = [(q, q.read_text(encoding="utf-8", errors="replace")) for q in files]
    except OSError as e:
        log(f"UNRUN: 읽기 실패 — {type(e).__name__}: {e}")
        return UNRUN

    orphans = []
    for a in assets:
        rel = a.relative_to(root).as_posix()
        # ⛔ **경로 문자열**로 찾는다. stem 만 쓰면 산문이 걸린다.
        if not any(rel in t for q, t in blobs if q.resolve() != a.resolve()):
            orphans.append(rel)

    print(f"분모: 자산 {len(assets)}개 · 참조 탐색 대상 {len(files)}개 파일")
    print(f"  참조됨                             : {len(assets) - len(orphans)}")
    print(f"  고아(어디서도 경로로 불리지 않음)     : {len(orphans)}")
    for o in orphans:
        print(f"      {o}")
    if orphans:
        log(f"VIOLATION: 고아 자산 {len(orphans)}건 — 참조를 잇거나 파일을 지워라")
        return VIOLATION
    print("OK: 전 자산이 경로로 참조된다")
    return OK


def self_test():
    """행동 fixture — 고아에서 **실패**, 참조를 이으면 **통과** (플랜 verify #5)."""
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

    def mk(root, assets, referrers):
        for rel, body in assets.items():
            q = root / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(body, encoding="utf-8")
        for rel, body in referrers.items():
            q = root / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(body, encoding="utf-8")
        return root

    def c_referenced_passes(tmp):
        r = mk(tmp / "r", {"modules/X.md": "# a\n"},
               {"skills/x/SKILL.md": "참조: `modules/X.md`\n"})
        assert census(r) == OK, "참조가 있는데 고아로 판정했다"

    def c_orphan_detected(tmp):
        r = mk(tmp / "r", {"modules/X.md": "# a\n", "modules/Y.md": "# lonely\n"},
               {"skills/x/SKILL.md": "참조: `modules/X.md`\n"})
        assert census(r) == VIOLATION, "⛔ 고아를 놓쳤다"

    def c_stem_is_not_reference(tmp):
        """⛔ 산문의 같은 단어는 참조가 아니다 — 실측: stem 32곳 vs 경로 2곳."""
        r = mk(tmp / "r", {"modules/X.md": "# adv\n"},
               {"skills/x/SKILL.md": "X 리뷰를 수행한다 (경로 참조 아님)\n"})
        assert census(r) == VIOLATION, "⛔ 산문 언급을 경로 참조로 셌다"

    def c_self_reference_not_counted(tmp):
        r = mk(tmp / "r", {"modules/X.md": "이 파일은 modules/X.md 다\n"}, {})
        assert census(r) == VIOLATION, "⛔ 자기 참조를 근거로 셌다"

    def c_release_note_not_referrer(tmp):
        """⛔ 사료(릴리즈 노트)가 가리키는 것만으로는 살아 있다고 보지 않는다."""
        r = mk(tmp / "r", {"modules/X.md": "# old\n"},
               {"docs/releases/v1.0.0.md": "modules/X.md 를 신설했다\n",
                "skills/x/SKILL.md": "# x\n"})
        assert census(r) == VIOLATION, "⛔ 릴리즈 노트를 현행 참조로 셌다"

    def c_workflow_asset_covered(tmp):
        r = mk(tmp / "r", {"workflows/w.js": "// w\n"}, {"skills/x/SKILL.md": "# x\n"})
        assert census(r) == VIOLATION, "⛔ 모집단에 workflows/ 가 빠졌다"

    def c_empty_population_unrun(tmp):
        r = tmp / "r"
        (r / "skills").mkdir(parents=True)
        (r / "skills" / "x.md").write_text("# x\n", encoding="utf-8")
        assert census(r) == UNRUN, "⛔ 모집단 0건이 통과했다 — 0건은 측정 실패를 먼저 의심"

    for n, f in [("referenced-passes", c_referenced_passes),
                 ("orphan-detected", c_orphan_detected),
                 ("stem-is-not-reference", c_stem_is_not_reference),
                 ("self-reference-not-counted", c_self_reference_not_counted),
                 ("release-note-not-referrer", c_release_note_not_referrer),
                 ("workflow-asset-covered", c_workflow_asset_covered),
                 ("empty-population-unrun", c_empty_population_unrun)]:
        case(n, f)

    print(f"self-test {len(passed)}/{cases} 통과")
    for x in passed:
        print(f"  ok   {x}")
    for x in failed:
        print(f"  FAIL {x}")
    return OK if not failed else VIOLATION


def main():
    ap = argparse.ArgumentParser(description="자산 고아 census (B13 / S21)")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(SCRIPT_DIR).parent)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else census(a.root)


if __name__ == "__main__":
    sys.exit(main())
