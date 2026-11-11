#!/usr/bin/env python3
"""check_comment_worthy.py — 큐레이션한 리뷰(review.json 에 `excluded` 키)의 코멘트 가치 계약 검사 (Curate · D1~D4).

왜: 피어 리뷰가 후보를 거의 다 코멘트로 올렸다 — 도달 경로 없는 추론 · SDK 내부 가정 · 이미 달린 스레드 중복 · 원래 있던 문제까지.
Curate 는 후보마다 "코멘트 | 제외(E1~E8)" 를 고르게 하고, 이 검사기가 그 결과를 기계로 본다(문서 규칙만으로는 발화하지 않았다 — F-285).

issue(코멘트할 것) 필수:
  kind             bug | structure | quality | intent-question
  evidence[]       하나 이상이 `path:line[-line]@sha` — sha 는 review.json `target.sha`(gather 의 target.json · PR 이면 headRefOid)의 접두
                   (`pr.headSha` 는 게시 메타일 뿐이다 — 브랜치 대상은 pr 이 없다)
  bug              repro{status: reproduced | code-determined, how} · symptom_screen · symptom_reach
  structure|quality measure(관례 표본 N:M 필수 — 이번 형태 N : 다른 형태 M 을 센 수 · 중복 줄 수 · 결함 위험은 덧붙인다 ·
                   측정값 없는 구조 제안은 E3 · N:M 이 없으면 위반 — 어느 쪽이 관례인지 세지 않은 비대칭 지적이다(F-053))
  major 이상       chain[{step, grade: code | comment | inference}] — 인과 체인을 단계로 쪼개 근거 종류를 단다. 주석 · 추론 단계가
                   하나라도 있으면 major 이상 불가(F-116 — 주석 인용 단계 위에 선 major 가 회수됐다)
                   severity_basis{kind: output-change | path-only | zero-cases, note} — 무게의 근거. path-only(경로만) ·
                   zero-cases(사례 0) 면 major 이상 불가(F-090 — 사실 게이트는 9개인데 무게 게이트가 0개였다)
  제안 식별자      suggestion · comment 의 백틱 · 코드 펜스 안 식별자가 review.json 폴더 head/ · base/ · diff.patch 어디에도 없으면
                   위반 — 새로 만드는 심볼이면 symbol_notes{이름: new}, SDK 심볼이면 {이름: sdk}(F-063 — 없는 메서드를 부르는
                   제안이 나갔다). head/ 가 없으면 대조하지 않고 info 줄에 적는다
  origin           regression · improvement 중 하나(pre-existing 은 E4 로 제외 · 리포트 ④ · 그 밖 표기는 위반 — F-037 우회 차단)
  base_evidence    origin=regression 이면 `path:line@sha` — sha 는 review.json meta.base_sha 이고, meta.base_sha 는 review.json 폴더의
                   base-sha.txt(gather 가 base/ 를 뜬 커밋)와 같다. 그 파일이 없으면 판정 불가(exit 2) · head · 로컬 develop sha 는 위반(F-037)
  base_quote       origin=regression 이면 base 원문 인용(그 줄의 코드) — 위치만으로는 base 를 열어 봤다는 증거가 아니다(F-037).
                   review.json 폴더에 base/<path> 가 있으면 base_evidence 줄 ±2 안에 그 인용이 있어야 한다(공백 정규화)
  suggestion       있다(조치 없는 지적은 E6) — intent-question 은 질문이 조치라 면제
  refute           재검증 기록(반박 시도와 결과)
  comment          코드 펜스 밖 산문 ≤ 4줄 · 마무리 어조(…부탁드립니다 · …여쭙습니다 · ?)가 없으면 WARN(차단 아님)
  duplicateOf      있으면 위반 — 중복은 E5 로 제외한다
  기존 스레드      existing-threads.json(status ok)에 같은 path ±3줄 스레드가 있으면 duplicateOf(→ 제외) 또는 distinctFrom[{thread, why}]
excluded[]       {id, what, code E1~E8, reason} · E5 = duplicateOf(+선택 reply 답글 초안) · E8 = refute
strengths        string[] 그대로 · 원소마다 strengthGaps[{claim(= 그 강점), uncovered(그 강점이 못 막는 시나리오 — 비지 않음)}](F-117 · F-517)
  E1 도달 경로 미확인(코드 경로만 있음)       E2 SDK · 바이너리 내부 동작 가정       E3 결함 없는 설계 선호(측정값 없음)
  E4 원래 있던 문제 — 리포트 ④ 참고          E5 기존 스레드와 중복(스레드 id)        E6 작성자가 할 조치가 없음
  E7 작업 트리에서 읽은 사실(대상 SHA 아님)   E8 재검증에서 반박됨(반박 근거 인용)
risk.json 슬롯   review.json 폴더 risk.json(gather)의 plugin_refs 가 비지 않으면 pluginRefsRead[{plugin, refs}] 가 플러그인마다(F-520) ·
                 runtime_axes 가 비지 않으면 runtimeAxes[{axis, how: probe | gpt | none, note}] 가 축마다(none 은 note 사유 · F-258).
                 risk.json 이 없거나 판독 불가면 대조하지 않는다(info)
커버리지         candidates(review.json `candidates` 가 가리키는 merged.json `candidates[].id` ∪ synthesized `issues[].id`)
                 ⊆ issues ∪ excluded ∪ covers. covers: 대상 id 는 candidates 에 실재 · 한 후보는 소유자 하나 · 소유자 id 는 covers 대상이 아니다.
                 excluded 의 covers 는 묶음 제외다(대상 id 를 모두 적는다)
GPT 패스         review.json 옆 `gpt-independent/` 가 있는데(GPT 독립 패스가 돌았다) merged.json 이 candidates 에 없으면 판정 불가 —
                 review.json `gptPass` 가 있으면 폴더보다 선언이 먼저다 — `independent` 면 merged.json 필수 · `challenger` · `none` 이면 묻지 않는다

사용: check_comment_worthy.py REVIEW_JSON   (렌더러 render_review.py 가 `check_review()` 를 import 한다)
exit: 0 PASS · 1 VIOLATION · 2 UNRUN(파일 · target · 후보 원본 부재 — ⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from check_synthesized import normalize  # noqa: E402 — 두 생산자 모양을 같은 규칙으로 읽는다(F-530)
try:                                                       # 공용 토크나이저(F-458) — JS 템플릿 보간식 경계를 정한다
    import shell_tokens  # noqa: E402
except Exception:                                          # noqa: BLE001 — 권한 · 구문 오류도 같다
    shell_tokens = None

KINDS = ("bug", "structure", "quality", "intent-question")
ORIGINS = ("regression", "pre-existing", "improvement")    # workflows/peer-review.js finding 스키마 origin enum 과 같다
CODES = tuple(f"E{n}" for n in range(1, 9))
REPRO = ("reproduced", "code-determined")
EVIDENCE_RE = re.compile(r"(?s)^(?P<path>.+):(?P<a>\d+)(?:-(?P<b>\d+))?@(?P<sha>[0-9a-f]{7,40})$")   # 경로는 공백 · @ · : 를 가질 수 있다 — 끝의 :줄@sha 만 떼어 낸다
CLOSING_RE = re.compile(r"(?:(?:부탁드립니다|여쭙습니다)[.!]?|\?)\s*$")
NEAR = 3
SHA_RE = re.compile(r"[0-9a-f]{7,40}\Z")
MAJOR_UP = ("critical", "major")
CHAIN_GRADES = ("code", "comment", "inference")
BASIS_KINDS = ("output-change", "path-only", "zero-cases")
NM_RE = re.compile(r"\d+\s*:\s*\d+")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# 제안 코드 식별자 대조에서 빼는 말 — 언어 키워드 · 흔한 표준 타입(트리에 없어도 실재한다). 그 밖 SDK 심볼은 symbol_notes 로 선언한다
CODE_WORDS = frozenset(
    "let var guard else return self Self func nil true false if for in case switch default weak unowned lazy private fileprivate "
    "internal public open static final class struct enum protocol extension import init deinit some any where throws rethrows try "
    "catch do defer while repeat break continue inout override mutating typealias associatedtype get set willSet didSet super is as "
    "await async actor Task MainActor escaping autoclosure discardableResult objc String Int Bool Double Float Array Dictionary Set "
    "Optional Void Any AnyObject Error Result print "
    # 다른 지원 언어(Kotlin · Java · JS/TS · Python · ObjC)의 키워드 · 리터럴 — 트리에 없어도 문법이다
    "new throw function const def val fun null undefined this from export interface implements extends package void "
    "int long char boolean None True False pass lambda yield raise except finally with not and elif then of typeof "
    "instanceof delete object when sealed companion suspend "
    # Java · Kotlin · TS · Python 수식어 · 선언어 · 기본 타입(F-063 리뷰 — 제안 코드의 문법 낱말을 없는 심볼로 요구했다)
    "protected abstract synchronized volatile transient native strictfp assert byte short float double goto "
    "data inline reified lateinit vararg tailrec operator infix crossinline noinline annotation Unit Nothing "
    "readonly declare namespace module type keyof infer unknown never global nonlocal del cls string number bigint symbol constructor".split())
# 제안 코드의 문자열 · 주석은 식별자가 아니다 — 한 번에 훑어 먼저 시작한 쪽을 지운다(문자열 속 `//` 를 주석으로 보지 않는다).
# 문자열: 큰 · 작은따옴표와 JS 템플릿(백틱). 주석: `//` · `/* */` · 뒤에 공백이 오는 `#`(Python · 셸) — `#if` · `#selector` 는 Swift 지시어라 남긴다
_LEX_S = r'(?P<s>"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`)'
CODE_LEXEME = re.compile(_LEX_S + r'|(?P<c>//[^\n\r\u2028\u2029]*|/\*.*?\*/|(?<![\w#])#(?=[ \t]|$)[^\n]*)', re.S | re.M)   # JS 줄 주석은 CR · U+2028 · U+2029 에서도 끝난다
# 펜스 언어가 `#` 주석 언어면 `#` 은 붙어 있어도 주석이다(`#Connection refused`)
CODE_LEXEME_HASH = re.compile(_LEX_S + r'|(?P<c>//[^\n\r\u2028\u2029]*|/\*.*?\*/|#[^\n]*)', re.S | re.M)
HASH_LANGS = {"python", "py", "sh", "bash", "zsh", "shell", "console", "ruby", "rb", "yaml", "yml", "toml", "perl", "r"}


UNLEXED = "__fz_unlexed_template__"   # 못 읽은 템플릿 자리 — 트리에 없는 이름이라 미지 심볼로 걸린다(fail-open 아님)
REGEX_PREFIX_WORDS = frozenset(("typeof", "instanceof", "in", "of", "new", "delete", "void", "return", "throw", "case", "do", "else", "yield", "await"))
# 정규식 리터럴(`/…/`)을 따지는 펜스 언어 — 언어 표시 없는 펜스 · 인라인 코드 · 산문 꼴 펜스의 `/`(경로 · `A/B`)까지 정규식 위험으로 보면
# 코드 펜스의 4분의 1이 못 읽음이 됐다(실사용 대조 — scripts/judge_corpus_diff.py fence). 그 밖 언어의 `//` 든 정규식 뒤 심볼은 주석으로 읽혀
# 빠질 수 있다 — 과잉 거부 쪽 대가가 커서 받아들인 한계다
REGEX_LANGS = frozenset(("js", "javascript", "ts", "typescript", "jsx", "tsx", "mjs", "cjs"))
REGEX_PAREN_WORDS = frozenset(("if", "while", "for", "with"))   # 이 낱말의 조건 괄호 뒤 `/` 는 정규식 리터럴이다(`if (x) /re/`)


def _division(prev: str) -> bool:
    """`prev` 바로 뒤의 `/` 가 나눗셈인가 — 피연산자(식별자 · 숫자 · `]` · 문자열 끝 · 짝이 조건 괄호가 아닌 `)`) 뒤다."""
    if prev[-1:] in ("]", '"', "'", "`"):
        return True
    word = re.search(r"[A-Za-z0-9_$]+$", prev)
    if word is not None:
        return word.group(0) not in REGEX_PREFIX_WORDS
    if prev[-1:] != ")":
        return False
    depth = 0
    for i in range(len(prev) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(prev[i], 0)
        if depth == 0:
            kw = re.search(r"(?:\bfor\s+await|([A-Za-z_$][A-Za-z0-9_$]*))\s*$", prev[:i])   # `for await (…)` 도 조건 괄호다
            return not (kw and (kw.group(1) is None or kw.group(1) in REGEX_PAREN_WORDS))
    return False                                          # 짝 `(` 를 못 찾았다 — 정규식일 수 있다(보수)


def _regex_start(prev: str) -> bool:
    """`prev` 바로 뒤의 `/` 가 확실히 정규식 리터럴의 시작인가 — 본문을 지워도 되는 자리만 본다. `_division` 의 False 는 '정규식일 수
    있다' 는 보수 답이라(`}` · `++` 뒤도 False) 지우는 근거가 못 된다 — 지우면 나눗셈 사이 식별자가 사라진다(fail-open)."""
    p = prev.rstrip()
    word = re.search(r"[A-Za-z0-9_$]+$", p)
    if word is not None and p[:word.start()].rstrip().endswith("."):
        return False                                      # `obj.return / x /` — 속성 이름은 키워드가 아니다(피연산자 뒤 나눗셈)
    return not p or p[-1] in "=(,:[!?;&|{" or (word is not None and word.group(0) in REGEX_PREFIX_WORDS)


