#!/usr/bin/env python3
"""재발 방지 lint 11종 (B6) — 고친 문서 결함이 다시 생기면 잡는다.

결함을 고치기만 하면 다시 생긴다. 등재된 결함마다 기계 검사를 하나씩 둔다.

| lint | 잡는 것 | 출처 |
|---|---|---|
| copies | `<!-- shared:NAME begin/end -->` 블록이 원문(templates/…)과 · 서로 다르다 · 짝 없는 블록 | F-046 · F-461 |
| project-rules | GPT 역할 스킬에 Project Rules 공유 블록이 없다 | F-472 |
| team-residue | 일몰된 TEAM/P2P 실행 지시(TeamCreate · SendMessage · TEAM 모드 · *-team.md)가 운영 문서에 남았다 | F-482 |
| head-declaration | 머리에서 pilot(제한 범위)이라 선언한 모듈을 여러 파일이 일반 규칙으로 인용한다 | F-484 |
| module-size | 모듈 500줄 초과는 분리 검토 **경고**(실패 아님) · SKILL.md 500줄 초과는 실패 | F-485 |
| broken-refs | "<대상>: <모듈 경로> 참조" 의 대상 이름이 그 파일에 없다(앵커 없는 산문 참조) | F-474 |
| count-mismatch | "**N개 …**" 머리말 바로 아래 표의 행 수가 N 이 아니다 | F-479 |
| catalog-required | 점검 카탈로그(templates/check-catalog-*.md)가 있어야 할 경로에 없다 — Workflow 워커 · GPT 역할 스킬은 공용 블록 · light Lead 는 템플릿 Read 지시 | F-005 외 PROMPT 15 |
| audit-wiring | 워크플로 호출 지시(`Workflow({ scriptPath …`)가 적힌 스킬 · 모듈 · 가이드에 워커 심볼 도구 점검 줄(`--mcp-audit` 이 든 줄 — 직접 호출 `--direct` 줄은 세지 않는다)이 없다 | 점검이 호출 지시 파일 11개 중 1개에만 있었다 — 새 스킬이 빠뜨리지 않게 |
| stack-skill-channel | `## 스택 스킬` 절이 있는 스킬의 그 절에 소비 경로 낱말(`스택 스킬 요구 사항` · `스택 스킬은 Lead 판단용`)이 정확히 하나가 아니다 · 워커에게 가는 통로가 있는 스킬(구현 · 수정 · 계획 · 리뷰 · 접근 탐색)이 앞의 것이 아니다 | 스택 스킬을 Lead 만 읽고 코드를 쓰는 워커는 모르는 일을 막는다 |
| symbol-tools-block | frontmatter `tools:` 에 Serena 심볼 도구(`find_symbol` · `find_referencing_symbols` · `get_symbols_overview`)가 있는 에이전트에 `## Symbol tools` 절(그 제목 줄부터 다음 `## ` 제목 전까지)이 정확히 하나가 아니다 · 그 절이 에이전트끼리 · `templates/agent-template.md` 와 글자가 다르다 · 그 도구가 없는 에이전트에 절이 있다 | 같은 절의 사본이 에이전트 13개와 템플릿에 있는데 저장소 안에서 같음을 지키는 검사가 없었다 |

⛔ 미실행은 PASS 가 아니다 — 검사 대상이 0개면 그 lint 는 UNRUN 이고 전체도 PASS 가 아니다.

usage: lint_recurrence.py [--root R] [--only NAME]   ·   --self-test
출력: lint 마다 `<name>: PASS|WARN|FAIL|UNRUN …` · 끝에 `lint_recurrence: k/11 PASS`
exit: 0 전부 PASS(WARN 포함) · 1 위반 · 2 미실행 있음
"""
from __future__ import annotations

import glob
import os
import re
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
LINTS = ("copies", "project-rules", "team-residue", "head-declaration", "module-size", "broken-refs", "count-mismatch", "catalog-required",
         "audit-wiring", "stack-skill-channel", "symbol-tools-block")
