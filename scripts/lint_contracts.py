#!/usr/bin/env python3
"""fz 플러그인 계약 lint — `fz-manage check` 의 결정론 판정기.

⛔ 본 스크립트가 **검사 항목의 SSOT**다. SKILL.md는 항목 표를 재정의하지 않고 `--list`에 위임한다.
   이유: 항목을 두 곳에 쓰면 드리프트한다 (플러그인 자체 감사에서 F-5·F-19로 실측된 실패 모드).

판정자 3분류 (guides/skill-authoring.md §11 "결과가 binary(pass/fail)인가? → 스크립트"):
  DETERMINISTIC — 스크립트가 판정
  THRESHOLD     — 임계/문법 미정 → SKIP (정하면 DETERMINISTIC 승격)
  SEMANTIC      — 의미 판단 → SKIP (사람/모델 소관)

exit code (⛔ 3분 — modules/cross-validation.md §Negative-Result Gate 요소2):
  0 = 위반 없음
  1 = 위반 있음
  2 = configuration/parse error  ⛔ PASS도 SKIP도 아니다

Python 표준 라이브러리 전용. 루트는 자기 위치에서 해석한다(CWD 비의존).
"""
from __future__ import annotations
import argparse
import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # scripts/ → 플러그인 루트

# ─────────────────────────────────────────────────────────────────────────────
# 항목 레지스트리 (SSOT)
# ─────────────────────────────────────────────────────────────────────────────
ITEMS = [
    # id,   판정자,          대상,        설명
    ("1",  "DETERMINISTIC", "fz-*",      "YAML 필수 필드 (L1 공식 4 + L2 fz 정책 2) — 정본 modules/governance.md §스킬 최소 기준"),
    ("2",  "SEMANTIC",      "fz-*",      "MCP 유효성 — allowed-tools의 MCP 도구 실존 (서버 상태 의존)"),
    ("3",  "DETERMINISTIC", "fz-*",      "provides/needs 충족 + DAG 사이클 부재"),
    ("4",  "THRESHOLD",     "fz-*",      "intent-triggers '과도한 겹침' — ⛔ 임계 미정"),
    ("5",  "DETERMINISTIC", "fz-*",      "SKILL.md ≤500줄"),
    ("6",  "DETERMINISTIC", "all",       "깨진 파일 참조"),
    ("7",  "DETERMINISTIC", "agents",    "에이전트 파일 필드 (name/description/model/tools)"),
    ("8",  "SEMANTIC",      "agents",    "Team 불가 MCP 참조 — 판정에 런타임 지식 필요"),
    ("9",  "SEMANTIC",      "fz-*",      "테스트 케이스 충분성 — 존재는 세지만 충분성은 의미 판단"),
    ("10", "SEMANTIC",      "fz-*",      "Triggering 테스트 3개+ — 품질은 의미 판단"),
    ("11", "SEMANTIC",      "infra",     "skill-creator 설치 — 외부 환경"),
    ("12", "THRESHOLD",     "agents",    "frontmatter tools ↔ 본문 Primary 정합 — ⛔ 도구명 free-form grammar 미정"),
    # ⛔ 2026-08-09 DETERMINISTIC→SEMANTIC 강등: `agents/*.md`의 `CLAUDE.md ## Architecture` 는
    #    **소비 프로젝트의** CLAUDE.md를 뜻한다(에이전트는 대상 프로젝트 지침을 읽는다).
    #    플러그인 자신의 CLAUDE.md로 해석하면 89건 전부 오탐 — 정적으로 구별 불가.
    ("13", "SEMANTIC",      "all",       "CLAUDE.md 섹션 참조 유효성 — ⛔ 참조 대상이 소비 프로젝트인지 플러그인 자신인지 정적 구별 불가"),
    ("14", "DETERMINISTIC", "modules",   "100줄+ 모듈의 목차 존재"),
    ("16", "DETERMINISTIC", "agents",    "team-registry ↔ agents/ 양방향 일치"),
    ("17", "THRESHOLD",     "fz-*",      "Gate Evidence 패턴 — ⛔ 정규식 미정"),
    ("N1", "DETERMINISTIC", "schemas",   "codex_base_issue $defs 값이 소비 스키마와 일치 — severity enum + confidence 경계 (⛔ 값은 **인라인**한다: fz 스키마는 `$ref` 를 쓰지 않는다(실측 0건) — 본 검사가 인라인 정합을 본다)"),
    ("N2", "DETERMINISTIC", "infra",     "CLAUDE.md 인벤토리 선언 ↔ 실측 카운트"),
    ("N3", "DETERMINISTIC", "all",       "줄번호 인용 — 대상 파일 실재 + 행 범위 내 (⛔ 인용 *내용*의 정합은 검사하지 않는다)"),
    ("N4", "DETERMINISTIC", "all",       "ERE alternation 오용 — `grep -E` 같은 줄의 `\\|`"),
    ("N5", "DETERMINISTIC", "scripts",   "측정 명령의 신호 폐기 (`>/dev/null 2>&1` + exit 미사용)"),
    ("N6", "DETERMINISTIC", "scripts",   "루트 앵커 — **줄 단위 화이트리스트**(fail-closed). ⛔ 일반 분석 아님: 미지 형태는 거부하고 `ANCHOR_LINES` 에 명시 추가한다. `.sh` 는 첫 `<<` 이후를 데이터로 취급"),
    ("N7", "DETERMINISTIC", "all",       "셸 변수 정의-사용 불일치 — `[ ]`/`[[ ]]` × 인용/비인용 `-n`/`-z` 한정 (⛔ 범위 외: heredoc 내부·멀티라인 테스트·`${VAR:-기본값}`은 의도적 제외)"),
    ("N8", "DETERMINISTIC", "all",       "목차 앵커 해소 — GitHub slug + occupied 충돌 루프 + GFM fence 제외 (⛔ 범위 외: heading 내 inline markup·HTML)"),
]
DET = {i for i, k, _, _ in ITEMS if k == "DETERMINISTIC"}

# ─────────────────────────────────────────────────────────────────────────────
# MIN_HITS — 각 검사가 최소 몇 개의 후보를 봐야 하는가 (순회 회귀 탐지)
#
# 왜 필요한가 (2026-08-09 외부 감사 ISSUE-001·002): `hits`는 *본 후보 수*라 패턴이나
#   순회가 고장나도 0이 아니어서 `OK [검사 대상 N]`이 찍혔다. 실제로 #N2는 INV에 5개를
#   등재하고도 **3개만** 검사하며 통과했다 — 선언 형식 불일치를 조용히 skip했기 때문이다.
#   fixture는 *판정 로직*을 지키고, MIN_HITS는 *순회·수집*을 지킨다 (두 층).
#
# ⛔ 하한은 **보수적**으로 둔다 — 파일을 정당하게 삭제해도 즉시 깨지지 않도록.
#    미달 시 exit 2 메시지가 "트리 변화인가 도구 고장인가"를 묻는다.
# ⛔ 새 DETERMINISTIC 항목은 MIN_HITS를 **함께** 선언해야 한다 (구조 불변식이 강제).
# ─────────────────────────────────────────────────────────────────────────────
MIN_HITS = {
    "1": 15,     # 스킬 21개 — 보수적
    "3": 15,     # 동일
    "5": 15,     # 동일
    "6": 300,    # 참조 564건 — 절반 수준
    "7": 10,     # 에이전트 13개
    "14": 20,    # 목차 보유 모듈 30개
    "16": 10,    # 에이전트 13개
    # ⛔ #N1·#N2는 **여유 0**이 의도된 설계다. 하한은 *최소*이므로 항목 추가는 발화하지 않고
    #    **삭제만** 발화한다 — 소비 스키마나 INV 카테고리가 줄면 그때는 검토가 옳다.
    #    ⚠️ 미래 편집자: 여유가 0이라고 낮추지 말 것. 낮추면 "조용히 검사에서 빠짐"이 다시 가능해진다.
    "N1": 4,     # 소비 스키마 4개 — 삭제 시 발화(의도)
    "N2": 5,     # INV 카테고리 5개 전부 검사돼야 한다 (S6에서 3→5, 선언 형식 통일과 원자적)
    "N3": 10,    # 줄번호 인용 32건
    "N4": 15,    # grep -E 줄 29건
    # ⛔ N5·N6 는 하한만으로 "한 언어 계열 소실"을 못 잡는다(py 전멸 시 sh 6개가 남아 통과) —
    #    그 방어는 **통합 fixture 의 계열별 픽스처**(bad_n6.py + bad_n6.sh)가 담당한다 (ISSUE-007)
    "N5": 5,     # 스크립트 10개
    "N6": 5,     # 스크립트 10개
    "N7": 5,     # 셸 테스트 15건
    "N8": 100,   # 목차 앵커 237건
}


SKIP_DIRS = {".git", "worktrees", "node_modules", ".fz-work", "__pycache__"}
SKIP_REL_PARTS = ("docs/releases/",)