def _regex_risk(before: str, gap: str, tail: bool = False, spans=None) -> bool:
    """바깥 JS 코드의 홀로 선 `/` 가 렉심 경계를 넘는 정규식 리터럴일 수 있는가 — 그 안의 `//` · `/*` · 따옴표를 주석 · 문자열로 읽으면
    뒤 템플릿의 보간식이 통째로 사라진다(`/[//]/` · r3 4차 ISSUE-005). 나눗셈 자리(`_division`)는 보지 않는다. 정규식으로 읽어도 몸이
    `gap` 안 같은 줄에서 닫히면 그 몸에는 주석 · 문자열 시작이 없다(있었다면 `gap` 이 거기서 끊겼다) — 줄이 먼저 끝나면 정규식이 아니다.
    몸이 `gap` 끝(다음 렉심)까지 이어질 때만 위험이다 — 코드 끝(`tail`)이면 가릴 것이 없다. 닫힌 몸의 닫는 `/` 는 다시 여는 `/` 로
    보지 않는다(`/\d+/` 의 닫는 `/` 앞 `+` 가 정규식 시작 자리로 읽히던 과잉 거부 · r3 8.5 2차)."""
    k = gap.find("/")
    while k >= 0:
        if _division((before + gap[:k]).rstrip()):
            k = gap.find("/", k + 1)
            continue
        j, cls = k + 1, False
        while j < len(gap) and gap[j] not in "\n\r  ":
            c = gap[j]
            if c == "\\":
                j += 2
                continue
            if cls:
                cls = c != "]"
            elif c == "[":
                cls = True
            elif c == "/":
                break
            j += 1
        if j >= len(gap) and not tail:
            return True
        if spans is not None and j < len(gap) and gap[j] == "/" and _regex_start(before + gap[:k]):
            e = re.match(r"[a-z]*", gap[j + 1:]).end()
            spans.append((k, j + 1 + e))                  # 닫힌 정규식 리터럴(플래그 포함) — 본문은 패턴 글자다(식별자가 아니다)
        k = gap.find("/", j + 1)
    return False