TEMPLATES = {"review-core": "templates/review-shared-block.md", "project-rules": "templates/project-rules-block.md",
             "catalog-plan": "templates/check-catalog-plan.md", "catalog-review": "templates/check-catalog-review.md",
             "catalog-code": "templates/check-catalog-code.md"}
# 점검 카탈로그가 있어야 할 곳(round 3 S3) — copies 는 있는 사본이 같은지만 본다. 빠진 경로는 여기서 잡는다
CATALOG_BLOCKS = {"catalog-plan": ("agents/plan-edge-case.md", "gpt-skills/fz-planner/SKILL.md", "gpt-skills/fz-architect/SKILL.md"),
                  "catalog-review": ("agents/review-counter.md", "gpt-skills/fz-reviewer/SKILL.md"),
                  "catalog-code": ("agents/impl-correctness.md",)}
CATALOG_READS = {"skills/fz-plan/SKILL.md": "templates/check-catalog-plan.md", "skills/fz-review/SKILL.md": "templates/check-catalog-review.md",
                 "skills/fz-code/SKILL.md": "templates/check-catalog-code.md"}   # light Lead — Workflow 가 없어 템플릿을 직접 Read 한다
SHARED = re.compile(r"<!-- shared:([\w-]+) begin -->\n(.*?)<!-- shared:\1 end -->", re.S)
OPERATIVE = ("agents/*.md", "skills/*/SKILL.md", "modules/*.md")
TEAM_RE = re.compile(r"TeamCreate|SendMessage|-team\.md")   # 일몰된 장치를 쓰라는 실행 지시 — "TEAM" 은 지금도 full 추천 모드의 이름이라 대상이 아니다
TEAM_OK = re.compile(r"일몰|없음|없다|부재|아니다|아님|않|미사용|불필요|독립|이력|롤백|rollback|금지|sunset|retired|대체")   # 부정 · 이력 문장은 지시가 아니다
REF_RE = re.compile(r"(?P<term>[A-Za-z가-힣][^:|`*\n]{2,40}?)\**\s*[:：]\s*`?(?P<file>(?:modules|guides)/[\w.-]+\.md)`?\s*참조")
PROPER = re.compile(r"[A-Z][A-Za-z0-9]+(?:\s+[A-Z0-9][\w.]*)*")   # 대상의 고유 이름(영문) — 한국어 이름표(상세 · 절차)는 낱말 대조 대상이 아니다
COUNT_RE = re.compile(r"\*\*(\d+)개 ([^*\n]{2,40})\*\*")
WF_CALL = re.compile(r"Workflow\(\{ *scriptPath")   # 워크플로 호출 지시 — 이 꼴이 적힌 문서는 반환 뒤 심볼 도구 점검 줄을 함께 둔다
WIRING_DOCS = ("skills/*/SKILL.md", "modules/*.md", "guides/*.md")
STACK_HEAD = re.compile(r"^## 스택 스킬.*$", re.M)
STACK_WORKER, STACK_LEAD = "스택 스킬 요구 사항", "스택 스킬은 Lead 판단용"   # 소비 경로 두 낱말 — 워커 전달 · Lead 판단용
STACK_WORKER_SKILLS = ("fz-code", "fz-discover", "fz-fix", "fz-plan", "fz-review")   # 워커에게 가는 기존 통로(Step 맥락 · 알려진 제약 · 의도 맥락)가 있는 스킬
SYMBOL_HEAD = "## Symbol tools"   # 심볼 도구 공통 절의 제목 줄 머리 — 절은 이 줄부터 다음 `## ` 제목 전까지다
SYMBOL_TOOL_RE = re.compile(r"(?:(?<![\w-])|(?<=__))(?:find_symbol|find_referencing_symbols|get_symbols_overview)(?![\w-])")   # 맨 이름 · 서버 접두(`…__find_symbol`)
AGENT_TEMPLATE = "templates/agent-template.md"


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def _files(root, globs):
    return sorted({p for g in globs for p in glob.glob(os.path.join(root, g), recursive=True) if os.path.isfile(p)})


