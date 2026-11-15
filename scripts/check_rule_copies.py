#!/usr/bin/env python3
"""check_rule_copies.py — 같은 규칙을 여러 벌 둔 자리가 서로 같은지 대조한다.

왜: 규칙 사본 하나만 고치면 나머지는 옛 규칙으로 계속 돈다 — 아무 검사도 말하지 않았다.
  F-563 applied 정규식 세 벌 · fz-guard 쓰기 도구 집합과 hooks.json matcher 가 따로 적혀 있다
  F-557 리뷰 수정이 check_release_closes 만 네 자리 ID 를 받게 넓혀 배출기 · 위생 검사(세 자리)와 갈렸다
  F-476 pr-digest 가 정본 목차를 베끼며 절 하나를 빠뜨렸다 — 스킬 간 같은 긴 줄 사본이 여럿이다
  F-481 Serena 키 정책표 범주와 실제 write_memory 생산자가 갈렸다
  홈 경로 자리표시 이름 — 정본은 누수 규칙 모듈인데 커밋 훅이 셸 정규식 사본을 따로 든다. 한쪽만 고치면 커밋에서 통과한
        경로를 출하 게이트가 막거나, 커밋에서 막던 경로를 출하 게이트가 놓친다

검사 (위반마다 `VIOLATION <검사>: …`)
  applied-regex   scripts 의 `^applied:` · `^applied_ref:` 정규식 사본이 각각 한 글자열
  guard-matcher   guard.py 의 쓰기 · agent 도구 이름이 hooks.json PreToolUse matcher 에 걸린다 · 쓰기 도구는 PostToolUse 에도
  id-grammar      scripts · skills/*/scripts · mods/*/hooks 의 `F-\\d{` 정규식 리터럴이 같은 자릿수({3}) ·
                  ID 를 끝까지 읽는 자리(뒤가 \\Z · $ · \\b · - · \\s · \\*)는 접미 `[a-z]?` 까지 같은 문법
  skill-dup       skills/*/SKILL.md 에서 300B 이상 줄이 두 스킬 이상에 글자 그대로 있으면 허용 목록
                  (tests/fixtures/lint/skill-dup-allow.tsv · `sha12<TAB>스킬,…<TAB>사유`)에 있어야 하고,
                  허용 행의 사본은 나열된 스킬 모두에 그대로 있어야 한다(한 벌만 고치면 FAIL)
  serena-census   modules/memory-policy.md 키 표의 fz 범주 = write_memory("fz:<범주> 생산자 —
                  표 밖 생산 접두 · 생산자 0 인데 `생산자 없음` 표지가 없는 범주 · 생산자가 생겼는데 표지가 남은 범주
  home-allow-names
                  커밋 훅(.githooks/pre-commit)의 셸 정규식 사본 ⊆ 정본(scripts/leak_rules.py) — 자리표시 홈 · dev 이름
                  (PLACEHOLDER_RE ⊆ DOC_HOME_NAMES · DOC_DEV_NAMES)과 차단 루트(USER_PATH_RE 의 루트 ⊆ HOME_RE 의 루트 ·
                  dev 폴더 꼴은 DEV_RE 도 본다). 훅에 사본이 없고 훅이 정본을 부르면 위임이 끝난 것이라 위반 0 이다

사용: check_rule_copies.py [--root DIR] | --self-test
exit: 0 충족 · 1 위반 · 2 UNRUN(대상 파일 부재 · 파싱 실패 — ⛔ 통과 아님)
출력: self-test 는 케이스마다 `PASS <셀>`(FZ_SELFTEST_LIST=1)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

OK, VIOLATION, UNRUN = 0, 1, 2
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APPLIED_FILES = ("scripts/check_findings_hygiene.py", "scripts/eject_findings.py", "scripts/check_release_closes.py")
GUARD, HOOKS = "mods/fz-guard/hooks/guard.py", "mods/fz-guard/hooks/hooks.json"
ID_GLOBS = ("scripts/*.py", "skills/*/scripts/*.py", "mods/*/hooks/*.py")
DUP_ALLOW = "tests/fixtures/lint/skill-dup-allow.tsv"
DUP_MIN = 300
POLICY = "modules/memory-policy.md"
PRODUCER_DIRS = ("skills", "modules", "agents", "workflows", "scripts", "guides", "templates")
NO_PRODUCER = "생산자 없음"
PRE_COMMIT, LEAK_RULES = ".githooks/pre-commit", "scripts/leak_rules.py"


class Unrun(Exception):
    pass


def _read(root: Path, rel: str) -> str:
    p = root / rel
    if not p.is_file():
        raise Unrun(f"{rel} 이 없다")
    return p.read_text(encoding="utf-8")


def _consts(src: str, rel: str):
    try:
        tree = ast.parse(src, filename=rel)
    except SyntaxError as e:
        raise Unrun(f"{rel} 파싱 실패: {e}")
    return [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def check_applied(root: Path) -> list[str]:
    seen: dict[str, dict[str, list[str]]] = {"^applied:": {}, "^applied_ref:": {}}
    for rel in APPLIED_FILES:
        for c in _consts(_read(root, rel), rel):
            for key in seen:
                if c.value.startswith(key):
                    seen[key].setdefault(c.value, []).append(f"{rel}:{c.lineno}")
    out = []
    if not seen["^applied:"]:
        raise Unrun("^applied: 정규식 사본을 하나도 찾지 못했다")
    for key, vals in seen.items():
        if len(vals) > 1:
            out.append(f"applied-regex: `{key}` 사본이 {len(vals)}가지 — " +
                       " / ".join(f"{v!r} ({', '.join(locs)})" for v, locs in vals.items()))
    return out


def _expand(pattern: str) -> list[str]:
    """`^a(x|y)$` 꼴 정규식 하나를 구체 이름들로 — `.*` 는 `plugin_fz_` 로 채운다."""
    body = pattern.strip("^$").replace(".*", "plugin_fz_")
    m = re.search(r"\(([^()]*)\)", body)
    if not m:
        return [body]
    return [body[:m.start()] + alt + body[m.end():] for alt in m.group(1).split("|")]


def check_guard(root: Path) -> list[str]:
    src = _read(root, GUARD)
    try:
        tree = ast.parse(src, filename=GUARD)
    except SyntaxError as e:
        raise Unrun(f"{GUARD} 파싱 실패: {e}")
    vals: dict[str, object] = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            name, v = n.targets[0].id, n.value
            if isinstance(v, ast.Set):
                vals[name] = {e.value for e in v.elts if isinstance(e, ast.Constant)}
            elif isinstance(v, ast.Call) and v.args and isinstance(v.args[0], ast.Constant):
                vals[name] = v.args[0].value
    need = ("WRITE_EXACT", "SERENA_WRITE", "XCODE_WRITE", "AGENT_TOOLS")
    if any(k not in vals for k in need):
        raise Unrun(f"guard.py 에서 {[k for k in need if k not in vals]} 를 찾지 못했다")
    write = sorted(vals["WRITE_EXACT"]) + _expand(vals["SERENA_WRITE"]) + _expand(vals["XCODE_WRITE"])
    agent = sorted(vals["AGENT_TOOLS"])
    try:
        hooks = json.loads(_read(root, HOOKS))["hooks"]
        pre = [re.compile(h["matcher"]) for h in hooks.get("PreToolUse", []) if "matcher" in h]
        post = [re.compile(h["matcher"]) for h in hooks.get("PostToolUse", []) if "matcher" in h]
    except (ValueError, KeyError, TypeError, re.error) as e:
        raise Unrun(f"{HOOKS} 를 읽지 못했다: {type(e).__name__}: {e}")
    out = []
    for tool in write + agent:
        if not any(m.search(tool) for m in pre):
            out.append(f"guard-matcher: guard 가 다루는 `{tool}` 이 PreToolUse matcher 에 없다 — 훅이 그 도구에서 불리지 않는다")
    for tool in write:
        if not any(m.search(tool) for m in post):
            out.append(f"guard-matcher: 쓰기 도구 `{tool}` 이 PostToolUse matcher 에 없다")
    return out


ID_LIT = re.compile(r"F-\\d(\{[^}]*\}|\+|\*)")
ID_FULL_TAIL = re.compile(r"^(?:\\Z|\$|\\b|-|\\s|\\\*)")


def check_id_grammar(root: Path) -> list[str]:
    files = sorted({p for g in ID_GLOBS for p in root.glob(g) if p.is_file()})
    if not files:
        raise Unrun("ID 문법 대상 파일 0개")
    out = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        if rel == "scripts/check_rule_copies.py":
            continue      # 자기 참조 — 시험 문자열이 일부러 어긋난 문법을 담는다
        for c in _consts(p.read_text(encoding="utf-8"), rel):
            for m in ID_LIT.finditer(c.value):
                if m.group(1) != "{3}":
                    out.append(f"id-grammar: {rel}:{c.lineno} `{c.value[:60]}` — 자릿수 {m.group(1)} ≠ {{3}} (배출기 · 위생 검사와 문법이 갈린다)")
                    continue
                tail = c.value[m.end():]
                if not tail.startswith("[a-z]?") and ID_FULL_TAIL.match(tail):
                    out.append(f"id-grammar: {rel}:{c.lineno} `{c.value[:60]}` — ID 를 끝까지 읽는데 접미 `[a-z]?` 가 없다(F-123a 를 거부한다)")
    return out


def _sha12(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def check_skill_dup(root: Path) -> list[str]:
    skills = sorted(root.glob("skills/*/SKILL.md"))
    if not skills:
        raise Unrun("skills/*/SKILL.md 0개")
    seen: dict[str, dict[str, list[int]]] = {}
    for p in skills:
        for i, ln in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            s = ln.strip()
            if len(s.encode("utf-8")) >= DUP_MIN:
                seen.setdefault(_sha12(s), {}).setdefault(p.parent.name, []).append(i)
    allow: dict[str, tuple[set[str], str]] = {}
    ap = root / DUP_ALLOW
    if ap.is_file():
        for n, ln in enumerate(ap.read_text(encoding="utf-8").split("\n"), 1):
            if not ln.strip() or ln.startswith("#"):
                continue
            cols = ln.split("\t")
            if len(cols) < 3 or not re.fullmatch(r"[0-9a-f]{12}", cols[0]) or not cols[2].strip():
                raise Unrun(f"{DUP_ALLOW}:{n} 형식 오류 — `sha12<TAB>스킬,…<TAB>사유`")
            allow[cols[0]] = ({s.strip() for s in cols[1].split(",") if s.strip()}, cols[2].strip())
    out = []
    for h, where in sorted(seen.items()):
        if len(where) < 2:
            continue
        locs = ", ".join(f"{k}:{v[0]}" for k, v in sorted(where.items()))
        if h not in allow:
            out.append(f"skill-dup: 300B 이상 줄이 스킬 {len(where)}곳에 글자 그대로 — {locs} (sha {h}) · 정본 포인터로 바꾸거나 {DUP_ALLOW} 에 사유와 함께 적는다")
    for h, (want, _why) in sorted(allow.items()):
        have = set(seen.get(h, {}))
        if have != want:
            miss = sorted(want - have)
            out.append(f"skill-dup: 허용 사본 {h} 이 갈렸다 — 나열 {sorted(want)} · 지금 {sorted(have)}"
                       + (f" · 사라짐 {miss} (한 벌만 고쳤으면 나머지도 같이 · 사본을 걷었으면 행을 지운다)" if miss else ""))
    return out


POLICY_ROW = re.compile(r"^\|\s*`fz`\s*\|\s*`([a-z_-]+)`\s*\|", re.M)
WRITER = re.compile(r'write_memory\(\s*["\']fz:([a-z_-]+)')


def check_serena(root: Path) -> list[str]:
    policy = _read(root, POLICY)
    cats: dict[str, bool] = {}
    for m in POLICY_ROW.finditer(policy):
        row = policy[m.start():policy.find("\n", m.start())]
        cats[m.group(1)] = cats.get(m.group(1), False) or NO_PRODUCER in row
    if not cats:
        raise Unrun(f"{POLICY} 에서 `fz` 키 표 행을 찾지 못했다")
    producers: dict[str, list[str]] = {}
    for d in PRODUCER_DIRS:
        for p in sorted((root / d).rglob("*")) if (root / d).is_dir() else []:
            if not p.is_file() or p.suffix not in (".md", ".py", ".js", ".sh"):
                continue
            rel = p.relative_to(root).as_posix()
            if rel == "scripts/check_rule_copies.py":
                continue
            for m in WRITER.finditer(p.read_text(encoding="utf-8", errors="replace")):
                producers.setdefault(m.group(1), []).append(rel)
    out = []
    for cat, files in sorted(producers.items()):
        if cat not in cats:
            out.append(f"serena-census: `fz:{cat}` 를 쓰는데({files[0]}) {POLICY} 키 표에 범주가 없다 — 행 · 수명 · GC 를 적는다")
    for cat, marked in sorted(cats.items()):
        if cat not in producers and not marked:
            out.append(f"serena-census: 키 표 범주 `{cat}` 를 쓰는 곳이 0 — 생산 절차를 두거나 행에 `{NO_PRODUCER}` 를 적는다")
        if cat in producers and marked:
            out.append(f"serena-census: 범주 `{cat}` 에 생산자가 생겼는데({producers[cat][0]}) `{NO_PRODUCER}` 표지가 남았다")
    return out


# ── home-allow-names — 커밋 훅의 셸 정규식 사본 ⊆ 누수 규칙 정본 ──────────────────────
# 커밋 훅의 셸 정규식 사본 — `이름='값'` 한 줄
SH_RULE = re.compile(r"^(PLACEHOLDER_RE|USER_PATH_RE)='([^']*)'\s*$", re.M)
# 같은 이름에 값을 주는 줄 전부 — 따옴표 꼴 · 들여쓰기 · `export` · `readonly` · `local` · `declare` 를 가리지 않는다.
#   SH_RULE 이 못 읽는 꼴의 사본을 '사본 없음' 으로 넘기지 않으려고 따로 센다
SH_ASSIGN = re.compile(r"^[ \t]*(?:(?:export|readonly|local|declare|typeset)(?:[ \t]+-\w+)*[ \t]+)?(PLACEHOLDER_RE|USER_PATH_RE)=", re.M)
HOME_ROOTS = r"/(?:Users|home)/"
DEV_ROOT = "~/d" + "ev/"   # ⛔ 쪼개 적는다 — 이 파일도 커밋 훅 · 누수 규칙으로 훑인다


def _names(value: str, prefix: str) -> set:
    """셸 정규식 사본의 `<prefix>(a|b)/` · `<prefix>a/` 꼴 → 자리 이름 집합."""
    out: set = set()
    for m in re.finditer(prefix + r"(?:\(([^()]*)\)|([^/()|\s]+))/", value):
        out |= set(m.group(1).split("|")) if m.group(1) is not None else {m.group(2)}
    return out


def _leak_canon(root: Path) -> dict:
    """정본의 자리표시 이름 집합(DOC_HOME_NAMES · DOC_DEV_NAMES)과 홈 · dev 정규식 원문(HOME_RE · DEV_RE) — AST 로 읽는다(실행하지 않는다)."""
    try:
        tree = ast.parse(_read(root, LEAK_RULES), filename=LEAK_RULES)
    except SyntaxError as e:
        raise Unrun(f"{LEAK_RULES} 파싱 실패: {e}")
    vals: dict = {}
    for n in tree.body:
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)):
            continue
        v = n.value.args[0] if isinstance(n.value, ast.Call) and n.value.args else n.value
        if isinstance(v, ast.Set):
            vals[n.targets[0].id] = {x.value for x in v.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)}
        elif isinstance(v, ast.Constant) and isinstance(v.value, str):
            vals[n.targets[0].id] = v.value
    want = {"DOC_HOME_NAMES": set, "DOC_DEV_NAMES": set, "HOME_RE": str, "DEV_RE": str}
    miss = [k for k, t in want.items() if not isinstance(vals.get(k), t)]
    if miss:
        raise Unrun(f"{LEAK_RULES} 에서 {miss} 를 읽지 못했다")
    return vals


def check_home_names(root: Path) -> list[str]:
    src = _read(root, PRE_COMMIT)
    hook = dict(SH_RULE.findall(src))
    # 대입마다 센다 — 이름으로만 대조하면 읽히는 대입 하나가 같은 이름의 못 읽는 재대입을 가린다(셸이 쓰는 값은 마지막 대입이다)
    assigned, parsed = SH_ASSIGN.findall(src), [name for name, _ in SH_RULE.findall(src)]
    odd = sorted({name for name in assigned if assigned.count(name) > parsed.count(name)})
    if odd:
        raise Unrun(f"{PRE_COMMIT} 에 {' · '.join(odd)} 대입이 있는데 `이름='값'` 한 줄 꼴이 아니라 값을 읽지 못했다 — "
                    "큰따옴표 · export 꼴의 사본도 사본이다(정본 호출이 함께 있어도 통과가 아니다)")
    if not hook:
        if os.path.basename(LEAK_RULES) in src:
            return []   # 위임 끝 — 훅이 사본 없이 정본을 부른다. 사본이 다시 생기면 아래 대조로 돌아온다
        raise Unrun(f"{PRE_COMMIT} 에서 PLACEHOLDER_RE · USER_PATH_RE 사본도 정본({LEAK_RULES}) 호출도 찾지 못했다")
    canon = _leak_canon(root)
    out = []
    if "PLACEHOLDER_RE" in hook:
        home = _names(hook["PLACEHOLDER_RE"], HOME_ROOTS)
        dev = _names(hook["PLACEHOLDER_RE"], re.escape(DEV_ROOT))
        # 한쪽만 읽힌 경우도 미판정이다 — 루트가 값에 있는데 이름이 0이면 그쪽 대조가 조용히 빠진다
        lost = [part for part, there, got in (("홈", re.search(HOME_ROOTS, hook["PLACEHOLDER_RE"]), home),
                                              ("dev", DEV_ROOT in hook["PLACEHOLDER_RE"], dev)) if there and not got]
        if lost or (not home and not dev):
            raise Unrun(f"{PRE_COMMIT} PLACEHOLDER_RE 에서 자리표시 이름을 읽지 못했다({' · '.join(lost) or '루트 없음'})")
        out += [f"home-allow-names: 커밋 훅 PLACEHOLDER_RE 의 홈 자리표시 이름 `{x}` 가 정본 DOC_HOME_NAMES 에 없다 — "
                "커밋에서 통과한 경로를 출하 게이트가 막는다" for x in sorted(home - canon["DOC_HOME_NAMES"])]
        out += [f"home-allow-names: 커밋 훅 PLACEHOLDER_RE 의 dev 자리표시 이름 `{x}` 가 정본 DOC_DEV_NAMES 에 없다 — "
                "커밋에서 통과한 경로를 출하 게이트가 막는다" for x in sorted(dev - canon["DOC_DEV_NAMES"])]
    if "USER_PATH_RE" in hook:
        roots = set(re.findall(r"/(Users|home)/", hook["USER_PATH_RE"]))
        dev_blocked = DEV_ROOT in hook["USER_PATH_RE"]
        if not roots and not dev_blocked:
            raise Unrun(f"{PRE_COMMIT} USER_PATH_RE 에서 차단 루트를 읽지 못했다")
        m = re.match(r"/\(\?:([A-Za-z|]+)\)/", canon["HOME_RE"])
        if not m:
            raise Unrun(f"{LEAK_RULES} HOME_RE 의 루트 묶음(`/(?:A|B)/`)을 읽지 못했다")
        out += [f"home-allow-names: 커밋 훅 USER_PATH_RE 가 막는 루트 `{x}` 를 정본 HOME_RE 가 보지 않는다 — "
                "커밋에서 막던 경로를 출하 게이트가 놓친다" for x in sorted(roots - set(m.group(1).split("|")))]
        # 정본 식이 dev 폴더 꼴을 보는지는 식을 돌려 본다 — 접두 묶음으로 시작하는 식은 글자 대조로 읽히지 않는다
        try:
            dev_seen = re.search(canon["DEV_RE"], DEV_ROOT + "name/") is not None
        except re.error as e:
            raise Unrun(f"{LEAK_RULES} DEV_RE 를 정규식으로 읽지 못했다: {e}")
        if dev_blocked and not dev_seen:
            out.append("home-allow-names: 커밋 훅 USER_PATH_RE 가 막는 dev 폴더 꼴을 정본 DEV_RE 가 보지 않는다 — "
                       "커밋에서 막던 경로를 출하 게이트가 놓친다")
    return out


CHECKS = (("applied-regex", check_applied), ("guard-matcher", check_guard), ("id-grammar", check_id_grammar),
          ("skill-dup", check_skill_dup), ("serena-census", check_serena), ("home-allow-names", check_home_names))


def run(root: Path) -> int:
    hits, unrun = [], []
    for name, fn in CHECKS:
        try:
            hits += fn(root)
        except (Unrun, OSError, UnicodeDecodeError) as e:
            unrun.append(f"{name}: {e}")
    for h in hits:
        print(f"VIOLATION {h}")
    for u in unrun:
        print(f"UNRUN: {u} (⛔ 통과 아님)")
    print(f"rule-copies: checks={len(CHECKS)} violations={len(hits)} unrun={len(unrun)}")
    return UNRUN if unrun else (VIOLATION if hits else OK)


def self_test() -> int:
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    def case(name, files: dict, fn, want: bool, unrun: bool = False):
        """unrun=True 면 미판정(Unrun)이 기대값이다 — 위반 여부를 돌려주면 실패다."""
        nonlocal passed
        with tempfile.TemporaryDirectory(prefix="fz-rule-copies-") as d:
            for rel, body in files.items():
                q = Path(d) / rel
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_text(body, encoding="utf-8")
            try:
                got = bool(fn(Path(d)))
            except Unrun as e:
                if unrun:
                    passed += 1
                    if listing:
                        print(f"PASS {name}")
                else:
                    fails.append(f"{name}: UNRUN {e}")
                return
        if unrun:
            fails.append(f"{name}: 미판정(UNRUN)이 기대인데 위반 {got} 을 돌려줬다")
        elif got == want:
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(f"{name}: 위반 {got} (기대 {want})")

    ap_ok = {f: f'A = re.compile(r"^applied:[ \\t]*([^\\s#]*)", re.M)\n' for f in APPLIED_FILES}
    ap_bad = dict(ap_ok, **{APPLIED_FILES[2]: 'A = re.compile(r"^applied:\\s*(\\S*)", re.M)\n'})
    case("f563-applied-regex-copies", ap_bad, check_applied, True)
    case("f563-applied-regex-same-ok", ap_ok, check_applied, False)

    g = ('WRITE_EXACT = {"Write", "Edit"}\nSERENA_WRITE = re.compile(r"^mcp__.*serena__(replace_content|rename_symbol)$")\n'
         'XCODE_WRITE = re.compile(r"^mcp__xcode__Xcode(Write)$")\nAGENT_TOOLS = {"Agent"}\n')
    hk = lambda pre, post: json.dumps({"hooks": {"PreToolUse": [{"matcher": pre}], "PostToolUse": [{"matcher": post}]}})
    full = r"^(Write|Edit|Agent|mcp__.*serena__(replace_content|rename_symbol)|mcp__xcode__Xcode(Write))$"
    post = r"^(Write|Edit|mcp__.*serena__(replace_content|rename_symbol)|mcp__xcode__Xcode(Write))$"
    case("f563-guard-matcher-copies", {GUARD: g, HOOKS: hk(full.replace("|rename_symbol", ""), post)}, check_guard, True)
    case("f563-guard-matcher-post-missing", {GUARD: g, HOOKS: hk(full, post.replace("Edit|", ""))}, check_guard, True)
    case("f563-guard-matcher-ok", {GUARD: g, HOOKS: hk(full, post)}, check_guard, False)

    case("f557-id-grammar-copies", {"scripts/a.py": 'ID = re.compile(r"^F-\\d{3}[a-z]?$")\n',
                                    "scripts/b.py": 'ID = re.compile(r"^F-\\d{3,4}[a-z]?$")\n'}, check_id_grammar, True)
    case("f557-id-suffix-missing", {"scripts/a.py": 'ID = re.compile(r"F-\\d{3}\\Z")\n'}, check_id_grammar, True)
    case("f557-id-prefix-use-ok", {"scripts/a.py": 'P = re.compile(r"^F-\\d{3}")\nQ = re.compile(r"fz-|F-\\d{3}|x")\n'
                                                   'ID = re.compile(r"^(F-\\d{3}[a-z]?)-[a-z0-9-]+$")\n'}, check_id_grammar, False)

    long_line = "가" * 120
    sk = lambda a, b: {"skills/x/SKILL.md": f"# x\n{a}\n", "skills/y/SKILL.md": f"# y\n{b}\n"}
    case("f476-cross-skill-dup-block", sk(long_line, long_line), check_skill_dup, True)
    allow_row = f"{_sha12(long_line)}\tx,y\t두 스킬이 각각 싣는다\n"
    case("f476-dup-allowlisted-ok", dict(sk(long_line, long_line), **{DUP_ALLOW: allow_row}), check_skill_dup, False)
    case("f476-allowlisted-copy-diverged", dict(sk(long_line, long_line + "!"), **{DUP_ALLOW: allow_row}), check_skill_dup, True)

    pol = ("| 네임스페이스 | 카테고리 | 예시 | 용도 |\n|---|---|---|---|\n"
           "| `fz` | `checkpoint` | `fz:checkpoint:x` | 임시 |\n| `fz` | `decision` | `fz:decision:x` | 영속 · ⛔ 생산자 없음 |\n")
    w = 'write_memory("fz:checkpoint:x", "y")\n'
    case("f481-serena-key-census", {POLICY: pol, "modules/a.md": w + 'write_memory("fz:rtm:R-1", "z")\n'}, check_serena, True)
    case("f481-unmarked-empty-category", {POLICY: pol.replace(" · ⛔ 생산자 없음", ""), "modules/a.md": w}, check_serena, True)
    case("f481-stale-no-producer-mark", {POLICY: pol, "modules/a.md": w + 'write_memory("fz:decision:t", "z")\n'}, check_serena, True)
    case("f481-census-ok", {POLICY: pol, "modules/a.md": w}, check_serena, False)

    hp = "/Us" + "ers/"
    hook_sh = lambda names, dev, top="Users": (f"PLACEHOLDER_RE='{hp}({names})/|{DEV_ROOT}{dev}/'\n"
                                               f"USER_PATH_RE='/{top}/[a-zA-Z0-9_-]+/|{DEV_ROOT}[a-zA-Z0-9_-]+/'\n")
    canon_py = lambda tops="Users|home": ('DOC_HOME_NAMES = frozenset({"example", "u", "me"})\nDOC_DEV_NAMES = frozenset({"gone"})\n'
                                          f'HOME_RE = re.compile(r"/(?:{tops})/([^/]+)(?=/)")\n'
                                          f'DEV_RE = re.compile(r"{DEV_ROOT}([^/]+)(?=/)")\n')
    case("home-names-hook-subset-ok", {PRE_COMMIT: hook_sh("example|u", "gone"), LEAK_RULES: canon_py()}, check_home_names, False)
    case("home-names-hook-only-name", {PRE_COMMIT: hook_sh("example|zz", "gone"), LEAK_RULES: canon_py()}, check_home_names, True)
    case("home-names-dev-name-drift", {PRE_COMMIT: hook_sh("example", "gone2"), LEAK_RULES: canon_py()}, check_home_names, True)
    case("home-names-root-not-in-canon", {PRE_COMMIT: hook_sh("example", "gone", "home"), LEAK_RULES: canon_py("Users")},
         check_home_names, True)
    # 정본 dev 정규식이 접두 묶음으로 시작해도 dev 폴더 꼴을 보는 것이다(식을 돌려 본다) · 그 꼴을 보지 않는 식은 위반이다
    grouped = ('DOC_HOME_NAMES = frozenset({"example", "u", "me"})\nDOC_DEV_NAMES = frozenset({"gone"})\n'
               'HOME_RE = re.compile(r"/(?:Users|home)/([^/]+)")\nDEV_RE = re.compile(r"(?:~|\\$HOME)/d' 'ev/([^/]+)")\n')
    case("home-names-dev-prefix-group-ok", {PRE_COMMIT: hook_sh("example", "gone"), LEAK_RULES: grouped}, check_home_names, False)
    case("home-names-dev-not-in-canon", {PRE_COMMIT: hook_sh("example", "gone"), LEAK_RULES: grouped.replace("(?:~|\\$HOME)/d" "ev/", "/opt/")},
         check_home_names, True)
    case("home-names-delegated-ok", {PRE_COMMIT: 'python3 "$ROOT/scripts/leak_rules.py" --staged\n'}, check_home_names, False)
    # 읽지 못하는 꼴의 사본 — 정본 이름이 훅에 있어도(주석 포함) '위임 끝' 으로 넘기지 않는다
    delegated = 'python3 "$ROOT/scripts/leak_rules.py" --staged\n'
    case("home-names-double-quoted-copy-unrun", {PRE_COMMIT: delegated + f'PLACEHOLDER_RE="{hp}(example|zz)/"\n', LEAK_RULES: canon_py()},
         check_home_names, False, unrun=True)
    case("home-names-export-copy-unrun", {PRE_COMMIT: delegated + f"  export USER_PATH_RE='/home/[a-z]+/'\n", LEAK_RULES: canon_py()},
         check_home_names, False, unrun=True)
    # 읽히는 대입 뒤에 같은 이름을 못 읽는 꼴로 다시 대입한다 — 앞의 값만 대조하고 통과시키지 않는다
    case("home-names-reassigned-double-quoted-unrun",
         {PRE_COMMIT: hook_sh("example", "gone") + f'PLACEHOLDER_RE="{hp}(zz)/"\n', LEAK_RULES: canon_py()}, check_home_names, False, unrun=True)
    # 홈 쪽은 읽히고 dev 쪽은 못 읽는다(겹친 괄호) — 한쪽만 대조하고 통과시키지 않는다
    case("home-names-dev-part-unparsed-unrun",
         {PRE_COMMIT: f"PLACEHOLDER_RE='{hp}(example)/|{DEV_ROOT}(gone|(x))/'\n", LEAK_RULES: canon_py()}, check_home_names, False, unrun=True)

    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=Path(SCRIPT_DIR).parent)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else run(a.root)


if __name__ == "__main__":
    sys.exit(main())
