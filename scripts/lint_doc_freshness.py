#!/usr/bin/env python3
"""lint_doc_freshness.py — fz 문서 최신성 lint (탐지 자동화).

배경: 2026-07-25 전수 감사에서 `last audited` 보유 파일이 105개 중 4개뿐임이 드러났다.
즉 fz는 자기 문서의 stale을 탐지할 수단이 없었고, Opus 5 최신화도 자동 탐지가 아니라
사람이 출시를 알아채서 시작됐다. 본 스크립트는 그 탐지를 사람 주의력에서 분리한다.

설계 원칙 (⛔ 규칙 추가 아님):
  하네스 레벨 결정론적 강제 — "신뢰성 필수 동작은 advisory memory가 아니라 hooks"
  [verified: guides/llm-references.md §4-1]. 문서에 지켜야 할 규칙을 늘리는 대신
  기계가 검출한다. 따라서 adherence tax가 없다.

SSOT:
  현행 모델명은 `guides/llm-references.md` 의 `모델 정책: <X> only` 한 줄에서 읽는다.
  모델이 바뀌면 그 파일 한 곳만 고치면 본 lint가 따라온다.

⛔ 한계 (정직성):
  1. 최신성 ≠ 정확성. `last audited`가 오늘이어도 내용이 틀릴 수 있다. 본 도구는
     "언제 확인했는지 모르는 문서"를 찾을 뿐, 내용 검증은 하지 않는다.
  2. 모델명 검사는 규칙마다 입도가 다르다.
     - `stale-model-ref` = **파일 단위 휴리스틱**. 구세대 모델명이 인용/비교 맥락으로
       쓰이는 것은 정상이므로(예: `[verified: anthropic.com/news/claude-opus-4-8]`),
       "구세대만 있고 현행이 없는 파일"만 신고한다. 본문 라인 판정은 하지 않는다.
     - `stale-model-heading` = **heading 라인 단위**(2026-08-20 신설). 본문과 달리
       섹션 제목에 모델명이 박히면 그 절 전체가 그 모델에 종속돼 읽히므로 형식만으로
       판정이 닫힌다. ⛔ 본문 라인 전체 검사는 여전히 하지 않는다 — 실측상 오탐 24건.
  3. 대상은 **외부 URL을 인용하는 문서**로 한정한다. 내부 근거만 인용하는 문서는
     외부가 바뀌어도 stale해지지 않는다.

사용:
  python3 scripts/lint_doc_freshness.py                 # 기본 (90일)
  python3 scripts/lint_doc_freshness.py --days 60
  python3 scripts/lint_doc_freshness.py --json          # 기계 판독
  python3 scripts/lint_doc_freshness.py --strict        # 경고 시 exit 1 (CI/hook용)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# 감사 대상: 외부 사실이 바뀌면 stale해질 수 있는 문서만
EXTERNAL_URL = re.compile(
    r"platform\.claude\.com|code\.claude\.com|anthropic\.com|arxiv|developers\.openai\.com"
)
AUDIT_DATE = re.compile(r"last audited:\s*(\d{4}-\d{2}-\d{2})")
MODEL_POLICY = re.compile(r"모델 정책:\s*\*{0,2}([A-Za-z0-9. ]+?)\*{0,2}\s*only")

# 스캔 루트 (역사 기록·타 벤더 스킬·과거 산출물 제외)
SCAN_DIRS = ["guides", "modules", "skills", "agents", "templates"]
SCAN_FILES = ["CLAUDE.md"]
EXCLUDE_PARTS = {".claude", "node_modules", "docs", ".fz-work", "codex-skills"}

# 구세대 모델명 (현행이 없을 때만 신고)
LEGACY_MODELS = [
    "Opus 4.8", "opus-4-8", "Opus 4.7", "opus-4-7",
    "Opus 4.6", "opus-4-6", "Opus 4.5", "opus-4-5",
    "Sonnet 4.6", "sonnet-4-6", "Sonnet 4.5", "sonnet-4-5",
    # ⛔ `Claude N` 표기 (2026-08-20 신설): 어휘가 `Opus`/`Sonnet` 접두만 담고 있어
    #    `Claude 4.8` 형태가 통째로 빠져 있었다 — 실측 7곳(guides/ 3파일).
    "Claude 4.8", "Claude 4.7", "Claude 4.6",
]

# heading 판별 — `stale-model-heading` 전용 (아래 lint() 참조)
HEADING = re.compile(r"^#{1,6}\s")
# GFM fence 여닫이 — `iter_headings()`(lint_contracts.py #N8)와 같은 형태를 좁게 재현한다
FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})")


def find_docs(root: Path) -> list[Path]:
    out: list[Path] = []
    for d in SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*.md"):
            if EXCLUDE_PARTS & set(p.relative_to(root).parts):
                continue
            out.append(p)
    for f in SCAN_FILES:
        p = root / f
        if p.is_file():
            out.append(p)
    return sorted(out)


def current_model(root: Path) -> tuple[str, str]:
    """정본 문서에서 현행 모델명을 읽는다. (모델명, 출처) 반환."""
    canon = root / "guides" / "llm-references.md"
    if canon.is_file():
        m = MODEL_POLICY.search(canon.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(1).strip(), "guides/llm-references.md"
    return "", "(정본 미검출)"


def model_tokens(name: str) -> list[str]:
    """'Opus 5' -> ['Opus 5', 'opus-5', 'opus5'] 형태 변형 생성."""
    if not name:
        return []
    low = name.lower()
    return [name, low, low.replace(" ", "-"), low.replace(" ", "")]


def lint(root: Path, max_days: int) -> tuple[list[dict], dict]:
    today = date.today()
    cur, cur_src = current_model(root)
    cur_toks = model_tokens(cur)

    findings: list[dict] = []
    scanned = audited = 0

    for path in find_docs(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(root))

        if not EXTERNAL_URL.search(text):
            continue  # 외부 사실 미인용 → 대상 아님
        scanned += 1

        m = AUDIT_DATE.search(text)
        if not m:
            findings.append({
                "file": rel, "rule": "missing-audit-date", "severity": "warn",
                "detail": "외부 출처를 인용하지만 `last audited:` 가 없어 최신성 추적 불가",
            })
        else:
            audited += 1
            try:
                d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                age = (today - d).days
                if age > max_days:
                    findings.append({
                        "file": rel, "rule": "stale-audit", "severity": "warn",
                        "detail": f"last audited {m.group(1)} — {age}일 경과 (한도 {max_days}일)",
                    })
            except ValueError:
                findings.append({
                    "file": rel, "rule": "bad-audit-date", "severity": "warn",
                    "detail": f"날짜 파싱 실패: {m.group(1)!r}",
                })

        # 구세대 모델명만 있고 현행이 없는 파일
        if cur_toks:
            legacy_hits = [t for t in LEGACY_MODELS if t in text]
            has_current = any(t in text for t in cur_toks)
            if legacy_hits and not has_current:
                findings.append({
                    "file": rel, "rule": "stale-model-ref", "severity": "warn",
                    "detail": f"구세대 모델명 {sorted(set(legacy_hits))} 언급, 현행 '{cur}' 미언급",
                })

        # 구세대 모델명이 **섹션 제목**에 박힌 경우 (2026-08-20 신설)
        #
        # ⛔ 본문 잔존은 검사하지 않는다. 세대 비교표·역사 서술은 구모델명을 *써야* 한다 —
        #    실측: 라인 전면 검사 시 24건 발화, 다수가 `| Sonnet 4.5 시절 | Opus 4.6 이후 |`
        #    같은 정상 문서였다. 정상/결함 구분에 의미 판단이 필요해 결정론이 성립하지 않는다.
        # ✅ heading은 다르다. 섹션 제목에 모델명이 박히면 그 절 전체가 그 모델에 종속된 것으로
        #    읽히므로 **형식만으로 판정이 닫힌다** (실측 2건, 오탐 0).
        # ⚠️ 같은 heading에 현행 모델도 있으면 면제 — `### Opus 4.8 → Opus 5 마이그레이션`
        #    같은 정당한 비교 제목을 잡지 않기 위해서다.
        if cur_toks:
            # ⛔ fenced code 안의 `## …` 는 heading이 아니다 (CommonMark).
            #    실측(2026-08-20): 스캔셋에 fence 내 ATX 222건 — 그중 구세대 모델명 포함은
            #    **0건**이라 현재 오탐은 발화하지 않으나, 형태상 오탐이므로 차단한다.
            #    ⚠️ 범위 밖(실측 0건이라 미처리): 들여쓴 ATX 0건 · setext heading 중 모델명 0건.
            fence = None
            for ln, line in enumerate(text.split("\n"), 1):
                fm = FENCE.match(line)
                if fence is None:
                    if fm:
                        fence = fm.group(2)[0]
                        continue
                else:
                    if fm and fm.group(2)[0] == fence:
                        fence = None
                    continue
                if not HEADING.match(line):
                    continue
                hits = [t for t in LEGACY_MODELS if t in line]
                if hits and not any(t in line for t in cur_toks):
                    findings.append({
                        "file": f"{rel}:{ln}", "rule": "stale-model-heading", "severity": "warn",
                        "detail": f"섹션 제목에 구세대 모델명 {sorted(set(hits))} — 절 전체가 그 모델에 종속돼 읽힌다",
                    })

    summary = {
        "current_model": cur, "current_model_source": cur_src,
        "target_files": scanned, "with_audit_date": audited,
        "findings": len(findings), "max_days": max_days,
        "checked_on": today.isoformat(),
    }
    return findings, summary


def main() -> int:
    ap = argparse.ArgumentParser(description="fz 문서 최신성 lint")
    ap.add_argument("root", nargs="?", default=".", help="플러그인 루트 (기본: .)")
    ap.add_argument("--days", type=int, default=90, help="last audited 허용 경과일 (기본 90)")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--strict", action="store_true", help="경고 있으면 exit 1")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not (root / "guides").is_dir():
        print(f"⛔ 플러그인 루트가 아님: {root}", file=sys.stderr)
        return 2

    findings, summary = lint(root, args.days)

    if args.json:
        print(json.dumps({"summary": summary, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        print("=" * 78)
        print("fz 문서 최신성 lint — lint_doc_freshness.py")
        print("⛔ 최신성 ≠ 정확성. 본 도구는 '언제 확인했는지 모르는 문서'만 찾는다.")
        print("=" * 78)
        print(f"현행 모델: {summary['current_model'] or '(미검출)'}"
              f"  [SSOT: {summary['current_model_source']}]")
        print(f"대상(외부 출처 인용): {summary['target_files']}개"
              f" / audit 날짜 보유: {summary['with_audit_date']}개"
              f" / 한도: {summary['max_days']}일")
        print()
        if not findings:
            print("✅ 지적 없음")
        else:
            by_rule: dict[str, list[dict]] = {}
            for f in findings:
                by_rule.setdefault(f["rule"], []).append(f)
            for rule, items in sorted(by_rule.items()):
                print(f"■ {rule} ({len(items)}건)")
                for it in items:
                    print(f"   {it['file']}")
                    print(f"     └ {it['detail']}")
                print()
        print(f"총 {len(findings)}건")

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