def lint_copies(root):
    v, groups = [], {}
    for p in _files(root, ("agents/*.md", "skills/**/*.md", "gpt-skills/**/*.md", "modules/*.md")):
        for m in SHARED.finditer(_read(p)):
            groups.setdefault(m.group(1), []).append((os.path.relpath(p, root), m.group(2)))
    if not groups:
        return None, "shared 블록 0개"
    for name, occ in sorted(groups.items()):
        tpl = TEMPLATES.get(name)
        if tpl:
            tp = os.path.join(root, tpl)
            if not os.path.isfile(tp):
                v.append(f"{name}: 원문 {tpl} 없음")
                continue
            want = _read(tp)
            v += [f"{name}: {rel} 의 블록이 원문 {tpl} 과 다르다" for rel, body in occ if body != want]
        else:
            if len(occ) < 2:
                v.append(f"{name}: 짝 없는 공유 블록 — {occ[0][0]} 하나뿐")
            v += [f"{name}: {rel} 의 블록이 {occ[0][0]} 과 다르다" for rel, body in occ[1:] if body != occ[0][1]]
    return v, f"블록 이름 {len(groups)}개 · 사본 {sum(len(o) for o in groups.values())}개"


def lint_project_rules(root):
    skills = _files(root, ("gpt-skills/*/SKILL.md",))
    if not skills:
        return None, "GPT 역할 스킬 0개"
    v = [f"{os.path.relpath(p, root)}: shared:project-rules 블록 없음" for p in skills
         if not any(m.group(1) == "project-rules" for m in SHARED.finditer(_read(p)))]
    return v, f"GPT 역할 스킬 {len(skills)}개"


def lint_team_residue(root):
    files = _files(root, OPERATIVE)
    if not files:
        return None, "운영 문서 0개"
    v = []
    for p in files:
        for i, line in enumerate(_read(p).split("\n"), 1):
            if TEAM_RE.search(line) and not TEAM_OK.search(line):
                v.append(f"{os.path.relpath(p, root)}:{i}: 일몰된 TEAM/P2P 지시 — {line.strip()[:80]}")
    return v, f"운영 문서 {len(files)}개"


def lint_head_declaration(root):
    mods = _files(root, ("modules/*.md",))
    if not mods:
        return None, "모듈 0개"
    every = _files(root, ("agents/*.md", "skills/**/*.md", "modules/*.md", "CLAUDE.md"))
    texts = {p: _read(p) for p in every}
    v = []
    for p in mods:
        head = "\n".join(_read(p).split("\n")[:12])
        if not re.search(r"\bpilot\b|Pilot|파일럿", head):
            continue
        rel = os.path.relpath(p, root)
        users = [q for q, t in texts.items() if q != p and rel in t]
        if len(users) > 3:
            v.append(f"{rel}: 머리에서 pilot(제한 범위)이라 선언했는데 {len(users)}개 파일이 인용한다 — 범위 선언을 실제에 맞춘다")
    return v, f"모듈 {len(mods)}개"


def lint_module_size(root):
    mods, skills = _files(root, ("modules/*.md",)), _files(root, ("skills/*/SKILL.md",))
    if not mods and not skills:
        return None, "대상 0개"
    warn = [f"{os.path.relpath(p, root)}: {len(_read(p).splitlines())}줄 > 500 — 분리 검토(경고)" for p in mods
            if len(_read(p).splitlines()) > 500]
    fail = [f"{os.path.relpath(p, root)}: {len(_read(p).splitlines())}줄 > 500 — SKILL 상한 초과" for p in skills
            if len(_read(p).splitlines()) > 500]
    return fail, f"모듈 {len(mods)} · SKILL {len(skills)}" + (f" · 경고 {len(warn)}: " + "; ".join(warn[:3]) if warn else "")


