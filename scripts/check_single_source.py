#!/usr/bin/env python3
# lint:no-root-anchor — 루트를 `--root` 로 받는다(기본값은 이 파일 기준 부모 상수).
"""같은 사실이 **한 곳에서만 선언**되는지 검사한다 (C4 / N10·S9 잔여).

⛔ 왜 필요한가: *"TEAM 메커니즘 일몰은 확산 판정 시 결정"* 이 스킬 3곳에 **같은 문장으로
   복제**돼 있었다. 결정 주체도 시점도 없는 미결이 세 벌로 흩어지면 어느 쪽을 고쳐야 하는지가
   문서에 없다. 통합 후에도 **재복제를 막는 것은 절차가 아니라 검사**다.

판정은 **정수 단언**이다 — 부분 문자열 존재로 판단하지 않는다. "있다/없다" 는 몇 벌인지를
말해주지 않으므로, 두 벌로 늘어난 것을 놓친다.

  canonical 선언 수 == 1   (0 이면 정본 소실 · 2+ 면 정본이 갈렸다)
  consumer 선언 수  == 0   (소비자는 **가리키기만** 한다)
  consumer 언급이 있으면 그 줄이 정본을 **참조**해야 한다

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# ⛔ 사실 하나가 표의 한 행이다. 새 사실을 넣을 때 코드가 아니라 이 표만 늘린다.
FACTS = [
    {
        "name": "TEAM 메커니즘 일몰 미결",
        "canonical_file": "modules/promotion-ledger.md",
        # 정본은 **heading** 으로 센다 — 산문 언급이 정본으로 오인되지 않게
        "canonical_re": r"^##\s*미결 안건 — TEAM 메커니즘 일몰",
        "consumer_globs": ["skills/*/SKILL.md", "skills/*/*/*.md", "guides/*.md"],
        # 소비자에 있으면 **재복제**인 선언 문구
        "declaration_re": r"확산 판정 시 결정",
        # 소비자가 정본을 가리키는 형태
        "reference_re": r"promotion-ledger\.md",
        "mention_re": r"TEAM 일몰",
    },
]


def read(q: pathlib.Path) -> str:
    return q.read_text(encoding="utf-8", errors="replace")


def audit(root: pathlib.Path) -> dict:
    v, unread, rows = [], [], []
    for f in FACTS:
        cf = root / f["canonical_file"]
        if not cf.is_file():
            # ⛔ 정본 파일 부재는 "위반 0건" 이 아니라 측정 실패다
            unread.append(f"{f['canonical_file']} 부재 — {f['name']} 판정 불가")
            continue
        can_n = len(re.findall(f["canonical_re"], read(cf), re.M))

        decl_n, mention_lines, decl_where = 0, [], []
        for g in f["consumer_globs"]:
            for q in sorted(root.glob(g)):
                if q.resolve() == cf.resolve():
                    continue          # 정본 자신은 소비자가 아니다
                try:
                    t = read(q)
                except OSError as e:
                    unread.append(f"{q.relative_to(root).as_posix()}: {type(e).__name__}")
                    continue
                for i, ln in enumerate(t.splitlines(), 1):
                    if re.search(f["declaration_re"], ln):
                        # ⛔ 여기서 위반을 쌓지 않는다 — **위치만** 모은다. 줄마다 위반을 넣으면
                        #    아래 정수 단언이 죽은 로직이 되고(어블레이션에서 제거해도 통과했다),
                        #    계획이 요구한 *"정수로 단언"* 이 형식만 남는다.
                        decl_n += 1
                        decl_where.append(f"{q.relative_to(root).as_posix()}:{i}")
                    elif re.search(f["mention_re"], ln) and not re.search(f["reference_re"], ln):
                        mention_lines.append(f"{q.relative_to(root).as_posix()}:{i}")

        # ⛔ **정수 단언** — 존재 여부가 아니라 개수다
        if can_n != 1:
            v.append(f"정본 선언 수 {can_n} (기대 1) — 0 이면 소실, 2+ 면 정본이 갈렸다: {f['canonical_file']}")
        if decl_n != 0:
            v.append(f"소비자 선언 수 {decl_n} (기대 0) — 재복제: {', '.join(decl_where[:5])}"
                     + (" …" if len(decl_where) > 5 else "")
                     + f" (정본: {f['canonical_file']})")
        rows.append({"name": f["name"], "canonical": can_n, "consumer": decl_n,
                     "bare_mentions": mention_lines})
    return {"violations": v, "unread": unread, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description="단일 출처 검사 (정수 단언)")
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    ap.add_argument("--strict-mentions", action="store_true",
                    help="정본을 참조하지 않는 맨 언급도 위반으로 센다 (기본: 보고만)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    try:
        r = audit(args.root)
    except OSError as e:
        print(f"UNRUN: {type(e).__name__}: {e} (⛔ 통과 아님)")
        return UNRUN
    if r["unread"]:
        # ⛔ 읽기 오류는 판정과 **분리**한다 — 섞으면 못 읽은 것이 '위반 없음' 이 된다
        print(f"UNRUN: 읽지 못한 대상 {len(r['unread'])}건 (⛔ 통과 아님)")
        for x in r["unread"]:
            print(f"  {x}")
        return UNRUN
    for row in r["rows"]:
        print(f"{row['name']}: canonical={row['canonical']} consumer={row['consumer']}")
        if row["bare_mentions"]:
            print(f"  ⚠️ 정본 미참조 맨 언급 {len(row['bare_mentions'])}건: "
                  + ", ".join(row["bare_mentions"][:4]) + (" …" if len(row["bare_mentions"]) > 4 else ""))
            if args.strict_mentions:
                r["violations"].append(f"{row['name']}: 정본 미참조 언급 {len(row['bare_mentions'])}건")
    for x in r["violations"]:
        print(f"  ⛔ {x}")
    if r["violations"]:
        print(f"VIOLATION {len(r['violations'])}건")
        return VIOLATION
    print("PASS")
    return OK


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []

    def mk(canon_text, skill_text):
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-ss-"))
        (d / "modules").mkdir()
        (d / "skills" / "fz-x").mkdir(parents=True)
        (d / "guides").mkdir()
        if canon_text is not None:
            (d / "modules" / "promotion-ledger.md").write_text(canon_text, encoding="utf-8")
        (d / "skills" / "fz-x" / "SKILL.md").write_text(skill_text, encoding="utf-8")
        return d

    CANON = "# L\n\n## 미결 안건 — TEAM 메커니즘 일몰 (통합)\n\n본문\n"

    def case(name, canon, skill, want, needle=None):
        nonlocal passed
        d = mk(canon, skill)
        try:
            r = audit(d)
            got = "UNRUN" if r["unread"] else ("VIOLATION" if r["violations"] else "PASS")
            pool = r["violations"] + r["unread"]
            if got != want:
                fails.append(f"{name}: {got} (기대 {want}) · {pool[:1]}")
            elif needle and not any(needle in x for x in pool):
                fails.append(f"{name}: 사유에 {needle!r} 없음 — {pool[:2]}")
            else:
                passed += 1
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # ① 정본 1 · 소비자 0 → PASS
    case("single-source", CANON, "> TEAM 일몰 상태는 `modules/promotion-ledger.md` § 미결 안건 참조\n", "PASS")
    # ② ⛔ 소비자 재복제 → 위반 (개수로 잡는다)
    case("consumer-duplicate", CANON, "> TEAM 일몰은 확산 판정 시 결정한다\n", "VIOLATION", "소비자 선언 수 1")
    # ③ ⛔ 정본이 둘 → 정본이 갈렸다 (존재 여부로는 못 잡는다)
    case("canonical-split", CANON + "\n## 미결 안건 — TEAM 메커니즘 일몰 (사본)\n\n본문\n",
         "> TEAM 일몰 상태는 `modules/promotion-ledger.md` 참조\n", "VIOLATION", "정본 선언 수 2")
    # ④ ⛔ 정본 소실 → 0 도 1 이 아니다
    case("canonical-missing", "# L\n\n본문만\n",
         "> TEAM 일몰 상태는 `modules/promotion-ledger.md` 참조\n", "VIOLATION", "정본 선언 수 0")
    # ⑤ ⛔ 정본 파일 부재 → **미판정**. 위반 0건으로 인쇄하지 않는다
    case("canonical-file-absent", None, "> 본문\n", "UNRUN", "부재")
    # ⑥ 정본 미참조 맨 언급은 기본 **보고만** (위반 아님) — 경계를 고정한다
    case("bare-mention-reports-only", CANON, "> TEAM 일몰 경로로 대체됐다\n", "PASS")

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