# ─────────────────────────────────────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────────────────────────────────────
def walk_files(*exts: str, root: Path | None = None):
    """⛔ `root` 는 **통합 fixture 전용** 주입점 (S8) — 기본값은 전역 ROOT로 동작 호환을 유지한다.

    신설 근거(외부 감사 ISSUE-PLAN-003): 술어 fixture + MIN_HITS 만으로는 end-to-end가 아니다.
      잘못된 파일 순회 · 잘못된 디렉토리 제외 · 잘못된 블록 문맥 · 결과 반전이 전부 통과한다.
      ⇒ 임시 트리를 주입해 `chk_*` 를 **통째로** 호출하고 위반 위치·건수를 단정한다.
    """
    base = root or ROOT
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            p = Path(dp) / fn
            rel = p.relative_to(base).as_posix()
            if any(s in rel for s in SKIP_REL_PARTS):
                continue
            if exts and not fn.endswith(exts):
                continue
            yield rel, p


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def frontmatter(p: Path):
    """(dict, 본문줄수). frontmatter 미존재/미종료는 None 반환 → 호출자가 parse error 처리."""
    lines = read(p).split("\n")
    if not lines or lines[0].strip() != "---":
        return None, len(lines)
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, len(lines)
    d, key = {}, None
    for l in lines[1:end]:
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", l)
        if m:
            key = m.group(1)
            d[key] = m.group(2).strip()
        elif key and l.strip():
            d[key] += " " + l.strip()
    n = len(lines) - (1 if lines and lines[-1] == "" else 0)
    return d, n


def find_named_defs(node, name: str, path: str = "") -> list[tuple[str, dict]]:
    """`name` 키의 정의 노드를 모두 수집한다 (범용 — severity·confidence 등)."""
    out: list[tuple[str, dict]] = []
    if isinstance(node, dict):
        for k, val in node.items():
            if k == name and isinstance(val, dict):
                out.append((f"{path}/{name}", val))
            out += find_named_defs(val, name, f"{path}/{k}")
    elif isinstance(node, list):
        for idx, x in enumerate(node):
            out += find_named_defs(x, name, f"{path}[{idx}]")
    return out


def find_severity_defs(node, path: str = "") -> list[tuple[str, dict]]:
    """JSON 트리를 순회해 `severity` 정의 노드를 모두 수집한다 (enum · `$ref` 양쪽).

    ⛔ 정규식으로 `critical` 포함 enum을 찾던 1차 방식은 *critical 삭제*를 탐지하지 못했다 (ISSUE-004).
    ⛔ 2차(inline enum만 인정)는 **`$ref` 로 base를 재사용하는 정당한 형태를 위반으로 만들었다** —
       그게 SSOT를 지키는 방식인데도 (ISSUE-005 / ISSUE-PLAN-005). 이제 `$ref` 를 resolve한다.
    """
    out: list[tuple[str, dict]] = []
    if isinstance(node, dict):
        for k, val in node.items():
            if k == "severity" and isinstance(val, dict):
                out.append((f"{path}/severity", val))
            out += find_severity_defs(val, f"{path}/{k}")
    elif isinstance(node, list):
        for idx, x in enumerate(node):
            out += find_severity_defs(x, f"{path}[{idx}]")
    return out


def resolve_ref(ref: str, base_doc: dict, base_name: str):
    """`file#/a/b` 또는 `#/a/b` 를 따라간다. 반환: (enum 또는 None, 오류 메시지 또는 None).

    ⛔ 로드/경로 실패는 **조용히 통과시키지 않는다** — 호출자가 ParseError로 승격한다.
    """
    file_part, _, frag = ref.partition("#")
    if file_part and Path(file_part).name != base_name:
        return None, f"알 수 없는 `$ref` 대상 파일: {file_part} (base는 {base_name})"
    cur = base_doc
    for seg in [s for s in frag.split("/") if s]:
        if not isinstance(cur, dict) or seg not in cur:
            return None, f"`$ref` 경로 미해소: {ref}"
        cur = cur[seg]
    if not isinstance(cur, dict) or not isinstance(cur.get("enum"), list):
        return None, f"`$ref` 대상에 enum 부재: {ref}"
    return cur["enum"], None


SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))
AGENTS = sorted((ROOT / "agents").glob("*.md"))
MODULES = sorted((ROOT / "modules").rglob("*.md"))
SCRIPTS = sorted(p for p in (ROOT / "scripts").glob("*") if p.is_file())


# ─────────────────────────────────────────────────────────────────────────────
# 검사 구현 — 각 함수는 (violations, positive_control_hits) 반환
#   positive_control_hits: 검사기가 실제로 무언가를 봤다는 증거 (0이면 도구 고장 의심)
# ─────────────────────────────────────────────────────────────────────────────
REQ_L1 = ("name", "description", "user-invocable", "allowed-tools")
REQ_L2 = ("provides", "needs")


def chk_1():
    v, seen = [], 0
    for p in SKILLS:
        name = p.parent.name
        fm, _ = frontmatter(p)
        if fm is None:
            raise ParseError(f"skills/{name}/SKILL.md: frontmatter 파싱 실패")
        seen += 1
        miss = [f for f in REQ_L1 + REQ_L2 if f not in fm]
        if miss:
            v.append(f"skills/{name}/SKILL.md: 필수 필드 누락 {miss}")
    return v, seen


def chk_3():
    prov, need, seen = {}, {}, 0
    for p in SKILLS:
        name = p.parent.name
        fm, _ = frontmatter(p)
        if fm is None:
            raise ParseError(f"skills/{name}: frontmatter 파싱 실패")
        seen += 1
        prov[name] = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", fm.get("provides", ""))
        need[name] = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", fm.get("needs", "")) if t != "none"]
    producer = defaultdict(set)
    for s, ts in prov.items():
        for t in ts:
            producer[t].add(s)
    v = [f"{s}: needs '{t}' — provides 하는 스킬 없음" for s, ts in need.items() for t in ts if t not in producer]
    # DAG 사이클
    edges = defaultdict(set)
    for s, ts in need.items():
        for t in ts:
            edges[s] |= producer.get(t, set())
    color = {}

    def dfs(u, stack):
        color[u] = 1
        for w in edges.get(u, ()):
            if w == u:
                v.append(f"자기 순환: {u}")
            elif color.get(w) == 1:
                v.append("사이클: " + " -> ".join(stack + [w]))
            elif color.get(w, 0) == 0:
                dfs(w, stack + [w])
        color[u] = 2

    for s in prov:
        if color.get(s, 0) == 0:
            dfs(s, [s])
    return v, seen


def chk_5():
    v, seen = [], 0
    for p in SKILLS:
        _, n = frontmatter(p)
        seen += 1
        if n > 500:
            v.append(f"skills/{p.parent.name}/SKILL.md: {n}줄 > 500")
    return v, seen


PATHREF = re.compile(
    r"`((?:guides|modules|skills|workflows|agents|scripts|schemas|examples|templates|codex-skills)"
    r"/[A-Za-z0-9_./\-]+\.(?:md|js|py|sh|json))`"
)
# 의도된 플레이스홀더·예시 (본 감사에서 FP로 판정된 것 — 근거는 plan/plan-final.md S9)
REF_ALLOW = {
    "modules/X.md", "templates/X.md",
    "modules/shared-utils.md",            # forward-looking 후보 (governance 게이트)
    "modules/scope-drift-monitor.md",     # 기각된 제안 기록 (docs/design — "옵션 B 채택, §4.4에 흡수")
    "scripts/check_patterns.sh",          # skill-authoring §11 표의 예시
    "scripts/parse_build_log.sh",         # 동
}


def chk_6():
    existing = {rel for rel, _ in walk_files()}
    v, seen = [], 0
    for rel, p in walk_files(".md", ".js", ".py"):
        if rel == "CHANGELOG.md":
            continue
        for i, line in enumerate(read(p).split("\n"), 1):
            for m in PATHREF.finditer(line):
                seen += 1
                t = m.group(1)
                if t not in existing and t not in REF_ALLOW:
                    v.append(f"{rel}:{i}: 깨진 참조 `{t}`")
    return v, seen


def chk_7():
    v, seen = [], 0
    for p in AGENTS:
        fm, _ = frontmatter(p)
        if fm is None:
            raise ParseError(f"agents/{p.name}: frontmatter 파싱 실패")
        seen += 1
        miss = [f for f in ("name", "description", "model", "tools") if f not in fm]
        if miss:
            v.append(f"agents/{p.name}: 필드 누락 {miss}")
    return v, seen


SECREF = re.compile(r"CLAUDE\.md\s*`##\s*([^`]+)`")


# ⛔ `chk_13` 제거 (2026-08-10, 3라운드 감사 ISSUE-008): 항목 13은 SEMANTIC(스크립트 판정 대상 아님)인데
#    `CHECKS` 에 등록돼 있어 **도달 불가 구현 15줄**이 남아 있었다. 새 레지스트리 불변식이 이를 검출했다.
#    판정 근거는 항목 설명에 있다 — 참조 대상이 소비 프로젝트인지 플러그인 자신인지 정적 구별 불가.