def _strip_lexemes(code: str, hash_comments: bool, regex: bool = False) -> str:
    """문자열 · 주석을 지운다 — JS 템플릿은 정적 글자만 지우고 실행되는 `${…}` 는 남긴다(보간식의 미지 함수도 대조한다).

    템플릿의 끝과 보간식 경계는 공용 토크나이저가 정한다(F-458) — 중첩 중괄호(`${wrap({}) + missingHelper()}`) · 보간식 안
    문자열 · 템플릿을 따라간다. 보간식은 같은 규칙으로 다시 벗긴다 — 그 안의 문자열(`${"Connection refused"}`)은 심볼이 아니다.
    ⛔ 못 읽으면(닫히지 않은 보간식 · 토크나이저 없음) `UNLEXED` 를 남긴다 — 정규식 추출로 돌아가 미지 함수를 흘리지 않는다."""
    rx, out, i = CODE_LEXEME_HASH if hash_comments else CODE_LEXEME, [], 0

    def gap(text, tail=False):                           # 정규식 리터럴은 JS 계열 펜스만 따진다(REGEX_LANGS)
        spans = []
        risky = regex and not hash_comments and _regex_risk("".join(out), text, tail, spans)
        for a, b in reversed(spans):
            text = text[:a] + '""' + text[b:]
        out.append(text + (" " + UNLEXED + " " if risky else ""))
    while True:
        m = rx.search(code, i)
        if not m:
            gap(code[i:], tail=True)
            return "".join(out)
        gap(code[i:m.start()])
        s = m.group("s")
        if not s:
            out.append(" ")
            i = m.end()
        elif not s.startswith("`"):
            out.append('""')
            i = m.end()
        else:
            r = shell_tokens.js_template(code, m.start()) if shell_tokens is not None else None
            if r is None or shell_tokens.is_unknown(r):
                out.append('"" ' + UNLEXED + " ")
                i = m.end()
            else:
                out.append('""' + "".join(" " + _strip_lexemes(e, hash_comments, regex) for e in r[1]))
                i = r[0]


REPO_ROOT_FILE = "repo-root.txt"   # gather.sh 가 적은 저장소 루트 — head/ · base/ 는 바뀐 파일만이라 그 밖 식별자는 대상 sha 전체에서 찾는다
BASE_SHA_FILE = "base-sha.txt"   # gather.sh 가 base/ 를 실제로 떠 온 커밋 — review.json 폴더(target.json 과 같은 자리)


