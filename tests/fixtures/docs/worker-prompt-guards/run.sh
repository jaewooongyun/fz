#!/bin/bash
# 워커 프롬프트 가드 — 워커에게 가는 글(워크플로 OVERRIDE · 프롬프트 · 에이전트 본문)과 워크플로 목록 설명 · Lead 가 적용 전에 읽는 칸의
#   고친 결함이 다시 생기면 잡는다. 몇 조건은 손으로 적은 계약 표(tests/fixtures/docs/finding-contracts.tsv)에도 있지만 health-check 는 그 표의
#   자기 시험만 돌리고 표 자체는 대조하지 않는다 — 자동으로 도는 저장소 시험이 없어서 이 러너를 둔다
#   (health-check 가 tests/fixtures/*/*/run.sh 로 자동 실행한다).
# 셀:
#   collab-no-placeholder             workflows/plan-collaborative.js 에 '참조 허용:' 자리 표시 줄이 없다(가리키던 프롬프트 줄은 지웠다)
#   override-module-clause-live       OVERRIDE 블록(문자열 리터럴만 — 주석은 프롬프트가 아니다)이 '프롬프트가 허용한 모듈 문서' 를 말하면 같은
#                                     워크플로의 주석 밖 줄에 '참조 허용:' 이 있다 — 허용을 주는 줄 없이 남은 절은 죽은 절이다
#   override-scope-not-whole-task     workflows/*.js 의 OVERRIDE 블록마다 '이 콜의 과제 범위다' 가 있고 '과제의 전부다' 가 없다 — 하네스는 워커
#                                     프롬프트 앞에 사용자 요청을 싣는다. 플러그인 문장은 이 콜의 범위만 말하고 그 요청과 권위를 다투지 않는다
#   agent-body-no-doc-pointer         agents/*.md 의 frontmatter 뒤 본문에 modules · guides 아래 .md 포인터가 없다(frontmatter 주석은 본문이 아니다 —
#                                     워크플로 OVERRIDE 는 파일 접근을 프롬프트가 적은 경로로 좁힌다)
#   direct-agents-no-internal-worker  Lead 가 직접 부르는 에이전트 셋(memory-curator · review-correctness · search-pattern)에 '내부 워커' 가 없다 ·
#                                     대조: 나머지 에이전트 전부에 'fz 워크플로 내부 워커(' 가 있다(새 에이전트는 둘 중 하나로 분류된다)
#   code-open-questions-before-apply  skills/fz-code/SKILL.md 에 '적용 전에 `openQuestions`' 가 있다 — changeset 을 적용하기 전에 구현자의 의문을 읽는다
#   workflow-meta-internal            workflows/*.js 의 meta.description 마다 '직접 실행하지 않는다' 가 있다 — 플러그인 워크플로는 이름으로 자동 등록돼
#                                     목록에 보인다. 스킬이 인자를 준비해 부르는 내부 스크립트임을 그 설명이 말한다
#   plant-control                     셀마다 합성 문자열에 결함을 심으면 그 판정이 결함을 낸다 · 결함이 아닌 꼴(frontmatter 주석의 포인터 · 허용 줄이
#                                     있는 절 · 새 문장만 있는 OVERRIDE · 표지가 있는 설명)은 결함을 내지 않는다 — 판정이 헛돌지 않는다
# OVERRIDE 블록 · 리터럴은 scripts/check_wf_advisor_ban.py 의 같은 함수로 뗀다 — 두 검사가 블록을 다르게 읽지 않는다.
# ⛔ 트리에 쓰지 않는다 — 읽기만 한다. 합성 경로는 조각을 이어 만든다(계약 lint 의 깨진 참조 검사가 실제 참조로 읽지 않게).
# 출력: 셀마다 `<셀>: PASS|FAIL <이유>` · 끝에 `worker-prompt-guards: PASS|FAIL`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(python3 · 파일 부재 · 인자)
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 2; }
            ROOT="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 2; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 2 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 2; }
for f in scripts/check_wf_advisor_ban.py workflows/plan-collaborative.js skills/fz-code/SKILL.md; do
  [ -f "$ROOT/$f" ] || { echo "SETUP $f 없음: $ROOT"; exit 2; }
done

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" <<'PY'
import glob, importlib.util, os, re, sys
ROOT = sys.argv[1]
fails = []


def case(name, ok, why=""):
    print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" {why}"))
    if not ok:
        fails.append(name)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


spec = importlib.util.spec_from_file_location("wf_advisor_ban", os.path.join(ROOT, "scripts", "check_wf_advisor_ban.py"))
ban = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ban)