TOC = re.compile(r"^#+\s*(목차|Index|Contents|TOC)\b", re.M)


def chk_14():
    v, seen = [], 0
    for p in MODULES:
        txt = read(p)
        n = txt.count("\n") + 1
        if n < 100:
            continue
        seen += 1
        if not TOC.search(txt):
            v.append(f"{p.relative_to(ROOT).as_posix()}: {n}줄인데 목차 없음")
    return v, seen






def chk_16():
    reg = ROOT / "modules" / "team-registry.md"
    if not reg.exists():
        raise ParseError("modules/team-registry.md 부재")
    listed = set(re.findall(r"^\|\s*([a-z][a-z0-9-]+)\s*\|", read(reg), re.M))
    actual = {p.stem for p in AGENTS}
    v = []
    for a in sorted(actual - listed):
        v.append(f"agents/{a}.md: team-registry.md 미등재")
    for a in sorted(listed - actual):
        if a in {"에이전트", "스킬"}:
            continue
        v.append(f"team-registry.md: '{a}' 등재됐으나 agents/{a}.md 부재")
    return v, len(actual)


def chk_N1():
    sd = ROOT / "schemas"
    base = sd / "codex_base_issue_schema.json"
    if not base.exists():
        raise ParseError("schemas/codex_base_issue_schema.json 부재")
    try:
        bd = json.loads(read(base))
    except json.JSONDecodeError as e:
        raise ParseError(f"codex_base_issue_schema.json JSON 파싱 실패: {e}")
    sev = bd.get("$defs", {}).get("severity", {}).get("enum")
    if not sev:
        raise ParseError("base 스키마에 $defs.severity.enum 부재")
    v, seen = [], 0
    for f in sorted(sd.glob("*.json")):
        if f.name == base.name:
            continue
        try:
            doc = json.loads(read(f))
        except json.JSONDecodeError as e:
            raise ParseError(f"{f.name} JSON 파싱 실패: {e}")
        defs = find_severity_defs(doc)
        if not defs:
            seen += 1
            v.append(f"schemas/{f.name}: severity 정의 부재 — base와 대조 불가 (⛔ skip 아님)")
            continue
        for path, node in defs:
            seen += 1
            if isinstance(node.get("enum"), list):
                got = node["enum"]
            elif isinstance(node.get("$ref"), str):
                got, err = resolve_ref(node["$ref"], json.loads(read(base)), base.name)
                if err:
                    v.append(f"schemas/{f.name}{path}: {err}")
                    continue
            else:
                v.append(f"schemas/{f.name}{path}: enum도 `$ref`도 없다 — 대조 불가")
                continue
            if got != sev:
                v.append(f"schemas/{f.name}{path}: severity enum {got} ≠ base {sev}")

        # ⛔ 2026-08-10 확장 (4라운드 감사 ISSUE-004): severity **만** 보던 탓에
        #    `codex_review_schema` 의 `confidence` 가 base 의 `minimum/maximum` 을 잃은 채
        #    통과했고 → `confidence: 101` 이 검증기를 통과했다. **경계도 정합 대상**이다.
        base_doc = json.loads(read(base))
        for cname, keys in (("confidence", ("minimum", "maximum")),):
            bdefs = find_named_defs(base_doc, cname)
            if not bdefs:
                continue
            want = {k: bdefs[0][1].get(k) for k in keys if k in bdefs[0][1]}
            if not want:
                continue
            for path, node in find_named_defs(doc, cname):
                seen += 1
                got = {k: node.get(k) for k in want}
                if got != want:
                    v.append(f"schemas/{f.name}{path}: {cname} 경계 {got} ≠ base {want}")
    return v, seen


# ⛔ 선언 카운트를 갖는 디렉토리는 전부 등재한다 — scripts/는 2026-08-09에 한 세션 안에서
#    6→7로 늘며 CLAUDE.md가 stale해졌다(미등재 탓에 #N2가 침묵). 새 디렉토리 카운트 추가 시 여기도 추가.
INV = {
    "modules": lambda: len(MODULES),
    "guides": lambda: len(list((ROOT / "guides").glob("*.md"))),
    "scripts": lambda: len(SCRIPTS),
    "agents": lambda: len(AGENTS),
    "workflows": lambda: len(list((ROOT / "workflows").glob("*.js"))),
}


def chk_N2():
    cm = ROOT / "CLAUDE.md"
    if not cm.exists():
        raise ParseError("CLAUDE.md 부재")
    txt = read(cm)
    v, seen = [], 0
    for key, counter in INV.items():
        m = re.search(rf"`{key}/`[^\n]*?\((\d+)\s*개", txt)
        seen += 1
        if not m:
            # ⛔ 2026-08-09 정정 (외부 감사 ISSUE-002): 이전에는 `continue` 로 **조용히 skip**했다.
            #    INV에 5개를 등재하고도 `agents/`(괄호 없음)·`workflows/`(선언 부재) 2개가 빠져
            #    `[검사 대상 3]`으로 통과했다 — 선언을 지우면 enforcement가 사라지는 구조였다.
            v.append(f"CLAUDE.md: `{key}/` 카운트 선언 부재 또는 형식 불일치 "
                     f"— 형식은 `` - `{key}/` — 설명 (N개) `` (⛔ skip 아님)")
            continue
        declared, actual = int(m.group(1)), counter()
        if declared != actual:
            v.append(f"CLAUDE.md: `{key}/` 선언 {declared}개 ≠ 실측 {actual}개")
    return v, seen


CITE = re.compile(r"([A-Za-z0-9_./\-]+\.(?:md|js|py|sh|json)):(\d+)")


def chk_N3():
    """⛔ 판정은 사람이 한다 — 스크립트는 인용 줄의 실제 내용을 병기해 대조를 가능하게 한다."""
    by_base = defaultdict(list)
    for rel, _ in walk_files():
        by_base[Path(rel).name].append(rel)
    existing = {rel for rel, _ in walk_files()}
    v, seen = [], 0
    for rel, p in walk_files(".md", ".js"):
        if rel == "CHANGELOG.md":
            continue
        for i, line in enumerate(read(p).split("\n"), 1):
            for m in CITE.finditer(line):
                raw, num = m.group(1).lstrip("./"), int(m.group(2))
                target = raw if raw in existing else (by_base[Path(raw).name][0]
                                                     if len(by_base.get(Path(raw).name, [])) == 1 else None)
                if target is None:
                    continue
                seen += 1
                tl = read(ROOT / target).split("\n")
                if num > len(tl):
                    v.append(f"{rel}:{i}: → {target}:{num} 범위 초과 (파일 {len(tl)}줄)")
    return v, seen


# ⛔ #N8 신설 근거 (2026-08-09 외부 감사 ISSUE-014 + **본 세션의 자기 오류**):
#    ① 24개 모듈에 추가한 목차의 앵커 8개가 실제 heading과 불일치 ② 그걸 고치려고 쓴 첫 스크립트가
#    `\s+ → -` 로 **공백 연속을 합쳐** 14곳을 새로 깨뜨렸다. GitHub slugger는 구두점 제거 후
#    **공백 하나당 하이픈 하나**다 (`A + B` → `a--b`). 사람이 slug를 손으로 맞추면 또 틀린다.
GH_STRIP = re.compile(r"[^\w \-]", re.UNICODE)
# GFM fence 여닫이 — ⛔ ``` 만 보면 부족하다 (외부 감사 ISSUE-PLAN-008):
#   `~~~` · 4-backtick 이상 · 최대 3칸 인덴트 · **닫는 fence는 여는 것과 같은 문자이고 길이가 ≥** 여야 한다.
FENCE_OPEN = re.compile(r"^( {0,3})(`{3,}|~{3,})")
# 닫는 fence — 뒤에 fence 문자 외 내용이 있으면 닫지 못한다 (```python 은 여는 것)
FENCE_CLOSE = re.compile(r"^( {0,3})(`{3,}|~{3,})\s*$")
# 단락 줄 — setext 밑줄이 붙을 수 있는 유일한 선행 문맥.
#   ⛔ 리스트(`- ` `* ` `+ ` `1. `)·인용(`>`)·heading(`#`)·표(`|`)·들여쓴 코드(4칸)·빈 줄은 제외.
# ⛔ 4라운드 ISSUE-008 정정: 마커는 **뒤에 공백이 있을 때만** 리스트/heading 이다.
#    `-foo`·`*emphasis*`·`#hashtag` 는 **단락**이므로 setext 밑줄을 받을 수 있다.
PARAGRAPH_LINE = re.compile(r"^ {0,3}(?!([-*+]|>|#{1,6}|\d+[.)])(\s|$))\S")


