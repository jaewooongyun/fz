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
  구세대도 그 줄에서 **도출**한다 — 줄에 적힌 계열(Fable · Opus · Sonnet · Haiku)마다 그 판보다 낮은 판이 구세대다
  (수치 비교 — 5.10 > 5.9 · 맨 주 버전 `Opus 5` = 5.0 · 줄보다 높은 판은 구세대가 아니다). 그래서 모델이 바뀌면
  그 한 줄만 고치면 직전 판을 어디에도 적지 않아도 본 lint가 따라온다. 손 목록 `LEGACY_MODELS` 는 줄에 없는
  계열(지금 Sonnet)과 `Claude N.N` 표기에만 쓰이고, 거기서는 목록에 적은 판만 잡는다 — 그래서 정책 줄에서 빠진 계열은
  목록에 판을 적기 전까지 잡히지 않는다(지금 목록에 Fable · Opus 판은 없다).

⛔ 한계 (정직성):
  1. 최신성 ≠ 정확성. `last audited`가 오늘이어도 내용이 틀릴 수 있다. 본 도구는
     "언제 확인했는지 모르는 문서"를 찾을 뿐, 내용 검증은 하지 않는다.
  2. 모델명 검사는 규칙마다 입도가 다르다.
     - `stale-model-ref` = **파일 단위 휴리스틱**. 구세대 모델명이 인용/비교 맥락으로
       쓰이는 것은 정상이므로(예: `[verified: anthropic.com/news/claude-opus-4-8]`),
       "구세대만 있고 현행이 없는 파일"만 신고한다. 본문 라인 판정은 하지 않는다.
       ⛔ 그래서 현행 모델을 한 번이라도 적은 파일은 본문에 '현행 Lead 는 <직전 판>' 같은 낡은 문장이 남아도
       잡지 못한다 — 모델을 바꿀 때 그런 문장은 사람이 grep 해 읽는다. 거꾸로 현행을 적지 않은 파일은
       출처 인용(`[verified: …구판 페이지]`)만 구세대여도 신고된다 — 유래 인용이면 고치지 않고 사유를 남긴다.
     - `stale-model-heading` = **heading 라인 단위**(2026-08-20 신설). 본문과 달리
       섹션 제목에 모델명이 박히면 그 절 전체가 그 모델에 종속돼 읽히므로 형식만으로
       판정이 닫힌다. ⛔ 본문 라인 전체 검사는 여전히 하지 않는다 — 실측상 오탐 24건.
       같은 제목 줄에 현행 모델이나 이력 표지(`이전` · `이력` — `HISTORY_MARK`)가 있으면 면제한다. 표지는 낱말만
       보고 뜻은 읽지 않는다 — `이전` 이 '옮김' 뜻이어도 면제되고, 본문에 적은 표지는 제목을 면제하지 않는다.
     - 두 규칙은 아래 3의 거르기 밖이다 — 스캔 대상(`SCAN_DIRS` · `SCAN_FILES`, `EXCLUDE_PARTS` 제외) 전부에서 돈다. 모델명 자체가
       외부 사실이라(모델이 바뀌면 낡는다) 외부 URL 을 인용하지 않는 문서도 구세대만 남으면 신고한다.
       스캔 루트 밖의 살아 있는 문서 둘(`MODEL_ONLY_FILES` — 루트 README · `docs/architecture.md`)도 이 두 규칙만 본다.
       그 밖의 스캔 밖 문서(`docs/` 의 나머지 · `tests/` · `gpt-skills/` · CHANGELOG · experiment-log)는 보지 않는다 — 이력 · fixture · 타 벤더 문서다.
  3. 감사일 규칙(`missing-audit-date` · `stale-audit` · `bad-audit-date`)의 대상은 **외부 URL을 인용하는 문서**로 한정한다.
     내부 근거만 인용하는 문서는 외부가 바뀌어도 stale해지지 않는다 — 요약 줄의 `대상(외부 출처 인용)` 수도 이 대상만 센다.
  4. Claude Code 버전 대조는 기본 실행에서 **설치 버전과 기준 줄의 대소**만 본다(네트워크 없음 · 경고) — 무엇이 바뀌었는지는
     모른다. changelog 를 읽는 대조(`--online` · `--changelog-file`)도 '새 기본 모델 공지' 한 꼴만 본다 — 옵션 · 기본값 ·
     한도 같은 다른 변경은 사람이 changelog 를 읽어 대조한다.