def lint_broken_refs(root):
    files = _files(root, OPERATIVE)
    if not files:
        return None, "운영 문서 0개"
    v, n = [], 0
    for p in files:
        for i, line in enumerate(_read(p).split("\n"), 1):
            for m in REF_RE.finditer(line):
                n += 1
                target = os.path.join(root, m.group("file"))
                names = PROPER.findall(m.group("term"))
                if not os.path.isfile(target):
                    v.append(f"{os.path.relpath(p, root)}:{i}: 참조 대상 {m.group('file')} 없음")
                    continue
                body = _read(target)
                missing = [x for x in names if x not in body]
                if missing:
                    v.append(f"{os.path.relpath(p, root)}:{i}: '{missing[0]}' 이 {m.group('file')} 에 없다 — 앵커 없는 산문 참조")
    return v, f"산문 참조 {n}건"


def lint_count_mismatch(root):
    files = _files(root, OPERATIVE)
    if not files:
        return None, "운영 문서 0개"
    v, n = [], 0
    for p in files:
        lines = _read(p).split("\n")
        for i, line in enumerate(lines):
            m = COUNT_RE.search(line)
            if not m:
                continue
            j = next((k for k in range(i + 1, min(i + 4, len(lines))) if lines[k].lstrip().startswith("|")), None)
            if j is None or j + 1 >= len(lines) or not re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[j + 1]):
                continue
            n += 1
            rows = 0
            for k in range(j + 2, len(lines)):
                if not lines[k].lstrip().startswith("|"):
                    break
                rows += 1
            if rows != int(m.group(1)):
                v.append(f"{os.path.relpath(p, root)}:{i + 1}: '{m.group(1)}개 {m.group(2)}' 인데 표는 {rows}행")
    return v, f"개수 머리말 {n}건"


def lint_catalog_required(root):
    if not any(os.path.isfile(os.path.join(root, TEMPLATES[n])) for n in CATALOG_BLOCKS):
        return None, "점검 카탈로그 템플릿 0개"
    v = [f"{n}: 원문 {TEMPLATES[n]} 없음" for n in CATALOG_BLOCKS if not os.path.isfile(os.path.join(root, TEMPLATES[n]))]
    for name, paths in CATALOG_BLOCKS.items():
        for rel in paths:
            p = os.path.join(root, rel)
            if not os.path.isfile(p) or not any(m.group(1) == name for m in SHARED.finditer(_read(p))):
                v.append(f"{rel}: shared:{name} 블록 없음 — 이 경로의 워커가 카탈로그를 받지 못한다")
    for rel, tpl in CATALOG_READS.items():
        p = os.path.join(root, rel)
        if not os.path.isfile(p) or tpl not in _read(p):
            v.append(f"{rel}: {tpl} Read 지시 없음 — light Lead 경로가 카탈로그를 받지 못한다")
    return v, f"블록 경로 {sum(len(x) for x in CATALOG_BLOCKS.values())} · Read 경로 {len(CATALOG_READS)}"


def lint_audit_wiring(root):
    """워크플로를 부르는 문서마다 반환 뒤 심볼 도구 점검 줄이 있는가 — 직접 호출(`--direct`) 줄은 워크플로 점검이 아니라 세지 않는다."""
    files = [p for p in _files(root, WIRING_DOCS) if WF_CALL.search(_read(p))]
    if not files:
        return None, "워크플로 호출 지시가 있는 문서 0개"
    v = [f"{os.path.relpath(p, root)}: 워크플로를 부르는데 심볼 도구 점검 줄(`--mcp-audit`)이 없다 — 명령 꼴은 modules/tool-status.md"
         for p in files if not any("--mcp-audit" in ln and "--direct" not in ln for ln in _read(p).split("\n"))]
    return v, f"워크플로 호출 문서 {len(files)}개"


