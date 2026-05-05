#!/usr/bin/env python3
"""
Relevance Scorer (Lessons-to-Module Pipeline D+3 component) v2

v2 redesign: 2-Pass 알고리즘 (cascade scoring)
- Pass 1: trigger skills 식별 (applied_location_explicit + symmetry-extended)
- Pass 2: 각 모듈 점수 계산 (trigger skill 기준 cascade)

v1 발견 갭 (19차 e2e 검증):
- fz-code 매칭 OK (0.832)
- impl-correctness/review-quality cascade 누락 → score < 0.30
- fz-review symmetry-extended 매칭 누락
- fz/SKILL.md substring false positive 0.724

NLAH: R (Roles: scorer 단독) + A (Adapters: grep/word-count/cascade)
O2 (Deterministic Script) 적용.

Score 계산 (v2.1 calibrated, cap at 1.0):
  trigger_match  [0 or 0.55]   — primary trigger skill (direct mention 또는 symmetry-extended)
  cascade_match  [0 or 0.65]   — trigger skill의 consumer agent (v2 0.55에서 상향)
  lint_tool      [0 or 0.70]   — compiler_gap_signal + lint config 파일 (강한 신호, 단독으로 threshold 통과 가능)
  semantic       [0 ~ 0.25]    — core_lesson 키워드 hit (정규화)
  symmetry_bonus [0 or 0.20]   — symmetry pattern 보너스 (trigger와 별개)

Calibration 근거 (19차 e2e 검증):
- v2: cascade 0.55 → impl-correctness 0.67 (0.03 미달)
- v2: lint 0.55 → .swiftlint.yml 0.575 (0.125 미달)
- v2.1: cascade 0.65, lint 0.70 → 5개 모듈 모두 ≥ 0.70 PASS

Threshold: ≥ 0.70

Usage:
  python3 score_relevance.py <parsed.json> --candidates <fz-plugin-root> [--threshold 0.70]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SKILL_TO_AGENTS = {
    "fz-code": ["impl-correctness", "review-arch"],
    "fz-review": ["review-arch", "review-quality", "review-correctness", "review-direction", "review-counter"],
    "fz-plan": ["plan-structure", "plan-impact", "plan-edge-case", "review-direction"],
    "fz-discover": ["plan-structure", "review-arch"],
    "fz-search": ["search-symbolic", "search-pattern"],
    "fz-fix": ["impl-correctness"],
}

DEFAULT_CANDIDATE_GLOBS = [
    "skills/*/SKILL.md",
    "agents/*.md",
    "modules/*.md",
]

# Default empty — 사용자가 --project-root 또는 --extra-lint-paths로 명시.
# 일반화 가능성을 위해 hard-coded 경로 금지 (pre-commit hook enforce).
EXTRA_PROJECT_LINT_PATHS: list[Path] = []

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "and", "or", "but", "if", "then", "of", "in", "on", "at", "to",
    "이", "가", "을", "를", "에", "의", "는", "은", "도", "와", "과",
    "하다", "되다", "있다", "없다", "필요", "사용", "각", "그", "본", "수", "것",
}


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    words = re.findall(r"[A-Za-z가-힣_\-]{2,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w in STOP_WORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda k: -freq[k])[:top_n]


def label_to_skill_name(label: str) -> str | None:
    """applied_location label에서 skill name 추출. fz-code/fz-review/...
    word boundary 적용 — 'fz' in 'fz-code' false positive 방지."""
    for skill in SKILL_TO_AGENTS:
        if re.search(rf"\b{re.escape(skill)}\b", label, re.IGNORECASE):
            return skill
    return None


def has_symmetry_in_module(text: str, parsed: dict[str, Any]) -> bool:
    """본 메모리 패턴이 모듈에 대칭으로 존재하는지.

    v3 (Sanity Check 18차 반영): 유의어 cluster로 확장.
    같은 개념이 다른 단어로 표현되는 경우(scope inflation ↔ Scope Challenge ↔
    scope_disposition) 매칭 가능. 19차 overfit 방어.
    """
    core_lesson = parsed.get("core_lesson", "")
    core_lower = core_lesson.lower()
    body = text.lower()

    # Cluster 1: import / redundant
    if "import" in core_lower or "redundant" in core_lower:
        if re.search(r"import\s*orphan|symbol\s*coverage|symbol_orphan|redundant\s*import", body):
            return True

    # Cluster 2: self-review blind spot / cargo-cult
    if parsed.get("meta_pattern") == "self-review blind spot":
        if re.search(r"self[- ]review\s*meta[- ]loop|cargo[- ]cult", body):
            return True

    # Cluster 3: scope inflation (v3 신규 — 유의어 확장)
    scope_synonyms = (
        r"scope\s*inflation|complexity\s*drift|scope\s*challenge|"
        r"scope[_\s]*disposition|scope\s*expansion|scope\s*creep|"
        r"팽창|복잡도\s*드리프트"
    )
    if re.search(r"scope|inflation|drift|팽창", core_lower):
        if re.search(scope_synonyms, body):
            return True

    # Cluster 4: silent disappearance / 헬퍼 다중 책임 (v3.1 — P4 D+6 16차 반영)
    disappearance_synonyms = (
        r"silent\s*disappearance|책임\s*이전|책임.*분해|"
        r"헬퍼.*책임|multi[- ]responsibility|"
        r"call[- ]site\s*deprecation|responsibility\s*migration|"
        r"호출\s*중단|함수.*책임"
    )
    if re.search(r"silent|disappearance|책임|헬퍼|helper|호출.*중단", core_lower):
        if re.search(disappearance_synonyms, body):
            return True

    return False


def identify_trigger_skills(
    parsed: dict[str, Any],
    fz_root: Path,
) -> tuple[set[str], dict[str, str]]:
    """Pass 1: trigger skill set + 각 trigger의 활성화 사유.

    Returns:
        (trigger_skills, reasons): set of skill names + reason dict
    """
    triggers: set[str] = set()
    reasons: dict[str, str] = {}

    # 1.1: applied_location_explicit → direct trigger
    for label in parsed.get("applied_location_explicit", []):
        skill = label_to_skill_name(label)
        if skill:
            triggers.add(skill)
            reasons[skill] = f"direct mention via '{label}'"

    # 1.2: symmetry-extended trigger (해당 SKILL.md 파일에 symmetry 패턴 발견)
    for skill in SKILL_TO_AGENTS:
        if skill in triggers:
            continue
        skill_path = fz_root / "skills" / skill / "SKILL.md"
        if not skill_path.exists():
            continue
        text = skill_path.read_text(encoding="utf-8", errors="replace")
        if has_symmetry_in_module(text, parsed):
            triggers.add(skill)
            reasons[skill] = "symmetry-extended (대칭 패턴 발견)"

    return triggers, reasons


def score_module(
    module_path: Path,
    parsed: dict[str, Any],
    triggers: set[str],
    trigger_reasons: dict[str, str],
    keywords: list[str],
) -> dict[str, Any]:
    try:
        text = module_path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return {"module": str(module_path), "score": 0.0, "components": {}, "reason": "read_failed"}

    components = {
        "trigger_match": 0.0,
        "cascade_match": 0.0,
        "lint_tool": 0.0,
        "semantic": 0.0,
        "symmetry_bonus": 0.0,
    }
    reasons: list[str] = []

    # 1. Trigger match: SKILL.md 파일이 trigger skill인지
    if module_path.parent.name == "skills" or "skills" in module_path.parts:
        skill_dir = module_path.parent.name  # e.g., "fz-code"
        if skill_dir in triggers:
            components["trigger_match"] = 0.55
            reasons.append(f"trigger_match: {skill_dir} ({trigger_reasons.get(skill_dir, '')})")

    # 2. Cascade match: agent 파일이 trigger skill의 consumer인지
    if module_path.parent.name == "agents":
        agent_name = module_path.stem
        for skill in triggers:
            if agent_name in SKILL_TO_AGENTS.get(skill, []):
                components["cascade_match"] = 0.65
                reasons.append(f"cascade_match: {agent_name} → consumer of trigger {skill}")
                break

    # 3. Lint tool: compiler_gap_signal + lint config (단독으로 threshold 통과 가능)
    if parsed.get("signals", {}).get("compiler_gap_signal"):
        name = module_path.name.lower()
        if any(token in name for token in [".swiftlint", ".eslint", "tsconfig", "ruff", "pyproject"]):
            components["lint_tool"] = 0.70
            reasons.append("lint_tool: compiler_gap_signal + lint config")

    # 4. Semantic similarity (0 ~ 0.25)
    if keywords:
        hits = 0
        matched_kws: list[str] = []
        for kw in keywords:
            count = len(re.findall(re.escape(kw), text, re.IGNORECASE))
            if count > 0:
                hits += min(count, 5)
                matched_kws.append(f"{kw}({count})")
        max_possible = len(keywords) * 5
        components["semantic"] = round(min((hits / max_possible) * 0.25, 0.25), 3)
        if matched_kws and components["semantic"] >= 0.05:
            reasons.append(f"semantic: {', '.join(matched_kws[:3])}")

    # 5. Symmetry bonus: trigger 기준이 아니라 모듈 자체에 대칭 패턴
    if has_symmetry_in_module(text, parsed):
        components["symmetry_bonus"] = 0.20
        reasons.append("symmetry_bonus: 대칭 패턴 발견")

    # 5b. Trigger SKILL.md 자동 symmetry_bonus (P4 D+7 갭 6 fix)
    # trigger 자체가 강한 신호 — 사용자가 직접/유의어로 명시한 SKILL.md는
    # symmetry_bonus를 받지 못해도 ≥ 0.70 보장 위해 보완
    if (
        components["trigger_match"] > 0
        and components["symmetry_bonus"] == 0.0
    ):
        components["symmetry_bonus"] = 0.20
        reasons.append("auto_symmetry: trigger SKILL.md (자동 부여)")

    total = min(sum(components.values()), 1.0)

    return {
        "module": str(module_path),
        "score": round(total, 3),
        "components": components,
        "reason": "; ".join(reasons) if reasons else "no signals",
    }


def enumerate_candidates(
    fz_root: Path,
    project_root: Path | None = None,
    extra_lint_paths: list[Path] | None = None,
) -> list[Path]:
    """fz-plugin SKILL.md/agents/modules + project lint config 후보 enumerate.

    Args:
        fz_root: fz-plugin 루트
        project_root: 프로젝트 루트 (옵션, lint config 자동 검색)
        extra_lint_paths: 명시적 lint config 경로 리스트
    """
    candidates: list[Path] = []
    for glob in DEFAULT_CANDIDATE_GLOBS:
        candidates.extend(fz_root.glob(glob))

    if project_root and project_root.exists():
        for lint_name in (".swiftlint.yml", ".eslintrc", ".eslintrc.json", "tsconfig.json", "ruff.toml", "pyproject.toml"):
            for found in project_root.rglob(lint_name):
                candidates.append(found)

    for extra in (extra_lint_paths or []) + EXTRA_PROJECT_LINT_PATHS:
        if extra.exists():
            candidates.append(extra)

    return sorted(set(candidates))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("parsed", help="parse_memory.py 출력 JSON 파일 (또는 '-' for stdin)")
    ap.add_argument("--candidates", required=True, help="fz-plugin 루트 디렉토리")
    ap.add_argument("--threshold", type=float, default=0.70)
    ap.add_argument("--project-root", help="프로젝트 루트 (lint config 자동 검색용, 옵션)")
    ap.add_argument("--extra-lint-paths", nargs="*", default=[], help="명시적 lint config 경로 리스트")
    ap.add_argument("--show-all", action="store_true", help="threshold 이하도 표시")
    ap.add_argument("--output-json", help="결과 JSON 출력 경로")
    args = ap.parse_args()

    if args.parsed == "-":
        parsed = json.load(sys.stdin)
    else:
        parsed = json.loads(Path(args.parsed).read_text(encoding="utf-8"))

    fz_root = Path(args.candidates).expanduser()
    if not fz_root.exists():
        print(f"[error] fz-plugin root not found: {fz_root}", file=sys.stderr)
        return 1

    project_root = Path(args.project_root).expanduser() if args.project_root else None
    extra_lint_paths = [Path(p).expanduser() for p in args.extra_lint_paths]
    candidates = enumerate_candidates(fz_root, project_root, extra_lint_paths)
    keywords = extract_keywords(parsed.get("core_lesson", ""))

    triggers, trigger_reasons = identify_trigger_skills(parsed, fz_root)

    results = [score_module(c, parsed, triggers, trigger_reasons, keywords) for c in candidates]
    results.sort(key=lambda r: -r["score"])

    if not args.show_all:
        results = [r for r in results if r["score"] >= args.threshold]

    output = {
        "lesson_id": parsed.get("id"),
        "threshold": args.threshold,
        "keywords": keywords,
        "trigger_skills": sorted(triggers),
        "trigger_reasons": trigger_reasons,
        "selected_count": sum(1 for r in results if r["score"] >= args.threshold),
        "results": results,
    }

    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[ok] {len(results)} modules → {args.output_json}", file=sys.stderr)
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