PLACEHOLDER = "참조 허용:"
MODULE_CLAUSE = "프롬프트가 허용한 모듈 문서"
SCOPE_NEW, SCOPE_OLD = "이 콜의 과제 범위다", "과제의 전부다"
DOC_POINTER = re.compile(r"(?:modules|guides)/[\w./-]*\.md")
INTERNAL_MARK, INTERNAL_WORD = "fz 워크플로 내부 워커(", "내부 워커"
DIRECT = ("memory-curator", "review-correctness", "search-pattern")
OPEN_Q = "적용 전에 `openQuestions`"
INTERNAL_RUN = "직접 실행하지 않는다"
META_DESC = re.compile(r"^\s*description:\s*'([^'\n]*)'", re.M)


def code_lines(text):
    return "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("//"))


def override_text(text):
    block = ban.override_block(text)
    return None if block is None else ban.literal_text(block)


def agent_body(text):
    """frontmatter(첫 줄 `---` 부터 다음 `---` 줄까지) 뒤 본문 — 경계가 없으면 None."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1:])
    return None


# ── 판정 — 결함 목록을 돌려준다(빈 목록 = 통과). 실제 트리와 아래 심기가 같은 함수를 지난다 ──
def p_placeholder(collab):
    return [PLACEHOLDER] if PLACEHOLDER in collab else []


def p_module_clause(wfs):
    return [n for n, t in sorted(wfs.items())
            if MODULE_CLAUSE in (override_text(t) or "") and PLACEHOLDER not in code_lines(t)]


def p_scope(wfs):
    bad = []
    for n, t in sorted(wfs.items()):
        o = override_text(t)
        if o is None:
            bad.append(f"{n}: OVERRIDE 상수 없음")
        elif SCOPE_OLD in o:
            bad.append(f"{n}: '{SCOPE_OLD}'")
        elif SCOPE_NEW not in o:
            bad.append(f"{n}: '{SCOPE_NEW}' 없음")
    return bad


def p_doc_pointer(agents):
    bad = []
    for n, t in sorted(agents.items()):
        b = agent_body(t)
        m = None if b is None else DOC_POINTER.search(b)
        if b is None:
            bad.append(f"{n}: frontmatter 경계 없음")
        elif m:
            bad.append(f"{n}: {m.group(0)}")
    return bad


def p_direct(agents):
    bad = [f"{n}: 파일 없음" for n in DIRECT if n not in agents]
    bad += [f"{n}: '{INTERNAL_WORD}'" for n in DIRECT if INTERNAL_WORD in agents.get(n, "")]
    internal = sorted(n for n in agents if n not in DIRECT)
    if not internal:
        bad.append("대조할 내부 워커 0개")
    bad += [f"{n}: '{INTERNAL_MARK}' 없음" for n in internal if INTERNAL_MARK not in agents[n]]
    return bad


def p_open_q(code_skill):
    return [] if OPEN_Q in code_skill else [f"'{OPEN_Q}' 없음"]


def p_meta(wfs):
    """`export const meta` 블록(다음 줄 머리 `}` 까지)의 description 리터럴 값에 표지가 있어야 한다 — 주석의 낱말은 세지 않는다."""
    bad = []
    for n, t in sorted(wfs.items()):
        k = t.find("export const meta")
        m = None if k < 0 else META_DESC.search(t[k:t.find("\n}", k)])
        if m is None:
            bad.append(f"{n}: meta.description 없음")
        elif INTERNAL_RUN not in m.group(1):
            bad.append(f"{n}: '{INTERNAL_RUN}' 없음")
    return bad


# ── 실제 트리 ──
wfs = {os.path.basename(p): read(p) for p in sorted(glob.glob(os.path.join(ROOT, "workflows", "*.js")))}
agents = {os.path.basename(p)[:-3]: read(p) for p in sorted(glob.glob(os.path.join(ROOT, "agents", "*.md")))}
if not wfs or not agents:
    print(f"SETUP 워크플로 {len(wfs)}개 · 에이전트 {len(agents)}개 — 검사 대상 0개는 통과가 아니다: {ROOT}")
    sys.exit(2)
show = lambda bad: " · ".join(bad[:4]) + (f" 외 {len(bad) - 4}" if len(bad) > 4 else "")
bad = p_placeholder(wfs.get("plan-collaborative.js", ""))
case("collab-no-placeholder", not bad, show(bad))
bad = p_module_clause(wfs)
case("override-module-clause-live", not bad, "허용 줄 없는 절: " + show(bad))
bad = p_scope(wfs)
case("override-scope-not-whole-task", not bad, f"워크플로 {len(wfs)}개 중 " + show(bad))
bad = p_doc_pointer(agents)
case("agent-body-no-doc-pointer", not bad, show(bad))
bad = p_direct(agents)
case("direct-agents-no-internal-worker", not bad, show(bad))
bad = p_open_q(read(os.path.join(ROOT, "skills", "fz-code", "SKILL.md")))
case("code-open-questions-before-apply", not bad, show(bad))
bad = p_meta(wfs)
case("workflow-meta-internal", not bad, f"워크플로 {len(wfs)}개 중 " + show(bad))

# ── 심기 대조 — (이름, 결함을 심은 입력의 판정, 결함이 아닌 꼴의 판정 또는 None) ──
MOD, GUIDE = "modules" + "/", "guides" + "/"
ovr = lambda s, tail="": "const OVERRIDE =\n  '[합성 오버라이드] ' +\n  '" + s + "'\n" + tail
allow = "  `(" + PLACEHOLDER + " {플러그인 루트}/" + MOD + "synthetic-scan.md — 합성)\\n` +\n"
clause = "파일 접근은 명시된 경로와 그 안에 나열된 파일, 그리고 " + MODULE_CLAUSE + "만. "
scope_ok = "이 프롬프트의 [합성 입력]이 " + SCOPE_NEW + ". "
fm = "---\nname: synthetic\ndescription: >-\n  합성 에이전트.\n# 합성 주석: " + MOD + "synthetic-note.md\n---\n\n## Role\n\n"
quiet = {n: "합성 직접 호출 에이전트." for n in DIRECT}
meta = lambda desc, extra="": "export const meta = {\n  name: 'synthetic',\n" + extra + "  description: '" + desc + "',\n}\n"
plants = [
    ("collab-placeholder", p_placeholder("const P = `" + allow + "`\n"), p_placeholder("const P = `[역할] 합성`\n")),
    ("dead-module-clause", p_module_clause({"a.js": ovr(clause)}), p_module_clause({"b.js": ovr(clause, "const P = `" + allow + "`\n")})),
    ("module-clause-allow-only-in-comment", p_module_clause({"a.js": ovr(clause, "// " + allow)}), None),
    ("scope-old-sentence", p_scope({"a.js": ovr("이 프롬프트의 [합성 입력]만이 " + SCOPE_OLD + ". ")}), p_scope({"b.js": ovr(scope_ok)})),
    ("scope-both-sentences", p_scope({"a.js": ovr(scope_ok + "[합성 입력]만이 " + SCOPE_OLD + ". ")}), None),
    ("scope-new-only-in-comment", p_scope({"a.js": "const OVERRIDE =\n  '[합성 오버라이드] ' +\n  // " + SCOPE_NEW + "\n  '끝.'\n"}), None),
    ("scope-no-override", p_scope({"a.js": "const X = 1\n"}), None),
    ("agent-body-pointer", p_doc_pointer({"s": fm + "자세한 것은 " + GUIDE + "synthetic-guide.md 를 읽는다.\n"}), p_doc_pointer({"s": fm + "합성 본문.\n"})),
    ("agent-no-frontmatter", p_doc_pointer({"s": "## Role\n\n합성 본문.\n"}), None),
    ("direct-agent-marked-internal", p_direct({**quiet, "memory-curator": INTERNAL_MARK + "합성) — 직접 쓰지 않는다.", "x": INTERNAL_MARK + "합성)"}),
     p_direct({**quiet, "x": INTERNAL_MARK + "합성)"})),
    ("internal-agent-unmarked", p_direct({**quiet, "x": "합성 워커."}), None),
    ("code-open-questions-missing", p_open_q("4. **changeset 적용 (Lead)**: 합성 절차.\n"), p_open_q("4. 합성: " + OPEN_Q + " 를 읽는다.\n")),
    ("meta-unmarked", p_meta({"a.js": meta("합성 워크플로 — 3콜")}), p_meta({"b.js": meta("fz-x 내부 — fz-x 스킬이 인자를 준비해 부른다. " + INTERNAL_RUN)})),
    ("meta-mark-only-in-comment", p_meta({"a.js": meta("합성 워크플로 — 3콜", "  // " + INTERNAL_RUN + "\n")}), None),
]
missed = [n for n, defect, clean in plants if not defect or (clean is not None and clean)]
case("plant-control", not missed, "놓치거나 잘못 잡은 심기: " + ", ".join(missed))

print(f"worker-prompt-guards: {'FAIL' if fails else 'PASS'}" + (f" ({', '.join(fails)})" if fails else ""))
sys.exit(1 if fails else 0)
PY