def gh_slug(heading: str) -> str:
    """GitHub slugger: 소문자화 → 영숫자/공백/하이픈/`_` 외 제거 → 공백 각각을 하이픈으로."""
    return GH_STRIP.sub("", heading.strip().lower()).replace(" ", "-")


def iter_headings(txt: str):
    """fenced 코드 블록 **밖**의 heading 텍스트만 순서대로 낸다.

    ⛔ 신설 근거: 1차 구현은 fence 안의 `## …` 도 heading으로 셌다 — 목차가 실재하지 않는
       앵커를 가리켜도 '해소됨'으로 보일 수 있었다 (외부 감사 ISSUE-007).
    """
    fence: str | None = None
    prev: str | None = None
    for line in txt.split("\n"):
        if fence is None:
            m = FENCE_OPEN.match(line)
            if m:
                fence = m.group(2)
                prev = None
                continue
        else:
            m = FENCE_CLOSE.match(line)
            # ⛔ 닫는 fence 는 **같은 문자 + 길이 ≥ + 뒤에 fence 문자 외 내용 없음**.
            #    3라운드 감사 ISSUE-004: 접두만 보면 ```python 이 기존 ``` 를 닫아버렸다.
            if m and m.group(2)[0] == fence[0] and len(m.group(2)) >= len(fence):
                fence = None
            continue
        h = re.match(r"^ {0,3}(#{2,6})\s+(.*?)\s*$", line)
        if h:
            # ⛔ ATX 닫는 해시 제거 — `## Foo ##` 의 GitHub slug 는 `foo` 다 (ISSUE-004)
            yield re.sub(r"\s+#+\s*$", "", h.group(2))
            prev = None
            continue
        # setext heading — 직전 줄이 **단락**이고 이 줄이 `===`/`---` 이면 heading 이다 (ISSUE-004)
        # ⛔ GFM 은 setext 밑줄이 **단락**만 뒤따르게 허용한다. 리스트 항목·인용·표·heading 뒤의
        #    `---` 는 thematic break 다 — 이를 setext 로 읽으면 **유령 heading**이 생기고,
        #    존재하지 않는 절을 가리키는 목차 앵커가 "해소됨"으로 통과한다 (Lead 자체 발견, 2026-08-10).
        if prev and re.match(r"^ {0,3}(=+|-+)\s*$", line):
            yield prev.strip()
            prev = None
            continue
        prev = line if PARAGRAPH_LINE.match(line) else None


def gh_anchors(txt: str) -> dict:
    """slug → heading. 중복은 **github-slugger의 occupied-slug 루프**를 따른다.

    ⛔ 1차 구현은 `slug-N` 을 만들고 그것이 이미 점유됐는지 확인하지 않아 덮어썼다:
       `Foo`/`Foo`/`Foo-1` → foo, foo-1 (2개) — GitHub는 foo, foo-1, **foo-1-1** (3개).
       [외부: codex — github-slugger 2.0.0 occupied-slug 루프 검증 통과]
    """
    out: dict[str, str] = {}
    counts: dict[str, int] = {}
    for heading in iter_headings(txt):
        base = gh_slug(heading)
        slug = base
        if slug in out:
            n = counts.get(base, 0)
            while True:
                n += 1
                slug = f"{base}-{n}"
                if slug not in out:                # ⛔ 점유됐으면 계속 증가시킨다
                    break
            counts[base] = n
        out[slug] = heading
    return out


TOC_LINK = re.compile(r"\]\(#([^)]+)\)")


def chk_N8(root: Path | None = None):
    v, seen = [], 0
    for rel, p in walk_files(".md", root=root):
        txt = read(p)
        if "## 목차" not in txt:
            continue
        valid = gh_anchors(txt)
        rest = txt.split("## 목차", 1)[1]
        block = rest.split("\n##", 1)[0] if "\n##" in rest else rest
        for line in block.split("\n"):
            m = TOC_LINK.search(line)
            if not m:
                continue
            seen += 1
            if m.group(1) not in valid:
                v.append(f"{rel}: 목차 앵커 `#{m.group(1)}` 가 어떤 heading으로도 해소되지 않는다")
    return v, seen


# ⛔ #N7 신설 근거 (2026-08-09 외부 감사 ISSUE-008): `get_codex_skill()` → `get_codex_skill_path()`
#    전환에서 **할당은 `_SKILL_PATH`로 바뀌고 조건문은 옛 `_SKILL`을 검사**하는 스니펫이 3곳 남았다
#    (`SEARCHER_SKILL`·`FIXER_SKILL`·`CHALLENGER_SKILL`). `[ -n "$미정의" ]`는 false라 searcher 보조·
#    fixer 보조·final DA가 **조용히 실행되지 않았다.** 사람 눈으로 한 번 잡고도 3곳을 놓쳤으므로 기계화한다.
# ⛔ `local`/`export`/`declare`/`readonly` 접두를 포함한다 — 누락 시 `local SKILL=`가 미할당으로 오판된다
#    (첫 실행에서 cross-validation.md:317·325 오탐 2건. 대상이 아니라 도구가 틀렸다)
# 할당 인정 형태 — ⛔ 2026-08-09 S3 확장 (외부 감사 ISSUE-006):
#   `local`/`export`/`declare`/`readonly` 접두(1차) + `read`·`printf -v`·`for X in`(2차).
#   누락하면 정당한 할당을 미할당으로 오판한다(1차에서 `local SKILL=` 오탐 2건 실측).
ASSIGN = re.compile(
    r"^\s*(?:local|export|declare|readonly)?\s*([A-Z][A-Z0-9_]*)="      # X= / local X=
    r"|^\s*read\s+(?:-\w+\s+)*([A-Z][A-Z0-9_]*)"                        # read X
    r"|^\s*printf\s+-v\s+([A-Z][A-Z0-9_]*)"                            # printf -v X
    r"|^\s*for\s+([A-Z][A-Z0-9_]*)\s+in\b"                             # for X in …
)
# 검사 형태 — `[ ]`/`[[ ]]` × 인용/비인용 × `-n`/`-z`.
# ⛔ `${VAR:-default}`는 **의도적으로 제외**한다 — 기본값을 공급하므로 미정의가 결함이 아니다.
#    (`\}` 를 이름 직후에 요구하여 `:-`/`:=`/`:?` 형태를 배제)
TESTED = re.compile(
    r'\[\[?\s*-[nz]\s+"?(?:\$([A-Z][A-Z0-9_]*)\b|\$\{([A-Z][A-Z0-9_]*)\})'
)
# 환경/외부 주입 변수 — 스니펫 안에 할당이 없어도 정당하다.
# ⛔ 알려진 한계 (외부 감사 ISSUE-006): 전역 허용목록이라 **여기 등재된 이름은
#    로컬 할당이 삭제·개명돼도 통과한다**(예: `SKIP_FLAG`). 제거하면 오탐이 폭증하므로
#    유지하되, 이 목록에 이름을 추가하는 것은 그 변수의 회귀 탐지를 포기하는 것이다.
EXTERNAL_OK = {
    "FZ_PLUGIN_ROOT", "GIT_ROOT", "PROJECT_ROOT", "HOME", "CODEX_HOME", "SHARED_MODULES",
    "BASE_BRANCH", "PLAN_CONTENT", "AFFECTED_SYMBOLS", "HAS_FIXABLE_ISSUES",
    "MAJOR_ISSUES_COUNT", "REVIEW_FILE", "DA_REVIEW_FILE", "RESULT_FILE", "WORK_DIR",
    "EXPECTED_BRANCH", "SKIP_FLAG", "PLUGIN_AVAILABLE", "CLAUDE_PROJECT_DIR",
    "TIER_OPT",   # peer-review 사용자 명시 옵션 — 블록 바깥에서 주입된다
}


def chk_N7(root: Path | None = None):
    """마크다운 ```bash 블록 안에서 `[ -n "$VAR" ]`를 검사하는데 같은 블록에 `VAR=` 할당이 없는 경우."""
    v, seen = [], 0
    for rel, p in walk_files(".md", root=root):
        if rel == "CHANGELOG.md":
            continue
        lines = read(p).split("\n")
        in_block, start, assigned = False, 0, set()
        for i, line in enumerate(lines, 1):
            if re.match(r"\s*```(bash|sh|shell)\b", line):
                in_block, start, assigned = True, i, set()
                continue
            if in_block and re.match(r"\s*```\s*$", line):
                in_block = False
                continue
            if not in_block:
                continue
            m = ASSIGN.match(line)
            if m:
                assigned.add(next(g for g in m.groups() if g))
            for t2 in TESTED.finditer(line):
                name = t2.group(1) or t2.group(2)
                seen += 1
                if name in assigned or name in EXTERNAL_OK:
                    continue
                v.append(f"{rel}:{i}: `${name}`를 검사하는데 같은 bash 블록(:{start}~)에 "
                         f"`{name}=` 할당이 없다 — 오타/이름 변경 잔존 의심")
    return v, seen


