#!/usr/bin/env python3
"""measure_constraint_load.py — fz 제약 가이드 hot-path 로드 부하 계측 (COST 축).

목적: Opus 4.8 전환 이후 "강한 제약 가이드로 인한 성능 저하" 가설을 데이터로 검증하기
위한 1차 도구. 각 스킬이 참조하는 modules/guides의 토큰/라인 부하를 계측하고, 각 모듈의
operative(게이트/체크리스트/절차) vs justification(근거/인용/서사) 비율을 추정한다.

⛔ 한계 (정직성):
  1. COST ≠ REMOVAL-SAFETY. 본 도구는 "무엇이 비싼가"만 측정한다. "제거해도 에러가
     안 느는가"(VALUE 축)는 측정하지 못한다 — 그건 paired A/B + 회귀 라벨링이 필요하다.
     따라서 출력은 *제거 후보 우선순위*이지 *제거 정당화*가 아니다.
  2. (2026-07-25 P2로 부분 해소) 참조는 **floor(무조건) / ceiling(전체 정적)** 으로
     분리 계측한다. floor = 조건 마커 없는 참조만 = 그 스킬을 부르면 항상 드는 비용.
     ⛔ 단 floor도 **정적 판정**이다 — 조건 판정은 참조가 적힌 줄의 마커 휴리스틱이며
     (`CONDITIONAL_PAT`), 실제 런타임 로드는 대화 흐름에 따라 달라진다. 판정 근거는
     `--refs <skill>` 로 전수 감사할 것. 오분류 방향은 보수적(기본값 unconditional).
  3. operative/justification 분류는 휴리스틱(마커 기반)이다. 정밀 분류는 사람 검토 필요.
  4. (P2) floor 판정 휴리스틱의 알려진 한계 — `--refs`로 반증 가능하게 설계했다:
     (a) 조건이 **부모 줄**에 있으면 들여쓰기로 상속하지만, 산문 문단으로 떨어져 있으면 놓친다.
     (b) 버킷 판정은 참조 **직전 60자에서 가장 가까운 마커**가 이긴다 — 어순이 특이하면 오분류.
     (c) `## 모듈 참조` 표만 카탈로그로 인식한다. 다른 이름의 카탈로그 표는 load로 샌다.
     ⛔ 이 셋 다 **floor를 과대평가하는 방향**(안전측)으로 기운다. 과소평가보다 낫다.

사용:
  python3 scripts/measure_constraint_load.py [PLUGIN_ROOT]
  python3 scripts/measure_constraint_load.py --json          # 기계 판독용 JSON
  python3 scripts/measure_constraint_load.py --refs fz-plan  # 조건부 판정 근거 감사
  python3 scripts/measure_constraint_load.py --sections modules/foo.md

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


# ── 조건부 로드 판정 휴리스틱 (P2, 2026-07-25) ──
# 참조가 적힌 *그 줄*에 조건 마커가 있으면 conditional로 본다.
# ⛔ 기본값은 unconditional (보수적): unconditional→conditional 오분류는 최소 로드를
#    과소평가해 비용을 실제보다 싸게 보이게 한다. COST 축에서는 과소평가가 더 위험하다.
CONDITIONAL_PAT = re.compile(
    r"(Level\s*3"                                  # "본문: modules/x.md 참조 (Level 3)"
    r"|해당\s*시|가용\s*시|발동\s*시|필요\s*시|실패\s*시|미가용"
    r"|없으면|있으면|시에만|경우에만|조건부|\(선택\)"
    r"|\d\+\s*스텝|TEAM\s*시|팀\s*모드|Swift/iOS|계획\s*시"
    r"|폴백|fallback)",
    re.IGNORECASE,
)
# 조건 마커가 있어도 무조건으로 되돌리는 강제 표현
UNCONDITIONAL_OVERRIDE = re.compile(r"(반드시|항상|무조건|전수|선행\s*의무)")

# ⛔ 로드가 **아닌** 참조 2종 — floor/ceiling 어느 쪽에도 세지 않는다.
# (a) 카탈로그: `## 모듈 참조` 표의 행. 원 docstring이 경고한 "카탈로그 ≠ 실제 Read".
CATALOG_SECTION = re.compile(r"^#{2,3}\s*(모듈 참조|모듈 목록|Module Reference)", re.IGNORECASE)
# (b) 출처 표기: 근거/계보를 밝히는 인용이지 읽으라는 지시가 아님.
CITATION_PAT = re.compile(
    r"(single\s*source|출처|근거|정합|canonical|규약:|학술|참조 표기)", re.IGNORECASE
)
# 로드 지시로 보는 표현 (출처 표기와 공존 시 로드 우선)
LOAD_PAT = re.compile(r"(참조|본문|Read\b|읽기|로드|절차:)", re.IGNORECASE)


def ref_files_in_skill(skill_md: Path) -> dict[str, dict]:
    """SKILL.md의 modules/guides 참조를 **줄 단위**로 수집하고 3-버킷 분류한다.

    버킷: `catalog`(모듈 참조 표) / `citation`(출처 표기) / `load`(실제 로드 지시).
    floor·ceiling 집계는 **load 버킷만** 대상으로 한다 — 카탈로그와 출처 표기는
    "그 파일을 읽으라"는 지시가 아니므로 로드 비용이 아니다.

    반환: {rel: {"bucket": str, "conditional": bool, "sites": [...]}}

    한 파일이 여러 번 참조되면 우선순위는 load > citation > catalog이고,
    load 중 **하나라도 unconditional이면 그 파일은 unconditional**이다.
    """
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    out: dict[str, dict] = {}
    in_catalog = False
    rank = {"catalog": 0, "citation": 1, "load": 2}

    # 조건 문맥 상속 스택: 부모 줄(더 얕은 들여쓰기)의 조건이 자식 참조에 전파된다.
    # 예) "5. **핵심 모듈 선로드** (6+ 스텝 또는 TEAM):" 아래 "- `Read(modules/x.md)`"
    cond_stack: list[tuple[int, bool]] = []              # (indent, conditional)

    for i, raw in enumerate(text.splitlines(), 1):
        if re.match(r"^#{2,3}\s", raw):                  # 섹션 경계 → 문맥 리셋
            in_catalog = bool(CATALOG_SECTION.match(raw))
            cond_stack.clear()

        indent = len(raw) - len(raw.lstrip())
        if raw.strip():
            while cond_stack and cond_stack[-1][0] >= indent:
                cond_stack.pop()

        line_cond = (bool(CONDITIONAL_PAT.search(raw))
                     and not UNCONDITIONAL_OVERRIDE.search(raw))

        hits = list(re.finditer(r"(?:modules|guides)/[a-z0-9-]+\.md", raw))
        if not hits:
            # 참조 없는 줄이라도 조건 마커가 있으면 자식에게 상속시킨다
            if line_cond and raw.strip():
                cond_stack.append((indent, True))
            continue

        inherited = any(c for _, c in cond_stack)
        cond = line_cond or inherited
        row_is_catalog = in_catalog and raw.lstrip().startswith("|")

        for m in hits:
            rel = m.group(0)
            # ⛔ 참조별 판정: 한 줄에 로드 지시와 출처 표기가 **공존**할 수 있다.
            #    (예: "…plan-deep-planning.md 참조. 원칙(single source: prompt-optimization.md §1)")
            #    각 참조의 **직전 40자**를 보고 그 참조 자체의 성격을 정한다.
            before = raw[max(0, m.start() - 60):m.start()]
            # **가장 가까운 마커가 이긴다** — 한 줄에 두 종류가 섞여 있을 때
            # 앞선 참조의 동사("참조")가 뒤 참조를 오염시키는 것을 막는다.
            def _last(pat: re.Pattern) -> int:
                hits_ = list(pat.finditer(before))
                return hits_[-1].start() if hits_ else -1
            cit_at, load_at = _last(CITATION_PAT), _last(LOAD_PAT)
            if row_is_catalog:
                bucket = "catalog"
            elif cit_at < 0 and load_at < 0:
                bucket = "load"          # 단서 없음 → 보수적으로 load
            else:
                bucket = "citation" if cit_at > load_at else "load"

            e = out.setdefault(rel, {"bucket": "catalog", "conditional": True, "sites": []})
            e["sites"].append({"line": i, "bucket": bucket,
                               "conditional": cond, "text": raw.strip()[:110]})
            if rank[bucket] > rank[e["bucket"]]:        # 더 강한 버킷으로 승격
                e["bucket"] = bucket
                e["conditional"] = True                 # 승격 시 재판정
            if bucket == "load" and e["bucket"] == "load" and not cond:
                e["conditional"] = False
    return out


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

    # --refs <skill>: 참조별 조건부 판정 근거 출력 (휴리스틱 감사용)
    if "--refs" in sys.argv:
        skill = args[0] if args else ""
        skill_md = root / "skills" / skill / "SKILL.md"
        if not skill_md.is_file():
            sys.exit(f"사용: --refs fz-plan  (없음: {skill_md})")
        refs = ref_files_in_skill(skill_md)
        docs_ = collect_doc_stats(root)
        ld = {r: m for r, m in refs.items() if m["bucket"] == "load" and r in docs_}
        u = sum(docs_[r]["tokens"] for r, m in ld.items() if not m["conditional"])
        t = sum(docs_[r]["tokens"] for r in ld)
        ex = sum(docs_[r]["tokens"] for r, m in refs.items()
                 if m["bucket"] != "load" and r in docs_)
        print(f"참조 판정: skills/{skill}/SKILL.md")
        print(f"  floor(무조건 로드) {u} / ceiling(로드 전체) {t} ~tokens"
              f"  · 로드 아님(카탈로그·출처표기) {ex} 제외")
        print("⛔ 휴리스틱 3-버킷 — catalog(모듈 참조 표) / citation(출처 표기) / load(로드 지시).")
        print("   조건 판정은 참조가 적힌 *그 줄*의 마커 기준. 기본값 unconditional(보수적).")
        print("-" * 78)
        order = {"load": 0, "citation": 1, "catalog": 2}
        for rel, meta in sorted(refs.items(),
                                key=lambda x: (order[x[1]["bucket"]], x[1]["conditional"])):
            tok = docs_.get(rel, {}).get("tokens", 0)
            if meta["bucket"] == "load":
                tag = "로드/조건부" if meta["conditional"] else "로드/무조건"
            else:
                tag = "카탈로그  " if meta["bucket"] == "catalog" else "출처표기  "
            print(f"[{tag}] {rel:<38} ~{tok:>6} tok")
            for s in meta["sites"]:
                mark = {"catalog": "  ·", "citation": "  ~"}.get(
                    s["bucket"], "  ?" if s["conditional"] else "  !")
                print(f"   {mark} L{s['line']}: {s['text']}")
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
        lines = tokens = 0                       # ceiling: load 버킷 전체
        u_lines = u_tokens = u_count = 0         # floor: load & unconditional
        n_load = n_cat = n_cit = 0
        excluded_tokens = 0                      # catalog+citation (로드 아님)
        for ref, meta in refs.items():
            if ref not in docs:
                continue
            docs[ref]["referenced_by"].append(name)
            if meta["bucket"] != "load":
                excluded_tokens += docs[ref]["tokens"]
                n_cat += meta["bucket"] == "catalog"
                n_cit += meta["bucket"] == "citation"
                continue
            n_load += 1
            lines += docs[ref]["lines"]
            tokens += docs[ref]["tokens"]
            if not meta["conditional"]:
                u_count += 1
                u_lines += docs[ref]["lines"]
                u_tokens += docs[ref]["tokens"]
        skill_load[name] = {
            "ref_count": len(refs), "load_refs": n_load,
            "catalog_refs": n_cat, "citation_refs": n_cit,
            "lines": lines, "tokens": tokens, "excluded_tokens": excluded_tokens,
            # P2: 무조건 로드 subset = "실제 최소 로드"의 하한
            "uncond_count": u_count, "uncond_lines": u_lines, "uncond_tokens": u_tokens,
            "cond_tokens": tokens - u_tokens,
            "refs_detail": {k: {"bucket": v["bucket"], "conditional": v["conditional"],
                                "sites": v["sites"]} for k, v in refs.items()},
        }

    if as_json:
        print(json.dumps({"skills": skill_load, "docs": docs}, ensure_ascii=False, indent=2))
        return

    # ── 사람 판독 리포트 ──
    print("=" * 78)
    print("fz 제약 가이드 hot-path 로드 부하 (COST 축) — measure_constraint_load.py")
    print("⛔ COST ≠ 제거 안전. floor=무조건 로드 / ceiling=로드 지시 전체 (둘 다 정적 판정).")
    print("   카탈로그(모듈 참조 표)·출처 표기는 로드가 아니므로 제외. 근거 감사: --refs <skill>")
    print("=" * 78)

    print("\n■ 표1: 스킬별 hot-path 로드 — 무조건(floor) vs 조건부(ceiling)")
    print("  floor = 조건 마커 없는 참조만 = 그 스킬을 부르면 **항상** 드는 비용")
    print("  ceiling = 전체 정적 참조 (기존 UPPER BOUND). 검증: --refs <skill>")
    print(f"{'skill':<16}{'refs':>5}{'floor~tok':>11}{'ceil~tok':>10}{'floor%':>8}")
    print("-" * 51)
    for name, d in sorted(skill_load.items(), key=lambda x: -x[1]["tokens"]):
        if not d["ref_count"]:
            continue
        pct = round(100 * d["uncond_tokens"] / (d["tokens"] or 1))
        print(f"{name:<16}{d['ref_count']:>5}{d['uncond_tokens']:>11}"
              f"{d['tokens']:>10}{pct:>7}%")

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