def _same_sha(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def _txt(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def prose_lines(comment: str) -> list:
    out, fence = [], False
    for ln in comment.splitlines():
        if ln.strip().startswith("```"):
            fence = not fence
            continue
        if not fence and ln.strip():
            out.append(ln.strip())
    return out


def load_candidates(review: dict, base: pathlib.Path):
    """(후보 id 집합, 출처 목록, UNRUN 사유 | None)."""
    srcs = review.get("candidates")
    if not isinstance(srcs, list) or not srcs or not all(isinstance(s, str) and s for s in srcs):
        return None, [], "candidates(후보 원본 파일 목록 — merged.json · synthesized-issues.json)가 없다"
    ids, used = set(), []
    for rel in srcs:
        p = base / rel
        if not p.is_file():
            return None, used, f"후보 원본 {rel} 이 없다 — 어떤 후보가 처분됐는지 판정할 수 없다"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return None, used, f"후보 원본 {rel} 을 읽지 못했다 — {type(e).__name__}"
        shape, items, problems = normalize(data)
        if shape is None:
            return None, used, f"후보 원본 {rel} 의 모양을 모른다(issues[] · candidates[] 없음)"
        if problems:   # 깨진 후보를 버리고 남은 것만 세면 커버리지가 그 후보를 놓친다
            return None, used, f"후보 원본 {rel} 에 판정할 수 없는 항목 — {problems[0]}"
        ids |= {str(x["id"]) for x in items}
        used.append(rel)
    # 이번 실행의 GPT 경로를 review.json `gptPass` 로 밝혔으면(challenger · none) 남은 gpt-independent/ 로 병합본을 요구하지 않는다 —
    # 같은 작업 폴더에서 독립 패스 뒤 challenger 로 다시 돌린 경우다. 밝히지 않았으면 폴더가 안전망이다
    merged = any(pathlib.PurePath(r).name == "merged.json" for r in used)
    if review.get("gptPass") == "independent" and not merged:   # 선언이 폴더보다 먼저다
        return None, used, "gptPass=independent 인데 merged.json 이 후보 원본에 없다 — GPT 전용 후보의 처분을 볼 수 없다"
    if review.get("gptPass") not in ("challenger", "none", "independent") and (base / "gpt-independent").is_dir() and not merged:
        return None, used, "GPT 독립 패스가 돌았는데(gpt-independent/) merged.json 이 후보 원본에 없다 — GPT 전용 후보의 처분을 볼 수 없다"
    return ids, used, None


def threads_of(base: pathlib.Path):
    """(스레드 목록 | None, 대조 줄)."""
    p = base / "existing-threads.json"
    if not p.is_file():
        return None, "기존 스레드 대조 불가 — existing-threads.json 없음"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"기존 스레드 대조 불가 — existing-threads.json 읽기 실패({type(e).__name__})"
    st = d.get("status")
    if st != "ok":
        return None, f"기존 스레드 대조 불가 — status {st}" + (f" · {d.get('reason')}" if d.get("reason") else "")
    cs = [c for c in d.get("comments") or [] if isinstance(c, dict)]
    return cs, f"기존 스레드 {len(cs)}개와 대조"


def _norm(s: str) -> str:
    return " ".join(s.split())


def base_quote_misses(base: pathlib.Path, ms: list, quote: str) -> list:
    """base/<path> 가 있으면 base_evidence 줄 ±2 안에 인용이 있어야 한다. 파일이 없으면 대조하지 않는다(gather 는 바뀐 파일만 뜬다)."""
    out = []
    for m in ms:
        f = base / "base" / m["path"]
        if not f.is_file():
            continue
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        a = int(m["a"])
        b = int(m["b"] or m["a"])
        window = _norm(" ".join(lines[max(0, a - 3):b + 2]))
        if _norm(quote) not in window:
            out.append(f"base_quote 가 base/{m['path']}:{a}-{b}(±2) 원문에 없다 — 열어 본 줄을 그대로 인용한다(F-037)")
    return out


def code_idents(text: str) -> set:
    """백틱 · 코드 펜스 안의 식별자(3글자 이상 · 키워드 · 흔한 표준 타입 제외)."""
    fences = [(m.group(1).lower(), m.group(2)) for m in re.finditer(r"```(\w*)(.*?)```", text, re.S)]
    ticks = [("", s) for s in re.findall(r"`([^`\n]+)`", re.sub(r"```.*?```", " ", text, flags=re.S))]
    ids = {x for lang, s in fences + ticks for x in IDENT_RE.findall(_strip_lexemes(s, lang in HASH_LANGS, lang in REGEX_LANGS))}
    return {x for x in ids if len(x) > 2 and x not in CODE_WORDS}


def tree_idents(base: pathlib.Path):
    """head/ · base/ · diff.patch 의 식별자 집합. head/ 가 없으면 None — 대조하지 않는다."""
    if not (base / "head").is_dir():
        return None
    out = set()
    for root in ("head", "base"):
        for f in sorted((base / root).rglob("*")) if (base / root).is_dir() else []:
            if f.is_file():
                out |= set(IDENT_RE.findall(f.read_text(encoding="utf-8", errors="replace")))
    if (base / "diff.patch").is_file():
        out |= set(IDENT_RE.findall((base / "diff.patch").read_text(encoding="utf-8", errors="replace")))
    return out


def repo_has(base: pathlib.Path, sha: str, names) -> set | None:
    """스냅샷에 없는 식별자를 대상 sha 의 전체 트리에서 찾는다 — 찾은 이름 집합. 저장소 · sha 를 못 쓰면 None(미검증)."""
    try:
        root = (base / REPO_ROOT_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    found = set()
    for n in names:
        p = subprocess.run(["git", "-C", root, "grep", "-q", "-w", "-F", "-e", n, sha, "--"], capture_output=True)
        if p.returncode == 0:
            found.add(n)
        elif p.returncode != 1:            # 1 = 없음 · 그 밖(128 등) = 저장소 · sha 를 못 씀
            return None
    return found


RUNTIME_HOW = ("probe", "gpt", "none")


def risk_slots(review: dict, base: pathlib.Path, info: dict) -> list:
    """gather risk.json 의 표지(plugin_refs · runtime_axes)마다 review.json 에 처리 기록이 있는가(F-520 · F-258)."""
    try:
        risk = json.loads((base / "risk.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info.setdefault("risk_slots", "risk.json 없음 · 판독 불가 — 표지 슬롯을 대조하지 않았다")
        return []
    out = []
    refs = risk.get("plugin_refs") if isinstance(risk.get("plugin_refs"), dict) else {}
    read = {str(x.get("plugin")) for x in review.get("pluginRefsRead") or [] if isinstance(x, dict) and x.get("refs")}
    miss = sorted(set(refs) - read)
    if miss:
        out.append(f"risk.json plugin_refs {', '.join(miss)} 를 읽은 기록이 없다 — pluginRefsRead[{{plugin, refs}}](F-520)")
    axes = risk.get("runtime_axes") if isinstance(risk.get("runtime_axes"), list) else []
    done = {str(x.get("axis")) for x in review.get("runtimeAxes") or []
            if isinstance(x, dict) and x.get("how") in RUNTIME_HOW and (x.get("how") != "none" or _txt(x.get("note")))}
    miss = sorted(set(map(str, axes)) - done)
    if miss:
        out.append(f"risk.json runtime_axes {', '.join(miss)} 의 처리 기록이 없다 — runtimeAxes[{{axis, how: {' | '.join(RUNTIME_HOW)}, note}}](none 은 사유 · F-258)")
    return out


def check_review(review: dict, base: pathlib.Path):
    """(code, 위반 목록, WARN 목록, 정보 {thread_line, candidates})."""
    bad, warn = [], []
    info = {"thread_line": "", "candidates": 0}
    tgt = review.get("target")
    sha = _txt(tgt.get("sha")).lower() if isinstance(tgt, dict) else ""
    if len(sha) < 7:
        return UNRUN, ["target.sha 가 없다 — evidence 의 @sha 를 대조할 기준이 없다(gather 의 target.json 을 review.json target 으로)"], warn, info
    cands, _, why = load_candidates(review, base)
    if why:
        return UNRUN, [why], warn, info
    info["candidates"] = len(cands)
    threads, info["thread_line"] = threads_of(base)
    tree = tree_idents(base)
    bad.extend(risk_slots(review, base, info))
    issues = [i for i in review.get("issues") or [] if isinstance(i, dict)]
    excluded = review.get("excluded")
    if not isinstance(excluded, list):
        return VIOLATION, ["excluded 가 배열이 아니다"], warn, info
    # ⛔ regression 은 base 커밋에서 보인 근거가 필요하다(F-037) — evidence(@head)만으로는 '원래 없었다' 를 증명하지 못하고,
    #    base 를 낡은 로컬 develop 으로 읽으면 틀린 근거로 충족된다(F-240). 기준은 gather 가 base/ 를 뜬 커밋 하나다
    regress = [i for i in issues if i.get("origin") == "regression"]
    if regress:
        try:
            base_sha = (base / BASE_SHA_FILE).read_text(encoding="utf-8").strip().lower()
        except OSError:
            return UNRUN, [f"regression 이슈 {len(regress)}건인데 {BASE_SHA_FILE} 가 없다 — base 근거를 대조할 기준이 없다(gather 산출물)"], warn, info
        if not SHA_RE.match(base_sha):
            return UNRUN, [f"{BASE_SHA_FILE} 가 커밋 sha 꼴이 아니다 — {base_sha[:20]!r}"], warn, info
        meta = review.get("meta") if isinstance(review.get("meta"), dict) else {}
        msha = _txt(meta.get("base_sha")).lower()
        if not SHA_RE.match(msha):
            bad.append("meta.base_sha 가 없거나 커밋 sha 꼴이 아니다 — regression 근거의 기준 커밋")
        elif not _same_sha(msha, base_sha):
            bad.append(f"meta.base_sha {msha[:12]} ≠ {BASE_SHA_FILE} {base_sha[:12]} — gather 가 base/ 를 뜬 커밋이 아니다(F-037)")
        for i in regress:
            be = i.get("base_evidence")
            bes = [be] if isinstance(be, str) else ([x for x in be if isinstance(x, str)] if isinstance(be, list) else [])
            ms = [m for m in (EVIDENCE_RE.match(x.strip()) for x in bes) if m]
            if not ms:
                bad.append(f"{i.get('id')}: regression 은 base_evidence(`path:line@base-sha`)가 필요하다 — base 커밋에서 없던 것을 보인다(F-037)")
            elif not any(_same_sha(m["sha"].lower(), base_sha) for m in ms):
                bad.append(f"{i.get('id')}: base_evidence @sha 가 base {base_sha[:12]} 가 아니다 — head · 로컬 develop 근거는 regression 을 증명하지 못한다")
            q = _txt(i.get("base_quote"))
            if not q:
                bad.append(f"{i.get('id')}: regression 은 base_quote(base 원문 인용 — 그 줄의 코드)가 필요하다 — 위치만으로는 base 를 열어 봤다는 증거가 아니다(F-037)")
            elif ms:
                bad.extend(f"{i.get('id')}: {w}" for w in base_quote_misses(base, ms, q))
    # 강점은 string[] 그대로 · 원소마다 그 강점이 못 막는 시나리오(strengthGaps)를 둔다(F-117 · F-517)
    if "strengths" in review:
        st = review.get("strengths")
        if not isinstance(st, list) or not all(isinstance(s, str) for s in st):
            bad.append("strengths 는 string[] 이다 — 못 막는 시나리오는 strengthGaps[{claim, uncovered}] 에 둔다")
        else:
            gaps_raw = review.get("strengthGaps")
            if gaps_raw is not None and not isinstance(gaps_raw, list):
                bad.append("strengthGaps 가 배열이 아니다")
            gaps = {g["claim"].strip(): _txt(g.get("uncovered")) for g in (gaps_raw if isinstance(gaps_raw, list) else [])
                    if isinstance(g, dict) and isinstance(g.get("claim"), str)}
            for s in st:
                if s.strip() not in gaps:
                    bad.append(f"강점 {s.strip()[:30]!r} 에 strengthGaps 항목이 없다 — 이 강점이 못 막는 시나리오(uncovered)를 적는다")
                elif not gaps[s.strip()]:
                    bad.append(f"강점 {s.strip()[:30]!r} 의 strengthGaps.uncovered 가 비었다")
    owners = {}
    for kind, rows in (("issue", issues), ("excluded", excluded)):
        for x in rows:
            if not isinstance(x, dict):
                bad.append(f"{kind} 항목이 객체가 아니다")
                continue
            xid = str(x.get("id"))
            for t in [xid] + [str(c) for c in x.get("covers") or []]:
                if t == xid and t not in cands:
                    continue   # 새로 만든 id(묶음 · 질문)는 후보에 없어도 된다
                if t in owners and owners[t] != xid:   # 같은 항목이 자기 id 를 covers 에도 적은 것은 이중 소유가 아니다
                    bad.append(f"covers 이중 소유 — 후보 {t} 를 {owners[t]} 와 {xid} 가 함께 가진다")
                owners[t] = xid
            for c in x.get("covers") or []:
                if str(c) not in cands:
                    bad.append(f"{xid}.covers — {c} 는 후보에 없다(댕글링)")
    covered_by = {(str(c), str(x.get("id"))) for rows in (issues, excluded) for x in rows if isinstance(x, dict) for c in x.get("covers") or []}
    for rows in (issues, excluded):
        for x in rows:
            xid = str(x.get("id")) if isinstance(x, dict) else None
            if xid and any(t == xid and o != xid for t, o in covered_by):
                bad.append(f"{xid} — 소유자 id 가 다른 항목의 covers 대상이다(순환)")
    lost = sorted(cands - set(owners))
    if lost:
        bad.append(f"조용히 사라진 후보 {len(lost)}건 — {', '.join(lost[:6])} · issues · excluded · covers 어디에도 없다")
    for i in issues:
        iid = i.get("id")
        k = i.get("kind")
        if k not in KINDS:
            bad.append(f"{iid}: kind 는 {' · '.join(KINDS)} 중 하나다 — {k!r}")
        ev = [e for e in i.get("evidence") or [] if isinstance(e, str)]
        pinned = [m for m in (EVIDENCE_RE.match(e.strip()) for e in ev) if m]
        if not pinned:
            bad.append(f"{iid}: evidence 에 `path:line@sha` 가 없다")
        elif not any(sha.startswith(m["sha"]) or m["sha"].startswith(sha) for m in pinned):
            bad.append(f"{iid}: evidence @sha 가 리뷰 대상 {sha[:12]} 와 다르다 — 작업 트리에서 읽은 사실이면 E7")
        if k == "bug":
            r = i.get("repro") if isinstance(i.get("repro"), dict) else {}
            if r.get("status") not in REPRO or not _txt(r.get("how")):
                bad.append(f"{iid}: bug 는 repro{{status: {' | '.join(REPRO)}, how}} 가 필요하다 — 미재현이면 질문으로 내리거나 E1")
            if not (_txt(i.get("symptom_screen")) and _txt(i.get("symptom_reach"))):
                bad.append(f"{iid}: bug 는 symptom_screen · symptom_reach 가 필요하다(Gate 4.7-S)")
        if k in ("structure", "quality") and not _txt(i.get("measure")):
            bad.append(f"{iid}: {k} 제안은 measure(관례 표본 N:M · 중복 줄 수 · 결함 위험)가 필요하다 — 없으면 E3")
        elif k in ("structure", "quality") and not NM_RE.search(_txt(i.get("measure"))):
            bad.append(f"{iid}: measure 에 관례 표본 N:M 이 없다 — 이번 형태와 다른 형태를 센 수(N : M)를 적는다. 어느 쪽이 관례인지 세지 않은 비대칭 지적이다(F-053)")
        if i.get("severity") in MAJOR_UP:
            chain = i.get("chain")
            steps = [c for c in chain if isinstance(c, dict)] if isinstance(chain, list) else []
            if not steps or len(steps) != len(chain) or any(c.get("grade") not in CHAIN_GRADES or not _txt(c.get("step")) for c in steps):
                bad.append(f"{iid}: major 이상은 chain[{{step, grade: {' | '.join(CHAIN_GRADES)}}}] 이 필요하다 — 인과 체인을 단계로 쪼개 근거 종류를 단다(F-116)")
            elif any(c["grade"] != "code" for c in steps):
                soft = [f"{c['step'][:20]}({c['grade']})" for c in steps if c["grade"] != "code"]
                bad.append(f"{iid}: major 이상인데 인과 체인에 주석 · 추론 단계가 있다 — {', '.join(soft)} · 그 단계를 코드로 재거나 minor 로 내린다(F-116)")
            sb = i.get("severity_basis") if isinstance(i.get("severity_basis"), dict) else {}
            if sb.get("kind") not in BASIS_KINDS or not _txt(sb.get("note")):
                bad.append(f"{iid}: major 이상은 severity_basis{{kind: {' | '.join(BASIS_KINDS)}, note}} 가 필요하다 — 무게의 근거(F-090)")
            elif sb["kind"] != "output-change":
                bad.append(f"{iid}: severity_basis {sb['kind']} — 출력 변화를 보이지 못한 판정은 minor 까지다(F-090)")
        notes = i.get("symbol_notes") if isinstance(i.get("symbol_notes"), dict) else {}
        if any(v not in ("new", "sdk") for v in notes.values()):
            bad.append(f"{iid}: symbol_notes 값은 new · sdk 다 — {notes}")
        idents = code_idents(" ".join(_txt(i.get(f)) for f in ("suggestion", "comment")))
        if idents and tree is not None:
            missing = sorted(idents - tree - set(notes))
            got = repo_has(base, sha, missing) if missing else set()
            if got is None:                # 바뀐 파일 스냅샷에 없다는 것만으로 '없는 심볼' 이 아니다 — 대조 못 하면 미검증
                note = f"제안 식별자 {', '.join(missing[:3])} 를 스냅샷 밖에서 대조 못 함 — {REPO_ROOT_FILE} 없음 · git 실패(미검증)"
                info.setdefault("symbol_check", note)
                warn.append(f"{iid}: {note}")   # 출력 · 렌더 리포트에 남긴다 — info 에만 두면 '검증 통과' 와 구별되지 않는다
                missing = []
            missing = [m for m in missing if m not in (got or set())]
            if missing:
                bad.append(f"{iid}: 제안 코드 식별자 {', '.join(missing[:5])} 가 head/ · base/ · diff · 대상 sha 트리 어디에도 없다 — 새 심볼이면 symbol_notes 에 new, SDK 면 sdk(F-063)")
        elif idents and tree is None:
            info.setdefault("symbol_check", "제안 식별자 대조 못 함 — head/ 스냅샷 없음(미검증)")
            warn.append(f"{iid}: 제안 식별자 대조 못 함 — head/ 스냅샷 없음(미검증)")
        if i.get("origin") not in ORIGINS:
            # ⛔ 어휘를 닫는다 — 'Regression' · 'new-code' 처럼 적으면 regression 의 base 근거 검사(F-037)를 통째로 건너뛴다
            bad.append(f"{iid}: origin {i.get('origin')!r} 은 정본 어휘({' · '.join(ORIGINS)}) 밖이다")
        elif i.get("origin") == "pre-existing":
            bad.append(f"{iid}: origin 이 pre-existing — 원래 있던 문제는 E4 로 제외한다(리포트 ④)")
        if k != "intent-question" and not _txt(i.get("suggestion")):
            bad.append(f"{iid}: suggestion 이 없다 — 작성자가 할 조치가 없으면 E6")
        if not _txt(i.get("refute")):
            bad.append(f"{iid}: refute(재검증 기록 — 반박 시도와 결과)가 없다")
        pl = prose_lines(_txt(i.get("comment")))
        if not pl:
            bad.append(f"{iid}: comment 가 없다")
        elif len(pl) > 4:
            bad.append(f"{iid}: comment 산문 {len(pl)}줄 > 4 — 근거는 evidence 로 옮긴다")
        elif not CLOSING_RE.search(pl[-1]):
            warn.append(f"{iid}: comment 마무리 어조(…부탁드립니다 · …여쭙습니다 · 질문)가 없다")
        if i.get("duplicateOf"):
            bad.append(f"{iid}: duplicateOf 가 있는 항목은 코멘트가 아니다 — E5 로 제외한다")
        if threads:
            ds = {str(d.get("thread")) for d in i.get("distinctFrom") or [] if isinstance(d, dict) and _txt(d.get("why"))}
            for s in i.get("sites") or []:
                if not isinstance(s, dict):
                    continue
                for t in threads:
                    ln = t.get("line") or t.get("original_line")
                    a = s.get("start")
                    b = s.get("end") if isinstance(s.get("end"), int) else a
                    if t.get("path") == s.get("path") and isinstance(ln, int) and isinstance(a, int) \
                            and a - NEAR <= ln <= b + NEAR and str(t.get("id")) not in ds:
                        bad.append(f"{iid}: 기존 스레드 {t.get('id')}({t.get('path')}:{ln}) 근처다 — E5(duplicateOf) 로 빼거나 distinctFrom[{{thread, why}}]")
    for x in excluded:
        if not isinstance(x, dict):
            continue
        xid = x.get("id")
        if x.get("code") not in CODES:
            bad.append(f"excluded {xid}: code 는 E1~E8 이다 — {x.get('code')!r}")
        if not _txt(x.get("reason")):
            bad.append(f"excluded {xid}: reason 이 없다")
        if x.get("code") == "E5" and not x.get("duplicateOf"):
            bad.append(f"excluded {xid}: E5 는 duplicateOf(스레드 id)가 필요하다")
        if x.get("code") == "E8" and not _txt(x.get("refute")):
            bad.append(f"excluded {xid}: E8 은 refute(반박 근거)가 필요하다")
    return (VIOLATION if bad else OK), bad, warn, info


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {detail}"))

    SHA = "abc1234def5678"
    BSHA = "0123456789abcdef0123456789abcdef01234567"   # base-sha.txt — gather 가 base/ 를 뜬 커밋
    MERGED = {"inputs": {"claude": 2, "gpt": 1, "gptUnavailable": None, "evidenceChecked": True},
              "candidates": [{"id": "claude:C1", "source": "claude", "severity": "major"},
                             {"id": "claude:C2", "source": "claude", "severity": "minor", "origin": "pre-existing"},
                             {"id": "gpt:G1", "source": "gpt", "severity": "minor"}],
              "summary": {"candidatesIn": 3, "candidatesOut": 3}}
    ISSUE = {"id": "A1", "kind": "bug", "severity": "major", "origin": "regression", "covers": ["claude:C1"],
             "evidence": [f"src/a.swift:11-12@{SHA[:7]}"], "base_evidence": f"src/a.swift:11@{BSHA[:7]}", "repro": {"status": "code-determined", "how": "nil 경로"},
             "symptom_screen": "목록", "symptom_reach": "탭 → 목록", "suggestion": "guard 추가", "refute": "반박 실패 — 호출 1곳",
             "base_quote": "let items = load()", "chain": [{"step": "nil 이 넘어온다", "grade": "code"}, {"step": "guard 가 빈 배열을 돌려준다", "grade": "code"}],
             "severity_basis": {"kind": "output-change", "note": "목록이 빈다"},
             "comment": "nil 이면 목록이 비어 보입니다.\nguard 를 두면 좋겠습니다. 확인 부탁드립니다.",
             "sites": [{"path": "src/a.swift", "start": 11, "end": 12}]}
    BASE = {"verdict": "v", "target": {"kind": "pr", "ref": "pr-1", "sha": SHA}, "meta": {"base_sha": BSHA}, "candidates": ["merged.json"],
            "issues": [ISSUE],
            "excluded": [{"id": "claude:C2", "what": "원래 있던 문제", "code": "E4", "reason": "base 에도 같다"},
                         {"id": "gpt:G1", "what": "SDK 가정", "code": "E2", "reason": "SDK 내부 동작 가정"}]}
    with tempfile.TemporaryDirectory() as t:
        seq = [0]

        def run(review, merged=MERGED, threads=None, gpt_dir=False, extra=None, base_sha=BSHA, cli=False, trees=None):
            seq[0] += 1
            d = pathlib.Path(t) / f"c{seq[0]}"
            d.mkdir()
            for rel, text in (trees or {}).items():   # {"head/src/a.swift": "…"} — gather 스냅샷 모양
                (d / rel).parent.mkdir(parents=True, exist_ok=True)
                (d / rel).write_text(text, encoding="utf-8")
            if base_sha is not None:
                (d / BASE_SHA_FILE).write_text(base_sha + "\n", encoding="utf-8")
            for name, obj in (extra or {}).items():
                (d / name).write_text(json.dumps(obj), encoding="utf-8")
            if merged is not None:
                (d / "merged.json").write_text(json.dumps(merged), encoding="utf-8")
            if threads is not None:
                (d / "existing-threads.json").write_text(json.dumps(threads), encoding="utf-8")
            if gpt_dir:
                (d / "gpt-independent").mkdir()
            if cli:   # 실제 CLI — 기본 경로(플래그 없이 review.json 폴더의 base-sha.txt)를 사용자가 부르는 꼴로 잰다
                (d / "review.json").write_text(json.dumps(review), encoding="utf-8")
                return subprocess.run([sys.executable, os.path.abspath(__file__), str(d / "review.json")],
                                      capture_output=True, text=True).returncode, [], [], {}
            return check_review(json.loads(json.dumps(review)), d)

        def mod(**kw):
            r = json.loads(json.dumps(BASE))
            for k, v in kw.items():
                r[k] = v
            return r

        def mi(**kw):
            i = json.loads(json.dumps(ISSUE))
            for k, v in kw.items():
                if v is None:
                    i.pop(k, None)
                else:
                    i[k] = v
            return mod(issues=[i])

        case("curated-ok", run(BASE)[0] == OK, run(BASE)[1])
        case("candidate-lost", run(mod(excluded=BASE["excluded"][:1]))[0] == VIOLATION)
        case("covers-dangling", run(mi(covers=["claude:C1", "claude:NOPE"]))[0] == VIOLATION)
        case("covers-double-owner", run(mod(excluded=BASE["excluded"] + [{"id": "B1", "what": "w", "code": "E3", "reason": "취향", "covers": ["claude:C1"]}]))[0] == VIOLATION)
        case("self-cover-not-double", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E4", "reason": "r", "covers": ["claude:C2"]},
                                                        BASE["excluded"][1]]))[0] == OK)
        case("covers-cycle", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E4", "reason": "r", "covers": ["gpt:G1"]},
                                               {"id": "B2", "what": "w", "code": "E3", "reason": "r", "covers": ["claude:C2"]}]))[0] == VIOLATION)
        case("evidence-missing", run(mi(evidence=None))[0] == VIOLATION)
        case("evidence-path-with-space", run(mi(evidence=["Sources/My View.swift:11@abc1234"]))[0] == OK)
        case("malformed-candidate-unrun", run(BASE, merged={"candidates": [{"id": "claude:C1", "severity": "major"}, None]})[0] == UNRUN)
        case("site-end-null-near-thread", run(mi(sites=[{"path": "src/a.swift", "start": 11, "end": None}]),
                                              threads={"status": "ok", "comments": [{"id": 77, "path": "src/a.swift", "line": 13}]})[0] == VIOLATION)
        case("evidence-sha-mismatch", run(mi(evidence=["src/a.swift:11@fff0000"]))[0] == VIOLATION)
        case("bug-needs-repro", run(mi(repro={"status": "not-reproduced", "how": "x"}))[0] == VIOLATION)
        case("bug-needs-symptom", run(mi(symptom_reach=None))[0] == VIOLATION)
        case("structure-needs-measure", run(mi(kind="structure", repro=None))[0] == VIOLATION)
        case("structure-with-measure-ok", run(mi(kind="structure", repro=None, measure="관례 4:1"))[0] == OK)
        # round 2 S10 — 판정 층 계약(F-053 · F-116 · F-090 · F-063 · F-037)
        case("f053-nm-missing", run(mi(kind="structure", repro=None, measure="형제와 다르다 — 중복 12줄"))[0] == VIOLATION)
        case("f116-chain-grade-caps-major", run(mi(chain=[{"step": ".startPlay 재발화", "grade": "comment"}, {"step": "재호출", "grade": "code"}]))[0] == VIOLATION
             and run(mi(chain=None))[0] == VIOLATION and run(mi(severity="minor", chain=[{"step": "주석 근거", "grade": "comment"}]))[0] == OK)
        case("f090-severity-basis-missing", run(mi(severity_basis=None))[0] == VIOLATION)
        case("f090-path-only-not-major", run(mi(severity_basis={"kind": "path-only", "note": "경로만 있다"}))[0] == VIOLATION
             and run(mi(severity="minor", severity_basis={"kind": "path-only", "note": "경로만"}))[0] == OK)
        head = {"head/src/a.swift": "func rollStep() {}\nlet items = load()\n"}
        # 대상 저장소 — head/ 는 바뀐 파일(a.swift)만이고 sharedHelper 는 바뀌지 않은 util.swift 에 있다
        rd = tempfile.mkdtemp(prefix="ccw-repo-", dir=t)   # 바깥 임시 폴더와 함께 지워진다
        gx = lambda *a: subprocess.run(["git", "-C", rd, "-c", "user.email=t@t", "-c", "user.name=fixture-user", *a], capture_output=True, text=True)
        gx("init", "-q")
        os.makedirs(os.path.join(rd, "src"))
        for rel, body in (("src/a.swift", "func rollStep() {}\n"), ("src/util.swift", "func sharedHelper() {}\n")):
            with open(os.path.join(rd, rel), "w", encoding="utf-8") as fh:
                fh.write(body)
        gx("add", "-A")
        gx("commit", "-qm", "c")
        real = gx("rev-parse", "HEAD").stdout.strip()
        at = lambda r: json.loads(json.dumps(r).replace(SHA, real).replace("abc1234", real[:7]))   # 리뷰 대상 sha = 픽스처 커밋
        heads = dict(head, **{REPO_ROOT_FILE: rd + "\n"})
        case("f063-suggestion-symbol-missing", run(at(mi(suggestion="`rollOneStep()` 을 부른다")), trees=heads)[0] == VIOLATION)
        case("f063-unchanged-file-helper-ok — 바뀌지 않은 파일의 도우미는 대상 sha 트리에서 찾는다",
             run(at(mi(suggestion="`sharedHelper()` 를 재사용한다")), trees=heads)[0] == OK)
        nr = run(mi(suggestion="`sharedHelper()` 를 재사용한다"), trees=head)
        case("f063-no-repo-unverified-not-violation — 저장소를 못 쓰면 위반이 아니라 미검증(경고로 드러낸다)",
             nr[0] == OK and "symbol_check" in nr[3] and any("미검증" in w for w in nr[2]), nr)
        case("f063-known-or-declared-ok", run(mi(suggestion="`rollStep()` 을 부른다"), trees=head)[0] == OK
             and run(mi(suggestion="`rollOneStep()` 을 새로 만든다", symbol_notes={"rollOneStep": "new"}), trees=head)[0] == OK)
        # 저장소를 갖춘 형태로 잰다 — 저장소가 없으면 없는 이름이 미검증으로 빠져 이 셀이 늘 통과한다
        lit = lambda s: run(at(mi(suggestion=s)), trees=heads)[0]
        case("f063-literals-keywords-not-symbols — 문자열 · 주석 · 템플릿 · 지원 언어 키워드는 심볼이 아니다(Swift 지시어는 남긴다)",
             all(lit(s) == OK for s in ('```\nthrow new Error("Connection refused") // retry later\n```',
                                         '```\nif ok:\n    pass  # Connection refused\n```',
                                         '```\nconst m = `Connection ${id} refused`; rollStep()\n```',
                                         '```\nprotected abstract synchronized void rollStep();\n```',
                                         '```python\nok = True  #Connection refused\n```',
                                         '```ts\nconst s: string = ""; rollStep()\n```',
                                         '```kotlin\nclass A constructor() { fun go() = rollStep() }\n```',
                                         '```js\nrollStep(`${rollStep()} done`)\n```'))
             and lit('```\nthrow new Error("x"); rollOneStep()\n```') == VIOLATION
             and lit('```\n#selector(rollOneStep)\n```') == VIOLATION
             and lit('```js\nrollStep(`${missingHelper()}`)\n```') == VIOLATION)   # 템플릿 보간식은 실행되는 코드다
        nested = [lit('```js\nrollStep(`${rollStep({}) + missingHelper()}`)\n```'),
                  lit('```js\nrollStep(`${1 // c\r + missingHelper()\n}`)\n```'),        # 줄 주석은 CR 에서 끝난다(r3 ISSUE-005)
                  lit('```js\nrollStep() // c\rmissingHelper()\n```')]
        # 보간식 안 중첩 중괄호 뒤의 미지 함수도 대조한다(ISSUE-202622)
        case("r3-f063-template-nested-brace", nested == [VIOLATION] * 3, nested)
        strs = [lit('```js\nrollStep(`${"Connection refused"}`)\n```'), lit('```js\nrollStep(`${rollStep("a}b")} ok`)\n```')]
        # 보간식 안 문자열은 심볼이 아니다 · 그 안의 } 는 보간식을 닫지 않는다(ISSUE-202607)
        case("r3-f063-template-string-literal",
             strs == [OK, OK], strs)
        unread = [lit('```js\nrollStep(`${rollStep()`)\n```'),
                  lit('```js\nrollStep(`${/[}]/.test("}") ? missingHelper() : 0}`)\n```'),   # 정규식 리터럴(r3 ISSUE-004)
                  lit('```js\nrollStep(`${typeof /[}]/ + missingHelper()}`)\n```'),          # 키워드 뒤 정규식(r3 2차 ISSUE-003)
                  lit('```js\nconst re = /[//]/; rollStep(`${missingHelper()}`)\n```')]        # 바깥 정규식 리터럴 안 //(r3 4차 ISSUE-005)
        # 못 읽은 보간식은 미지 심볼이다(fail-open 아님)
        case("r3-unknown-final-comment-worthy",
             unread == [VIOLATION] * 4 and UNLEXED in code_idents('```js\nrollStep(`${rollStep()`)\n```')
             and UNLEXED in code_idents('```js\nconst re = /[//]/; const t = `${missingHelper()}`;\n```'), unread)
        # 흔한 나눗셈 · 경로 꼴은 못 읽음이 아니다 — 조건 괄호가 아닌 `)` 뒤 `/` 는 나눗셈 · 정규식은 JS 계열 펜스만 · 몸이 같은 줄에서
        # 닫히는 정규식은 렉심을 가리지 않는다(실사용 대조에서 펜스의 4분의 1이 못 읽음이던 회귀). 조건 괄호 뒤 정규식은 그대로 못 읽음
        divs = [lit('```swift\nlet w = (rollStep() - 1) / 2\n```'), lit('```kotlin\nval r = rollStep(rollStep) / 2\n```'),
                lit('```js\nconst h = (rollStep() - 1) / 2 // half\n```'), lit('```\n~/rollStep "rollStep"\n```'),
                lit('`~/rollStep "x"`'), lit('```ts\nconst m = /^a(?:b)?$/i; rollStep("x")\n```'),
                lit('```js\nconst re = /\\d+/; rollStep("x")\n```'), lit('```js\nconst re = /x*/g; rollStep("x")\n```')]   # 닫는 / 앞 연산자(r3 8.5 2차)
        case("r3-s1-division-and-paths-lexed",
             divs == [OK] * 8 and UNLEXED in code_idents('```js\nif (x) /[//]/.test(s); const t = `${missingHelper()}`;\n```'), divs)
        # 수정 전 트리(002df3b)의 옛 추출이 찾던 식별자 — 새 추출도 전부 찾는다(보간식 안 문자열을 심볼에서 뺀 고침은 위 셀이 잰다)
        before = {"```js\nrollStep(`${missingHelper()}`)\n```": {"missingHelper", "rollStep"},
                  "```\nconst m = `Connection ${id} refused`; rollStep()\n```": {"rollStep"},
                  "```js\nrollStep(`${rollStep()} done`)\n```": {"rollStep"},
                  "```js\nrollStep(`${wrap({}) + missingHelper()}`)\n```": {"rollStep", "wrap"}}
        lost = {k: sorted(v - code_idents(k)) for k, v in before.items() if not v <= code_idents(k)}
        case("r3-replaced-path-parity-comment-worthy", not lost, lost)
        js = lambda s: code_idents("```js\n" + s + "\n```")   # noqa: E731
        got = js('async function scan() { for await (const item of ["/"]) /[//]/.test(item) && missingHelper(item); } scan();')
        case("r3-s1-r6-012-for-await-paren", UNLEXED in got, sorted(got))   # `for await (…)` 뒤 / 는 정규식 — 그 안 // 를 주석으로 읽지 않는다
        got = [js("const pattern = /neverInRepo/; pattern.test(value);"), js("const pat = /abcdefXyz/gimsu; pat.test(value);"),
               js("const r = x++ / missingHelper() / 2;"), js("const r = total / count / scale;")]
        case("r3-s1-r6-014-regex-body-stripped",   # 확실한 정규식 시작 자리의 닫힌 본문 · 플래그는 식별자가 아니다 · 나눗셈 사이 식별자는 남는다
             got == [{"pattern", "test", "value"}, {"pat", "test", "value"}, {"missingHelper"}, {"total", "count", "scale"}], [sorted(x) for x in got])
        got = [js("const result = obj.return / missingHelper() / 2;"), js("const r = a?.typeof / missingHelper() / 2;")]
        case("r3-s1-r7-property-keyword-division",   # `.` 뒤 키워드 철자는 속성 이름 — 그 뒤 / 는 나눗셈이라 지우지 않는다(GPT check r7 P2)
             all("missingHelper" in x for x in got), [sorted(x) for x in got])
        case("f063-no-head-not-checked", run(mi(suggestion="`rollOneStep()` 을 부른다"))[0] == OK)
        case("f037-regression-without-base-quote", run(mi(base_quote=None))[0] == VIOLATION)
        rk = {"risk.json": {"risk": 0, "plugin_refs": {"SwiftUI Expert": ["state-management"]}, "runtime_axes": ["gesture"]}}
        case("f520-read-slot-required", run(BASE, extra=rk)[0] == VIOLATION
             and run(mod(pluginRefsRead=[{"plugin": "SwiftUI Expert", "refs": ["state-management"]}],
                         runtimeAxes=[{"axis": "gesture", "how": "probe", "note": "시뮬 드래그"}]), extra=rk)[0] == OK)
        case("f258-runtime-axes-decided", run(mod(pluginRefsRead=[{"plugin": "SwiftUI Expert", "refs": ["s"]}],
                                                  runtimeAxes=[{"axis": "gesture", "how": "none"}]), extra=rk)[0] == VIOLATION)
        based = {"head/src/a.swift": "x\n", "base/src/a.swift": "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\nlet items = load()\n"}
        case("f037-base-quote-matches-base", run(BASE, trees=based)[0] == OK and run(mi(base_quote="let items = fetch()"), trees=based)[0] == VIOLATION)
        case("preexisting-not-comment", run(mi(origin="pre-existing"))[0] == VIOLATION)
        case("question-no-suggestion-ok", run(mi(kind="intent-question", repro=None, suggestion=None, comment="의도가 X 인지 여쭙습니다"))[0] == OK)
        case("needs-refute", run(mi(refute=None))[0] == VIOLATION)
        case("comment-too-long", run(mi(comment="1\n2\n3\n4\n5"))[0] == VIOLATION)
        case("comment-fence-not-counted", run(mi(comment="a\n```\nx\ny\nz\nw\n```\n부탁드립니다"))[0] == OK)
        r = run(mi(comment="첫 줄\n둘째 줄"))
        case("closing-tone-warn", r[0] == OK and len(r[2]) == 1, r)
        case("duplicate-is-not-comment", run(mi(duplicateOf="T9"))[0] == VIOLATION)
        th = {"status": "ok", "comments": [{"id": 77, "path": "src/a.swift", "line": 13}]}
        case("near-thread-needs-disposition", run(BASE, threads=th)[0] == VIOLATION)
        case("near-thread-distinct-ok", run(mi(distinctFrom=[{"thread": 77, "why": "다른 줄 다른 결함"}]), threads=th)[0] == OK)
        case("threads-unavailable-line", "status unavailable" in run(BASE, threads={"status": "unavailable", "reason": "gh 실패"})[3]["thread_line"])
        case("e5-needs-duplicate-of", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E5", "reason": "r"}, BASE["excluded"][1]]))[0] == VIOLATION)
        case("e8-needs-refute", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E8", "reason": "r"}, BASE["excluded"][1]]))[0] == VIOLATION)
        case("bad-code", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E9", "reason": "r"}, BASE["excluded"][1]]))[0] == VIOLATION)
        case("no-target-unrun", run(mod(target=None))[0] == UNRUN)
        case("merged-missing-unrun", run(BASE, merged=None)[0] == UNRUN)
        case("evidence-path-with-newline", run(mi(evidence=["Sources/a\nb.swift:11@abc1234"]))[0] == OK)
        case("stale-gpt-dir-challenger-ok", run(mod(candidates=["syn.json"], gptPass="challenger"), merged=None, gpt_dir=True, extra={"syn.json": MERGED})[0] == OK)
        case("declared-independent-without-merged-unrun", run(mod(candidates=["syn.json"], gptPass="independent"), merged=None, extra={"syn.json": MERGED})[0] == UNRUN)
        case("stale-gpt-dir-undeclared-unrun", run(mod(candidates=["syn.json"]), merged=None, gpt_dir=True, extra={"syn.json": MERGED})[0] == UNRUN)
        case("gpt-ran-without-merged-unrun", run(mod(candidates=["syn.json"]), merged=None, gpt_dir=True)[0] == UNRUN)
        # F-037 — regression 의 base 근거
        case("regression-without-base-evidence", run(mi(base_evidence=None))[0] == VIOLATION)
        case("regression-base-evidence-head-sha-rejected", run(mi(base_evidence=f"src/a.swift:11@{SHA[:7]}"))[0] == VIOLATION)
        case("regression-base-evidence-local-develop-rejected", run(mi(base_evidence="src/a.swift:11@feedfacecafe"))[0] == VIOLATION)
        r = run(BASE)
        case("regression-base-evidence-ok", r[0] == OK and not r[1], r[1])
        case("base-sha-default-review-dir", run(BASE, cli=True)[0] == OK and run(BASE, base_sha="feedfacecafe00", cli=True)[0] == VIOLATION)
        case("base-sha-missing-unrun", run(BASE, base_sha=None)[0] == UNRUN and run(mi(origin="improvement"), base_sha=None)[0] == OK)
        case("origin-outside-vocabulary-rejected", run(mi(origin="Regression"))[0] == VIOLATION and run(mi(origin="new-code"))[0] == VIOLATION)
        wrong = mi(base_evidence="src/a.swift:11@2222222")
        wrong["meta"] = {"base_sha": "2222222222222222"}
        case("meta-and-evidence-both-wrong-rejected", run(wrong)[0] == VIOLATION and run(wrong, cli=True)[0] == VIOLATION)
        # F-117 · F-517 — 강점이 못 막는 시나리오
        case("strength-gap-missing", run(mod(strengths=["범위가 맞다"]))[0] == VIOLATION)
        case("strength-gap-empty-uncovered", run(mod(strengths=["범위가 맞다"], strengthGaps=[{"claim": "범위가 맞다", "uncovered": " "}]))[0] == VIOLATION)
        r = run(mod(strengths=["범위가 맞다"], strengthGaps=[{"claim": "범위가 맞다", "uncovered": "동시 호출 경로는 이 PR 이 막지 않는다"}]))
        case("strength-gap-ok", r[0] == OK, r[1])
        case("strengths-string-array-kept", run(mod(strengths=[{"claim": "범위가 맞다"}], strengthGaps=[{"claim": "범위가 맞다", "uncovered": "u"}]))[0] == VIOLATION
             and r[0] == OK)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("review", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.review:
        print("UNRUN: REVIEW_JSON 이 필요하다", file=sys.stderr)
        return UNRUN
    p = pathlib.Path(a.review)
    try:
        review = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"UNRUN: 읽기 실패 — {type(e).__name__}: {e}", file=sys.stderr)
        return UNRUN
    if not isinstance(review, dict) or "excluded" not in review:
        print("UNRUN: excluded 키가 없다 — 큐레이션하지 않은 리뷰다", file=sys.stderr)
        return UNRUN
    code, bad, warn, info = check_review(review, p.parent)
    print(f"코멘트 가치 — issues {len(review.get('issues') or [])} · excluded {len(review.get('excluded') or [])} · 후보 {info['candidates']} · {info['thread_line']}")
    for b in bad:
        print(f"  ✗ {b}")
    for w in warn:
        print(f"  WARN {w}")
    return code


if __name__ == "__main__":
    sys.exit(main())
