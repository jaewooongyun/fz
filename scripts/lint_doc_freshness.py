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
  현행 모델명은 `guides/llm-references.md` 의 `모델 정책: … only` 한 줄에서 읽는다.
  단일 표기 `모델 정책: <X> only` 와 역할별 다중 표기
  `모델 정책: <A> (Lead) · <B> (worker) only` 를 모두 파싱하며, 열거된 모델은
  **전부 현행**으로 취급한다(2026-09-06 신설 — Lead=Fable 5.1 / worker=Opus 5).
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
  python3 scripts/lint_doc_freshness.py --pointer-base <ref>   # `파일:N` 포인터가 가리키는 줄 내용이 <ref> 때와 다르면 보고

계약 규칙 (severity error — `--strict` 없이도 exit 1. 문서 숫자 · 등재가 실측과 갈린 것은 경고가 아니다):
  arxiv-unregistered   트리가 인용하는 arxiv ID ⊆ llm-references.md ∪ harness-engineering.md §참고 문헌 (F-287 —
                       레지스트리가 둘이라 어느 쪽에도 없는 인용이 생겼다. 새 인용은 llm-references.md §2 에 등재한다)
  cited-selftest-count docs · examples · modules 가 적은 `gate_stop_hook.py --self-test` 케이스 수 = 실측 (F-426)
  fixture-case-count   docs/architecture.md 의 판정기 회귀 'N케이스 (M범주)' = manifest 실측 (F-555)