def lint_stack_skill_channel(root):
    """`## 스택 스킬` 절(다음 `## ` 제목 전까지)에 소비 경로 낱말이 정확히 하나 · 워커 통로가 있는 스킬은 워커 전달이어야 한다."""
    skills = [p for p in _files(root, ("skills/*/SKILL.md",)) if STACK_HEAD.search(_read(p))]
    if not skills:
        return None, "`## 스택 스킬` 절이 있는 스킬 0개"
    v = []
    for p in skills:
        t = _read(p)
        m = STACK_HEAD.search(t)
        nxt = re.search(r"^## ", t[m.end():], re.M)
        sec = t[m.end():m.end() + nxt.start()] if nxt else t[m.end():]
        has = [w for w in (STACK_WORKER, STACK_LEAD) if w in sec]
        rel, name = os.path.relpath(p, root), os.path.basename(os.path.dirname(p))
        if len(has) != 1:
            v.append(f"{rel}: 스택 스킬 절의 소비 경로 낱말이 {len(has)}개다 — `{STACK_WORKER}` 또는 `{STACK_LEAD}` 가운데 하나만 적는다")
        elif name in STACK_WORKER_SKILLS and has[0] != STACK_WORKER:
            v.append(f"{rel}: 워커에게 가는 통로가 있는 스킬인데 `{STACK_LEAD}` 다 — `{STACK_WORKER}` 를 그 통로에 싣는다")
    return v, f"스택 스킬 절 {len(skills)}개"


def _symbol_sections(text):
    """`## Symbol tools` 로 시작하는 줄부터 다음 `## ` 제목 줄 전까지의 절 목록(끝 빈 줄은 뺀다)."""
    lines, out = text.split("\n"), []
    for i, ln in enumerate(lines):
        if ln.startswith(SYMBOL_HEAD):
            j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
            out.append("\n".join(lines[i:j]).rstrip())
    return out