ERE_BAD = re.compile(r"grep\s+(?:-\w+\s+)*-\w*E\w*\b")


def chk_N4(root: Path | None = None):
    """ERE에서 `\\|`는 alternation이 아니다 — 항상 매칭 실패한다.
    ⚠️ BRE(`grep` 무옵션)의 `\\|`는 정당하므로 `grep -E` **같은 줄**만 본다."""
    self_rel = Path(__file__).resolve().relative_to(ROOT).as_posix()
    v, seen = [], 0
    for rel, p in walk_files(".md", ".sh", ".py", root=root):
        if rel == "CHANGELOG.md":
            continue
        # ⛔ 자기 참조 제외 — 검사기의 *설명 문구*가 검사 대상 패턴을 포함한다 (첫 실행에서 3건 오탐)
        if rel == self_rel:
            continue
        for i, line in enumerate(read(p).split("\n"), 1):
            if not ERE_BAD.search(line):
                continue
            # ⛔ 마크다운 표 행 제외 — 표 셀 안의 `\|`는 **파이프 이스케이프**이지 ERE가 아니다
            #    (verify-evidence-matrix.md:11 `curl -s "$url" \| grep -iE` 가 실제 오탐이었다)
            if line.lstrip().startswith("|"):
                continue
            seen += 1
            if "\\|" in line:
                v.append(f"{rel}:{i}: `grep -E` 같은 줄의 `\\|` — ERE alternation 아님 (항상 0건)")
    return v, seen


def chk_N5(root: Path | None = None):
    v, seen = [], 0
    scripts = (sorted(p for p in (root / "scripts").glob("*") if p.is_file())
               if root else SCRIPTS)
    for p in scripts:
        if p.name == Path(__file__).name:
            continue
        seen += 1
        txt = read(p)
        for i, line in enumerate(txt.split("\n"), 1):
            if ">/dev/null 2>&1" not in line and "> /dev/null 2>&1" not in line:
                continue
            # 같은 줄 또는 다음 2줄에서 exit code를 쓰는지
            ctx = "\n".join(txt.split("\n")[i - 1:i + 2])
            if not re.search(r"\$\?|returncode|check=|\|\||&&|if\s", ctx):
                v.append(f"scripts/{p.name}:{i}: 측정 신호 폐기 — exit code 미사용")
    return v, seen


# ─────────────────────────────────────────────────────────────────────────────
# #N6 루트 앵커 — **줄 단위 화이트리스트**(.py/.sh 공통). fail-closed.
#
# ⛔ 설계 전환 (2026-08-10, 4라운드 감사 ISSUE-005·006 + Codex C3):
#   3차 구현은 `.py` 를 `ast` 로 **일반 분석**했다. 그 방향은 실패했다 —
#     · `from evil import Path as P` → `P(__file__)` 통과 (ImportFrom.module 미검증)
#     · `X().resolve(__file__)` 통과 (임의 attr 이름이 화이트리스트와 충돌)
#     · 고치려면 import 해소·스코프·shadowing 분석이 따라온다 (반응적 확장)
#   그리고 `.sh` 의 heredoc 제거도 POSIX 규칙(정확 일치 / `<<-` 탭만 / `<<\EOF` / 다중)을
#   재구현하려다 3방향으로 틀렸다.
#   ⇒ **일반 분석을 포기한다.** 대상은 우리 스크립트 **10개**(.py 4 · .sh 6)뿐이므로
#      *실제로 쓰는 루트 해석 줄*을 정확히 열거하고, **미지 형태는 거부**한다.
#      새 형태가 필요하면 여기 추가한다 — 그게 명시 승인이다.
#
# ⛔ heredoc: 종료 규칙을 재구현하지 않는다. `<<` 가 보이면 **그 줄 이후 전체를 데이터로 취급**
#    (fail-closed). 앵커는 heredoc **앞**에 있어야 한다 — 과도하게 숨기는 방향은 안전하다.
# ─────────────────────────────────────────────────────────────────────────────

# 허용 형태 — 정확히 이 형태의 **한 줄**이 있어야 한다 (양끝 공백만 무시)
ANCHOR_LINES = [
    # .py — 자기 위치에서 루트 해석
    re.compile(r"^[A-Za-z_]\w* = Path\(__file__\)\.resolve\(\)(\.parent)*\s*(#.*)?$"),
    re.compile(r"^[A-Za-z_]\w* = Path\(__file__\)\.parent(\.parent)*\s*(#.*)?$"),
    re.compile(r"^[A-Za-z_]\w* = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\s*(#.*)?$"),
    re.compile(r"^[A-Za-z_]\w* = os\.path\.dirname\(__file__\)\s*(#.*)?$"),
    # .sh — 자기 위치 또는 git 루트
    re.compile(r'^[A-Z_]\w*="\$\(\s*cd\s+"\$\(\s*dirname\s+"\$\{?BASH_SOURCE\[0\]\}?"\s*\)"'
               r'\s*&&\s*pwd(\s+-P)?\s*\)"\s*$'),
    # ⛔ 2026-08-10 Lead 자체 발견: 이전 판은 `[A-Z_]*="$(cd "…" && pwd)"` 를 **경로 무관**하게 허용해
    #    `X="$(cd "/tmp" && pwd)"` 나 `$HOME` 도 루트 앵커로 인정했다 — fail-closed 화이트리스트에
    #    내가 직접 구멍을 냈다. **자기 위치에서 유도한 경로만** 허용한다.
    re.compile(r'^[A-Z_]\w*="\$\(\s*cd\s+"\$(\{?BASH_SOURCE\[0\]\}?|0|\{?\w*(?:DIR|ROOT|dir|root)\w*\}?)'
               r'[^"]*"\s*&&\s*pwd(\s+-P)?\s*\)"\s*$'),
    re.compile(r'^[A-Z_]\w*="\$\(\s*dirname\s+"\$0"\s*\)"\s*$'),
    re.compile(r'^[A-Z_]\w*="\$\(\s*cd\s+"\$\(\s*dirname\s+"\$0"\s*\)"\s*&&\s*pwd(\s+-P)?\s*\)"\s*$'),
    re.compile(r'^(cd\s+|[A-Z_]\w*=)"\$\(\s*git rev-parse --show-toplevel\s*\)"\s*$'),
]
# CWD·인수 루트를 쓰되 **마커로 fail-closed 검증**하는 형태 (형태 b)
ROOT_MARKER = re.compile(r'["\']?(guides|skills|codex-skills)["\']?\s*\)?\s*(?:/|\)\s*)?'
                         r'\.?(?:is_dir|exists)\(\)'
                         r'|-d\s+"?\$?\{?\w*(?:ROOT|root)\w*\}?/(guides|skills|codex-skills)')
NONZERO_EXIT = re.compile(r"return\s+[1-9]|exit\s+[1-9]|sys\.exit\(\s*[1-9]")
# 명시 면제 — 루트를 아예 참조하지 않는 스크립트. 상단 20줄 + 사유 10자+
WAIVER = re.compile(r"lint:no-root-anchor\s*[—:-]\s*(\S.{9,})")


def code_lines(txt: str, suffix: str) -> list[str]:
    """검사 대상 '코드 줄'. 주석 제거 + `.sh` 는 **첫 `<<` 이후 전체를 데이터로 취급**(fail-closed)."""
    out: list[str] = []
    for line in txt.split("\n"):
        if suffix == ".sh" and "<<" in line:
            out.append(re.sub(r"(^|\s)#.*$", r"\1", line))
            break                                   # ⛔ 이후는 heredoc 가능성 → 전부 버린다
        out.append(re.sub(r"(^|\s)#.*$", r"\1", line))
    return out


def anchored_line(txt: str, suffix: str) -> bool:
    """허용 형태에 **정확히** 매칭되는 줄이 있는가 (fail-closed)."""
    return any(any(p.match(l.strip()) for p in ANCHOR_LINES)
               for l in code_lines(txt, suffix))


def n6_ok(txt: str, suffix: str) -> bool:
    """루트 해석이 안전한가. ⛔ chk_N6 와 self-test 가 **같은 함수**를 쓴다.

    허용 3형태:
      (a) `ANCHOR_LINES` 중 하나와 **정확히 일치하는 줄** (주석·문자열·heredoc 은 제외됨)
      (b) 마커(`guides`/`skills`/`codex-skills`) 검사 + 3줄 내 비0 종료
      (c) 상단 20줄 내 `# lint:no-root-anchor — 사유(10자+)`
    """
    if anchored_line(txt, suffix):
        return True
    lines = code_lines(txt, suffix)
    for i, line in enumerate(lines):
        if ROOT_MARKER.search(line) and NONZERO_EXIT.search("\n".join(lines[i:i + 3])):
            return True
    return bool(WAIVER.search("\n".join(txt.split("\n")[:20])))


