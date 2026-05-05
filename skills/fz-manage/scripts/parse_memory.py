#!/usr/bin/env python3
"""
Memory Parser (Lessons-to-Module Pipeline D+2 component)

Phase 3 fz-cargo-cult-defense Pilot 산출물.
입력: memory/feedback_*.md (frontmatter + 본문)
출력: JSON (id, frontmatter, core_lesson, applied_location_*, meta_family, signals)

NLAH: C (Contracts: 출력 JSON schema) + A (Adapters: regex/file)
O2 (Deterministic Script) 적용 — LLM 미사용, 재현 가능.

Usage:
  python3 parse_memory.py <path/to/feedback_*.md>
  python3 parse_memory.py --batch <directory> --output <out.jsonl>

기대 출력 형식 (기대 정답: manual-pattern-extraction.md §4.1):
{
  "id": "19차",
  "source_file": "feedback_import_copy_without_verification.md",
  "frontmatter": {...},
  "core_lesson": "...",
  "applied_location_explicit": [...],
  "applied_location_implicit": [...],
  "meta_family": [...],
  "meta_pattern": "...",
  "trigger_case": "...",
  "severity": "...",
  "signals": {
    "compiler_gap_signal": bool,
    "symmetry_candidate": str | null,
    "self_review_blind_spot": bool,
    "fan_out_count_estimate": int
  }
}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL
)

# id 추출: "ASD-1260", "X차", "feedback_..." 변형 모두 수용
ID_FROM_FILENAME_PATTERN = re.compile(r"feedback_(.+?)\.md$")

# meta_family 차수 추출: "16차/23차/33차/34차" 또는 "16차 / 23차 / ..."
# Note: 끝의 \b 제거 — 한글 다음 한글에는 ASCII word boundary가 없어서
# "차/" 다음 "34차"가 매칭되지 않는 버그 방지
META_FAMILY_PATTERN = re.compile(r"\b(\d{1,3})차")

# Self-exclusion: frontmatter name 또는 본문에 "(N차" 패턴 있으면 self id
SELF_ID_FROM_NAME = re.compile(r"\((\d+)차\b")

# v2 (Sanity Check 18차 반영): [skill: X, Y, Z] 태그 인식
# 18차 메모리 본문에 `[skill: fz-plan, fz-review, fz-codex] [status: ...] [priority: ...]`
# 형식의 명시적 모듈 태깅이 있음을 발견 (19차에는 없음)
SKILL_TAG_PATTERN = re.compile(r"\[skill:\s*([^\]]+)\]", re.IGNORECASE)

# applied_location 추출 휴리스틱: "fz-code", "fz-review", "modules/", "agents/", ...
APPLIED_LOCATION_HINTS = [
    (r"fz-code(?:의|에|\.\w+)?(?:\s*마찰\s*신호|\s*친구\s*마찰\s*검사)?", "fz-code 마찰 신호 카탈로그"),
    (r"fz-review(?:의|에|\.\w+)?(?:\s*검증\s*4-E|\s*Symbol\s*Coverage)?", "fz-review 검증 4-E"),
    (r"impl-correctness", "impl-correctness 에이전트"),
    (r"review-quality", "review-quality 에이전트"),
    (r"review-arch", "review-arch 에이전트"),
    (r"lead-reasoning", "lead-reasoning.md"),
    (r"SwiftLint|unused_import", "SwiftLint 설정"),
    (r"self[- ]review\s*meta[- ]loop", "self-review meta-loop"),
]

# meta_pattern 휴리스틱
META_PATTERN_HINTS = [
    (r"self[- ]review\s*blind\s*spot", "self-review blind spot"),
    (r"cargo[- ]cult", "cargo-cult"),
    (r"scope\s*inflation", "scope inflation"),
    (r"thought[- ]terminator", "thought-terminator"),
    (r"silent\s*disappearance", "silent disappearance"),
]

# trigger_case 휴리스틱: "ASD-XXXX" or "PR #XXXX"
TRIGGER_CASE_PATTERN = re.compile(r"\b(ASD-\d{2,5}|PR\s*#\d{2,5}|D\d+\s*회귀)")

# severity 휴리스틱
SEVERITY_HINTS = [
    (r"critical|치명|크래시|crash", "critical"),
    (r"high|심각|고위험", "high"),
    (r"medium|중간|보통", "medium"),
    (r"low|minor|경미|낮음", "low"),
]

# signals 휴리스틱
COMPILER_GAP_HINTS = [
    r"compiler\s*(?:warning|경고)?\s*없음",
    r"(?:Swift|컴파일러)\s*(?:는|이)?\s*(?:강한\s*)?경고\s*(?:를)?\s*내지\s*않",
    r"unused_import\s*(?:rule|규칙)?",
    r"명시적\s*grep만\s*catch",
]

SYMMETRY_HINTS = [
    (r"Import\s*Orphan", "Import Orphan (대칭쌍)"),
    (r"대칭", "symmetric pattern detected"),
    (r"양방향", "bidirectional pattern"),
]


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Frontmatter (--- ... ---) + body 분리. 단순 line-based key: value."""
    m = FRONTMATTER_PATTERN.match(text)
    if not m:
        return {}, text
    fm_block, body = m.group(1), m.group(2)
    fm: dict[str, str] = {}
    current_key: str | None = None
    for line in fm_block.splitlines():
        if not line.strip():
            continue
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            current_key = key.strip()
            fm[current_key] = val.strip()
        elif current_key:
            fm[current_key] = (fm[current_key] + " " + line.strip()).strip()
    return fm, body