사용:
  python3 scripts/lint_doc_freshness.py                 # 기본 (90일)
  python3 scripts/lint_doc_freshness.py --days 60
  python3 scripts/lint_doc_freshness.py --json          # 기계 판독
  python3 scripts/lint_doc_freshness.py --strict        # 경고 시 exit 1 (CI/hook용 — 아래 보고 규칙 경고도 센다)
  python3 scripts/lint_doc_freshness.py --pointer-base <ref>   # `파일:N` 포인터가 가리키는 줄 내용이 <ref> 때와 다르면 보고
  python3 scripts/lint_doc_freshness.py --online        # Claude Code changelog 대조(opt-in · 네트워크) — 아래 대조 모드
  python3 scripts/lint_doc_freshness.py --changelog-file <사본>   # 같은 대조를 changelog 사본으로(네트워크 없음 · fixture)

계약 규칙 (severity error — `--strict` 없이도 exit 1. 문서 숫자 · 등재가 실측과 갈린 것은 경고가 아니다):
  arxiv-unregistered   트리가 인용하는 arxiv ID ⊆ llm-references.md ∪ harness-engineering.md §참고 문헌 (F-287 —
                       레지스트리가 둘이라 어느 쪽에도 없는 인용이 생겼다. 새 인용은 llm-references.md §2 에 등재한다)
  cited-selftest-count docs · examples · modules 가 적은 `gate_stop_hook.py --self-test` 케이스 수 = 실측 (F-426)
  fixture-case-count   docs/architecture.md 의 판정기 회귀 'N케이스 (M범주)' = manifest 실측 (F-555)
