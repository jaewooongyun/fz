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

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님 — 스킬 0개 · 기준값을 읽지 못함)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent

# 프레임워크 토큰 — 번들 스킬이 실제로 박고 있던 스택 어휘다(기준 트리 실측). 단어 경계로 본다.
FRAMEWORK_WORDS = ("RIBs", "SwiftUI", "UIKit", "Swift", "iOS", "Xcode", "PromiseKit", "RxSwift", "Interactor",
                   "ViewController", "ObservableObject", "Clean Architecture", "disposeBag", "didBecomeActive",
                   "willResignActive", "deinit", "nonisolated", "withCheckedContinuation", "AsyncStream", "TaskGroup",
                   "Sendable", "xcconfig", "swiftlint")
FRAMEWORK_SYMBOLS = (r"@MainActor", r"@StateObject", r"@ObservedObject", r"@Observable\b", r"@State\b", r"@Published",
                     r"@Binding", r"@Bindable", r"#available", r"\[weak self\]", r"\bweak var\b", r"\.swift\b",
                     r"\bactor-isolated\b", r"\basync let\b")
FRAMEWORK_RE = re.compile("|".join([rf"(?<![\w@#.]){re.escape(w)}(?![\w])" for w in FRAMEWORK_WORDS] + list(FRAMEWORK_SYMBOLS)))
# 작성자 프로젝트 전용 관례 — 규칙으로 싣지 않는다(팩에도). 인용 형식 예시는 플레이스홀더로만 쓴다.
AUTHOR_RE = re.compile(r"\{Feature\}|optional chaining|옵셔널 체이닝", re.I)
AI_PATH_RE = re.compile(r"\bAI/[\w.-]*guidelines", re.I)
LAYERS = r"\b(?:Network|Repository|UseCase|Workflow)\b"   # 단어 경계 — `OrderRepository → NetworkClient` 는 사슬이 아니다
LAYER_RE = re.compile(rf"{LAYERS}\s*(?:→|←|->|<-|>|<)\s*{LAYERS}")
LOADER_RE = re.compile(r"references/(domain-[\w-]+\.md)")
PROJECT_RULES = "## Project Rules (runtime)"
ABSENT = "## When Project Guidelines Are Absent"
OLD_REJECT = "Claude plan detected. Provide requirements only"
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def baseline():
    """지침 파일 집합(추출기)과 6축(워크플로) — 두 모델이 같은 정의를 쓰도록 이 트리의 정본에서 읽는다."""
    sys.path.insert(0, str(HERE))
    try:
        import extract_project_rules as epr
        guides = sorted(epr.GUIDE_NAMES) + sorted(epr.GUIDE_PATHS)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(f"지침 파일 집합을 읽지 못했다(scripts/extract_project_rules.py): {e}")
    wf = HERE.parent / "workflows" / "peer-review.js"
    try:
        m = re.search(r"const CRAFT_AXES = \[([^\]]*)\]", wf.read_text(encoding="utf-8"))
    except OSError as e:
        raise RuntimeError(f"6축을 읽지 못했다({wf}): {e}")
    axes = re.findall(r"'([a-z_]+)'", m.group(1)) if m else []
    if len(axes) != 6:
        raise RuntimeError(f"CRAFT_AXES 가 6개가 아니다({wf}): {axes}")
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
            miss = [f"Q{n}" for n in range(1, 9) if not re.search(rf"\bQ{n}\b", body)]
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


def run(root: pathlib.Path) -> int:
    try:
        guides, axes = baseline()
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


def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []
    guides, axes = baseline()

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
        ("펜스 안 토큰도 센다 → framework", lambda d: edit(d, SK.format("fz-other"), "- 도메인 팩", "```\nif let listener = listener { }  // guard let on weak var\n```\n- 도메인 팩"), ["framework"]),
        ("로더가 없는 팩을 가리킴 → loader", lambda d: edit(d, SK.format("fz-other"), "domain-ios.md", "domain-android.md"), ["loader"]),
        ("팩이 있는데 로더 줄 없음 → loader", lambda d: edit(d, SK.format("fz-other"), "- 도메인 팩: 프로젝트가 Swift 를 쓰면 `references/domain-ios.md` 를 읽는다", "- 팩 없음"), ["loader"]),
        ("팩이 ruleSource·상한을 안 밝힘 → pack-policy", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "ruleSource=plugin-default · 상한 suggestion", "일반 지식"), ["pack-policy"]),
        ("AI 지침 경로 → ai-path", lambda d: edit(d, SK.format("fz-planner"), "## Output", "읽기: `AI/ai-guidelines.md`\n\n## Output"), ["ai-path"]),
        ("팩 안 레이어 사슬 → layer-chain", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "- `@MainActor`", "- Network → Repository → UseCase → Workflow\n- `@MainActor`"), ["layer-chain"]),
        ("레이어 이름이 단어 안에 든 화살표 → 사슬 아님", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "- `@MainActor`", "- OrderRepository → NetworkClient\n- `@MainActor`"), []),
        ("팩 안 작성자 관례 → author", lambda d: edit(d, "gpt-skills/fz-other/references/domain-ios.md", "- `@MainActor`", "- weak var 는 optional chaining 으로 호출한다\n- `@MainActor`"), ["author"]),
        ("본문 {Feature} 명명 → author", lambda d: edit(d, SK.format("fz-planner"), "## Output", "명명: `{Feature}Router`\n\n## Output"), ["author"]),
        ("Project Rules 절 없음 → section", lambda d: edit(d, SK.format("fz-other"), PROJECT_RULES, "## Context Collection"), ["section"]),
        ("absent 절 없음(옛 CLAUDE.md 절) → section", lambda d: edit(d, SK.format("fz-other"), ABSENT, "## When CLAUDE.md Is Absent"), ["section"]),
        ("지침 파일 집합 결손 → guide-set", lambda d: edit(d, SK.format("fz-other"), f"`{guides[1]}`", "`X.md`"), ["guide-set"]),
        ("6축 결손 → reviewer-axes", lambda d: edit(d, SK.format("fz-reviewer"), f"`{axes[4]}`", "`place`"), ["reviewer-axes"]),
        ("over-engineering 없음 → reviewer-axes", lambda d: edit(d, SK.format("fz-reviewer"), "over-engineering 도 본다.", "끝."), ["reviewer-axes"]),
        ("Q8 없음 → architect-q", lambda d: edit(d, SK.format("fz-architect"), "- Q8 질문", "- Q9 질문"), ["architect-q"]),
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
                passed += 1
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
            passed += 1
        else:
            fails.append(f"스킬 0개 → 측정 실패: want {UNRUN} got {rc}")
    except Exception as e:
        fails.append(f"스킬 0개: 예외 {type(e).__name__}: {e}")

    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else run(a.root)


if __name__ == "__main__":
    sys.exit(main())
