#!/usr/bin/env python3
"""measure_constraint_load.py — fz 제약 가이드 hot-path 로드 부하 계측 (COST 축).

목적: Opus 4.8 전환 이후 "강한 제약 가이드로 인한 성능 저하" 가설을 데이터로 검증하기
위한 1차 도구. 각 스킬이 참조하는 modules/guides의 토큰/라인 부하를 계측하고, 각 모듈의
operative(게이트/체크리스트/절차) vs justification(근거/인용/서사) 비율을 추정한다.

⛔ 한계 (정직성):
  1. COST ≠ REMOVAL-SAFETY. 본 도구는 "무엇이 비싼가"만 측정한다. "제거해도 에러가
     안 느는가"(VALUE 축)는 측정하지 못한다 — 그건 paired A/B + 회귀 라벨링이 필요하다.
     따라서 출력은 *제거 후보 우선순위*이지 *제거 정당화*가 아니다.
  2. 참조 수는 UPPER BOUND다. SKILL.md의 모듈 참조는 카탈로그이며 실제 Read는 조건부
     ("6+ 스텝 또는 TEAM 시" 등)인 경우가 많다. 실제 런타임 로드 < 정적 참조.
  3. operative/justification 분류는 휴리스틱(마커 기반)이다. 정밀 분류는 사람 검토 필요.

사용:
  python3 scripts/measure_constraint_load.py [PLUGIN_ROOT]
  python3 scripts/measure_constraint_load.py --json   # 기계 판독용 JSON 출력

근거: guides/harness-engineering.md §7 Ablation 프로세스 + §11 측정 지표. 본 도구는 그
프레임의 COST 축 계측기다. VALUE 축은 experiment-log.md Phase 5에 누적한다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ── operative(보존 대상) vs justification(강등 후보) 분류 휴리스틱 ──
# operative: 모델이 작업할 때 직접 따르는 지시 — 게이트/체크리스트/절차/표/금지·필수
OPERATIVE_PAT = re.compile(
    r"(⛔|✅|^\s*-\s*\[\s*\]|^\s*\d+\.\s|^\|)"  # 마커/체크박스/번호절차/표
    r"|(필수|의무|금지|MUST|Gate|게이트|Step\b|절차|체크리스트)",
    re.IGNORECASE,
)
# justification: 모델 실행에 불필요한 근거/인용/서사 — 유지보수자용
JUSTIFICATION_PAT = re.compile(
    r"(arxiv|ICLR|NeurIPS|ACL|Spotlight|논문|근거|출처|연구|왜\b|why\b"
    r"|Anthropic 실측|이론|프레임|배경|참조:)",
    re.IGNORECASE,
)


def est_tokens(text: str) -> int:
    """거친 토큰 추정 (chars/4). 정밀 토크나이저 없이 상대 비교용."""
    return len(text) // 4


def classify_lines(text: str) -> dict:
    """파일 본문을 operative/justification/neutral로 분류 (라인 단위 휴리스틱)."""
    operative = justification = neutral = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):  # 빈 줄/헤더는 neutral(구조)
            neutral += 1
            continue
        is_op = bool(OPERATIVE_PAT.search(raw))
        is_just = bool(JUSTIFICATION_PAT.search(line))
        if is_op and not is_just:
            operative += 1
        elif is_just and not is_op:
            justification += 1
        else:
            neutral += 1
    return {"operative": operative, "justification": justification, "neutral": neutral}


# 섹션 헤더가 reference-leaning(강등 후보)임을 시사하는 키워드
REFERENCE_HEADER_PAT = re.compile(
    r"(왜\b|배경|근거|이론|학술|상세\)|Phase \d|실측|트레이드오프|비용-품질"
    r"|정의|구성 요소|핵심 근거|매핑)",
    re.IGNORECASE,
)


def section_breakdown(md: Path) -> list[dict]:
    """파일을 ##/### 섹션으로 쪼개 각 섹션을 operative vs reference로 분류.

    line-keyword 휴리스틱의 과소계산을 보완: 섹션 헤더 + operative 마커 밀도로 판정.
    reference-leaning 섹션 = 강등 후보 (operative 마커 밀도 낮음 + 헤더가 근거/배경/상세형).
    """
    text = md.read_text(encoding="utf-8", errors="replace")
    sections: list[dict] = []
    cur = {"header": "(preamble)", "level": 0, "lines": [], "start": 1}
    for i, raw in enumerate(text.splitlines(), 1):
        m = re.match(r"^(#{2,3})\s+(.*)", raw)
        if m:
            sections.append(cur)
            cur = {"header": m.group(2).strip(), "level": len(m.group(1)), "lines": [], "start": i}
        else:
            cur["lines"].append(raw)
    sections.append(cur)

    out = []
    for s in sections:
        body = [ln for ln in s["lines"]]
        n = len(body) or 1
        op_markers = sum(1 for ln in body if OPERATIVE_PAT.search(ln))
        op_density = op_markers / n
        header_is_ref = bool(REFERENCE_HEADER_PAT.search(s["header"]))
        # 강등 후보: 헤더가 reference형이고 operative 마커 밀도가 낮음(<15%)
        demotable = header_is_ref and op_density < 0.15 and n >= 4
        out.append({
            "header": s["header"], "level": s["level"], "start": s["start"],
            "lines": len(body), "op_density": round(op_density, 2),
            "demotable": demotable,
        })
    return out


def ref_files_in_skill(skill_md: Path) -> set[str]:
    """SKILL.md가 참조하는 modules/guides 파일명 집합 (정적 = upper bound)."""
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"(?:modules|guides)/[a-z0-9-]+\.md", text))


def collect_doc_stats(root: Path) -> dict[str, dict]:
    """modules/ + guides/ 각 .md의 라인/토큰/분류 통계."""
    stats: dict[str, dict] = {}
    for sub in ("modules", "guides"):
        for md in sorted((root / sub).rglob("*.md")):
            rel = f"{sub}/{md.name}"
            text = md.read_text(encoding="utf-8", errors="replace")
            cls = classify_lines(text)
            total_cls = cls["operative"] + cls["justification"] or 1
            stats[rel] = {
                "lines": text.count("\n") + 1,
                "tokens": est_tokens(text),
                **cls,
                # justification 비율: 분류된 라인 중 근거/인용/서사 비중 → 강등 가능 분량
                "just_pct": round(100 * cls["justification"] / total_cls, 1),
                "referenced_by": [],  # 아래에서 채움
            }
    return stats


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    root = Path(__file__).resolve().parent.parent

    # --sections <file>: 단일 파일 섹션 분해 (강등 후보 식별, line-keyword 보완)
    if "--sections" in sys.argv:
        target = root / args[0] if args else None
        if not target or not target.is_file():
            sys.exit("사용: --sections modules/foo.md 또는 guides/foo.md")
        secs = section_breakdown(target)
        demot_lines = sum(s["lines"] for s in secs if s["demotable"])
        total = sum(s["lines"] for s in secs)
        print(f"섹션 분해: {args[0]} (총 {total}줄, 강등후보 {demot_lines}줄 = {round(100*demot_lines/(total or 1))}%)")
        print(f"{'demote':>7} {'lines':>6} {'op_dens':>8}  header")
        print("-" * 70)
        for s in secs:
            flag = "★강등" if s["demotable"] else "  유지"
            print(f"{flag:>7} {s['lines']:>6} {s['op_density']:>8}  {'  '*(s['level']-2 if s['level']>=2 else 0)}{s['header']}")
        return

    root = Path(args[0]).resolve() if args else root
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        sys.exit(f"skills/ 없음: {root} — PLUGIN_ROOT 인자를 확인하세요.")

    docs = collect_doc_stats(root)

    # 스킬별 hot-path 정적 로드 + 역참조 채우기
    skill_load: dict[str, dict] = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        refs = ref_files_in_skill(skill_md)
        lines = tokens = 0
        for ref in refs:
            if ref in docs:
                lines += docs[ref]["lines"]
                tokens += docs[ref]["tokens"]
                docs[ref]["referenced_by"].append(name)
        skill_load[name] = {"ref_count": len(refs), "lines": lines, "tokens": tokens}

    if as_json:
        print(json.dumps({"skills": skill_load, "docs": docs}, ensure_ascii=False, indent=2))
        return

    # ── 사람 판독 리포트 ──
    print("=" * 78)
    print("fz 제약 가이드 hot-path 로드 부하 (COST 축) — measure_constraint_load.py")
    print("⛔ COST ≠ 제거 안전. 정적 참조 = UPPER BOUND (실제 런타임 로드는 더 적음).")
    print("=" * 78)

    print("\n■ 표1: 스킬별 hot-path 정적 로드 (제거 후보 우선순위, 제거 정당화 아님)")
    print(f"{'skill':<16}{'refs':>5}{'lines':>8}{'~tokens':>9}")
    print("-" * 38)
    for name, d in sorted(skill_load.items(), key=lambda x: -x[1]["tokens"]):
        if d["ref_count"]:
            print(f"{name:<16}{d['ref_count']:>5}{d['lines']:>8}{d['tokens']:>9}")

    print("\n■ 표2: 모듈/가이드별 부하 + justification 비율 (강등 후보 식별)")
    print("  just_pct 높음 + ref 적음 = 저위험 강등 후보 (operative 보존, 근거만 이동)")
    print(f"{'file':<42}{'lines':>6}{'op':>5}{'just':>6}{'just%':>7}{'refs':>5}")
    print("-" * 71)
    for rel, d in sorted(docs.items(), key=lambda x: -x[1]["justification"]):
        n_ref = len(d["referenced_by"])
        print(f"{rel:<42}{d['lines']:>6}{d['operative']:>5}{d['justification']:>6}{d['just_pct']:>6}%{n_ref:>5}")

    # 강등 후보 추천: justification 절대량 상위 + hot-path 노출 낮은 순
    print("\n■ 강등 PoC 후보 (justification 절대량 ↑, 단 VALUE 측정 전 제거 금지)")
    cands = sorted(
        docs.items(),
        key=lambda x: (-x[1]["justification"], len(x[1]["referenced_by"])),
    )[:5]
    for rel, d in cands:
        print(f"  - {rel}: justification {d['justification']}줄 ({d['just_pct']}%), "
              f"참조 스킬 {len(d['referenced_by'])}개")


if __name__ == "__main__":
    main()