def _agent_tools(text):
    """frontmatter `tools:` 값(같은 줄 · 아래 `- 항목` 줄) — 주석 줄은 보지 않는다. frontmatter 가 없으면 빈 문자열."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return ""
    end = next((k for k in range(1, len(lines)) if lines[k].strip() == "---"), len(lines))
    vals = []
    for i in range(1, end):
        if lines[i].startswith("tools:"):
            vals.append(lines[i][len("tools:"):])
            vals += [x for x in lines[i + 1:end] if x.lstrip().startswith("- ")]
    return " ".join(vals)


def lint_symbol_tools_block(root):
    """심볼 도구를 선언한 에이전트마다 `## Symbol tools` 절이 하나 · 그 글자가 서로 · 템플릿과 같다 · 선언하지 않은 에이전트엔 절이 없다."""
    agents = _files(root, ("agents/*.md",))
    if not agents:
        return None, "에이전트 0개"
    v, holders = [], {}
    for p in agents:
        t, rel = _read(p), os.path.relpath(p, root)
        secs = _symbol_sections(t)
        if SYMBOL_TOOL_RE.search(_agent_tools(t)):
            if len(secs) != 1:
                v.append(f"{rel}: 심볼 도구를 선언했는데 `{SYMBOL_HEAD}` 절이 {len(secs)}개다 — 정확히 하나를 둔다")
            else:
                holders[rel] = secs[0]
        elif secs:
            v.append(f"{rel}: 심볼 도구를 선언하지 않았는데 `{SYMBOL_HEAD}` 절이 있다 — 절을 빼거나 `tools:` 에 도구를 둔다")
    if not holders and not v:
        return None, "심볼 도구를 선언한 에이전트 0개"
    tp = os.path.join(root, AGENT_TEMPLATE)
    tsecs = _symbol_sections(_read(tp)) if os.path.isfile(tp) else []
    tsec = tsecs[0] if len(tsecs) == 1 else None
    if tsec is None:
        v.append(f"{AGENT_TEMPLATE}: `{SYMBOL_HEAD}` 절이 {len(tsecs)}개다 — 원문 절을 정확히 하나 둔다")
    # 기준 글자 = 에이전트 사본의 다수 — 같은 수면 템플릿 글자가 이긴다. 다른 쪽(에이전트 · 템플릿)을 이름으로 낸다
    votes = {}
    for sec in holders.values():
        votes[sec] = votes.get(sec, 0) + 1
    ref = max(votes, key=lambda x: (votes[x], x == tsec)) if votes else tsec
    v += [f"{rel}: `{SYMBOL_HEAD}` 절이 다른 사본과 글자가 다르다" for rel, sec in holders.items() if sec != ref]
    if tsec is not None and ref is not None and tsec != ref:
        v.append(f"{AGENT_TEMPLATE}: `{SYMBOL_HEAD}` 절이 에이전트 사본과 글자가 다르다")
    return v, f"심볼 도구 선언 에이전트 {len(holders)}개 · 템플릿 절 {len(tsecs)}개"


FUNCS = {"copies": lint_copies, "project-rules": lint_project_rules, "team-residue": lint_team_residue,
         "head-declaration": lint_head_declaration, "module-size": lint_module_size, "broken-refs": lint_broken_refs,
         "count-mismatch": lint_count_mismatch, "catalog-required": lint_catalog_required, "audit-wiring": lint_audit_wiring,
         "stack-skill-channel": lint_stack_skill_channel, "symbol-tools-block": lint_symbol_tools_block}


def run(root, only=None):
    if only and only not in FUNCS:      # 오타도 미실행이다 — 0/0 PASS 로 끝나지 않게
        return {only: ("UNRUN", [], f"모르는 lint 이름 — {' · '.join(LINTS)} 중 하나")}
    results = {}
    for name in LINTS:
        if only and name != only:
            continue
        v, note = FUNCS[name](root)
        state = "UNRUN" if v is None else ("FAIL" if v else ("WARN" if "경고" in note else "PASS"))
        results[name] = (state, v or [], note)
    return results


def _mk(d, files):
    for rel, text in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)


def self_test():
    cases, fails = [], []

    def case(name, ok, why=""):
        cases.append(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" {why}"))
        if not ok:
            fails.append(name)

    blk = lambda n, b: f"x\n<!-- shared:{n} begin -->\n{b}<!-- shared:{n} end -->\n"
    mod = "modules" + "/"          # 합성 경로 — 조립해 둬야 계약 lint #6 이 실제 참조로 읽지 않는다
    ref_m = "`" + mod + "m.md` 참조"
    wf_call = "3. **Workflow 호출**: `Workflow(" + "{ scriptPath: '{WORK_DIR}/w.js', args })`\n"   # 조립 — 저장소의 호출 지시 집계에 섞이지 않게
    audit = "4. **심볼 도구 점검**: `python3 \"${FZ_PLUGIN_ROOT}/scripts/fz_wf_metrics.py\" --mcp-audit --wf {runId 폴더명}`\n"
    direct = "5. 직접 호출: `fz_wf_metrics.py --mcp-audit --direct --only-agent fz:review-correctness`\n"
    sym = (SYMBOL_HEAD + " — use them whenever they are in your tool list\n\n"
           "If a symbol tool is in your tool list, call it before Grep.\n- `find_symbol` — where a named function is defined.\n\n")
    sym_agent = lambda tools, body: f"---\nname: a\ntools: Read, Grep, {tools}\n---\n\n## Role\n\nr\n\n{body}## Return\n\nx\n"
    clean = {
        "templates/project-rules-block.md": "rules\n", "templates/review-shared-block.md": "core\n",
        "gpt-skills/a/SKILL.md": blk("project-rules", "rules\n"), "agents/x.md": blk("pair", "p\n"), "agents/y.md": blk("pair", "p\n"),
        "skills/s/SKILL.md": blk("review-core", "core\n") + "**2개 렌즈**\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n",
        mod + "m.md": "# m\n일반 모듈\nFinal Report 형식\n", mod + "u.md": "2. **Final Report 생성**: " + ref_m + "\n> 상세 원칙: " + ref_m + "\nTeamCreate 는 일몰됐다\n",
        "skills/w/SKILL.md": wf_call + audit + direct,
        "skills/fz-fix/SKILL.md": f"# f\n## 스택 스킬 (있으면 쓴다)\n{STACK_WORKER} 를 Step 맥락에 싣는다\n## 다음 절\n{STACK_LEAD}\n",   # 절 밖의 낱말은 세지 않는다
        "skills/fz-search/SKILL.md": f"## 스택 스킬 (있으면 쓴다)\n{STACK_LEAD} — 워커에게 넘기지 않는다\n",
        "agents/sym-a.md": sym_agent("mcp__plugin_fz_serena__find_symbol", sym),
        "agents/sym-b.md": sym_agent("mcp__plugin_fz_serena__get_symbols_overview", sym),
        AGENT_TEMPLATE: "# t\n\n```markdown\n## 도구 전략\n\n" + sym + "## 핵심 역할\n```\n",
    }
    for n, paths in CATALOG_BLOCKS.items():          # 카탈로그 원문 · 블록 배치 · light Read 지시(합성)
        clean[TEMPLATES[n]] = f"| {n} |\n"
        for rel in paths:
            base = blk("project-rules", "rules\n") if rel.startswith("gpt-skills/") else ""   # GPT 스킬은 project-rules lint 도 받는다
            clean[rel] = clean.get(rel, base) + blk(n, f"| {n} |\n")
    for rel, tpl in CATALOG_READS.items():
        clean[rel] = f"light: {tpl} 를 Read 한다\n"
    seeded = {
        "copies": {"agents/y.md": blk("pair", "DIFFERENT\n")},
        "project-rules": {"gpt-skills/b/SKILL.md": "no block\n"},
        "team-residue": {"modules/t.md": "TeamCreate 로 팀을 만든다\n"},
        "head-declaration": {"modules/p.md": "# p\n> Pilot — Transformation Spec 경로 전용\n",
                             **{f"skills/u{k}/SKILL.md": "see modules/p.md\n" for k in range(4)}},
        "module-size": {"skills/big/SKILL.md": "x\n" * 501},
        "broken-refs": {mod + "r.md": "2. **Missing Section 생성**: " + ref_m + "\n"},
        "count-mismatch": {"skills/c/SKILL.md": "**3개 렌즈**\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"},
        "catalog-required": {"gpt-skills/fz-reviewer/SKILL.md": "블록 없음\n"},
        "audit-wiring": {"guides/g.md": wf_call + direct},   # 직접 호출 줄만 있다 — 워크플로 점검 줄로 세지 않는다
        "stack-skill-channel": {"skills/fz-plan/SKILL.md": "## 스택 스킬\n부른 뒤 Lead 가 읽는다\n"},   # 둘 다 없음
        "symbol-tools-block": {"agents/sym-b.md": sym_agent("mcp__plugin_fz_serena__get_symbols_overview", sym.replace("before Grep", "after Grep"))},
    }
    # stack-skill-channel 의 나머지 꼴 — 절에 두 낱말이 다 있음 · 워커 통로가 있는 스킬인데 Lead 판단용(절 밖의 낱말은 세지 않는다 ·
    #   접근 탐색도 알려진 제약 인자로 워커에게 간다)
    stack_more = {"both": {"skills/fz-review/SKILL.md": f"## 스택 스킬\n{STACK_WORKER} · {STACK_LEAD}\n"},
                  "lead-on-worker-skill": {"skills/fz-fix/SKILL.md": f"## 스택 스킬\n{STACK_LEAD}\n## 다른 절\n{STACK_WORKER}\n"},
                  "lead-on-discover": {"skills/fz-discover/SKILL.md": f"## 스택 스킬\n{STACK_LEAD}\n"}}
    # symbol-tools-block 의 실패 꼴 — 절 없음 · 절 둘 · 에이전트끼리 다름 · 템플릿과 다름 · 도구 없는 에이전트에 절. 셀마다 그 파일 이름이 위반 줄에 있어야 한다
    symbol_more = {"missing": ("agents/sym-b.md", {"agents/sym-b.md": sym_agent("mcp__plugin_fz_serena__find_referencing_symbols", "")}),
                   "duplicate": ("agents/sym-a.md", {"agents/sym-a.md": sym_agent("mcp__plugin_fz_serena__find_symbol", sym + sym)}),
                   "differs": ("agents/sym-b.md", seeded["symbol-tools-block"]),
                   "template": (AGENT_TEMPLATE, {AGENT_TEMPLATE: "# t\n\n```markdown\n" + sym.replace("a named", "the") + "## 핵심 역할\n```\n"}),
                   "no-tool-has-section": ("agents/plain.md", {"agents/plain.md": sym_agent("mcp__context7__query-docs", sym)})}
    with tempfile.TemporaryDirectory() as d:
        _mk(d, clean)
        res = run(d)
        for name in LINTS:
            case(f"{name}-clean", res[name][0] in ("PASS", "WARN"), f"{res[name]}")
    for name in LINTS:
        with tempfile.TemporaryDirectory() as d:
            _mk(d, {**clean, **seeded[name]})
            st = run(d, only=name)[name][0]
            case(f"{name}-seeded", st == "FAIL", f"state {st}")
    for k, extra in stack_more.items():
        with tempfile.TemporaryDirectory() as d:
            _mk(d, {**clean, **extra})
            st = run(d, only="stack-skill-channel")["stack-skill-channel"][0]
            case(f"stack-skill-channel-{k}", st == "FAIL", f"state {st}")
    for k, (named, extra) in symbol_more.items():
        with tempfile.TemporaryDirectory() as d:
            _mk(d, {**clean, **extra})
            st, v, _ = run(d, only="symbol-tools-block")["symbol-tools-block"]
            case(f"symbol-tools-block-{k}", st == "FAIL" and any(x.startswith(named + ":") for x in v), f"state {st} · {v[:2]}")
    with tempfile.TemporaryDirectory() as d:
        res = run(d)
        case("not-run-is-not-pass", all(r[0] == "UNRUN" for r in res.values()) and summary(res)[1] == 2,
             f"{ {k: r[0] for k, r in res.items()} }")
    with tempfile.TemporaryDirectory() as d:
        _mk(d, {**clean, "modules/huge.md": "x\n" * 501})
        st = run(d, only="module-size")["module-size"][0]
        case("module-501-warn", st == "WARN", f"state {st}")
        res = run(d, only="no-such-lint")
        case("unknown-only-unrun", summary(res)[1] == 2, f"{ {k: r[0] for k, r in res.items()} } exit {summary(res)[1]}")
    print("\n".join(cases))
    print(f"lint_recurrence self-test: {'PASS' if not fails else 'FAIL'} ({len(cases) - len(fails)}/{len(cases)})")
    return 0 if not fails else 1


def summary(res):
    ok = sum(1 for r in res.values() if r[0] in ("PASS", "WARN"))
    code = 2 if any(r[0] == "UNRUN" for r in res.values()) else (1 if any(r[0] == "FAIL" for r in res.values()) else 0)
    return ok, code


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    root, only = ROOT, None
    while argv:
        if argv[0] == "--root" and len(argv) > 1:
            root, argv = os.path.abspath(argv[1]), argv[2:]
        elif argv[0] == "--only" and len(argv) > 1:
            only, argv = argv[1], argv[2:]
        else:
            print(__doc__.strip().split("\n\n")[-2], file=sys.stderr)
            return 2
    res = run(root, only)
    for name, (state, v, note) in res.items():
        print(f"{name}: {state} — {note}")
        for x in v[:20]:
            print(f"  - {x}")
        if len(v) > 20:
            print(f"  … {len(v) - 20} more")
    ok, code = summary(res)
    print(f"lint_recurrence: {ok}/{len(res)} PASS")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