def derive_id(filename: str, fm: dict[str, str]) -> str:
    """파일명 또는 frontmatter에서 id 추출.
    v3 (P4 D+7-D+10 33차/34차 반영): frontmatter name + description 모두 검사.
    33차 description: "Recommendation Default Bias (33차) — ..." 패턴 인식."""
    body_match = ID_FROM_FILENAME_PATTERN.search(filename)
    slug = body_match.group(1) if body_match else fm.get("name", filename)

    # frontmatter name에서 (N차) 매칭
    name_match = SELF_ID_FROM_NAME.search(fm.get("name", ""))
    if name_match:
        return f"{name_match.group(1)}차"

    # v3: description에서도 (N차) 매칭 시도
    desc_match = SELF_ID_FROM_NAME.search(fm.get("description", ""))
    if desc_match:
        return f"{desc_match.group(1)}차"

    if "차" in slug:
        digits = re.search(r"(\d+)차", slug)
        if digits:
            return f"{digits.group(1)}차"
    return slug


def extract_core_lesson(body: str, fm: dict[str, str]) -> str:
    """본문에서 첫 번째 강조 명제(굵은 표시 또는 첫 문단) 또는 description."""
    if "description" in fm and fm["description"]:
        return fm["description"]
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    for p in paragraphs:
        if not p.startswith(("##", "**Why", "**How", "**참조", "**관찰")):
            return p[:300]
    return paragraphs[0][:300] if paragraphs else ""