보고 규칙 (warn — 기본 실행의 exit 에는 미반영. `--strict` 면 다른 경고처럼 exit 1 이고, health-check `--strict-freshness` 도 이 건수를 세어 실패로 본다):
  pointer-drift        `--pointer-base <ref>` — 문서의 `파일:N` 포인터가 <ref> 때와 같은 글자인데 대상 N번째 줄 내용이 바뀌었다
                       (F-305 — 줄 삽입이 포인터를 조용히 밀었다. #N3 는 빈 줄만 본다)
  cc-version-ahead     설치된 `claude --version` 이 guides/llm-references.md 의 `대조 기준 Claude Code: X.Y.Z` 보다 높다 —
                       기준 뒤 changelog 를 대조하라는 안내(`--online`). 기본 실행이 낸다 · 네트워크 없음 · 기본 exit 에 미반영(`--strict` 면 1)
  cc-version-unjudged  기준 줄을 읽지 못했거나 CLI 가 없다 · 실패했다 — 미판정(⛔ 통과 아님 · 기본 exit 에 미반영 · `--strict` 면 1)
대조 모드 (`--online` · `--changelog-file` — 위 규칙은 돌리지 않고 이것만 본다. health-check 는 부르지 않는다):
  cc-new-default-model 기준 버전보다 새 changelog 항목에 'Added Claude … now the default …' 줄이 있다 (severity error → exit 1)
  조회 실패(받기 실패 · 사본 없음 · 못 읽음 · 버전 머리 0개 · 기준 줄 없음)는 통과가 아니라 판정 불가 — exit 2
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
    r"platform\.claude\.com|code\.claude\.com|anthropic\.com|arxiv|developers\.openai\.com|learn\.chatgpt\.com"
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
# 모델명 규칙만 보는 문서 — 스캔 루트 밖(루트 README · `docs/` 는 `EXCLUDE_PARTS`)이지만 현행 모델을 적는 살아 있는 문서다.
#   두 모델명 규칙(`stale-model-ref` · `stale-model-heading`)만 돌고, 감사일 규칙과 요약 줄의 대상 수에는 들지 않는다.
MODEL_ONLY_FILES = ["README.md", "docs/architecture.md"]

# 모델 언급 — 계열 · 주 버전 · 부 버전을 읽는다. 표시명 `Fable 5.1` · `Opus 5`(맨 주 버전 = N.0)와
#   ID 조각 `claude-fable-5-1` · `fable-5-1` · `opus-5` · `claude-fable-5-2[1m]` 두 꼴이다.
#   ID 끝 8자리 날짜(`claude-opus-4-8-20260101`)는 부 버전이 아니다 — 부 버전은 1~2자리이고 뒤에 숫자가 이어지지 않을 때만 읽는다.
#   한 언급을 통째로 읽으므로 `Opus 5.5` 는 (5, 5) 이지 `Opus 5` 가 아니다.
MODEL_MENTION = re.compile(
    r"(?<![A-Za-z])(?:(?P<fam>Fable|Opus|Sonnet|Haiku) (?P<maj>\d+)(?:\.(?P<min>\d+))?"
    r"|(?P<fid>fable|opus|sonnet|haiku)-(?P<imaj>\d+)(?:[-.](?P<imin>\d{1,2})(?!\d))?)"
)

# 구세대 모델명 손 목록 (현행이 없을 때만 신고)
# ⛔ 정책 줄이 적은 계열(지금 Fable · Opus)의 판은 여기 적지 않는다 — 그 계열은 정책 줄 판보다 낮은 판을 `legacy_hits()` 가
#    도출한다(여기 적힌 계열이 정책 줄에 오르면 그 항목은 건너뛴다). 이 목록은 정책 줄에 없는 계열(지금 Sonnet)과 `Claude N.N`
#    표기에 예전처럼 쓰이고, 거기서는 적은 판만 잡는다 — 정책 줄에서 빠진 계열은 여기 판을 적기 전까지 잡히지 않는다.
LEGACY_MODELS = [
    "Sonnet 4.6", "sonnet-4-6", "Sonnet 4.5", "sonnet-4-5",
    # ⛔ `Claude N` 표기 (2026-08-20 신설): 어휘가 `Opus`/`Sonnet` 접두만 담고 있어
    #    `Claude 4.8` 형태가 통째로 빠져 있었다 — 실측 7곳(guides/ 3파일).
    "Claude 4.8", "Claude 4.7", "Claude 4.6",
]

# heading 판별 — `stale-model-heading` 전용 (아래 lint() 참조)
HEADING = re.compile(r"^#{1,6}\s")
# 이력 표지 — 구세대 모델명만 적힌 heading 이라도 **그 제목 줄에** 이 낱말이 있으면 일부러 남긴 이력 절로 보고 면제한다.
#   트리가 제목에 이력을 적는 두 꼴만 둔다: `이전`(`### Fable 5.1 — 이전 Lead 모델 (…)`) · `이력`(`근거 · 이력`).
#   앞에 한글이 붙은 것은 낱말이 아니다 — `에이전트` 안의 `이전` 은 표지가 아니다. 본문의 표지는 제목을 면제하지 않는다.
HISTORY_MARK = re.compile(r"(?<![가-힣])(?:이전|이력)")
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


def model_version(m: re.Match) -> tuple[str, tuple[int, int]]:
    """`MODEL_MENTION` 매치 → (소문자 계열, (주, 부)). 부 버전이 없으면 0 — 비교는 수치다(5.10 > 5.9)."""
    fam = (m.group("fam") or m.group("fid")).lower()
    return fam, (int(m.group("maj") or m.group("imaj")), int(m.group("min") or m.group("imin") or 0))


def policy_floors(cur_toks: list[str]) -> dict[str, tuple[int, int]]:
    """현행 토큰에서 계열별 가장 낮은 현행 판 — 이보다 낮은 같은 계열 언급이 구세대다. 정책 줄에 없는 계열은 키가 없다."""
    floors: dict[str, tuple[int, int]] = {}
    for t in cur_toks:
        for m in MODEL_MENTION.finditer(t):
            fam, ver = model_version(m)
            floors[fam] = min(floors.get(fam, ver), ver)
    return floors


def legacy_hits(text: str, cur_toks: list[str]) -> list[str]:
    """`text` 에 나오는 구세대 모델 표기.

    - 정책 줄이 적은 계열: 언급을 통째로 읽어 그 계열의 현행 판보다 **낮으면** 구세대다(목록 없이 도출 · 높은 판은 구세대 아님).
      `Opus 5.5` · `claude-opus-5-5` 는 (5, 5) 로 읽혀 `Opus 5` 로 잘못 읽히지 않는다.
    - 그 밖(정책 줄에 없는 계열 · `Claude N.N`): 손 목록 `LEGACY_MODELS` — 같은 위치에서 현행 토큰이 시작하는 매치는 버린다.
    """
    floors = policy_floors(cur_toks)
    hits = set()
    for m in MODEL_MENTION.finditer(text):
        fam, ver = model_version(m)
        if fam in floors and ver < floors[fam]:
            hits.add(m.group(0))
    for t in LEGACY_MODELS:
        named = MODEL_MENTION.match(t)
        if named and model_version(named)[0] in floors:
            continue   # 정책 줄이 적은 계열 — 위에서 도출했다
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


# Claude Code 버전 대조 — 기준은 guides/llm-references.md 머리의 기계 판독 줄 하나다(산문 속 버전은 기준이 아니다)
CC_BASELINE = re.compile(r"대조 기준 Claude Code:\s*(\d+\.\d+\.\d+)")
SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")
CHANGELOG_VERSION = re.compile(r"^#{1,3}\s*\[?v?(\d+\.\d+\.\d+)", re.M)
NEW_DEFAULT = re.compile(r"\bAdded Claude\b[^\n]*\bnow the default\b")
CHANGELOG_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"


class LookupFail(Exception):
    """대조 조회 실패 — 통과(0)가 아니라 판정 불가(exit 2)다."""


def _semver(text: str):
    m = SEMVER.search(text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def cc_baseline(root: Path) -> tuple[str | None, str]:
    """(기준 버전 | None, 못 읽은 사유). 기준 줄이 정확히 하나일 때만 읽는다 — 없거나 둘 이상이면 None(⛔ '기준 없음 = 통과' 아님)."""
    canon = root / "guides" / "llm-references.md"
    try:
        hits = CC_BASELINE.findall(canon.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        return None, f"guides/llm-references.md 를 읽지 못했다 — {type(e).__name__}"
    if len(hits) != 1:
        return None, f"guides/llm-references.md 의 `대조 기준 Claude Code: X.Y.Z` 줄이 {len(hits)}개다(기대 1)"
    return hits[0], ""


def cc_version_findings(root: Path, cmd=("claude", "--version")) -> list[dict]:
    """기본 실행의 버전 확인 — 설치 버전이 기준보다 높으면 changelog 대조를 안내한다. 네트워크를 쓰지 않고 경고만 낸다(기본 exit 에 미반영 · `--strict` 면 exit 1)."""
    def unjudged(why):
        return [{"file": "guides/llm-references.md", "rule": "cc-version-unjudged", "severity": "warn",
                 "detail": f"Claude Code 버전 대조 미판정 — {why} (⛔ 통과 아님)"}]

    base, why = cc_baseline(root)
    if base is None:
        return unjudged(why)
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return unjudged(f"`{' '.join(cmd)}` 를 실행하지 못했다 — {type(e).__name__}")
    got = _semver(r.stdout) if r.returncode == 0 else None
    if got is None:
        return unjudged(f"`{' '.join(cmd)}` exit {r.returncode} — 버전을 읽지 못했다")
    if got > _semver(base):
        inst = ".".join(map(str, got))
        return [{"file": "guides/llm-references.md", "rule": "cc-version-ahead", "severity": "warn",
                 "detail": f"설치 Claude Code {inst} 가 대조 기준 {base} 보다 높다 — {base} 뒤 changelog 를 대조한다(`--online`). 대조했으면 기준 줄을 대조한 마지막 changelog 버전으로 고친다"}]
    return []


def changelog_findings(base: str, text: str):
    """기준보다 새 changelog 항목의 새 기본 모델 공지 → (findings, 기준 뒤 버전 목록). 버전 머리가 하나도 없으면 None(판정 불가)."""
    heads = list(CHANGELOG_VERSION.finditer(text))
    if not heads:
        return None
    b = _semver(base)
    out, newer = [], []
    for i, m in enumerate(heads):
        if _semver(m.group(1)) <= b:
            continue
        newer.append(m.group(1))
        body = text[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        for ln in body.split("\n"):
            if NEW_DEFAULT.search(ln):
                out.append({"file": f"changelog {m.group(1)}", "rule": "cc-new-default-model", "severity": "error",
                            "detail": f"기준 {base} 뒤 새 기본 모델 공지 — {ln.strip()[:160]} · 모델 정책 줄과 모델 사실을 대조한 뒤 기준 줄을 고친다"})
    return out, newer


def load_changelog(path, url: str = CHANGELOG_URL) -> tuple[str, str]:
    """(본문, 출처). path 가 있으면 사본을 읽고(네트워크 없음), 없으면 url 을 받는다(`--online` 일 때만). 실패는 LookupFail."""
    if path is not None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace"), path
        except OSError as e:
            raise LookupFail(f"changelog 사본을 읽지 못했다 — {path}: {type(e).__name__}")
    import http.client
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.read().decode("utf-8", "replace"), url
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise LookupFail(f"changelog 를 받지 못했다 — {url}: {type(e).__name__}: {e}")


def contrast(root: Path, path=None, url: str = CHANGELOG_URL) -> int:
    """대조 모드 — exit 0 기준 뒤 새 기본 모델 공지 없음 · 1 있음(error) · 2 판정 불가(조회 실패 · ⛔ 통과 아님)."""
    try:
        base, why = cc_baseline(root)
        if base is None:
            raise LookupFail(why)
        text, src = load_changelog(path, url)
        res = changelog_findings(base, text)
        if res is None:
            raise LookupFail(f"{src} 에서 버전 머리(`## X.Y.Z`)를 하나도 찾지 못했다")
    except LookupFail as e:
        print(f"⛔ 판정 불가 — {e} (통과 아님 · exit 2)", file=sys.stderr)
        return 2
    findings, newer = res
    print(f"Claude Code changelog 대조 — 기준 {base} [SSOT: guides/llm-references.md] · 출처 {src}")
    print(f"기준 뒤 항목 {len(newer)}개" + (f" ({' · '.join(newer)})" if newer else ""))
    for f in findings:
        print(f"■ {f['rule']} — {f['file']}")
        print(f"     └ {f['detail']}")
    print(f"총 {len(findings)}건")
    if findings:
        print(f"⛔ 계약 오류 {len(findings)}건 — 기준 뒤 새 기본 모델 공지 (exit 1)")
    return 1 if findings else 0


def lint(root: Path, max_days: int) -> tuple[list[dict], dict]:
    today = date.today()
    cur, cur_src = current_model(root)
    cur_label = " · ".join(cur)
    cur_toks = model_tokens(cur)

    findings: list[dict] = []
    scanned = audited = 0

    model_only = [root / f for f in MODEL_ONLY_FILES if (root / f).is_file()]
    for path in find_docs(root) + model_only:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(root))

        # 감사일 규칙은 외부 **사실** 인용 문서만 본다 (문자열 존재만으로는 대상이 아니다).
        # 아래 두 모델명 규칙은 이 거르기 밖이다 — 모델명 자체가 외부 사실이라 모든 스캔 문서를 본다.
        # `MODEL_ONLY_FILES` 는 감사일 규칙에 들지 않는다 — 아래 두 모델명 규칙만 본다.
        if path not in model_only and cites_external_fact(text):
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

        # 구세대 모델명만 있고 현행이 없는 파일 (외부 인용 여부와 무관)
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
        # ⚠️ 제목 줄에 이력 표지(`HISTORY_MARK`)가 있어도 면제 — `### Fable 5.1 — 이전 Lead 모델 (2026-09-06 대조)`
        #    같은 이력 절은 현행 모델명을 덧붙여 침묵시키면 안 되므로(이력 줄에 현행 사실을 주장하게 된다) 표지로 가른다.
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
                if hits and not any(t in line for t in cur_toks) and not HISTORY_MARK.search(line):
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
    check("learn-chatgpt-url", "[verified: https://learn.chatgpt.com/docs/changelog]", True)

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

    # ── 구세대는 정책 줄에서 **도출**한다 — 정책 줄이 적은 계열은 그 판보다 낮은 판이 구세대다(직전 판을 목록에 적지 않는다).
    #    정책 줄만 바꾼 트리에서 결과가 바뀌는지 본다 — 목록에 판을 적어야 따라오는 구현이면 아래 셀이 실패한다.
    def model_rule_files(d: Path, policy: str, body: str, rule: str) -> list:
        for sub_ in ("guides", "modules"):
            (d / sub_).mkdir(exist_ok=True)
        (d / "guides" / "llm-references.md").write_text(f"> **모델 정책: {policy} only**\n", encoding="utf-8")
        (d / "modules" / "a.md").write_text("> 근거 (arxiv 2503.13657) 실증\n\n" + body, encoding="utf-8")
        return [f["file"] for f in lint(d, 90)[0] if f["rule"] == rule]

    p52 = "Fable 5.2 (Lead) · Opus 5.5 (worker)"
    for name, policy, body, want in (
        ("derive-fable51-under-52-fires", p52, "Fable 5.1 운용\n", True),
        ("derive-fable51-id-fires", p52, "모델 ID `claude-fable-5-1`\n", True),
        ("derive-fable5-bare-fires", p52, "Fable 5 운용\n", True),
        ("derive-fable51-with-current-quiet", p52, "Fable 5.2 운용 · 이전은 Fable 5.1\n", False),
        ("derive-opus55-quiet", p52, "Opus 5.5 · `claude-opus-5-5` 운용\n", False),
        ("derive-opus5-bare-fires", p52, "Opus 5 운용\n", True),
        ("derive-opus48-dated-id-fires", p52, "`claude-opus-4-8-20260101`\n", True),
        ("derive-policy59-fable52-fires", "Fable 5.9 (Lead) · Opus 5.5 (worker)", "Fable 5.2 운용\n", True),
        ("derive-policy6-fable59-fires", "Fable 6 (Lead) · Opus 5.5 (worker)", "Fable 5.9 운용\n", True),
        ("derive-numeric-510-over-59-fires", "Fable 5.10 (Lead) · Opus 5.5 (worker)", "Fable 5.9 운용\n", True),
        ("derive-higher-than-policy-quiet", "Fable 5.9 (Lead) · Opus 5.5 (worker)", "Fable 5.10 운용\n", False),
        # 정책 줄이 적은 계열은 손 목록을 보지 않는다 — 목록의 `Sonnet 4.6` 도 정책 줄의 Sonnet 4.5 보다 높으면 구세대가 아니다
        ("derive-list-skipped-for-named-family", "Fable 5.2 (Lead) · Sonnet 4.5 (worker)", "Sonnet 4.6 운용\n", False),
    ):
        cases += 1
        with _tf.TemporaryDirectory() as _d:
            fired = model_rule_files(Path(_d), policy, body, "stale-model-ref") == ["modules/a.md"]
        (passed.append(name) if fired == want else failed.append(f"{name}: 발화 {fired} (기대 {want})"))
    # 같은 트리에서 정책 줄 한 줄만 바꾼다 — 5.2 일 때 조용하던 `Fable 5.2` 파일이 5.9 로 바꾸면 신고된다
    cases += 1
    with _tf.TemporaryDirectory() as _d:
        before = model_rule_files(Path(_d), p52, "Fable 5.2 운용\n", "stale-model-ref")
        (Path(_d) / "guides" / "llm-references.md").write_text(
            "> **모델 정책: Fable 5.9 (Lead) · Opus 5.5 (worker) only**\n", encoding="utf-8")
        after = [f["file"] for f in lint(Path(_d), 90)[0] if f["rule"] == "stale-model-ref"]
        ok = (before, after) == ([], ["modules/a.md"])
        (passed.append("derive-policy-line-only-change") if ok else
         failed.append(f"derive-policy-line-only-change: 5.2 때 {before} · 5.9 때 {after} (기대 [] · ['modules/a.md'])"))
    # 헬퍼 — ID 끝 8자리 날짜는 부 버전이 아니다 · `[1m]` 접미는 현행 ID 그대로다 · 정책 줄에 없는 계열과 `Claude N.N` 은 손 목록 그대로다
    toks52 = model_tokens(["Fable 5.2", "Opus 5.5"])
    for name, text, want in (
        ("derive-opus5-dated-id", "`claude-opus-5-20260101`", ["opus-5"]),
        ("derive-fable52-1m-current", "`claude-fable-5-2[1m]`", []),
        ("list-unnamed-family-kept", "Sonnet 4.6 · Claude 4.8 · Sonnet 5.5", ["Claude 4.8", "Sonnet 4.6"]),
    ):
        cases += 1
        got = legacy_hits(text, toks52)
        (passed.append(name) if got == want else failed.append(f"{name}: {got} (기대 {want})"))
    # ── heading 규칙도 도출한 구세대로 본다 + 이력 표지 면제(제목 줄에 있을 때만 · `에이전트` 안의 `이전` 은 표지가 아니다)
    for name, body, want in (
        ("heading-derived-fable51-fires", "### Fable 5.1 운용\n", True),
        ("heading-history-ijeon-exempt", "### Fable 5.1 — 이전 Lead 모델 (2026-09-06 대조)\n", False),
        ("heading-history-iryeok-exempt", "### 스니펫 채택 현황 (실측 이력 — Fable 5.1 2026-09-06)\n", False),
        ("heading-agent-word-not-history", "### Fable 5.1 에이전트 배선\n", True),
        ("heading-history-word-in-body-not-exempt", "### Fable 5.1 운용\n\n이전 Lead 모델의 기록이다\n", True),
    ):
        cases += 1
        with _tf.TemporaryDirectory() as _d:
            fired = model_rule_files(Path(_d), p52, "현행 Fable 5.2\n\n" + body, "stale-model-heading") == ["modules/a.md:5"]
        (passed.append(name) if fired == want else failed.append(f"{name}: 발화 {fired} (기대 {want})"))
    # ── 두 모델명 규칙은 외부 인용이 **없는** 문서에도 돈다(모델명 자체가 외부 사실이다) · 감사일 규칙과 대상 수는 외부 인용 문서만 본다(대조 셀)
    for name, body, rule, at, want in (
        ("uncited-file-rule-fires", "Fable 5.1 운용\n", "stale-model-ref", "modules/a.md", True),
        ("uncited-heading-rule-fires", "### Fable 5.1 운용\n", "stale-model-heading", "modules/a.md:1", True),
        ("uncited-not-audit-target", "Fable 5.1 운용\n", "missing-audit-date", "modules/a.md", False),
    ):
        cases += 1
        with _tf.TemporaryDirectory() as _d:
            d = Path(_d)
            for sub_ in ("guides", "modules"):
                (d / sub_).mkdir()
            (d / "guides" / "llm-references.md").write_text(f"> **모델 정책: {p52} only**\n", encoding="utf-8")
            (d / "modules" / "a.md").write_text(body, encoding="utf-8")
            got, summ = lint(d, 90)
            fired = any(f["rule"] == rule and f["file"] == at for f in got)
        ok = fired == want and summ["target_files"] == 0 and not cites_external_fact(body)
        (passed.append(name) if ok else failed.append(f"{name}: 발화 {fired} · 대상 {summ['target_files']}개 (기대 {want} · 대상 0개)"))

    # ── 스캔 루트 밖의 살아 있는 문서(`MODEL_ONLY_FILES` — 루트 README · `docs/architecture.md`)는 두 모델명 규칙만 본다.
    #    감사일 규칙과 대상 수에는 들지 않고(대조 셀), `docs/` 의 다른 문서는 여전히 스캔 밖이다(대조 셀)
    for name, relpath, body, rule, want in (
        ("model-only-readme-fires", "README.md", "Fable 5.1 운용\n", "stale-model-ref", True),
        ("model-only-architecture-fires", "docs/architecture.md", "Lead (Fable 5.1)\n", "stale-model-ref", True),
        ("model-only-not-audit-target", "README.md",
         "Fable 5.1 운용 [verified: platform.claude.com/docs/en/models/overview]\n", "missing-audit-date", False),
        ("docs-other-still-excluded", "docs/other.md", "Fable 5.1 운용\n", "stale-model-ref", False),
    ):
        cases += 1
        with _tf.TemporaryDirectory() as _d:
            d = Path(_d)
            for sub_ in ("guides", "docs"):
                (d / sub_).mkdir()
            (d / "guides" / "llm-references.md").write_text(f"> **모델 정책: {p52} only**\n", encoding="utf-8")
            (d / relpath).write_text(body, encoding="utf-8")
            got, summ = lint(d, 90)
            fired = any(f["rule"] == rule and f["file"] == relpath for f in got)
        cited_ok = cites_external_fact(body) if rule == "missing-audit-date" else True   # 감사일 대조 셀은 외부 사실을 인용해야 뜻이 있다
        ok = fired == want and summ["target_files"] == 0 and cited_ok
        (passed.append(name) if ok else failed.append(
            f"{name}: 발화 {fired} · 대상 {summ['target_files']}개 · 인용 {cited_ok} (기대 {want} · 대상 0개)"))

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

    # ── Claude Code 버전 대조 — changelog 대조 쌍(기준 뒤 공지 줄이 있으면 error · 그 줄을 지우면 0 · 버전 머리 없음 = 판정 불가)
    old_entry = "## 2.1.312\n\n- Added Claude Example 7 (`claude-example-7`), now the default Example model\n"
    for name, text, want in (
        ("cc-changelog-new-default-error",
         "## 2.1.321\n\n- Added Claude Example 9 (`claude-example-9`), now the default Example model\n\n" + old_entry, ["error"]),
        ("cc-changelog-line-removed-ok", "## 2.1.321\n\n- Fixed a crash\n\n" + old_entry, []),
        ("cc-changelog-no-version-unjudged", "<html><body>changelog</body></html>\n", None),
    ):
        cases += 1
        res = changelog_findings("2.1.312", text)
        got = None if res is None else [f["severity"] for f in res[0]]
        (passed.append(name) if got == want else failed.append(f"{name}: {got} (기대 {want})"))
    # ── 기본 실행의 버전 확인 — 경고만(기본 exit 에 미반영 · `--strict` 면 1). 표지가 산문에만 있거나 CLI 가 없으면 미판정, 높으면 대조 안내, 같으면 조용
    mark = "> ⚙️ **대조 기준 Claude Code: 2.1.312** — 합성 기준\n"
    with _tf.TemporaryDirectory() as _d:
        d = Path(_d)
        (d / "guides").mkdir()
        say = lambda v: (sys.executable, "-c", f"print('{v} (Claude Code)')")
        for name, body, cmd, want in (
            ("cc-baseline-prose-only-unjudged", "| /changelog (대조 · 설치 2.1.312) |\n", say("9.0.0"), [("cc-version-unjudged", "warn")]),
            ("cc-cli-absent-unjudged", mark, (str(d / "no-such-claude"), "--version"), [("cc-version-unjudged", "warn")]),
            ("cc-cli-ahead-warns", mark, say("2.1.400"), [("cc-version-ahead", "warn")]),
            ("cc-cli-same-quiet", mark, say("2.1.312"), []),
        ):
            cases += 1
            (d / "guides" / "llm-references.md").write_text(body, encoding="utf-8")
            got = [(f["rule"], f["severity"]) for f in cc_version_findings(d, cmd)]
            (passed.append(name) if got == want else failed.append(f"{name}: {got} (기대 {want})"))

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
    ap.add_argument("--strict", action="store_true",
                    help="경고가 하나라도 있으면 exit 1 — Claude Code 버전 경고(cc-version-ahead · cc-version-unjudged)도 센다")
    ap.add_argument("--self-test", action="store_true", help="술어 fixture 실행")
    ap.add_argument("--pointer-base", metavar="REF", help="`파일:N` 포인터 대상 줄 내용을 REF 와 대조(보고)")
    cl = ap.add_mutually_exclusive_group()
    cl.add_argument("--online", action="store_true",
                    help="Claude Code changelog 를 받아 대조 기준 뒤 새 기본 모델 공지를 본다(opt-in · 네트워크 · 다른 규칙은 돌리지 않는다)"
                         " — exit 0 없음 · 1 있음 · 2 판정 불가")
    cl.add_argument("--changelog-file", metavar="PATH", help="--online 과 같은 대조를 changelog 사본으로 한다(네트워크 없음 · fixture 주입)")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    root = Path(args.root).resolve()
    if not (root / "guides").is_dir():
        print(f"⛔ 플러그인 루트가 아님: {root}", file=sys.stderr)
        return 2
    if args.online or args.changelog_file is not None:
        return contrast(root, args.changelog_file)

    findings, summary = lint(root, args.days)
    findings += cc_version_findings(root)   # 기본 실행 — 네트워크 없음 · 경고만
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