def chk_N6(root: Path | None = None):
    v, seen = [], 0
    scripts = sorted(p for p in ((root / "scripts") if root else (ROOT / "scripts")).glob("*")
                     if p.is_file()) if root else SCRIPTS
    for p in scripts:
        if p.suffix not in (".py", ".sh"):
            continue
        seen += 1
        if not n6_ok(read(p), p.suffix):
            v.append(f"scripts/{p.name}: 루트 해석 불안전 — (a) 허용 형태 줄과 정확히 일치 · (b) 마커 검사 + 3줄 내 비0 종료 · (c) 상단 20줄 내 `# lint:no-root-anchor — 사유(10자+)` 중 하나도 없다 (허용 형태는 ANCHOR_LINES 에 명시 추가한다)")
    return v, seen


class ParseError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 양성 대조 (self-test) — ⛔ 패턴이 곧 검사인 항목에 한정
#
# 왜 필요한가: `hits`(검사 대상 수)는 *본 후보 수*이지 *탐지 능력*이 아니다. 패턴이 고장나도
#   후보는 세어지므로 `OK [검사 대상 N]`이 찍힌다. 실제로 #15는 `head -n 5`를 못 잡는 채
#   13개 후보를 세며 통과했고(ISSUE-003), #N6는 주석 속 토큰으로 통과했다(ISSUE-005).
# 왜 4개만인가: `guides/harness-engineering.md` §6 AP1(과도한 구조화) — 정규식이 판정의 전부인
#   항목만 fixture가 이득이다. 구조 순회형(#N1·N2·N16)은 파싱 실패가 곧 ParseError로 드러난다.
# ─────────────────────────────────────────────────────────────────────────────
SELF_TESTS: list[tuple[str, str, bool, str]] = [
    # (항목, 입력, 매칭 기대, 설명)
    ("N4", 'grep -E "^(a\\|b)" f',           True,  "ERE에서 `\\|`는 alternation 아님"),
    ("N4", 'grep -E "^(a|b)" f',             False, "정상 ERE"),
    ("N4", 'grep "a\\|b" f',                 False, "BRE의 `\\|`는 정당"),
    ("N5", "cmd >/dev/null 2>&1",            True,  "신호 폐기 후보"),
    ("N5", "cmd > /dev/null 2>&1",           True,  "공백 변형"),
    ("N5", "cmd 2>/dev/null",                False, "stderr만 → 후보 아님"),
    ("N6", "root = Path(__file__).resolve().parent", True,  "(a) .py 허용 형태"),
    ("N6", "d = os.path.dirname(__file__)",   True,  "(a) .py os.path 형태"),
    ("N6", '__file__ = "fake"',              False, "⛔ 재바인딩 — 허용 형태 아님"),
    ("N6", 'x = f"{__file__}"',              False, "⛔ f-string 내부"),
    ("N6", 'marker = "BASH_SOURCE"',         False, "⛔ 문자열 리터럴"),
    ("N6", "log.debug(__file__)",            False, "⛔ 무관한 읽기"),
    ("N6", "from evil import Path as P\nr = P(__file__)", False,
                                                    "⛔ 악성 출처 alias (4R ISSUE-005)"),
    ("N6", 'D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"', True, "(a) .sh 허용 형태"),
    ("N6", 'DIR="$(dirname "$0")"',          True,  "(a) .sh dirname"),
    ("N6", 'echo "BASH_SOURCE[0]"',          False, "⛔ .sh 언급만"),
    ("N6", 'cat <<EOF\nDIR="$(dirname "$0")"\nEOF', False,
                                                    "⛔ heredoc 본문 (4R ISSUE-006)"),
    ("N6", "if err:\n    return 2",          False, "⛔ 무관한 비0 종료"),
    ("N6", 'if not (root / "guides").is_dir():\n    return 2', True,
                                                    "(b) 마커 + 비0 종료"),
    ("N6", 'if not (root / "guides").is_dir():\n    warn()', False,
                                                    "⛔ 마커만 — fail-closed 아님"),
    ("N6", "# lint:no-root-anchor — 경로를 인수로 받는다", True, "(c) 사유 있는 면제"),
    ("N6", "# lint:no-root-anchor",          False, "⛔ 사유 없는 면제"),
    ("N1", "REF_OK",                         True,  "정상 `$ref` → base enum resolve"),
    ("N1", "REF_WRONG_PATH",                 True,  "⛔ 오참조 경로 → 위반 메시지"),
    ("N1", "REF_WRONG_FILE",                 True,  "⛔ 알 수 없는 대상 파일 → 위반 메시지"),
    ("N7", 'if [ -n "$VAR" ]; then',         True,  "인용 단일 대괄호"),
    ("N7", 'if [ -z "$VAR" ]; then',         True,  "-z"),
    ("N7", 'if [[ -n $VAR ]]; then',         True,  "⛔ 이중 대괄호 + 비인용 — 1차에서 미탐"),
    ("N7", 'if [ -n $VAR ]; then',           True,  "⛔ 단일 대괄호 비인용 — 1차에서 미탐"),
    ("N7", 'if [ -n "${VAR}" ]; then',       True,  "중괄호"),
    ("N7", 'if [ -n "${VAR:-x}" ]; then',    False, "⛔ 기본값 공급 — 의도적 제외"),
    ("N7", 'read VAR',                       True,  "read 할당 인정"),
    ("N7", 'printf -v VAR "%s" x',           True,  "printf -v 할당 인정"),
    ("N7", 'for VAR in a b; do',             True,  "for 할당 인정"),
    ("N8", "## A + B",                       True,  "⛔ 구두점 제거로 생긴 공백 2개 → 하이픈 2개"),
    ("N8", "## Plain Head",                  True,  "단일 공백 → 하이픈 1개"),
    ("N8", "COLLISION",                      True,  "⛔ Foo/Foo/Foo-1 → foo, foo-1, foo-1-1 (occupied 루프)"),
    ("N8", "FENCE_BACKTICK",                 True,  "⛔ ``` 안 heading 제외"),
    ("N8", "FENCE_TILDE",                    True,  "⛔ ~~~ 안 heading 제외"),
    ("N8", "FENCE_LONG",                     True,  "⛔ 4-backtick 안의 ``` 는 닫지 못한다"),
    ("N8", "FENCE_INDENT",                   True,  "⛔ 인덴트된 fence도 fence다"),
    ("N8", "SETEXT_PARA",                    True,  "단락 + --- → setext heading"),
    ("N8", "SETEXT_LIST",                    True,  "⛔ 리스트 + --- → thematic break (유령 heading 금지)"),
    ("N8", "SETEXT_QUOTE",                   True,  "⛔ 인용 + --- → 유령 금지"),
    ("N8", "ATX_TRAILING_HASH",              True,  "`## Foo ##` → foo"),
    ("N8", "FENCE_UNCLOSED",                 True,  "미종료 fence 내부 heading 제외"),
]
SELF_TEST_COUNT = len(SELF_TESTS)