def extract_applied_location(body: str, fm: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """applied_location_explicit: 동작 명시 + [skill: ...] 태그 + applies-to frontmatter
    applied_location_implicit: 메타 시그니처가 가리키는 위치

    v4 (P4 D+7-D+10 33차 반영): frontmatter `applies-to` 필드 인식.
    33차 frontmatter: applies-to: fz, fz-plan (Lead 권고 layer)
    """
    if fm is None:
        fm = {}
    explicit: list[str] = []
    implicit: list[str] = []

    # v4: frontmatter applies-to 필드 (33차 형식)
    applies_to = fm.get("applies-to", "")
    if applies_to:
        for raw in applies_to.split(","):
            cleaned = re.sub(r"\s*\(.*?\)\s*", "", raw).strip()
            if cleaned:
                label = f"{cleaned} 모듈"
                if label not in explicit:
                    explicit.append(label)

    # v2: [skill: X, Y, Z] 태그
    # v4.1 (P4 D+9 34차 fix): 쉼표 또는 공백 모두 구분자로 처리
    # 18차: [skill: fz-plan, fz-review, fz-codex] (쉼표)
    # 34차: [skill: fz-review fz-discover fz-plan] (공백)
    skill_tag_match = SKILL_TAG_PATTERN.search(body)
    if skill_tag_match:
        for raw in re.split(r"[,\s]+", skill_tag_match.group(1)):
            skill = raw.strip()
            if skill:
                label = f"{skill} 모듈"
                if label not in explicit:
                    explicit.append(label)

    for pattern, label in APPLIED_LOCATION_HINTS:
        if re.search(pattern, body, re.IGNORECASE):
            search_window = body
            if re.search(pattern + r"[^.]{0,80}" + r"(?:추가|반영|보강)", search_window, re.IGNORECASE):
                if label not in explicit:
                    explicit.append(label)
            else:
                if label not in implicit and label not in explicit:
                    implicit.append(label)
    if "체계적 self-review" in body or "체계적 self review" in body.replace("-", " "):
        if "self-review meta-loop" not in implicit and "self-review meta-loop" not in explicit:
            implicit.append("self-review meta-loop (체계적)")
    return explicit, implicit


def extract_meta_family(body: str, current_id: str) -> list[str]:
    """본문에서 16차/23차/... 등 family 차수 추출. 자기 자신은 제외.

    v3 (P4 D+6 16차 반영): false positive 방지 — "1차 review", "1차 발견" 같은
    *비-메모리 차수* 문맥 제외. 매칭 후 다음 단어가 review/발견/수정/peer 등이면
    skip (메모리 차수가 아닌 일반 동작 표현).
    """
    unique: list[str] = []
    # v3.1 (P4 D+6 16차 추가 fix): "self-review", "peer-review" 같은 hyphenated
    # 단어도 매칭하도록 [\w-]*review 패턴으로 확장
    excluded_next_words = re.compile(
        r"^\s*(?:[\w-]*review|발견|수정|이전|이후|peer|response|시도|드러|분석|레벨)",
        re.IGNORECASE,
    )

    for m in META_FAMILY_PATTERN.finditer(body):
        digits = m.group(1)
        end_pos = m.end()
        next_window = body[end_pos : end_pos + 30]
        if excluded_next_words.match(next_window):
            continue
        cand = f"{digits}차"
        if cand != current_id and cand not in unique:
            unique.append(cand)
    return unique


def extract_meta_pattern(body: str, fm: dict[str, str] | None = None) -> str | None:
    """v4 (P4 D+7-D+10 33차/34차 반영): frontmatter 우선 매칭으로 false positive 차단.
    33차 본문에 18차 인용 ("scope inflation") 있어도 frontmatter description의
    "Recommendation Default Bias"가 우선이어야 함.
    """
    if fm is None:
        fm = {}
    fm_text = fm.get("name", "") + " " + fm.get("description", "")
    for pattern, label in META_PATTERN_HINTS:
        if re.search(pattern, fm_text, re.IGNORECASE):
            return label

    # 보수적: frontmatter 매칭 실패 시 None 유지 (본문 fallback 제거)
    # 본문 매칭은 false positive 위험 (다른 메모리 인용 가능성)
    return None


def extract_trigger_case(body: str) -> str | None:
    m = TRIGGER_CASE_PATTERN.search(body)
    if m:
        return m.group(1).strip()
    return None


def extract_severity(body: str) -> str:
    for pattern, label in SEVERITY_HINTS:
        if re.search(pattern, body, re.IGNORECASE):
            return label
    return "medium"


def extract_signals(body: str) -> dict[str, Any]:
    compiler_gap = any(re.search(p, body, re.IGNORECASE) for p in COMPILER_GAP_HINTS)

    symmetry: str | None = None
    for pattern, label in SYMMETRY_HINTS:
        if re.search(pattern, body, re.IGNORECASE):
            symmetry = label
            break

    self_review = bool(
        re.search(r"self[- ]review\s*blind\s*spot", body, re.IGNORECASE)
    )

    fan_out_estimate = 0
    for pattern, _ in APPLIED_LOCATION_HINTS:
        if re.search(pattern, body, re.IGNORECASE):
            fan_out_estimate += 1

    return {
        "compiler_gap_signal": compiler_gap,
        "symmetry_candidate": symmetry,
        "self_review_blind_spot": self_review,
        "fan_out_count_estimate": fan_out_estimate,
    }


def parse_memory_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    current_id = derive_id(path.name, fm)
    explicit, implicit = extract_applied_location(body, fm)
    meta_family = extract_meta_family(body, current_id)
    meta_pattern = extract_meta_pattern(body, fm)
    return {
        "id": current_id,
        "source_file": path.name,
        "frontmatter": fm,
        "core_lesson": extract_core_lesson(body, fm),
        "applied_location_explicit": explicit,
        "applied_location_implicit": implicit,
        "meta_family": meta_family,
        "meta_pattern": meta_pattern,
        "trigger_case": extract_trigger_case(body),
        "severity": extract_severity(body),
        "signals": extract_signals(body),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("path", nargs="?", help="단일 메모리 파일 경로")
    ap.add_argument("--batch", help="디렉토리 일괄 처리")
    ap.add_argument("--output", help="출력 JSONL 경로 (--batch 시)")
    args = ap.parse_args()

    if args.batch:
        d = Path(args.batch)
        files = sorted(d.glob("feedback_*.md"))
        out = Path(args.output) if args.output else None
        records = [parse_memory_file(f) for f in files]
        if out:
            out.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                encoding="utf-8",
            )
            print(f"[ok] {len(records)} records → {out}", file=sys.stderr)
        else:
            for r in records:
                print(json.dumps(r, ensure_ascii=False))
        return 0

    if not args.path:
        ap.error("path 또는 --batch 필수")

    record = parse_memory_file(Path(args.path))
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
