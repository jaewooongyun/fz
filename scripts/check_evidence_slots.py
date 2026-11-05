#!/usr/bin/env python3
"""check_evidence_slots.py — 피어 리뷰 근거 슬롯이 Tier 가 요구하는 만큼 찼는가 (Gather 5.5 뒤 · Analyze 앞).

왜: 저장된 피어 리뷰 33회 중 18회가 Tier 의 상시(✓) 근거를 하나 이상 빠뜨렸다(2026-11-05 실측 — Tier 1 의
`old-new-pairs` · `base-patterns` 가 각 10회). 워커 tools 에서 외부 참조 그래프 도구를 걷어내는 결정(F-536)은 "Lead 가 슬롯
파일로 근거를 넘긴다" 가 조건이다 — 그 조건을 문서가 아니라 이 검사가 지킨다.

판정 (`<WORK_DIR>` 하나):
  ① Tier = `--tier N`(우선 — 재개 실행의 옛 tier.txt 를 믿지 않는다) · 없으면 `tier.txt` 를 읽는다(실측 6형식, 아래 TIER_FORMS).
     둘 다 없거나 tier.txt 안에서 값이 엇갈리면 판정 불가.
  ② 요구 슬롯 = `modules/peer-review-tiers.md` § Tier-Adaptive Evidence 표에서 그 Tier 열이 ✓ 인 ID — 표를 파싱한다(목록을 여기 베끼지 않는다).
     각 ID 는 `<id>.md`(루트) 또는 `evidence/<id>.md` 가 있거나, `evidence/skipped.md` 에 `- <id>: <사유>` 줄이 있어야 한다.
  ③ `evidence/tools.md` 첫 줄 = `Serena: active <path> @<sha> (languages: <목록>)` 또는 `[Serena 미사용 — <사유>]`.
     active 면 언어 목록이 비지 않아야 하고(빈 목록 = 언어 서버 미활성) `@sha` 가 `target.json` 의 `sha` 와 같은 커밋이어야 한다
     (앞부분 일치 · 7자 이상) — 작업 트리가 리뷰 대상이 아니면 Serena 결과는 근거가 아니다.
  ④ `evidence/caller-analysis.md` 가 있으면 `## 호출` · `## 구현` 두 절이 다 있고, 각 절은 내용 또는 `해당 없음 — <사유>` 다.
     `TODO` 자리표시는 거부한다(개인 도구가 `## 구현` 을 TODO 로 남겨 Lead 가 채우게 한다).

exit code:
  0  PASS
  1  VIOLATION — 빠진 슬롯 · 형식 위반 · 대상 불일치
  2  UNRUN — WORK_DIR 부재 · Tier 미상 · 표 파싱 실패. ⛔ 통과로 읽지 않는다

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TIERS_DOC = os.path.join(SCRIPT_DIR, "..", "modules", "peer-review-tiers.md")

# tier.txt 실측 6형식(2026-11-05 저장본 38개): `TIER=2 (…)` · `tier=0 (auto) · …` · `Tier 0 (user: …)` · 첫 줄 숫자만(`2` + rationale 줄)
# · 둘째 줄 `tier=1` · 한 줄 `tier=1 mode=light …`. `tier_delta=1` 같은 이웃 키는 `\btier` 뒤 `_` 때문에 걸리지 않는다
TIER_KEY = re.compile(r"(?i)\btier\s*[=:]?\s*([0-3])\b")
TIER_BARE = re.compile(r"^\s*([0-3])\s*$")
TOOLS_ACTIVE = re.compile(r"^Serena: active (\S.*?) @([0-9a-f]{7,40}) \(languages: ([^)]*)\)\s*$")
TOOLS_UNUSED = re.compile(r"^\[Serena 미사용 — (\S.*)\]\s*$")
SKIP_LINE = re.compile(r"^\s*-\s*([a-z-]+)\s*:\s*(\S.*)$")


def log(*a):
    print(*a, file=sys.stderr)


def tier_from_text(text: str):
    """tier.txt 본문 → 0~3. 못 읽거나 값이 엇갈리면 None."""
    lines = text.splitlines()
    found = {int(m.group(1)) for ln in lines for m in TIER_KEY.finditer(ln)}
    if lines and TIER_BARE.match(lines[0]):
        found.add(int(lines[0].strip()))
    return found.pop() if len(found) == 1 else None


def required_slots(doc_path: str, tier: int):
    """§ Tier-Adaptive Evidence 의 첫 표에서 `Tier <tier>` 열이 ✓ 인 ID 목록. 표를 못 찾으면 None."""
    try:
        text = open(doc_path, encoding="utf-8").read()
    except OSError:
        return None
    start = text.find("## Tier-Adaptive Evidence")
    if start < 0:
        return None
    header, out = None, []
    for ln in text[start:].splitlines()[1:]:
        if ln.startswith("## "):
            break
        if not ln.startswith("|"):
            if header and out:
                break   # 첫 표만 — 아래 pre-cache 표는 다른 집합이다
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if header is None:
            if cells and cells[0] == "ID":
                header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        col = f"Tier {tier}"
        if col not in header:
            return None
        out.append((cells[0].strip("`"), cells[header.index(col)]))
    ids = [i for i, mark in out if mark == "✓"]
    return ids if out else None


def skipped_ids(work: str):
    p = os.path.join(work, "evidence", "skipped.md")
    if not os.path.isfile(p):
        return {}
    return {m.group(1): m.group(2) for m in (SKIP_LINE.match(ln) for ln in open(p, encoding="utf-8")) if m}


def sections(text: str):
    """`## 제목` → 본문(다음 `## ` 전)."""
    out, cur = {}, None
    for ln in text.splitlines():
        if ln.startswith("## "):
            cur = ln[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(ln)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def check(work: str, tier_arg, doc_path: str = TIERS_DOC):
    if not os.path.isdir(work):
        log(f"UNRUN: WORK_DIR 없음 — {work}")
        return UNRUN
    tp = os.path.join(work, "tier.txt")
    file_tier = tier_from_text(open(tp, encoding="utf-8", errors="replace").read()) if os.path.isfile(tp) else None
    tier = tier_arg if tier_arg is not None else file_tier
    if tier is None:
        log("UNRUN: Tier 미상 — --tier 가 없고 tier.txt 를 읽지 못했다(없음 · 형식 밖 · 값이 엇갈림)")
        return UNRUN
    if tier_arg is not None and file_tier is not None and file_tier != tier_arg:
        print(f"  참고: tier.txt={file_tier} 와 --tier={tier_arg} 가 다르다 — --tier 를 쓴다")
    req = required_slots(doc_path, tier)
    if req is None:
        log(f"UNRUN: {doc_path} 의 § Tier-Adaptive Evidence 표를 파싱하지 못했다")
        return UNRUN

    bad = []
    skip = skipped_ids(work)
    for i in req:
        if any(os.path.isfile(os.path.join(work, p)) for p in (f"{i}.md", os.path.join("evidence", f"{i}.md"))):
            continue
        if i not in skip:
            bad.append(f"슬롯 `{i}` 없음 — 파일을 채우거나 evidence/skipped.md 에 `- {i}: <사유>`")

    tools = os.path.join(work, "evidence", "tools.md")
    first = open(tools, encoding="utf-8").readline().rstrip("\n") if os.path.isfile(tools) else None
    act = TOOLS_ACTIVE.match(first) if first else None
    if first is None:
        bad.append("evidence/tools.md 없음 — 첫 줄에 Serena 상태를 적는다")
    elif act:
        if not act.group(3).strip():
            bad.append("tools.md: languages 가 비었다 — 언어 서버가 안 떴다(미활성)")
        sha = None
        try:
            sha = str(json.load(open(os.path.join(work, "target.json"), encoding="utf-8")).get("sha") or "").lower()
        except (OSError, ValueError, AttributeError):
            pass
        at = act.group(2)
        if not sha or len(sha) < 7:
            bad.append("tools.md 가 Serena active 인데 target.json 의 sha 를 못 읽었다 — 대상 일치를 판정할 수 없다")
        elif not (sha.startswith(at) or at.startswith(sha)):
            bad.append(f"tools.md: Serena 트리 @{at} ≠ 리뷰 대상 {sha[:12]} — 대상 트리에서 다시 켜거나 `[Serena 미사용 — 작업 트리 ≠ 대상]`")
    elif not TOOLS_UNUSED.match(first):
        bad.append(f"tools.md 첫 줄 형식 밖 — {first[:80]!r}")

    ca = os.path.join(work, "evidence", "caller-analysis.md")
    if os.path.isfile(ca):
        secs = sections(open(ca, encoding="utf-8").read())
        for name in ("호출", "구현"):
            body = secs.get(name)
            if body is None:
                bad.append(f"caller-analysis.md: `## {name}` 절 없음")
            elif not body or re.fullmatch(r"해당 없음\s*", body):
                bad.append(f"caller-analysis.md: `## {name}` 이 비었다 — 내용 또는 `해당 없음 — <사유>`")
            elif "TODO" in body:
                bad.append(f"caller-analysis.md: `## {name}` 에 TODO 자리표시 — Lead 가 채운다")

    print(f"근거 슬롯 검사 — Tier {tier} · 요구 {len(req)}종 · skipped {len(skip)}")
    for b in bad:
        print(f"  ✗ {b}")
    return VIOLATION if bad else OK


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {detail}"))

    forms = {"TIER=2 (auto, SIGNIFICANT_LINES=251)": 2, "tier=0 (auto) · risk=0 · gpt=none (Tier 0, no --gpt)": 0,
             "Tier 0 (user: 경량)": 0, "2\nrationale: risk=1 (public_api, tier_delta=1)": 2,
             "mode=light (사용자 선택)\ntier=1\ngpt=x": 1, "tier=1 mode=light source=arg": 1}
    got = {k: tier_from_text(k) for k in forms}
    case("tier-forms-6", got == forms, got)
    case("tier-conflict-unrun", tier_from_text("tier=1\nTIER=2") is None)

    real = required_slots(TIERS_DOC, 1)
    case("table-tier1", real == ["requirements", "old-new-pairs", "base-behavior", "base-patterns"], real)

    with tempfile.TemporaryDirectory() as t:
        def mk(name, tools="Serena: active /x @abc1234def (languages: swift)\n"):
            d = os.path.join(t, name)
            os.makedirs(os.path.join(d, "evidence"))
            for p in ("tier.txt", "requirements.md", "base-behavior.md", "evidence/old-new-pairs.md", "evidence/base-patterns.md"):
                open(os.path.join(d, p), "w").write("tier=1\n" if p == "tier.txt" else "")
            json.dump({"kind": "pr", "ref": "pr-1", "sha": "abc1234def0"}, open(os.path.join(d, "target.json"), "w"))
            open(os.path.join(d, "evidence", "tools.md"), "w").write(tools)
            return d

        def w(d, rel, body):
            open(os.path.join(d, rel), "w").write(body)

        case("complete", check(mk("ok"), None) == OK)
        d = mk("miss")
        os.remove(os.path.join(d, "evidence", "base-patterns.md"))
        case("always-slot-missing", check(d, None) == VIOLATION)
        w(d, "evidence/skipped.md", "- base-patterns: 형제 패턴 없음(신규 파일만)\n")
        case("skip-with-reason", check(d, None) == OK)
        w(d, "evidence/skipped.md", "- base-patterns:\n")
        case("skip-without-reason", check(d, None) == VIOLATION)
        d = mk("notier")
        os.remove(os.path.join(d, "tier.txt"))
        case("tier-unknown-unrun", check(d, None) == UNRUN)
        case("tier-arg-wins", check(d, 0) == OK)
        d = mk("tier2")
        case("tier2-needs-more", check(d, 2) == VIOLATION)
        d = mk("todo")
        w(d, "evidence/caller-analysis.md", "## 호출\n- a\n## 구현\nTODO(Lead: Serena find_implementations)\n")
        case("impl-todo-rejected", check(d, None) == VIOLATION)
        w(d, "evidence/caller-analysis.md", "## 호출\n- a\n## 구현\n해당 없음 — 프로토콜 변경 없음\n")
        case("impl-not-applicable-ok", check(d, None) == OK)
        w(d, "evidence/caller-analysis.md", "## 호출\n- a\n")
        case("impl-section-missing", check(d, None) == VIOLATION)
        case("serena-sha-mismatch", check(mk("sha", "Serena: active /x @fff0000 (languages: swift)\n"), None) == VIOLATION)
        case("serena-no-languages", check(mk("lang", "Serena: active /x @abc1234 (languages: )\n"), None) == VIOLATION)
        case("serena-unused-ok", check(mk("unused", "[Serena 미사용 — 작업 트리 ≠ 대상]\n"), None) == OK)
        case("tools-free-text", check(mk("free", "Serena 썼음\n"), None) == VIOLATION)
        d = mk("notools")
        os.remove(os.path.join(d, "evidence", "tools.md"))
        case("tools-missing", check(d, None) == VIOLATION)
        case("table-missing-unrun", check(mk("nodoc"), None, os.path.join(t, "absent.md")) == UNRUN)
        case("workdir-missing-unrun", check(os.path.join(t, "absent"), 1) == UNRUN)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("work_dir", nargs="?")
    ap.add_argument("--tier", type=int, choices=(0, 1, 2, 3))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.work_dir:
        log("UNRUN: WORK_DIR 인자가 필요하다")
        return UNRUN
    return check(a.work_dir, a.tier)


if __name__ == "__main__":
    sys.exit(main())
