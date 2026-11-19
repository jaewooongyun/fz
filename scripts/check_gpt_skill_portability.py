#!/usr/bin/env python3
# lint:no-root-anchor — 검사 대상 루트를 `--root` 로 받는다(기본값은 이 파일 기준 부모). 기준값(지침 파일 집합 · 6축)은 이 파일이 속한 트리에서 읽는다.
"""GPT 역할 스킬(gpt-skills/)이 특정 프로젝트·프레임워크를 전제하지 않는지 검사한다 (S12 · AC-3).

⛔ 왜 필요한가: 번들 스킬 8개가 작성자 프로젝트의 스택(RIBs · SwiftUI · 고정 레이어 순서 · `AI/*-guidelines.md` 경로)을
   **보편 규칙**처럼 본문에 박고 있었다. 비-iOS 저장소나 지침이 없는 저장소에서 GPT 가 근거 없이 그 규칙을 적용한다(AC-3).
   규칙은 대상 저장소 지침에서 런타임에 뽑고(modules/project-rules.md), 프레임워크 지식은 조건부 도메인 팩
   (`references/domain-*.md`)으로만 싣는다.

검사 항목 (위반마다 `VIOLATION <파일>:<줄>: <규칙> — <내용>`)
  framework        SKILL.md 본문(펜스 안 포함)의 프레임워크 토큰 — `references/domain-` 을 가리키는 로더 줄만 예외
  author           작성자 프로젝트 전용 관례 표지 — SKILL.md 와 도메인 팩 모두
  ai-path          `AI/*guidelines*` 경로 — 모든 파일
  layer-chain      고정 레이어 순서 문자열(`A → B` 사슬) — 모든 파일
  loader           로더 줄이 가리키는 팩 파일이 없다 · 팩이 있는데 로더 줄이 없다
  pack-policy      도메인 팩이 `plugin-default`(ruleSource) · `suggestion`(상한)을 밝히지 않는다
  section          `## Project Rules (runtime)` · `## When Project Guidelines Are Absent` 절이 없다
  guide-set        Project Rules 절이 지침 파일 집합(extract_project_rules.py 와 같은 이름)을 다 대지 않는다
  reviewer-axes    fz-reviewer 에 6축(CRAFT_AXES 와 같은 이름) · over-engineering 이 없다
  architect-q      fz-architect 에 Q1~Q8 이 다 있지 않다
  planner-json     fz-planner 출력이 status(ok|rejected) · steps · riskMatrix 를 가진 JSON 이 아니다 · 옛 평문 거부 문장
  openai-yaml      agents/openai.yaml 이 없다 · 암묵 호출 정책이 fz-reviewer=허용 · 나머지=금지가 아니다

Claude 문서 모드(`--claude-docs`) — Swift 기준 줄에 프로젝트 조건을 단 Claude 문서(계약 CLAUDE_DOCS — 조건 문구를 실은
8개 · 전수 아님)가 조건 없는 스택 규칙을 다시 싣지 않는지 본다. 위 목록의 loader 부터 openai-yaml 까지(GPT 스킬 구조
규칙)는 돌리지 않는다. 계약이 읽지 않는다고 적은 절(제목 그대로 · 사유와 함께) 밖의 줄을 모두 읽는다 — 새 절도 읽는다.
  framework · author     프레임워크 토큰(+ CLAUDE_EXTRA_RE) · 작성자 관례 표지 — 조건 문구(CLAUDE_COND)가 덮지 않으면 위반.
                         덮는 범위: 문구를 실은 줄 · 문구를 실은 제목 줄이나 제목 바로 아래 첫 줄(목록 항목 · 표 행 아님)의 절 전체
                         제목 = 줄 머리 `#` 1~6개 + ASCII 공백 · 탭(유니코드 공백 뒤 표지는 제목이 아니다)
  ai-path · layer-chain  조건과 무관하게 위반
  contract               계약이 읽지 않는다고 적은 절 제목이 파일에 없다
  대상 파일이 없으면 측정 실패(2)

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님 — 스킬 0개 · 기준값을 읽지 못함)
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent

# 프레임워크 토큰 — 번들 스킬이 실제로 박고 있던 스택 어휘다(기준 트리 실측). 단어 경계로 본다.
# ⛔ 경계(`\w` 둘레 · `\b`)는 ASCII 로 본다(re.ASCII) — 유니코드 `\w` 는 한글을 포함해 `RIBs의` · `weak var를` 처럼 조사가 붙은
#    토큰을 놓친다. 뒤에 붙은 ASCII 영숫자 · `_` 는 여전히 낱말을 잇고(`RIBsX` 는 토큰이 아니다) 앞의 `@ # .` 는 그대로 뺀다
FRAMEWORK_WORDS = ("RIBs", "SwiftUI", "UIKit", "Swift", "iOS", "Xcode", "PromiseKit", "RxSwift", "Interactor",
                   "ViewController", "ObservableObject", "Clean Architecture", "disposeBag", "didBecomeActive",
                   "willResignActive", "deinit", "nonisolated", "withCheckedContinuation", "AsyncStream", "TaskGroup",
                   "Sendable", "xcconfig", "swiftlint")
FRAMEWORK_SYMBOLS = (r"@MainActor", r"@StateObject", r"@ObservedObject", r"@Observable\b", r"@State\b", r"@Published",
                     r"@Binding", r"@Bindable", r"#available", r"\[weak self\]", r"\bweak var\b", r"\.swift\b",
                     r"\bactor-isolated\b", r"\basync let\b")
FRAMEWORK_RE = re.compile("|".join([rf"(?<![\w@#.]){re.escape(w)}(?![\w])" for w in FRAMEWORK_WORDS] + list(FRAMEWORK_SYMBOLS)), re.ASCII)
# 작성자 프로젝트 전용 관례 — 규칙으로 싣지 않는다(팩에도). 인용 형식 예시는 플레이스홀더로만 쓴다.
AUTHOR_RE = re.compile(r"\{Feature\}|optional chaining|옵셔널 체이닝", re.I)
# 경로 · 레이어 사슬의 낱말 경계도 ASCII 다 — `(?a:\b)` 는 그 경계 자리만 ASCII 로 본다(`지침은AI/…` · `Repository를` 을 잡는다).
#   패턴 전체에 re.ASCII 를 걸지 않는다 — 사이의 `\s`(NBSP · 전각 공백)와 경로 이름의 `\w`(한글 파일 이름)까지 좁혀 놓친다
AI_PATH_RE = re.compile(r"(?a:\b)AI/[\w.-]*guidelines", re.I)
LAYERS = r"(?a:\b)(?:Network|Repository|UseCase|Workflow)(?a:\b)"   # 단어 경계 — `OrderRepository → NetworkClient` 는 사슬이 아니다
LAYER_RE = re.compile(rf"{LAYERS}\s*(?:→|←|->|<-|>|<)\s*{LAYERS}")
LOADER_RE = re.compile(r"references/(domain-[\w-]+\.md)")
PROJECT_RULES = "## Project Rules (runtime)"
ABSENT = "## When Project Guidelines Are Absent"
OLD_REJECT = "Claude plan detected. Provide requirements only"
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")

# ── Claude 문서 모드(--claude-docs) ──────────────────────────────────────────────
# 제목 표지 뒤는 ASCII 공백 · 탭만 받는다(CommonMark ATX 제목) — `\s` 는 유니코드 공백(전각 공백 · NBSP 등)도 받아,
#   `##` 뒤에 전각 공백을 둔 줄처럼 제목이 아닌 줄의 조건 문구가 절 전체를 덮고 그 아래 조건 없는 스택 규칙이 위반에서 빠진다
HEADING_RE = re.compile(r"^(#{1,6})[ \t]")
LIST_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|\|)")   # 목록 항목 · 표 행 — 절 머리 조건이 될 수 없다(그 줄만 덮는다)
# 조건 문구는 하나다. 줄 안에 두면 그 줄을, 절 제목 줄 또는 제목 바로 아래 첫 줄(`>` 줄 · 문단 — 목록 항목 · 표 행 아님)에
# 두면 그 절 전체(같거나 높은 수준의 다음 제목 전까지)를 덮는다.
CLAUDE_COND = "CLAUDE.md 아키텍처 절이 Swift/iOS 프로젝트를 지정하는 경우"
# FRAMEWORK_RE 밖 스택 어휘 — 조건을 단 줄 가운데 이 어휘만 싣는 줄이 있다(영속 저장소 · 앱 생명주기 진입점 · 격리 경계).
# 이 어휘를 보지 않으면 그 줄의 조건을 지워도 위반이 나지 않는다. GPT 모드는 쓰지 않는다. 경계는 FRAMEWORK_RE 와 같이 ASCII 다
CLAUDE_EXTRA_RE = re.compile(r"(?<![\w@#.])(?:UserDefaults|Keychain|CoreData|AppDelegate|SceneDelegate|UIWindow)(?![\w])|\bactor isolation\b",
                             re.ASCII)
# 대상 = 조건 문구를 실은 Claude 문서(전수 아님). 값 = 이 모드가 읽지 않는 절(제목 줄 그대로 → 사유).
#   건너뛰는 범위는 그 제목부터 다음 제목(수준 무관) 전까지다 — 그 안에 새 하위 절을 넣으면 읽는다.
#   목록에 없는 절(새 절 포함)은 모두 읽는다. 사유: 예시(코드 · 출력 · 괄호 예시) · 이름(원칙 · 문서 이름) ·
#   다른 조건(이 문구가 아닌 조건을 단 절) · 미조건(조건 없는 Swift 기준 — 조건을 달면 목록에서 뺀다)
# 심볼 도구 공통 블록 — 언어 낱말은 괄호 예시(`shell, Python, JavaScript, Swift and so on`)뿐이다. 그 도구를 가진 에이전트가 모두 싣는다
SYMBOL_TOOLS_HEAD = "## Symbol tools — use them whenever they are in your tool list"
_LENS_UNREAD = {
    SYMBOL_TOOLS_HEAD: "예시",
    "### 2. UI Framework Architecture (CLAUDE.md에 UI 프레임워크 명시 시)": "다른 조건",
    "## Library Semantics (이슈 판정 전 확인)": "다른 조건",
    "## Few-shot": "예시",
}
CLAUDE_DOCS = {
    "agents/arch-lens.md": {"### 1. Architecture Decision (Clean Architecture — Uncle Bob)": "이름", **_LENS_UNREAD},
    "agents/review-arch.md": {"### 1. Architecture Decision (Clean Architecture — Uncle Bob)": "이름", **_LENS_UNREAD},
    "agents/review-quality.md": {
        SYMBOL_TOOLS_HEAD: "예시",
        "### 2. Modern API + Dead Code (Layer 2 - CLAUDE.md references)": "예시",
        "### 4. UI Framework Quality (CLAUDE.md 플러그인·최소 타겟 정보에 UI 프레임워크 플러그인 명시 시)": "다른 조건",
        "## Library Semantics (이슈 판정 전 확인)": "다른 조건",
    },
    "agents/impl-correctness.md": {SYMBOL_TOOLS_HEAD: "예시"},
    "agents/plan-structure.md": {SYMBOL_TOOLS_HEAD: "예시"},
    "skills/fz-code/SKILL.md": {
        "## 모듈 참조": "이름",
        "## 스택 스킬 (있으면 쓴다 · 없어도 진행)": "다른 조건",
        "### 실행 절차 (Lead — Step 루프 소유)": "다른 조건",
        "## Phase 0.5: Swift Pattern Pre-detection (Swift/iOS 프로젝트 한정)": "다른 조건",
        "### Gate 0.5: Swift Pattern Pre-detection 통과": "다른 조건",
        "## 구현 절차": "미조건",
        "## Boundaries": "예시",
    },
    "skills/code-auditor/SKILL.md": {
        "### 컴포넌트 역할 경계 (CLAUDE.md `## Architecture` 참조)": "예시",
        "### SwiftUI Passive View 원칙": "미조건",
        "### SwiftUI weak var → strong reference 주의": "미조건",
        "### 리액티브 프레임워크 혼용 SRP 위반": "예시",
        "### Class Inheritance DI Pattern (PR 교훈)": "예시",
        "### 리액티브 프레임워크 생명주기 이슈": "예시",
        "### 삭제 vs 이동 판별 원칙": "예시",
        "### 예시: 리팩토링 불완전 추적": "예시",
        "### 예시: 의존성 역방향 참조 추적": "예시",
        "## 출력 형식 (JSON)": "예시",
        "### 예시 3 — 아키텍처 레이어 위반 (symbols.json.import_graph 활용)": "예시",
        "## 언어 정책": "예시",
    },
    "skills/arch-critic/SKILL.md": {
        "### 예시 시나리오": "예시",
        "### 예시 이슈 출력": "예시",
        "### 예시: 데이터 흐름 추적": "예시",
        "### ⛔ Guard Necessity Check (missing-guard 이슈 필수)": "예시",
        "### 예시: 상태 전환 누락 추적": "예시",
        "### 출력 예시 (JSON)": "예시",
        "### 예시": "예시",
        "## 이슈 분류 원칙 (Origin Classification)": "예시",
        "## 출력 형식 (JSON)": "예시",
    },
}


class AxesChanged(Exception):
    """CRAFT_AXES 선언은 찾았는데 6개가 아니다 — 내용 위반(1)이다. 선언을 못 찾은 측정 실패(2)와 다르다(F-396)."""


def baseline(wf: pathlib.Path | None = None):
    """지침 파일 집합(추출기)과 6축(워크플로) — 두 모델이 같은 정의를 쓰도록 이 트리의 정본에서 읽는다.

    - Parameters:
      - wf: 6축을 읽을 워크플로 파일. 기본값은 이 트리의 `workflows/peer-review.js` (self-test 가 사본을 넘긴다).
    - Throws: 선언을 못 찾거나 읽지 못하면 `RuntimeError`(측정 실패) · 찾았는데 6개가 아니면 `AxesChanged`(위반).
    """
    sys.path.insert(0, str(HERE))
    try:
        import extract_project_rules as epr
        guides = sorted(epr.GUIDE_NAMES) + sorted(epr.GUIDE_PATHS)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(f"지침 파일 집합을 읽지 못했다(scripts/extract_project_rules.py): {e}")
    wf = wf or HERE.parent / "workflows" / "peer-review.js"
    try:
        m = re.search(r"const CRAFT_AXES = \[([^\]]*)\]", wf.read_text(encoding="utf-8"))
    except OSError as e:
        raise RuntimeError(f"6축을 읽지 못했다({wf}): {e}")
    if not m:
        raise RuntimeError(f"CRAFT_AXES 선언을 찾지 못했다({wf})")
    axes = re.findall(r"'([a-z_]+)'", m.group(1))
    if len(axes) != 6:
        raise AxesChanged(f"CRAFT_AXES 가 6개가 아니다({wf}): {axes}")
    return guides, axes


def headings(lines):
    """펜스 밖 `## ` heading → 줄 번호(0-기반). 펜스는 여는 표지와 같은 문자 · 같거나 긴 길이로만 닫힌다."""
    out, fence = {}, None
    for i, l in enumerate(lines):
        m = FENCE_RE.match(l)
        if m:
            tok = m.group(1)
            if fence is None:
                fence = tok
            elif tok[0] == fence[0] and len(tok) >= len(fence) and l.strip() == tok:
                fence = None
            continue
        if fence is None and l.startswith("## "):
            out[l.rstrip()] = i
    return out


def section(lines, heads, name):
    if name not in heads:
        return None
    s = heads[name]
    nxt = [i for i in heads.values() if i > s]
    return "\n".join(lines[s + 1:min(nxt) if nxt else len(lines)])


def policy(text):
    """openai.yaml 의 policy.allow_implicit_invocation — 없으면 None(CLI 기본값 true)."""
    m = re.search(r"^policy:[ \t]*\n((?:[ \t]+.*\n?)*)", text, re.M)
    if not m:
        return None
    v = re.search(r"^[ \t]+allow_implicit_invocation:\s*(true|false)\s*$", m.group(1), re.M)
    return None if not v else v.group(1) == "true"


def scan(root: pathlib.Path, guides, axes):
    skills = sorted(p.parent for p in (root / "gpt-skills").glob("*/SKILL.md"))
    hits, nfiles = [], 0

    def hit(path, line, rule, text):
        hits.append((path.relative_to(root).as_posix(), line, rule, re.sub(r"\s+", " ", text).strip()[:140]))

    for d in skills:
        name, skill = d.name, d / "SKILL.md"
        lines = skill.read_text(encoding="utf-8").split("\n")
        packs = sorted((d / "references").glob("domain-*.md"))
        others = [p for p in sorted(d.rglob("*")) if p.is_file() and p != skill and p.suffix in (".md", ".yaml", ".yml")]
        nfiles += 1 + len(others)
        loaded = set()
        for i, l in enumerate(lines, 1):
            lm = LOADER_RE.search(l)
            if lm:
                loaded.add(lm.group(1))
                if not (d / "references" / lm.group(1)).is_file():
                    hit(skill, i, "loader", f"가리키는 팩이 없다: references/{lm.group(1)}")
            elif FRAMEWORK_RE.search(l):
                hit(skill, i, "framework", l)
            if AUTHOR_RE.search(l):
                hit(skill, i, "author", l)
        for p in packs:
            if p.name not in loaded:
                hit(p, 1, "loader", f"로더 줄이 없는 팩 — SKILL.md 가 references/{p.name} 을 가리키지 않는다")
            t = p.read_text(encoding="utf-8")
            if "plugin-default" not in t or "suggestion" not in t:
                hit(p, 1, "pack-policy", "ruleSource=plugin-default · 상한 suggestion 을 밝히지 않는다")
            for i, l in enumerate(t.split("\n"), 1):
                if AUTHOR_RE.search(l):
                    hit(p, i, "author", l)
        for p in [skill] + others:
            for i, l in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
                if AI_PATH_RE.search(l):
                    hit(p, i, "ai-path", l)
                if LAYER_RE.search(l):
                    hit(p, i, "layer-chain", l)
        heads = headings(lines)
        for h in (PROJECT_RULES, ABSENT):
            if h not in heads:
                hit(skill, 1, "section", f"절 없음: {h}")
        pr = section(lines, heads, PROJECT_RULES)
        if pr is not None:
            miss = [g for g in guides if g not in pr]
            if miss:
                hit(skill, heads[PROJECT_RULES] + 1, "guide-set", f"지침 파일 집합에 빠진 이름: {', '.join(miss)}")
        body = "\n".join(lines)
        if name == "fz-reviewer":
            miss = [a for a in axes if f"`{a}`" not in body]
            if miss:
                hit(skill, 1, "reviewer-axes", f"6축 결손: {', '.join(miss)}")
            if not re.search(r"over[-_ ]engineering", body, re.I):
                hit(skill, 1, "reviewer-axes", "over-engineering 항목 없음")
        if name == "fz-architect":
            miss = [f"Q{n}" for n in range(1, 9) if not re.search(rf"\bQ{n}\b", body, re.ASCII)]   # `Q1은` 도 Q1 이다 · `Q10` 은 아니다
            if miss:
                hit(skill, 1, "architect-q", f"결손: {', '.join(miss)}")
        if name == "fz-planner":
            need = ('"status"', '"rejected"', '"steps"', '"riskMatrix"')
            miss = [k for k in need if k not in body]
            if miss:
                hit(skill, 1, "planner-json", f"JSON 출력 키 결손: {', '.join(miss)}")
            for i, l in enumerate(lines, 1):
                if OLD_REJECT in l:
                    hit(skill, i, "planner-json", "옛 평문 거부 문장 — 거부는 JSON status 로 낸다")
        yml = d / "agents" / "openai.yaml"
        if not yml.is_file():
            hit(skill, 1, "openai-yaml", "agents/openai.yaml 없음")
        else:
            v = policy(yml.read_text(encoding="utf-8"))
            want = name == "fz-reviewer"
            if (v is not False) != want:
                hit(yml, 1, "openai-yaml", f"allow_implicit_invocation={'기본(true)' if v is None else v} — "
                    f"{'fz-reviewer 만 암묵 호출을 허용한다' if want else 'fz-reviewer 밖은 false 여야 한다'}")
    return skills, nfiles, hits


def run(root: pathlib.Path, wf: pathlib.Path | None = None) -> int:
    try:
        guides, axes = baseline(wf)
    except AxesChanged as e:
        print(f"VIOLATION {e}")
        return VIOLATION
    except RuntimeError as e:
        print(f"UNRUN: {e}")
        return UNRUN
    skills, nfiles, hits = scan(root, guides, axes)
    if not skills:
        print(f"UNRUN: gpt-skills/*/SKILL.md 0개 — {root} (경로 확인)")
        return UNRUN
    for f, i, rule, t in hits:
        print(f"VIOLATION {f}:{i}: {rule} — {t}")
    print(f"gpt-skill-portability: skills={len(skills)} files={nfiles} violations={len(hits)}")
    return VIOLATION if hits else OK


def outline(lines):
    """펜스 밖 제목 → [(줄 번호 0-기반, 수준, 제목 줄)] — 모든 수준. 펜스 규칙은 headings() 와 같다."""
    out, fence = [], None
    for i, l in enumerate(lines):
        m = FENCE_RE.match(l)
        if m:
            tok = m.group(1)
            if fence is None:
                fence = tok
            elif tok[0] == fence[0] and len(tok) >= len(fence) and l.strip() == tok:
                fence = None
            continue
        h = HEADING_RE.match(l)
        if fence is None and h:
            out.append((i, len(h.group(1)), l.rstrip()))
    return out


def scan_claude(root: pathlib.Path, docs=None):
    """Claude 문서 모드 — (읽은 파일 수, 위반, 없는 대상 파일).

    GPT 전용 규칙(loader · pack-policy · section 이하)은 돌리지 않는다. 읽는 줄(계약이 건너뛰는 절 밖)마다
    framework · author 는 CLAUDE_COND 로 덮이지 않았을 때만, ai-path · layer-chain 은 조건과 무관하게 위반이다.
    - Parameters:
      - docs: {파일: {읽지 않는 절 제목: 사유}}. 기본값은 CLAUDE_DOCS (self-test 가 합성 계약을 넘긴다).
    """
    docs = CLAUDE_DOCS if docs is None else docs
    hits, missing, nfiles = [], [], 0

    def hit(path, line, rule, text):
        hits.append((path.relative_to(root).as_posix(), line, rule, re.sub(r"\s+", " ", text).strip()[:140]))

    for rel, unread in docs.items():
        p = root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        nfiles += 1
        lines = p.read_text(encoding="utf-8").split("\n")
        heads = outline(lines)
        for h in sorted(set(unread) - {t for _, _, t in heads}):
            hit(p, 1, "contract", f"계약이 읽지 않는다고 적은 절이 없다: {h}")
        skip, cond = set(), set()
        for k, (i, lv, t) in enumerate(heads):
            nxt = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            end = next((j for j, lv2, _ in heads[k + 1:] if lv2 <= lv), len(lines))
            if t in unread:
                skip.update(range(i, nxt))
            first = next((j for j in range(i + 1, nxt) if lines[j].strip()), None)
            if CLAUDE_COND in t or (first is not None and CLAUDE_COND in lines[first] and not LIST_RE.match(lines[first])):
                cond.update(range(i, end))
        for i, l in enumerate(lines):
            if i in skip:
                continue
            if AI_PATH_RE.search(l):
                hit(p, i + 1, "ai-path", l)
            if LAYER_RE.search(l):
                hit(p, i + 1, "layer-chain", l)
            if i in cond or CLAUDE_COND in l:
                continue
            if FRAMEWORK_RE.search(l) or CLAUDE_EXTRA_RE.search(l):
                hit(p, i + 1, "framework", l)
            if AUTHOR_RE.search(l):
                hit(p, i + 1, "author", l)
    return nfiles, hits, missing


def run_claude(root: pathlib.Path, docs=None) -> int:
    nfiles, hits, missing = scan_claude(root, docs)
    if missing:
        print(f"UNRUN: Claude 문서 모드 대상 파일이 없다 — {', '.join(missing)} ({root} · 계약 CLAUDE_DOCS 확인)")
        return UNRUN
    for f, i, rule, t in hits:
        print(f"VIOLATION {f}:{i}: {rule} — {t}")
    print(f"claude-doc-portability: files={nfiles} violations={len(hits)}")
    return VIOLATION if hits else OK


def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []
    guides, axes = baseline()
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))

    def ok(name):
        nonlocal passed
        passed += 1
        if listing:
            print(f"  ok   {name}")

    def good(d: pathlib.Path):
        """위반 0 인 최소 트리 — 스킬 넷(reviewer · architect · planner · 팩을 쓰는 other)."""
        pr = f"{PROJECT_RULES}\n\n지침 파일: " + " · ".join(f"`{g}`" for g in guides) + "\n\n인용 형식: `{file}:{line} — \"<quote>\"`\n"
        ab = f"{ABSENT}\n\n일반 원칙만 적용한다.\n"
        bodies = {
            "fz-reviewer": "## Review Axes\n\n" + " · ".join(f"`{a}`" for a in axes) + "\n\nover-engineering 도 본다.\n",
            "fz-architect": "## Stress\n\n" + "\n".join(f"- Q{n} 질문" for n in range(1, 9)) + "\n",
            "fz-planner": '## Output\n\n```json\n{"status": "ok", "reason": null, "steps": [], "riskMatrix": []}\n```\n'
                          'status 는 "ok" 또는 "rejected".\n',
            "fz-other": "- 도메인 팩: 프로젝트가 Swift 를 쓰면 `references/domain-ios.md` 를 읽는다\n",
        }
        for n, b in bodies.items():
            (d / "gpt-skills" / n / "agents").mkdir(parents=True)
            (d / "gpt-skills" / n / "SKILL.md").write_text(f"---\nname: {n}\n---\n\n# {n}\n\n{pr}\n{b}\n{ab}", encoding="utf-8")
            v = "true" if n == "fz-reviewer" else "false"
            (d / "gpt-skills" / n / "agents" / "openai.yaml").write_text(f"policy:\n  allow_implicit_invocation: {v}\n", encoding="utf-8")
        (d / "gpt-skills" / "fz-other" / "references").mkdir()
        (d / "gpt-skills" / "fz-other" / "references" / "domain-ios.md").write_text(
            "# iOS 팩\n\n발견은 ruleSource=plugin-default · 상한 suggestion.\n\n- `@MainActor` 는 UI 경로에만\n", encoding="utf-8")

    def rules(d):
        return sorted({r for _, _, r, _ in scan(d, guides, axes)[2]})

    def edit(d, rel, old, new):
        p = d / rel
        t = p.read_text(encoding="utf-8")
        assert old in t, (rel, old)
        p.write_text(t.replace(old, new, 1), encoding="utf-8")

    # (이름, 트리 변형, 기대 규칙) — 각 변형은 새 트리에서. 옛 본문에서 실패하는 모양을 그대로 옮겼다
    SK = "gpt-skills/{}/SKILL.md"
    cases = [
        ("최소 트리 → 위반 0 (fz-other 로더 줄의 Swift 는 예외)", lambda d: None, []),
        ("본문 프레임워크 토큰 → framework", lambda d: edit(d, SK.format("fz-architect"), "- Q1 질문", "- Q1 질문 — RIBs Router 는 네비게이션만"), ["framework"]),
        ("조사가 붙은 프레임워크 토큰 → framework (뒤 한글은 낱말을 잇지 않는다)", lambda d: edit(d, SK.format("fz-architect"), "- Q1 질문", "- Q1 질문 — RIBs의 Router 는 네비게이션만"), ["framework"]),
        ("조사가 붙은 기호 토큰 → framework (`\\b` 경계도 ASCII)", lambda d: edit(d, SK.format("fz-architect"), "- Q1 질문", "- Q1 질문 — 캡처는 weak var를 쓴다"), ["framework"]),
        ("뒤에 ASCII 영숫자 · `_` 가 붙거나 앞에 `@ # .` 가 붙은 낱말 → 위반 0", lambda d: edit(d, SK.format("fz-architect"), "- Q1 질문", "- Q1 질문 — RIBsX · SwiftUI2 · UIKit_x · @Sendable · #iOS · .Swift"), []),
        ("펜스 안 토큰도 센다 → framework", lambda d: edit(d, SK.format("fz-other"), "- 도메인 팩", "```\nif let listener = listener { }  // guard let on weak var\n```\n- 도메인 팩"), ["framework"]),
        ("로더가 없는 팩을 가리킴 → loader", lambda d: edit(d, SK.format("fz-other"), "domain-ios.md", "domain-android.md"), ["loader"]),
        ("팩이 있는데 로더 줄 없음 → loader", lambda d: edit(d, SK.format("fz-other"), "- 도메인 팩: 프로젝트가 Swift 를 쓰면 `references/domain-ios.md` 를 읽는다", "- 팩 없음"), ["loader"]),
        ("팩이 ruleSource·상한을 안 밝힘 → pack-policy", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "ruleSource=plugin-default · 상한 suggestion", "일반 지식"), ["pack-policy"]),
        ("AI 지침 경로 → ai-path", lambda d: edit(d, SK.format("fz-planner"), "## Output", "읽기: `AI/ai-guidelines.md`\n\n## Output"), ["ai-path"]),
        ("팩 안 레이어 사슬 → layer-chain", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "- `@MainActor`", "- Network → Repository → UseCase → Workflow\n- `@MainActor`"), ["layer-chain"]),
        ("레이어 이름이 단어 안에 든 화살표 → 사슬 아님", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "- `@MainActor`", "- OrderRepository → NetworkClient\n- `@MainActor`"), []),
        ("조사가 붙은 레이어 사슬 → layer-chain (앞뒤 한글은 낱말을 잇지 않는다)", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "- `@MainActor`", "- 계층은Network → Repository를 쓴다\n- `@MainActor`"), ["layer-chain"]),
        ("레이어 이름에 ASCII 숫자 · `_` 가 붙은 화살표 → 사슬 아님", lambda d: edit(d, SK.format("fz-planner"), "## Output", "Network → Repository2 · UseCase → Workflow_x · v2Network → UseCase · _Workflow → Network\n\n## Output"), []),
        ("조사가 붙은 AI 지침 경로 → ai-path (앞 한글은 낱말을 잇지 않는다)", lambda d: edit(d, SK.format("fz-planner"), "## Output", "지침은AI/ai-guidelines.md 를 읽는다\n\n## Output"), ["ai-path"]),
        ("AI 앞에 ASCII 영숫자 · `_` 가 붙은 경로 → 위반 0", lambda d: edit(d, SK.format("fz-planner"), "## Output", "dataAI/ai-guidelines.md · v2AI/ai-guidelines.md · my_AI/ai-guidelines.md\n\n## Output"), []),
        ("경계만 ASCII — NBSP 사슬 · 한글 이름 지침 경로는 잡는다 → ai-path · layer-chain", lambda d: edit(d, SK.format("fz-planner"), "## Output", "`AI/리뷰-guidelines.md` · Network\u00a0→\u3000Repository\n\n## Output"), ["ai-path", "layer-chain"]),
        ("팩 안 작성자 관례 → author", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "- `@MainActor`", "- weak var 는 optional chaining 으로 호출한다\n- `@MainActor`"), ["author"]),
        ("본문 {Feature} 명명 → author", lambda d: edit(d, SK.format("fz-planner"), "## Output", "명명: `{Feature}Router`\n\n## Output"), ["author"]),
        ("Project Rules 절 없음 → section", lambda d: edit(d, SK.format("fz-other"), PROJECT_RULES, "## Context Collection"), ["section"]),
        ("absent 절 없음(옛 CLAUDE.md 절) → section", lambda d: edit(d, SK.format("fz-other"), ABSENT, "## When CLAUDE.md Is Absent"), ["section"]),
        ("지침 파일 집합 결손 → guide-set", lambda d: edit(d, SK.format("fz-other"), f"`{guides[1]}`", "`X.md`"), ["guide-set"]),
        ("6축 결손 → reviewer-axes", lambda d: edit(d, SK.format("fz-reviewer"), f"`{axes[4]}`", "`place`"), ["reviewer-axes"]),
        ("over-engineering 없음 → reviewer-axes", lambda d: edit(d, SK.format("fz-reviewer"), "over-engineering 도 본다.", "끝."), ["reviewer-axes"]),
        ("Q8 없음 → architect-q", lambda d: edit(d, SK.format("fz-architect"), "- Q8 질문", "- Q9 질문"), ["architect-q"]),
        ("조사가 붙은 Q 번호도 있다고 본다 → 위반 0", lambda d: edit(d, SK.format("fz-architect"), "- Q1 질문", "- Q1은 질문"), []),
        ("Q 번호 뒤에 ASCII 숫자가 붙으면 다른 번호다 → architect-q", lambda d: edit(d, SK.format("fz-architect"), "- Q8 질문", "- Q80 질문"), ["architect-q"]),
        ("planner status 없음 → planner-json", lambda d: edit(d, SK.format("fz-planner"), '"status": "ok", ', ""), ["planner-json"]),
        ("planner 옛 평문 거부 → planner-json", lambda d: edit(d, SK.format("fz-planner"), "## Output", f'Reply: "{OLD_REJECT} for cross-validation value."\n\n## Output'), ["planner-json"]),
        ("openai.yaml 없음 → openai-yaml", lambda d: (d / "gpt-skills/fz-other/agents/openai.yaml").unlink(), ["openai-yaml"]),
        ("reviewer 암묵 호출 금지 → openai-yaml", lambda d: edit(d, "gpt-skills/fz-reviewer/agents/openai.yaml", "true", "false"), ["openai-yaml"]),
        ("나머지 암묵 호출 허용(정책 생략=기본 true) → openai-yaml", lambda d: (d / "gpt-skills/fz-planner/agents/openai.yaml").write_text("interface:\n  display_name: \"x\"\n", encoding="utf-8"), ["openai-yaml"]),
    ]
    for name, mutate, want in cases:
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-gsp-"))
        try:
            good(d)
            mutate(d)
            got = rules(d)
            if got == want:
                ok(name)
            else:
                fails.append(f"{name}: want {want} got {got}")
        except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게
            fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
        finally:
            shutil.rmtree(d)
    try:
        empty = pathlib.Path(tempfile.mkdtemp(prefix="fz-gsp-empty-"))
        rc = run(empty)
        shutil.rmtree(empty)
        if rc == UNRUN:
            ok("스킬 0개 → 측정 실패")
        else:
            fails.append(f"스킬 0개 → 측정 실패: want {UNRUN} got {rc}")
    except Exception as e:
        fails.append(f"스킬 0개: 예외 {type(e).__name__}: {e}")
    # ⛔ 6축 선언이 5개면 내용 위반(1) · 선언이 없으면 측정 실패(2) — 둘을 섞지 않는다(F-396)
    real_wf = (HERE.parent / "workflows" / "peer-review.js").read_text(encoding="utf-8")
    for name, wf_text, want in (
        ("f396-portability-axes-violation", re.sub(r"const CRAFT_AXES = \[([^\]]*?),\s*'[a-z_]+'\s*\]", r"const CRAFT_AXES = [\1]", real_wf, count=1), VIOLATION),
        ("f396-portability-axes-decl-missing-unrun", real_wf.replace("const CRAFT_AXES", "const OTHER_AXES", 1), UNRUN),
    ):
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-gsp-axes-"))
        try:
            good(d)
            (d / "peer-review.js").write_text(wf_text, encoding="utf-8")
            rc = run(d, d / "peer-review.js")
            if rc == want:
                ok(name)
            else:
                fails.append(f"{name}: want {want} got {rc}")
        except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게
            fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
        finally:
            shutil.rmtree(d)

    # ── Claude 문서 모드 — 조건 문법 넷 · 읽지 않는 절 · GPT 전용 규칙 제외 ─────────────
    cdoc = "agents/x.md"

    def claude_good(d: pathlib.Path):
        """위반 0 인 Claude 문서 하나와 그 계약 — 줄 안 · `>` 머리 줄 · 제목 · 문단 머리 줄 조건과 읽지 않는 절. GPT 전용 절은 없다."""
        c = CLAUDE_COND
        (d / "agents").mkdir(parents=True)
        (d / cdoc).write_text(
            f"---\nname: x\n---\n\n## Role\n\n일반 원칙만 적는다.\n\n"
            f"## 상태\n\n- 영속 저장소({c} UserDefaults 등)가 과도하지 않은가\n- 컴포넌트 라이프사이클 기준\n\n"
            f"## 문법\n\n> 아래 항목은 {c}에만 적용한다.\n\n- `some`/`any` 표기 — Swift 5.7+\n\n### 문법 하위\n\n- `Sendable` 적합성\n\n"
            f"## API\n\n### Tier 분류 ({c})\n\n| `ObservableObject` | `@Observable` | iOS 17+ |\n\n### 판단\n\n- 신규 코드에만 적용\n\n"
            f"## 모듈\n\n{c}, 다음 모듈을 읽는다:\n\n- SwiftUI 결정 모듈\n- `weak var` 는 optional chaining 으로 부른다\n\n"
            f"## 예시\n\n- RIBs Router 는 네비게이션만\n", encoding="utf-8")
        return {cdoc: {"## 예시": "예시"}}

    def append(d, text):
        p = d / cdoc
        p.write_text(p.read_text(encoding="utf-8") + text, encoding="utf-8")

    claude_cases = [
        ("claude-docs: 최소 문서 → 위반 0 (조건 문법 넷 · 읽지 않는 절 · GPT 전용 절이 없어도 section 위반 없음)", lambda d: None, []),
        ("claude-docs: 줄 안 조건을 지움 → framework", lambda d: edit(d, cdoc, f"({CLAUDE_COND} UserDefaults", "(UserDefaults"), ["framework"]),
        ("claude-docs: `>` 머리 줄 조건을 지움 → framework", lambda d: edit(d, cdoc, f"> 아래 항목은 {CLAUDE_COND}에만", "> 아래 항목에만"), ["framework"]),
        ("claude-docs: 제목 줄 조건을 지움 → framework", lambda d: edit(d, cdoc, f"### Tier 분류 ({CLAUDE_COND})", "### Tier 분류"), ["framework"]),
        ("claude-docs: 문단 머리 줄 조건을 지움 → framework · author", lambda d: edit(d, cdoc, f"{CLAUDE_COND}, 다음 모듈", "다음 모듈"), ["author", "framework"]),
        ("claude-docs: 조건 없는 프레임워크 규칙을 새 절로 넣음 → framework", lambda d: append(d, "\n## 새 절\n\n- SwiftUI View 는 반드시 @MainActor 로 격리한다\n"), ["framework"]),
        ("claude-docs: 절 중간의 조건 문장은 뒤 줄을 덮지 않는다 → framework", lambda d: edit(d, cdoc, "- 컴포넌트 라이프사이클 기준", f"{CLAUDE_COND} 아래를 본다:\n- RIBs Interactor 라이프사이클 기준"), ["framework"]),
        ("claude-docs: 첫 줄이 조건 단 목록 항목이면 그 줄만 덮는다 → framework", lambda d: edit(d, cdoc, "- 컴포넌트 라이프사이클 기준", "- RIBs Interactor 라이프사이클 기준"), ["framework"]),
        ("claude-docs: 하위 제목의 조건은 부모 절 · 형제 절로 번지지 않는다 → framework", lambda d: edit(d, cdoc, "- 신규 코드에만 적용", "- `#available` 가드를 본다"), ["framework"]),
        ("claude-docs: 읽지 않는 절 안에 새 하위 절을 넣으면 읽는다 → framework", lambda d: append(d, "\n### 새 하위\n\n- `@MainActor` 를 붙인다\n"), ["framework"]),
        ("claude-docs: 조사가 붙은 프레임워크 토큰 → framework", lambda d: edit(d, cdoc, "일반 원칙만 적는다.", "SwiftUI는 반드시 상태를 분리한다."), ["framework"]),
        ("claude-docs: 조사가 붙은 스택 어휘(CLAUDE_EXTRA_RE) → framework", lambda d: edit(d, cdoc, "일반 원칙만 적는다.", "설정은 UserDefaults를 남용하지 않는다."), ["framework"]),
        ("claude-docs: 조사가 붙은 격리 경계 어휘(CLAUDE_EXTRA_RE 의 `\\b`) → framework", lambda d: edit(d, cdoc, "일반 원칙만 적는다.", "경계는 actor isolation을 지킨다."), ["framework"]),
        ("claude-docs: 뒤에 ASCII 영숫자 · `_` 가 붙은 스택 어휘 → 위반 0", lambda d: edit(d, cdoc, "일반 원칙만 적는다.", "UserDefaultsX · KeychainItem · CoreData_x · actor isolationX 는 다른 이름이다."), []),
        ("claude-docs: 조건 없는 작성자 관례 → author", lambda d: edit(d, cdoc, "일반 원칙만 적는다.", "호출은 optional chaining 으로 한다."), ["author"]),
        ("claude-docs: AI 지침 경로 · 레이어 사슬은 조건과 무관 → ai-path · layer-chain", lambda d: edit(d, cdoc, "UserDefaults 등)가 과도하지 않은가", "UserDefaults 등)가 과도하지 않은가 · `AI/ai-guidelines.md` · Network → Repository"), ["ai-path", "layer-chain"]),
        ("claude-docs: 조사가 붙은 AI 지침 경로 · 레이어 사슬 → ai-path · layer-chain", lambda d: edit(d, cdoc, "일반 원칙만 적는다.", "지침은AI/ai-guidelines.md 를 읽고 계층은Network → Repository를 따른다."), ["ai-path", "layer-chain"]),
        ("claude-docs: ASCII 영숫자 · `_` 가 붙은 경로 · 레이어 이름 → 위반 0", lambda d: edit(d, cdoc, "일반 원칙만 적는다.", "dataAI/ai-guidelines.md · my_AI/ai-guidelines.md · Network → Repository2 · UseCase → Workflow_x · xNetwork → UseCase"), []),
        ("claude-docs: 계약이 읽지 않는다고 적은 절이 없다 → contract", lambda d: edit(d, cdoc, "## 예시", "## 보기"), ["contract", "framework"]),
        ("claude-docs: 전각 공백 뒤 표지는 제목이 아니다 — 그 줄의 조건은 아래 규칙을 덮지 않는다 → framework",
         lambda d: edit(d, cdoc, "일반 원칙만 적는다.", f"일반 원칙만 적는다.\n\n##\u3000{CLAUDE_COND}\n\n- SwiftUI View 는 @MainActor 로 격리한다"), ["framework"]),
        ("claude-docs: 같은 자리 공백 뒤 표지는 제목이다 — 제목의 조건이 아래 규칙을 덮는다 → 위반 0",
         lambda d: edit(d, cdoc, "일반 원칙만 적는다.", f"일반 원칙만 적는다.\n\n## {CLAUDE_COND}\n\n- SwiftUI View 는 @MainActor 로 격리한다"), []),
        ("claude-docs: 같은 자리 탭 뒤 표지도 제목이다 — 제목의 조건이 아래 규칙을 덮는다 → 위반 0",
         lambda d: edit(d, cdoc, "일반 원칙만 적는다.", f"일반 원칙만 적는다.\n\n##\t{CLAUDE_COND}\n\n- SwiftUI View 는 @MainActor 로 격리한다"), []),
    ]
    for name, mutate, want in claude_cases:
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-gsp-claude-"))
        try:
            docs = claude_good(d)
            mutate(d)
            got = sorted({r for _, _, r, _ in scan_claude(d, docs)[1]})
            if got == want:
                ok(name)
            else:
                fails.append(f"{name}: want {want} got {got}")
        except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게
            fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
        finally:
            shutil.rmtree(d)
    name = "claude-docs: 대상 파일 없음 → 측정 실패"
    d = pathlib.Path(tempfile.mkdtemp(prefix="fz-gsp-claude-empty-"))
    try:
        rc = run_claude(d, {cdoc: {}})
        if rc == UNRUN:
            ok(name)
        else:
            fails.append(f"{name}: want {UNRUN} got {rc}")
    except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게
        fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(d)
    # 실제 대상 문서 — 위반 0 이고, 조건 문구를 하나씩 지우면 위반이 난다(조건마다 덮는 스택 어휘가 있다 — 되돌리면 실패)
    name = "claude-docs: 실제 대상 → 위반 0 · 조건을 하나씩 지우면 위반"
    d = pathlib.Path(tempfile.mkdtemp(prefix="fz-gsp-claude-real-"))
    try:
        for rel in CLAUDE_DOCS:
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(HERE.parent / rel, d / rel)
        base, seen, dead = scan_claude(d)[1], 0, []
        for rel in CLAUDE_DOCS:
            p = d / rel
            t = p.read_text(encoding="utf-8")
            at = t.find(CLAUDE_COND)
            while at >= 0:
                seen += 1
                p.write_text(t[:at] + t[at + len(CLAUDE_COND):], encoding="utf-8")
                if not scan_claude(d)[1]:
                    dead.append(f"{rel}:{t.count(chr(10), 0, at) + 1}")
                at = t.find(CLAUDE_COND, at + 1)
            p.write_text(t, encoding="utf-8")
        if not base and seen and not dead:
            ok(name)
        else:
            fails.append(f"{name}: 위반 {len(base)}건 · 조건 {seen}개 · 지워도 위반이 없는 자리 {dead}")
    except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게
        fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(d)
    # 제목 표지 뒤 문자 격자 — 파이썬이 공백으로 보는 문자 전부(실행 중 계산 — 파이썬 판마다 다르다) × 표지 길이 1~7 × 조건 자리 × 앞 맥락.
    #   오라클은 변형 관계다: 유니코드 공백 문서는 그 문자를 'x' 로 바꾼 문서와, 탭 문서는 공백 문서와 판정이 같아야 한다.
    #   앞 맥락마다 공백 문서와 'x' 문서의 판정이 갈리는 칸이 있어야 한다 — 없으면 관계가 헛돈다.
    #   격자 밖: 앞 공백 1~3칸 제목 · 닫는 `#` · setext 제목 · HTML 블록 · 유니코드 공백 뒤 펜스 표지(FENCE_RE)
    rule = "- SwiftUI View 는 @MainActor 로 격리한다\n"
    leads = {   # 앞 맥락 → (시험 줄 앞 본문, 계약이 읽지 않는 절)
        "조건 절": (f"## 조건 절 ({CLAUDE_COND})\n\n일반 문장이다.\n\n", {}),
        "읽지 않는 절": ("## 예시\n\n일반 문장이다.\n\n", {"## 예시": "예시"}),
        "평범한 절": ("## Role\n\n일반 원칙만 적는다.\n\n", {}),
    }
    spots = {   # 조건 자리 → 표지 줄부터 문서 끝까지
        "그 줄": lambda h: f"{h}{CLAUDE_COND}\n\n{rule}",
        "아래 문단 첫 줄": lambda h: f"{h}규칙\n\n{CLAUDE_COND}, 아래를 따른다.\n\n{rule}",
        "아래 목록 첫 줄": lambda h: f"{h}규칙\n\n- {CLAUDE_COND} UserDefaults 를 본다\n{rule}",
        "없음": lambda h: f"{h}규칙\n\n{rule}",
    }
    spaces = [c for c in map(chr, range(0x110000)) if c.isspace() and c not in " \t\n\r"]
    name = (f"claude-docs: heading-space-grid — 유니코드 공백 {len(spaces)}자 × 표지 1~7 × 조건 자리 {len(spots)} × 앞 맥락 {len(leads)}"
            " → 공백 · 탭 뒤 표지만 제목")
    d = pathlib.Path(tempfile.mkdtemp(prefix="fz-gsp-claude-grid-"))
    try:
        (d / "agents").mkdir()

        def verdict(lead, unread, text):
            (d / cdoc).write_text(f"---\nname: x\n---\n\n{lead}{text}", encoding="utf-8")
            return sorted((i, r) for _, i, r, _ in scan_claude(d, {cdoc: unread})[1])

        bad, split = [], dict.fromkeys(leads, 0)
        for n in range(1, 8):
            for c in [" ", "\t", "x"] + spaces:
                if bool(outline(["#" * n + c + "규칙"])) != (n <= 6 and c in " \t"):
                    bad.append(f"outline 표지 {n} · {hex(ord(c))}")
            for lk, (lead, unread) in leads.items():
                for sk, body in spots.items():
                    sp, x = verdict(lead, unread, body("#" * n + " ")), verdict(lead, unread, body("#" * n + "x"))
                    split[lk] += sp != x
                    for c in ["\t"] + spaces:
                        got, want = verdict(lead, unread, body("#" * n + c)), (sp if c == "\t" else x)
                        if got != want:
                            bad.append(f"표지 {n} · {hex(ord(c))} · {lk} · 조건 {sk}: want {want} got {got}")
        if not bad and all(split.values()):
            ok(name)
        else:
            fails.append(f"{name}: 어긋난 칸 {len(bad)}개 {bad[:4]} · 공백과 'x' 가 갈리는 칸 {split}")
    except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게
        fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(d)

    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--claude-docs", action="store_true", help="Claude 문서 모드 — 대상은 CLAUDE_DOCS 계약")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return run_claude(a.root) if a.claude_docs else run(a.root)


if __name__ == "__main__":
    sys.exit(main())