보고 규칙 (warn):
  pointer-drift        `--pointer-base <ref>` — 문서의 `파일:N` 포인터가 <ref> 때와 같은 글자인데 대상 N번째 줄 내용이 바뀌었다
                       (F-305 — 줄 삽입이 포인터를 조용히 밀었다. #N3 는 빈 줄만 본다)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

# 감사 대상: 외부 사실이 바뀌면 stale해질 수 있는 문서만
EXTERNAL_URL = re.compile(
    r"platform\.claude\.com|code\.claude\.com|anthropic\.com|arxiv|developers\.openai\.com"
)
# ⛔ 위 패턴은 **문자열 존재**만 본다. 물어야 할 것은 "stale 될 수 있는 **외부 사실을 주장**하는가" 다.
#    인용을 *다루는 방법*을 설명하는 문서(템플릿 플레이스홀더 · 표 헤더 · fallback 절차 · grep 예시)는
#    외부 사실이 바뀌어도 낡지 않는다 — 거기에 `last audited:` 를 찍으면 **거짓 감사 기록**이 된다.
#    실측(2026-09-21): 12건 중 4건이 이 오탐이었다 (fz-modernize SKILL + 템플릿 3종).
#    ⛔ 같은 술어 결함이 `fz-findings F-285` 에도 있었다 — 술어를 좁히지 않으면 방어가 헛돈다.
CITATION_SHAPE = re.compile(
    r"arxiv\s*\d{4}\.\d{4,5}"                    # arxiv 2503.13657
    r"|\d{4}\.\d{4,5}\s*[,)\]]"                   # (2510.07777)
    r"|https?://"                                  # 실 URL (치환자 `{}` 는 PLACEHOLDER 가 걸러낸다 — 중복 규칙 제거)
    r"|\[verified:[^\]]*(?:claude|openai|anthropic)"  # [verified: platform.claude.com/...]
    r"|\[(?:platform|code)\.claude\.com[^\]]*\]",   # [code.claude.com/docs/...]
    re.I,
)
# 플레이스홀더·절차 표지 — 이 줄은 인용으로 세지 않는다
PLACEHOLDER = re.compile(r"\{[A-Za-z_]+\}|YYYY-MM|\| *arxiv ID *\||grep\s+-|preprint\]?\s*$", re.I)


def cites_external_fact(text: str) -> bool:
    """**stale 될 수 있는 외부 사실 주장**이 있는가. 플레이스홀더·절차 설명은 제외한다."""
    for line in text.split("\n"):
        if not EXTERNAL_URL.search(line):
            continue
        if PLACEHOLDER.search(line):
            continue                      # 템플릿·표 헤더·절차 — 낡지 않는다
        if CITATION_SHAPE.search(line):
            return True
    return False
AUDIT_DATE = re.compile(r"last audited:\s*(\d{4}-\d{2}-\d{2})")
MODEL_POLICY = re.compile(r"모델 정책:\s*\*{0,2}(.+?)\*{0,2}\s*only")
# 역할 표기 제거 — `Fable 5.1 (Lead)` → `Fable 5.1`
MODEL_ROLE = re.compile(r"\s*\([^)]*\)\s*$")

# 스캔 루트 (역사 기록·타 벤더 스킬·과거 산출물 제외)
SCAN_DIRS = ["guides", "modules", "skills", "agents", "templates"]
SCAN_FILES = ["CLAUDE.md"]
EXCLUDE_PARTS = {".claude", "node_modules", "docs", ".fz-work", "gpt-skills"}

# 구세대 모델명 (현행이 없을 때만 신고)
LEGACY_MODELS = [
    "Opus 4.8", "opus-4-8", "Opus 4.7", "opus-4-7",
    "Opus 4.6", "opus-4-6", "Opus 4.5", "opus-4-5",
    "Sonnet 4.6", "sonnet-4-6", "Sonnet 4.5", "sonnet-4-5",
    # ⛔ `Claude N` 표기 (2026-08-20 신설): 어휘가 `Opus`/`Sonnet` 접두만 담고 있어
    #    `Claude 4.8` 형태가 통째로 빠져 있었다 — 실측 7곳(guides/ 3파일).
    "Claude 4.8", "Claude 4.7", "Claude 4.6",
    # ⛔ `Opus 5` (2026-09-25 신설): 워커가 Opus 5.5 로 바뀌어 구세대가 됐다. `Opus 5` ⊂ `Opus 5.5`,
    #    `opus-5` ⊂ `claude-opus-5-5` 라 부분문자열 검사로는 현행 표기까지 잡는다 → `legacy_hits()` 로 판정한다.
    "Opus 5", "opus-5",
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


def current_model(root: Path) -> tuple[list[str], str]:
    """정본 문서에서 현행 모델명을 읽는다. (모델명 목록, 출처) 반환.

    표기 2종을 모두 파싱한다 (하위 호환):
      - 단일: `모델 정책: Opus 5 only`                        -> ['Opus 5']
      - 다중: `모델 정책: Fable 5.1 (Lead) · Opus 5 (worker) only`
                                                             -> ['Fable 5.1', 'Opus 5']
    괄호 안 역할 표기는 이름에서 떼어낸다. 목록의 모델은 **전부 현행**이므로
    `stale-model-ref`·`stale-model-heading`은 그중 하나라도 있으면 면제한다.
    """
    canon = root / "guides" / "llm-references.md"
    if canon.is_file():
        m = MODEL_POLICY.search(canon.read_text(encoding="utf-8", errors="replace"))
        if m:
            names = []
            for part in re.split(r"[·,]", m.group(1)):
                name = MODEL_ROLE.sub("", part).strip().strip("*").strip()
                if name:
                    names.append(name)
            if names:
                return names, "guides/llm-references.md"
    return [], "(정본 미검출)"


def model_tokens(names: list[str] | str) -> list[str]:
    """'Opus 5' -> ['Opus 5', 'opus-5', 'opus5'] 형태 변형 생성 (목록 입력 허용).

    ⛔ 점을 대시로 바꾼 변형(`fable-5-1`)을 포함한다 — 모델 ID가 `claude-fable-5-1`
       형태라 `fable-5.1`만으로는 ID 표기를 놓친다 ('Opus 5'->'opus-5' 매칭과 같은 목적).
    """
    if isinstance(names, str):
        names = [names] if names else []
    out: list[str] = []
    for name in names:
        low = name.lower()
        out += [name, low, low.replace(" ", "-"),
                low.replace(" ", "-").replace(".", "-"), low.replace(" ", "")]
    return list(dict.fromkeys(out))


def legacy_hits(text: str, cur_toks: list[str]) -> list[str]:
    """`text` 에 나오는 구세대 모델 토큰 — 같은 위치에서 현행 토큰이 시작하는 매치는 버린다.

    `Opus 5.5` 안의 `Opus 5`, `claude-opus-5-5` 안의 `opus-5` 는 현행 표기의 일부라 구세대가 아니다.
    `claude-opus-4-8-20260101` 의 `opus-4-8` 은 같은 위치에 현행 토큰이 없으므로 그대로 잡는다.
    """
    hits = set()
    for t in LEGACY_MODELS:
        start = text.find(t)
        while start != -1:
            if not any(text.startswith(c, start) for c in cur_toks):
                hits.add(t)
                break
            start = text.find(t, start + 1)
    return sorted(hits)


ARXIV_CITE = re.compile(r"(?i)(?:arxiv\.org/(?:abs|pdf)/|arxiv[\s:]*(?:preprint)?[\s,:#]*)(\d{4}\.\d{4,5})(?:v\d+)?")
ARXIV_EXTS = (".md", ".py", ".js", ".sh", ".json", ".yaml", ".yml")
# 이력(릴리스 노트 · 실험 기록)과 일부러 지어낸 입력(fixture · 이 파일의 self-test)은 인용이 아니다
ARXIV_SKIP_DIRS = ("docs/releases/", "tests/fixtures/")
ARXIV_SKIP_FILES = {"CHANGELOG.md", "experiment-log.md", "scripts/lint_doc_freshness.py"}
REGISTRY_SECTION = re.compile(r"^#{1,3}[^\n]*참고\s*문헌[^\n]*\n(.*?)(?=^#{1,2} |\Z)", re.S | re.M)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _tree_files(root: Path) -> list:
    """검사 대상 파일 — 저장소 최상위면 추적 + ignore 되지 않은 새 파일만(`.fz-work/` · `.claude/worktrees/` 같은 로컬 산출물이
    릴리스 판정을 흔들지 않게). git 이 아니면(설치본) 전체를 순회한다."""
    if (root / ".git").exists():
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-co", "--exclude-standard"], capture_output=True)
        if r.returncode == 0:
            return sorted(root / p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0") if p)
    return sorted(root.rglob("*"))


def arxiv_findings(root: Path) -> list[dict]:
    """트리의 arxiv 인용 중 두 레지스트리 어디에도 없는 ID (F-287). 레지스트리 파일이 없으면 판정하지 않는다."""
    reg_doc = root / "guides" / "llm-references.md"
    if not reg_doc.is_file():
        return []
    reg = set(re.findall(r"\d{4}\.\d{4,5}", reg_doc.read_text(encoding="utf-8", errors="replace")))
    he = root / "guides" / "harness-engineering.md"
    if he.is_file():
        m = REGISTRY_SECTION.search(he.read_text(encoding="utf-8", errors="replace"))
        if m:
            reg |= set(re.findall(r"\d{4}\.\d{4,5}", m.group(1)))
    out = []
    for q in _tree_files(root):
        rel = q.relative_to(root).as_posix()
        if (not q.is_file() or q.suffix not in ARXIV_EXTS or any(s.startswith(".git") for s in q.parts)
                or rel.startswith(ARXIV_SKIP_DIRS) or rel in ARXIV_SKIP_FILES):
            continue
        text = q.read_text(encoding="utf-8", errors="replace")
        for m in ARXIV_CITE.finditer(text):
            if m.group(1) not in reg:
                out.append({"file": f"{rel}:{_line_of(text, m.start())}", "rule": "arxiv-unregistered", "severity": "error",
                            "detail": f"arxiv {m.group(1)} 이 llm-references.md · harness-engineering.md §참고 문헌 어디에도 없다 — llm-references.md §2 에 등재하거나 인용을 거둔다"})
    return out


HOOK_CITE_NUM = re.compile(r"(\d+)\s*케이스|(\d+)/(\d+)\s*passed")


def hook_case_count(root: Path) -> int | None:
    """`gate_stop_hook.py --self-test` 의 케이스 수 실측 — 끝 줄 `N/M passed` 의 M. 못 재면 None."""
    hook = root / "scripts" / "gate_stop_hook.py"
    if not hook.is_file():
        return None
    try:
        r = subprocess.run([sys.executable, str(hook), "--self-test"], cwd=root, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.findall(r"(\d+)/(\d+)\s*passed", r.stdout)
    return int(m[-1][1]) if m else None


def cited_count_findings(root: Path) -> list[dict]:
    """docs(릴리스 노트 제외) · examples · modules 의 `gate_stop_hook.py --self-test` 케이스 수 인용 = 실측 (F-426)."""
    sites = []
    for sub_ in ("docs", "examples", "modules"):
        for q in sorted((root / sub_).rglob("*")) if (root / sub_).is_dir() else []:
            rel = q.relative_to(root).as_posix()
            if not q.is_file() or rel.startswith("docs/releases/"):
                continue
            for i, ln in enumerate(q.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                if "gate_stop_hook" not in ln or "--self-test" not in ln:
                    continue
                tail = ln[ln.index("--self-test"):]
                m = HOOK_CITE_NUM.search(tail)
                if m:
                    sites.append((f"{rel}:{i}", int(m.group(1) or m.group(3))))
    if not sites:
        return []
    real = hook_case_count(root)
    if real is None:
        return [{"file": sites[0][0], "rule": "cited-selftest-unmeasured", "severity": "warn",
                 "detail": "gate_stop_hook.py --self-test 케이스 수를 재지 못했다 — 인용 대조 미판정(⛔ 통과 아님)"}]
    return [{"file": f, "rule": "cited-selftest-count", "severity": "error",
             "detail": f"gate_stop_hook --self-test 를 {n}케이스로 적었는데 실측 {real} — 숫자를 고친다"}
            for f, n in sites if n != real]


FIXTURE_CITE = re.compile(r"(\d+)\s*케이스\s*\((\d+)\s*범주")


def fixture_count_findings(root: Path) -> list[dict]:
    """docs/architecture.md 의 판정기 회귀 'N케이스 (M범주)' = tests/fixtures/gates/manifest.json 실측 (F-555)."""
    doc, man = root / "docs" / "architecture.md", root / "tests" / "fixtures" / "gates" / "manifest.json"
    if not doc.is_file() or not man.is_file():
        return []
    try:
        cases = json.loads(man.read_text(encoding="utf-8"))["cases"]
    except (ValueError, KeyError) as e:
        return [{"file": "tests/fixtures/gates/manifest.json", "rule": "fixture-case-count", "severity": "error",
                 "detail": f"manifest 를 읽지 못했다 — {type(e).__name__}: {e}"}]
    n, k = len(cases), len({c.get("category") for c in cases})
    out = []
    for i, ln in enumerate(doc.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
        if "fixtures/gates" not in ln:
            continue
        for m in FIXTURE_CITE.finditer(ln):
            if (int(m.group(1)), int(m.group(2))) != (n, k):
                out.append({"file": f"docs/architecture.md:{i}", "rule": "fixture-case-count", "severity": "error",
                            "detail": f"'{m.group(0)}' 로 적었는데 manifest 는 {n}케이스 ({k}범주) — 숫자를 고친다"})
    return out


POINTER = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:md|py|sh|js|json|yaml|tsv)):(\d+)(?!\d)")


def pointer_findings(root: Path, ref: str) -> list[dict]:
    """`파일:N` 포인터가 <ref> 때와 같은 글자로 문서에 있는데 대상 N번째 줄 내용이 바뀌었으면 보고 (F-305).

    - Note: 포인터를 이번에 새로 쓴 문서 줄은 보지 않는다 — 기준 문서에 같은 포인터 글자가 있을 때만 대조한다.
      대상 경로는 루트 기준 · 없으면 `skills/` 아래로 한 번 더 찾는다(`fz-review/SKILL.md:213` 꼴).
    """
    cache: dict[str, list[str] | None] = {}

    def base_lines(rel: str):
        if rel not in cache:
            r = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{rel}"], capture_output=True, text=True, errors="replace")
            cache[rel] = r.stdout.split("\n") if r.returncode == 0 else None
        return cache[rel]

    out = []
    for q in sorted(root.rglob("*.md")):
        rel = q.relative_to(root).as_posix()
        if any(s.startswith(".git") for s in q.parts) or rel.startswith(("docs/releases/", "tests/fixtures/")) \
                or rel in ("CHANGELOG.md", "experiment-log.md"):
            continue
        text = q.read_text(encoding="utf-8", errors="replace")
        base_doc = base_lines(rel)
        if base_doc is None:
            continue
        base_text = "\n".join(base_doc)
        for m in POINTER.finditer(text):
            tgt, n = m.group(1), int(m.group(2))
            if m.group(0) not in base_text:
                continue
            for cand in (tgt, f"skills/{tgt}"):
                if (root / cand).is_file():
                    tgt = cand
                    break
            else:
                continue
            old = base_lines(tgt)
            now = (root / tgt).read_text(encoding="utf-8", errors="replace").split("\n")
            if old is None or not (1 <= n <= len(old)) or not (1 <= n <= len(now)):
                continue
            if old[n - 1].strip() != now[n - 1].strip():
                out.append({"file": f"{rel}:{_line_of(text, m.start())}", "rule": "pointer-drift", "severity": "warn",
                            "detail": f"`{m.group(0)}` 의 대상 줄이 {ref} 때 {old[n - 1].strip()[:50]!r} → 지금 {now[n - 1].strip()[:50]!r} — 줄 삽입 · 삭제로 밀렸는지 본다"})
    return out


def lint(root: Path, max_days: int) -> tuple[list[dict], dict]:
    today = date.today()
    cur, cur_src = current_model(root)
    cur_label = " · ".join(cur)
    cur_toks = model_tokens(cur)

    findings: list[dict] = []
    scanned = audited = 0

    for path in find_docs(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(root))

        if not cites_external_fact(text):
            continue  # 외부 **사실** 미인용 → 대상 아님 (문자열 존재만으로는 대상이 아니다)
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
            legacy = legacy_hits(text, cur_toks)
            has_current = any(t in text for t in cur_toks)
            if legacy and not has_current:
                findings.append({
                    "file": rel, "rule": "stale-model-ref", "severity": "warn",
                    "detail": f"구세대 모델명 {legacy} 언급, 현행 '{cur_label}' 미언급",
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
                hits = legacy_hits(line, cur_toks)
                if hits and not any(t in line for t in cur_toks):
                    findings.append({
                        "file": f"{rel}:{ln}", "rule": "stale-model-heading", "severity": "warn",
                        "detail": f"섹션 제목에 구세대 모델명 {sorted(set(hits))} — 절 전체가 그 모델에 종속돼 읽힌다",
                    })

    # 계약 규칙 — 파일별 최신성 루프와 대상이 다르다(인용 전체 · 숫자 인용)
    findings += arxiv_findings(root) + cited_count_findings(root) + fixture_count_findings(root)

    summary = {
        "current_model": cur_label, "current_model_source": cur_src,
        "target_files": scanned, "with_audit_date": audited,
        "findings": len(findings), "max_days": max_days,
        "checked_on": today.isoformat(),
    }
    return findings, summary


def self_test():
    """술어 fixture — 실인용은 잡고 **플레이스홀더·절차는 안 잡는다**.

    ⛔ 신설 근거(2026-09-21): 이 검사기는 self-test 가 **없었다**. 술어가
    `EXTERNAL_URL.search(text)` — 파일 어딘가에 문자열이 있으면 대상이라 실측 12건 중 **4건이 오탐**이었다
    (`fz-modernize` 템플릿 3종 + SKILL). 인용을 *다루는 방법*을 설명하는 문서는 외부 사실이 바뀌어도
    낡지 않는데, 거기에 `last audited:` 를 찍으면 거짓 감사 기록이 된다.
    """
    passed, failed, cases = [], [], 0

    def check(name, text, want):
        nonlocal cases
        cases += 1
        got = cites_external_fact(text)
        if got == want:
            passed.append(name)
        else:
            failed.append(f"{name}: {got} (기대 {want})")

    # ── 실인용 — 잡아야 한다 ──
    check("arxiv-id", "근거 [verified: arxiv 2503.13657 \"Why Do Multi-Agent LLM Systems Fail?\"]", True)
    check("arxiv-paren", "Drift No More — Context Equilibria (arxiv 2510.07777) — 효과 실증", True)
    check("real-url", "참조: Anthropic 공식 Memory tool (https://platform.claude.com/docs/en/tool-use/memory-tool)", True)
    check("verified-tag", '"Re-run the sweep" [verified: platform.claude.com/docs/en/prompting-claude-fable-5-1]', True)
    check("bracket-doc", '*"From v2.1.154 …"* [code.claude.com/docs/en/code-review]', True)

    # ── 오탐 — 잡으면 안 된다 (실측 4건의 형태) ──
    check("placeholder-preprint", "[arxiv preprint, YYYY-MM]                      ← preprint 명시", False)
    check("table-header", "| # | arxiv ID | 제목 | 저자 | Status | 핵심 |", False)
    check("fallback-procedure", "| arxiv abs 페이지 변경 | arxiv.org/pdf/{ID} fallback |", False)
    check("grep-example", 'grep -nE "arxiv|arXiv" guides/*.md', False)
    check("status-label", "- Status 칼럼 (peer-reviewed / arxiv preprint / official / community)", False)
    check("no-external", "이 문서는 외부 출처를 인용하지 않는다", False)

    # ── 경계 ──
    check("mixed-file", "| arxiv ID |\n\n근거 (arxiv 2512.20845) 역할 분리", True)   # 한 줄이라도 실인용이면 대상
    check("templated-url", "폴백: https://arxiv.org/pdf/{ID}", False)               # {} 치환자 = 절차

    # ── ⛔ 두 방어를 **각각** 격리한다 (한쪽이 다른 쪽에 가려지면 ablation 이 헛돈다) ──
    # PLACEHOLDER 전용: CITATION_SHAPE 는 매칭되는데(실 arxiv ID) 플레이스홀더 문맥이라 제외돼야 한다
    check("placeholder-beats-shape",
          "예시 행: | B1 | arxiv 2510.07777 | 제목 | `[arxiv preprint, YYYY-MM]` |", False)
    # `{}` 전용: 스킴 있는 URL 이라 https 분기에 닿지만 치환자가 있어 제외돼야 한다
    check("brace-url-not-citation", "취득 경로: https://platform.claude.com/docs/{section}", False)

    # ── ⛔ 통합 fixture — **호출부**가 새 술어를 쓰는지 본다.
    #    위 check() 는 `cites_external_fact()` 를 직접 부르므로, 호출부가 구판
    #    `EXTERNAL_URL.search(text)` 로 되돌아가도 전부 통과한다(실측 헛돌이).
    #    실제 트리를 스캔해 **대상 수**로 판정한다.
    import tempfile as _tf
    cases += 1
    with _tf.TemporaryDirectory() as _d:
        root = Path(_d)
        (root / "modules").mkdir()
        (root / "modules" / "real.md").write_text(
            "> 근거 (arxiv 2503.13657) 실증\n", encoding="utf-8")
        (root / "modules" / "template.md").write_text(
            "| # | arxiv ID | 제목 |\n| B1 | | `[arxiv preprint, YYYY-MM]` |\n", encoding="utf-8")
        n_target = sum(1 for q in find_docs(root) if cites_external_fact(q.read_text(encoding="utf-8")))
        # 호출부가 구판이면 template.md 도 대상이 돼 2가 된다
        if n_target == 1:
            passed.append("caller-uses-new-predicate")
        else:
            failed.append(f"caller-uses-new-predicate: 대상 {n_target}개 (기대 1 — 템플릿은 제외돼야 한다)")

    # ── 구세대 판정 — 부분문자열 충돌(`Opus 5` ⊂ `Opus 5.5`) 과 날짜 ID
    toks = model_tokens(["Fable 5.1", "Opus 5.5"])
    for name, text, want in (
        ("legacy-opus5-bare", "Opus 5 운용 절", ["Opus 5"]),
        ("legacy-opus5-id", "모델 ID `claude-opus-5`", ["opus-5"]),
        ("legacy-opus5-not-inside-opus55", "Opus 5.5 · `claude-opus-5-5`", []),
        ("legacy-opus48-dated-id", "`claude-opus-4-8-20260101`", ["opus-4-8"]),
    ):
        cases += 1
        got = legacy_hits(text, toks)
        (passed.append(name) if got == want else failed.append(f"{name}: {got} (기대 {want})"))
    # ── 파일 규칙은 **호출부**로 본다 — 헬퍼만 부르면 lint() 가 구판 부분문자열 검사로 돌아가도 통과한다
    for name, body, want in (
        ("file-rule-opus5-only-fires", "> 근거 (arxiv 2503.13657) — Opus 5 운용\n", True),
        ("file-rule-opus55-exempt", "> 근거 (arxiv 2503.13657) — Opus 5.5 · `claude-opus-5-5` 운용\n", False),
    ):
        cases += 1
        with _tf.TemporaryDirectory() as _d:
            root = Path(_d)
            (root / "guides").mkdir()
            (root / "modules").mkdir()
            (root / "guides" / "llm-references.md").write_text(
                "> **모델 정책: Fable 5.1 (Lead) · Opus 5.5 (worker) only**\n", encoding="utf-8")
            (root / "modules" / "a.md").write_text(body, encoding="utf-8")
            fired = any(f["rule"] == "stale-model-ref" and f["file"] == "modules/a.md" for f in lint(root, 90)[0])
            (passed.append(name) if fired == want else failed.append(f"{name}: 발화 {fired} (기대 {want})"))

    # ── 계약 규칙 (F-287 · F-426 · F-555 · F-305) — 임시 루트에서 위반 · 충족 쌍
    def contract_root(d: Path, ref_ids: str, cite: str, hook_total: int, doc_cases: str):
        for sub_ in ("guides", "modules", "docs", "examples", "scripts", "tests/fixtures/gates"):
            (d / sub_).mkdir(parents=True, exist_ok=True)
        (d / "guides" / "llm-references.md").write_text(f"| arxiv | 제목 |\n| {ref_ids} | x |\n", encoding="utf-8")
        (d / "modules" / "m.md").write_text(f"근거 (arxiv {cite}) 실증\n", encoding="utf-8")
        (d / "scripts" / "gate_stop_hook.py").write_text(f"print('stop-hook self-test {hook_total}/{hook_total} passed')\n", encoding="utf-8")
        (d / "docs" / "completion-gates.md").write_text("python3 scripts/gate_stop_hook.py --self-test   # 40/40 passed\n", encoding="utf-8")
        (d / "tests/fixtures/gates/manifest.json").write_text(json.dumps({"cases": [{"category": "a"}, {"category": "a"}, {"category": "b"}]}), encoding="utf-8")
        (d / "docs" / "architecture.md").write_text(f"├── tests/  fixtures/gates/ — 판정기 회귀 {doc_cases}, 기대 exit)\n", encoding="utf-8")

    for name, args_, rule, want in (
        ("f287-arxiv-unregistered", ("2401.00001", "2401.00002", 40, "3케이스 (2범주"), "arxiv-unregistered", True),
        ("f287-registered-ok", ("2401.00001", "2401.00001", 40, "3케이스 (2범주"), "arxiv-unregistered", False),
        ("f426-cited-selftest-count", ("2401.00001", "2401.00001", 41, "3케이스 (2범주"), "cited-selftest-count", True),
        ("f426-cited-count-ok", ("2401.00001", "2401.00001", 40, "3케이스 (2범주"), "cited-selftest-count", False),
        ("f555-fixture-case-count", ("2401.00001", "2401.00001", 40, "99케이스 (17범주"), "fixture-case-count", True),
        ("f555-count-ok", ("2401.00001", "2401.00001", 40, "3케이스 (2범주"), "fixture-case-count", False),
    ):
        cases += 1
        with _tf.TemporaryDirectory() as _d:
            contract_root(Path(_d), *args_)
            got = [f for f in lint(Path(_d), 90)[0] if f["rule"] == rule]
            fired = bool(got) and all(f["severity"] == "error" for f in got)
            (passed.append(name) if fired == want else failed.append(f"{name}: 발화 {bool(got)} (기대 {want}) {got[:1]}"))

    # F-287 후속 — gitignore 된 로컬 산출물(.fz-work/)의 미등재 인용은 보지 않는다 · ignore 안 된 새 파일의 같은 인용은 본다(대조 셀)
    cases += 1
    with _tf.TemporaryDirectory() as _d:
        d = Path(_d)
        contract_root(d, "2401.00001", "2401.00001", 40, "3케이스 (2범주")
        (d / ".gitignore").write_text(".fz-work/\n", encoding="utf-8")
        (d / ".fz-work").mkdir()
        (d / ".fz-work" / "w.md").write_text("근거 (arxiv 2401.00009) 실증\n", encoding="utf-8")
        subprocess.run(["git", "-C", _d, "init", "-q"], capture_output=True)
        ign = [f["file"] for f in lint(d, 90)[0] if f["rule"] == "arxiv-unregistered"]
        (d / "modules" / "new.md").write_text("근거 (arxiv 2401.00009) 실증\n", encoding="utf-8")
        new = [f["file"] for f in lint(d, 90)[0] if f["rule"] == "arxiv-unregistered"]
        ok = ign == [] and new == ["modules/new.md:1"]
        (passed.append("f287-gitignored-work-skipped") if ok else failed.append(f"f287-gitignored-work-skipped: ignore {ign} · 새 파일 {new}"))

    # F-305 — 기준 커밋에서 `b.py:2` 를 가리키던 문서 · 대상 위에 줄을 끼우면 보고, 아래를 고치면 조용
    for name, edit, want in (
        ("f305-pointer-content-drift", lambda s: "inserted\n" + s, True),
        ("f305-pointer-same-content-ok", lambda s: s + "tail\n", False),
    ):
        cases += 1
        with _tf.TemporaryDirectory() as _d:
            d = Path(_d)
            (d / "guides").mkdir()
            (d / "guides" / "a.md").write_text("포인터 `scripts/b.py:2` 참조\n", encoding="utf-8")
            (d / "scripts").mkdir()
            (d / "scripts" / "b.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
            g = lambda *a: subprocess.run(["git", "-C", _d, "-c", "user.email=t@t", "-c", "user.name=t", *a], capture_output=True)
            if any(g(*a).returncode for a in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "base"))):
                failed.append(f"{name}: 픽스처 git 준비 실패")
                continue
            b = d / "scripts" / "b.py"
            b.write_text(edit(b.read_text(encoding="utf-8")), encoding="utf-8")
            fired = any(f["rule"] == "pointer-drift" for f in pointer_findings(d, "HEAD"))
            (passed.append(name) if fired == want else failed.append(f"{name}: 발화 {fired} (기대 {want})"))

    print(f"self-test {len(passed)}/{cases} 통과")
    for x in passed:
        print(f"  ok   {x}")
    for x in failed:
        print(f"  FAIL {x}")
    return 0 if not failed else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="fz 문서 최신성 lint")
    ap.add_argument("root", nargs="?", default=".", help="플러그인 루트 (기본: .)")
    ap.add_argument("--days", type=int, default=90, help="last audited 허용 경과일 (기본 90)")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--strict", action="store_true", help="경고 있으면 exit 1")
    ap.add_argument("--self-test", action="store_true", help="술어 fixture 실행")
    ap.add_argument("--pointer-base", metavar="REF", help="`파일:N` 포인터 대상 줄 내용을 REF 와 대조(보고)")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    root = Path(args.root).resolve()
    if not (root / "guides").is_dir():
        print(f"⛔ 플러그인 루트가 아님: {root}", file=sys.stderr)
        return 2

    findings, summary = lint(root, args.days)
    if args.pointer_base:
        findings += pointer_findings(root, args.pointer_base)

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
        n_err = sum(f["severity"] == "error" for f in findings)
        if n_err:
            print(f"⛔ 계약 오류 {n_err}건 — 경고와 달리 exit 1 (문서 숫자 · 등재가 실측과 갈렸다)")

    if any(f["severity"] == "error" for f in findings) or (args.strict and findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