# ─────────────────────────────────────────────────────────────────────────────
# 통합 fixture — 임시 트리에 known-bad 파일을 놓고 `chk_*` 를 **통째로** 호출한다.
#
# ⛔ 술어 fixture가 못 잡는 회귀를 잡는다 (외부 감사 ISSUE-PLAN-003):
#    잘못된 파일 순회 · 잘못된 확장자 필터 · 잘못된 디렉토리 제외 · 결과 반전 ·
#    `([], 그럴듯한 hits)` 반환. 위반의 **정확한 위치와 건수**를 단정한다.
# ─────────────────────────────────────────────────────────────────────────────
INTEG_TREE = {
    # #15: 잘림 + 3줄 뒤 카운트 → 위반 1
    # #N4: grep -E 같은 줄의 `\|` → 위반 1
    "modules/bad_n4.md": 'run: grep -E "^(a\\|b)" f\n',
    # #N7: 할당 없는 $VAR 검사 → 위반 1
    "modules/bad_n7.md": '```bash\nif [ -n "$NOPE" ]; then echo x; fi\n```\n',
    # #N8: 목차 앵커 미해소 → 위반 1
    "modules/bad_n8.md": '# T\n\n## 목차\n\n- [없는절](#없는절)\n\n## 실제절\n\n본문\n',
    # #N6: 앵커·면제 없는 스크립트 → 위반 2 (⛔ **언어 계열별로 각 1개** — 한 계열 순회가 죽으면 잡힌다)
    "scripts/bad_n6.sh": '#!/bin/bash\ncd ./somewhere\necho hi\n',
    "scripts/bad_n6.py": 'import os\nroot = os.getcwd()\nprint(root)\n',
    # #N5: 측정 신호 폐기(exit code 미사용) → **계열별 각 1개** (4R ISSUE-009)
    "scripts/bad_n5.sh": '#!/bin/bash\nDIR="$(dirname "$0")"\ngrep -q x f >/dev/null 2>&1\necho done\n',
    "scripts/bad_n5.py": 'from pathlib import Path\nroot = Path(__file__).parent\n'
                         'import subprocess\nsubprocess.run(["x"], stdout=None) >/dev/null 2>&1\n',
    # #N4 · #N7 도 계열별로 (스캔 대상이 .md/.sh/.py 인데 fixture 가 .md 뿐이었다)
    "scripts/bad_n4.sh": '#!/bin/bash\nDIR="$(dirname "$0")"\ngrep -E "^(a\\|b)" f\n',
    "scripts/bad_n4.py": 'from pathlib import Path\nroot = Path(__file__).parent\n'
                         '# run: grep -E "^(x\\|y)" f\n',
    # ⛔ SKIP_DIRS 미끼 — 제외 로직이 죽으면 여기가 세어져 카운트가 어긋난다
    # ⛔ SKIP 미끼 — 제외 로직이 죽으면 여기가 세어져 카운트가 어긋난다.
    #    내용은 **#N4·#N7 을 발동**시킨다 (2026-08-10 감사 ISSUE-009: 미끼가 #15 만 검증했다)
    "worktrees/decoy/modules/bad_n4.md": 'run: grep -E "^(a\\|b)" f\n',
    "node_modules/decoy_n4.md": 'run: grep -E "^(c\\|d)" f\n',
    "docs/releases/decoy_n7.md": '```bash\nif [ -n "$GONE" ]; then echo x; fi\n```\n',
    # 정상 대조군 — 위반 0이어야 한다
    "modules/ok.md": '# T\n\n## 목차\n\n- [실제절](#실제절)\n\n## 실제절\n\n본문\n',
    "scripts/ok.py": 'from pathlib import Path\nroot = Path(__file__).resolve().parent\n',
}
# ⛔ 위반 **건수 + 정확한 위치**를 단정한다 (3라운드 감사 ISSUE-006: 건수만 보면
#    잘못된 파일을 잡아도 통과한다). 위치는 `rel:line` 접두로 대조한다.
INTEG_EXPECT = {
    "N4": ["modules/bad_n4.md:1", "scripts/bad_n4.sh:3", "scripts/bad_n4.py:3"],
    "N5": ["scripts/bad_n5.sh:3", "scripts/bad_n5.py:4"],
    "N6": ["scripts/bad_n6.py", "scripts/bad_n6.sh"],
    "N7": ["modules/bad_n7.md:2"],
    "N8": ["modules/bad_n8.md"],
}


def run_integration_tests() -> list[str]:
    """실패 메시지 목록 반환 (빈 목록 = 전부 통과).

    ⛔ 3라운드 감사(ISSUE-006) 정정 3건:
      ① `tempfile.TemporaryDirectory()` 가 예외를 던지면 main 을 탈출해 **exit 1** 이 됐다
         (읽기 전용 환경에서 실측) — configuration error 는 exit 2 여야 한다 → 예외를 메시지로 변환
      ② 위반 **건수만** 단정해 잘못된 파일을 잡아도 통과했다 → **정확한 위치**를 단정
      ③ `#N5` 누락 + `#N6` 가 셸 픽스처만 있어 **파이썬 계열 순회 소실**이 통과했다 → 계열별 픽스처
    """
    import tempfile
    fails: list[str] = []
    try:
        td_ctx = tempfile.TemporaryDirectory()
    except Exception as e:                                            # noqa: BLE001
        return [f"임시 트리 생성 실패({type(e).__name__}: {e}) — 통합 fixture 실행 불가"]
    with td_ctx as td:
        root = Path(td)
        try:
            for rel, body in INTEG_TREE.items():
                fp = root / rel
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(body, encoding="utf-8")
            (root / "guides").mkdir(exist_ok=True)      # 루트 마커
        except OSError as e:
            return [f"임시 트리 기록 실패({e}) — 통합 fixture 실행 불가"]

        for item, want_locs in INTEG_EXPECT.items():
            try:
                v, hits = CHECKS[item](root=root)
            except TypeError:
                fails.append(f"#{item}: root 주입 미지원 — 통합 fixture 불가")
                continue
            except Exception as e:                                    # noqa: BLE001
                fails.append(f"#{item}: 통합 실행 예외 {type(e).__name__}: {e}")
                continue
            if len(v) != len(want_locs):
                fails.append(f"#{item} 통합 fixture: 위반 {len(v)}건 (기대 {len(want_locs)}) "
                             f"hits={hits} → {v}")
                continue
            for want in want_locs:
                # ⛔ 4R ISSUE-009: `startswith` 는 ':3' 이 ':30' 에 매칭됐다 → **경계**를 요구한다
                if not any(msg == want or msg.startswith(want + ":") or msg.startswith(want + " ")
                           for msg in v):
                    fails.append(f"#{item} 통합 fixture: 기대 위치 '{want}' 미검출 → {v}")
            if hits == 0:
                fails.append(f"#{item} 통합 fixture: 후보 0 — 순회가 트리를 못 봤다")
    return fails


def run_self_tests() -> list[str]:
    """실패 메시지 목록 반환 (빈 목록 = 전부 통과)."""
    fails = []
    for item, src, want, why in SELF_TESTS:
        if item == "N1":
            base_doc = {"$defs": {"severity": {"enum": ["critical", "major", "minor", "suggestion"]}}}
            if src == "REF_OK":
                enum, err = resolve_ref("codex_base_issue_schema.json#/$defs/severity",
                                        base_doc, "codex_base_issue_schema.json")
                got = err is None and enum == ["critical", "major", "minor", "suggestion"]
            elif src == "REF_WRONG_PATH":
                enum, err = resolve_ref("#/$defs/nope", base_doc, "codex_base_issue_schema.json")
                got = enum is None and err is not None
            else:                                     # REF_WRONG_FILE
                enum, err = resolve_ref("other.json#/$defs/severity",
                                        base_doc, "codex_base_issue_schema.json")
                got = enum is None and err is not None
        elif item == "N4":
            got = bool(ERE_BAD.search(src)) and "\\|" in src
        elif item == "N5":
            got = (">/dev/null 2>&1" in src) or ("> /dev/null 2>&1" in src)
        elif item == "N7":
            # 검사 형태 fixture는 TESTED, 할당 형태 fixture는 ASSIGN을 본다
            if src.startswith(("read ", "printf ", "for ")):
                got = bool(ASSIGN.match(src))
            else:
                got = bool(TESTED.search(src))
        elif item == "N8":
            if src == "COLLISION":
                a = gh_anchors("## Foo\n## Foo\n## Foo-1\n")
                got = sorted(a) == ["foo", "foo-1", "foo-1-1"]
            elif src == "FENCE_BACKTICK":
                a = gh_anchors("## Real\n```\n## Fake\n```\n")
                got = "fake" not in a and "real" in a
            elif src == "FENCE_TILDE":
                a = gh_anchors("## Real\n~~~\n## Fake\n~~~\n")
                got = "fake" not in a and "real" in a
            elif src == "FENCE_LONG":
                # 4-backtick 블록 안의 ``` 는 닫지 못하므로 그 뒤 heading도 fence 안이다
                a = gh_anchors("## Real\n````\n## Fake\n```\n## Also\n````\n")
                got = "fake" not in a and "also" not in a and "real" in a
            elif src == "SETEXT_PARA":
                got = sorted(gh_anchors("단락 텍스트\n---\n")) == ["단락-텍스트"]
            elif src == "SETEXT_LIST":
                # ⛔ GFM: setext 밑줄은 **단락**만 뒤따른다 — 리스트 뒤 `---` 는 thematic break
                got = gh_anchors("- 리스트\n---\n") == {}
            elif src == "SETEXT_QUOTE":
                got = gh_anchors("> 인용\n---\n") == {}
            elif src == "ATX_TRAILING_HASH":
                got = sorted(gh_anchors("## Foo ##\n")) == ["foo"]
            elif src == "FENCE_UNCLOSED":
                a = gh_anchors("## Real\n```\n## Fake\n")
                got = "fake" not in a and "real" in a
            elif src == "FENCE_INDENT":
                a = gh_anchors("## Real\n   ```\n   ## Fake\n   ```\n")
                got = "fake" not in a and "real" in a
            else:
                # slug 왕복: heading → slug
                expect = {"## A + B": "a--b", "## Plain Head": "plain-head"}[src]
                got = gh_slug(src[3:]) == expect
        elif item == "N6":
            # ⛔ chk_N6와 **동일 함수**를 호출한다 — fixture가 별도 로직을 검사하면 드리프트한다
            got = n6_ok(src, ".sh" if ("$" in src or src.startswith("echo ")) else ".py")
        else:                                                     # pragma: no cover
            fails.append(f"#{item}: self-test 라우팅 미구현")
            continue
        if got != want:
            fails.append(f"#{item} 양성대조 실패 ({why}): {src!r} → 기대 {want}, 실제 {got}")
    return fails


CHECKS = {
    "1": chk_1, "3": chk_3, "5": chk_5, "6": chk_6, "7": chk_7,
    "14": chk_14, "16": chk_16,
    "N1": chk_N1, "N2": chk_N2, "N3": chk_N3, "N4": chk_N4, "N5": chk_N5, "N6": chk_N6,
    "N7": chk_N7, "N8": chk_N8,
}


