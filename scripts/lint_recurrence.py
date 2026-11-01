#!/usr/bin/env python3
"""재발 방지 lint 7종 (B6) — 고친 문서 결함이 다시 생기면 잡는다.

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

⛔ 미실행은 PASS 가 아니다 — 검사 대상이 0개면 그 lint 는 UNRUN 이고 전체도 PASS 가 아니다.

usage: lint_recurrence.py [--root R] [--only NAME]   ·   --self-test
출력: lint 마다 `<name>: PASS|WARN|FAIL|UNRUN …` · 끝에 `lint_recurrence: k/7 PASS`
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
LINTS = ("copies", "project-rules", "team-residue", "head-declaration", "module-size", "broken-refs", "count-mismatch")
TEMPLATES = {"review-core": "templates/review-shared-block.md", "project-rules": "templates/project-rules-block.md"}
SHARED = re.compile(r"<!-- shared:([\w-]+) begin -->\n(.*?)<!-- shared:\1 end -->", re.S)
OPERATIVE = ("agents/*.md", "skills/*/SKILL.md", "modules/*.md")
TEAM_RE = re.compile(r"TeamCreate|SendMessage|-team\.md")   # 일몰된 장치를 쓰라는 실행 지시 — "TEAM" 은 지금도 full 추천 모드의 이름이라 대상이 아니다
TEAM_OK = re.compile(r"일몰|없음|없다|부재|아니다|아님|않|미사용|불필요|독립|이력|롤백|rollback|금지|sunset|retired|대체")   # 부정 · 이력 문장은 지시가 아니다
REF_RE = re.compile(r"(?P<term>[A-Za-z가-힣][^:|`*\n]{2,40}?)\**\s*[:：]\s*`?(?P<file>(?:modules|guides)/[\w.-]+\.md)`?\s*참조")
PROPER = re.compile(r"[A-Z][A-Za-z0-9]+(?:\s+[A-Z0-9][\w.]*)*")   # 대상의 고유 이름(영문) — 한국어 이름표(상세 · 절차)는 낱말 대조 대상이 아니다
COUNT_RE = re.compile(r"\*\*(\d+)개 ([^*\n]{2,40})\*\*")


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


FUNCS = {"copies": lint_copies, "project-rules": lint_project_rules, "team-residue": lint_team_residue,
         "head-declaration": lint_head_declaration, "module-size": lint_module_size, "broken-refs": lint_broken_refs,
         "count-mismatch": lint_count_mismatch}


def run(root, only=None):
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
    clean = {
        "templates/project-rules-block.md": "rules\n", "templates/review-shared-block.md": "core\n",
        "gpt-skills/a/SKILL.md": blk("project-rules", "rules\n"), "agents/x.md": blk("pair", "p\n"), "agents/y.md": blk("pair", "p\n"),
        "skills/s/SKILL.md": blk("review-core", "core\n") + "**2개 렌즈**\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n",
        mod + "m.md": "# m\n일반 모듈\nFinal Report 형식\n", mod + "u.md": "2. **Final Report 생성**: " + ref_m + "\n> 상세 원칙: " + ref_m + "\nTeamCreate 는 일몰됐다\n",
    }
    seeded = {
        "copies": {"agents/y.md": blk("pair", "DIFFERENT\n")},
        "project-rules": {"gpt-skills/b/SKILL.md": "no block\n"},
        "team-residue": {"modules/t.md": "TeamCreate 로 팀을 만든다\n"},
        "head-declaration": {"modules/p.md": "# p\n> Pilot — Transformation Spec 경로 전용\n",
                             **{f"skills/u{k}/SKILL.md": "see modules/p.md\n" for k in range(4)}},
        "module-size": {"skills/big/SKILL.md": "x\n" * 501},
        "broken-refs": {mod + "r.md": "2. **Missing Section 생성**: " + ref_m + "\n"},
        "count-mismatch": {"skills/c/SKILL.md": "**3개 렌즈**\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"},
    }
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
    with tempfile.TemporaryDirectory() as d:
        res = run(d)
        case("not-run-is-not-pass", all(r[0] == "UNRUN" for r in res.values()) and summary(res)[1] == 2,
             f"{ {k: r[0] for k, r in res.items()} }")
    with tempfile.TemporaryDirectory() as d:
        _mk(d, {**clean, "modules/huge.md": "x\n" * 501})
        st = run(d, only="module-size")["module-size"][0]
        case("module-501-warn", st == "WARN", f"state {st}")
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