def check_registry_invariants() -> list[str]:
    """레지스트리 자체의 구조 불변식. ⛔ 위반은 configuration error(exit 2)다.

    신설 근거(2026-08-09 ISSUE-002): 등재만 하고 검사되지 않는 항목이 조용히 존재할 수 있었다.
    """
    v = []
    id_list = [i for i, _, _, _ in ITEMS]
    ids = set(id_list)
    # ⛔ 중복 id — set 으로 접으면 놓친다 (3라운드 감사 ISSUE-008)
    seen_once: set[str] = set()
    for i in id_list:
        if i in seen_once:
            v.append(f"ITEMS에 중복 id '{i}' — 뒤 항목이 앞 항목을 가린다")
        seen_once.add(i)
    for k in CHECKS:
        if k not in ids:
            v.append(f"CHECKS['{k}'] 가 ITEMS에 없다 — 레지스트리 불일치")
        elif k not in DET:
            # ⛔ SKIP 판정자에 구현이 있으면 "판정하지 않는다"는 선언과 모순된다
            v.append(f"CHECKS['{k}'] 는 구현이 있는데 판정자가 DETERMINISTIC 이 아니다 — SKIP 선언과 모순")
    for i in sorted(DET):
        if i not in CHECKS:
            v.append(f"#{i} 는 DETERMINISTIC인데 CHECKS 구현이 없다")
        if i not in MIN_HITS:
            v.append(f"#{i} 는 DETERMINISTIC인데 MIN_HITS 선언이 없다 (순회 회귀 무방비)")
    for i in MIN_HITS:
        if i not in DET:
            v.append(f"MIN_HITS['{i}'] 가 DETERMINISTIC 항목이 아니다")
        # ⛔ 4R ISSUE-010: 0·음수는 존재 검사를 통과하면서 하한을 **무력화**한다
        if not isinstance(MIN_HITS[i], int) or MIN_HITS[i] < 1:
            v.append(f"MIN_HITS['{i}'] = {MIN_HITS[i]!r} — 1 이상의 정수여야 한다 (하한 무력화 방지)")
    # ⛔ 4R ISSUE-010: `kind` 오타(예: "DETERMINSTIC")는 DET 집합에서 빠져 **조용히 SKIP** 된다
    for i, kind, _, _ in ITEMS:
        if kind not in ("DETERMINISTIC", "THRESHOLD", "SEMANTIC"):
            v.append(f"#{i}: 알 수 없는 판정자 '{kind}' — 오타면 조용히 SKIP 된다")
    return v


def cmd_list() -> int:
    print("=" * 78)
    print("fz 계약 lint — 검사 항목 (본 스크립트가 SSOT)")
    print("=" * 78)
    for i, kind, target, desc in ITEMS:
        mark = {"DETERMINISTIC": "✅", "THRESHOLD": "⏸", "SEMANTIC": "👤"}[kind]
        print(f"{mark} #{i:<3s} [{kind:13s}] {target:8s} {desc}")
    d = sum(1 for _, k, _, _ in ITEMS if k == "DETERMINISTIC")
    t = sum(1 for _, k, _, _ in ITEMS if k == "THRESHOLD")
    s = sum(1 for _, k, _, _ in ITEMS if k == "SEMANTIC")
    print()
    print(f"총 {len(ITEMS)}항목 — DETERMINISTIC {d} / THRESHOLD {t}(SKIP) / SEMANTIC {s}(SKIP)")
    print("⏸ THRESHOLD = 임계/문법을 정하면 DETERMINISTIC 승격  ·  👤 SEMANTIC = 사람/모델 판정")
    print()
    print("exit: 0=위반 없음 · 1=위반 있음 · 2=configuration/parse error(⛔ PASS·SKIP 아님)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="fz 플러그인 계약 lint")
    ap.add_argument("--list", action="store_true", help="검사 항목 + 판정자 출력 (SSOT)")
    ap.add_argument("--only", help="쉼표 구분 항목 id만 실행 (예: 14,N4)")
    ap.add_argument("--self-test", action="store_true", help="양성 대조만 실행하고 종료")
    a = ap.parse_args()

    if a.list:
        return cmd_list()

    if not (ROOT / "guides").is_dir() or not (ROOT / "skills").is_dir():
        print(f"⛔ 플러그인 루트 해석 실패: {ROOT}", file=sys.stderr)
        return 2

    # ⛔ 양성 대조를 **항상** 선행한다 (Negative-Result Gate 요소1의 실체).
    #    `hits`는 *본 후보 수*라 패턴이 고장나도 0이 아니다 — 실제로 #15가 `head -n 5`를
    #    놓친 채 `OK [검사 대상 13]`을 냈다 (ISSUE-001·003). fixture 실패는 configuration error다.
    inv_fail = check_registry_invariants()
    if inv_fail:
        print("⛔ 레지스트리 구조 불변식 위반 (configuration error)", file=sys.stderr)
        for m in inv_fail:
            print(f"   {m}", file=sys.stderr)
        return 2

    it_fail = run_integration_tests()
    if it_fail:
        print("⛔ 통합 fixture 실패 — 검사기의 순회·수집이 고장났다", file=sys.stderr)
        for m in it_fail:
            print(f"   {m}", file=sys.stderr)
        return 2

    st_fail = run_self_tests()
    if st_fail:
        print("⛔ 양성 대조 실패 — 검사기가 고장났다 (결과를 '위반 0건'으로 읽지 말 것)", file=sys.stderr)
        for m in st_fail:
            print(f"   {m}", file=sys.stderr)
        return 2
    if a.self_test:
        print(f"양성 대조 {SELF_TEST_COUNT}건 + 통합 fixture {len(INTEG_EXPECT)}검사({sum(len(x) for x in INTEG_EXPECT.values())} 위치) 전부 통과")
        return 0

    only = {x.strip() for x in a.only.split(",")} if a.only else None
    if only:
        # ⛔ 오타 하나로 enforcement 전체가 조용히 무력해지던 결함 차단 (ISSUE-002):
        #    이전에는 `--only DOES_NOT_EXIST`가 검사 0개를 돌리고 "위반 0건" exit 0을 냈다.
        unknown = sorted(only - {i for i, _, _, _ in ITEMS})
        if unknown:
            print(f"⛔ 알 수 없는 --only 항목 id: {unknown} — `--list`로 확인", file=sys.stderr)
            return 2
        if not (only & DET):
            print(f"⛔ --only {sorted(only)}에 DETERMINISTIC 항목이 없다 — 검사 대상 0", file=sys.stderr)
            return 2

    violations, skipped, under_floor = [], [], []
    print("=" * 78)
    print(f"fz 계약 lint — root {ROOT}")
    print("=" * 78)

    for i, kind, target, desc in ITEMS:
        if only and i not in only:
            continue
        if kind != "DETERMINISTIC":
            skipped.append((i, kind, desc))
            continue
        try:
            v, hits = CHECKS[i]()
        except ParseError as e:
            print(f"⛔ #{i} configuration/parse error: {e}", file=sys.stderr)
            return 2
        except Exception as e:                                  # noqa: BLE001
            print(f"⛔ #{i} 예상 외 오류({type(e).__name__}): {e}", file=sys.stderr)
            return 2
        # ⛔ Negative-Result Gate 요소1 — 후보 수가 하한 미달이면 **순회·수집이 고장난 것**으로 본다
        floor = MIN_HITS.get(i)
        if floor is not None and hits < floor:
            under_floor.append((i, hits, floor))
        status = "OK  " if not v else f"FAIL({len(v)})"
        print(f"{status} #{i:<3s} {desc[:56]:<56s} [검사 대상 {hits}]")
        violations += [(i, x) for x in v]

    print()
    if skipped:
        print("── SKIP (스크립트 판정 대상 아님 — ⛔ PASS 아님)")
        for i, kind, desc in skipped:
            print(f"   ⏸ #{i:<3s} [{kind}] {desc[:70]}")
        print()
    if under_floor:
        print("⛔ 검사 대상 수가 하한 미달 — configuration error (Negative-Result Gate 요소1)",
              file=sys.stderr)
        for i, hits, floor in under_floor:
            print(f"   #{i}: 후보 {hits}개 < 하한 {floor}개", file=sys.stderr)
        print("   ⛔ 판별: 트리에서 대상이 정당하게 줄었는가(→ MIN_HITS 하향) "
              "아니면 순회·수집이 고장났는가(→ 코드 수정)? **결과를 '위반 0건'으로 읽지 말 것.**",
              file=sys.stderr)
        return 2
    if violations:
        print(f"── 위반 {len(violations)}건")
        cur = None
        for i, msg in violations:
            if i != cur:
                print(f"  #{i}")
                cur = i
            print(f"     {msg}")
        return 1
    print("위반 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
