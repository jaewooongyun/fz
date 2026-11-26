#!/usr/bin/env python3
# diff-parse: hunk-state — `added_lines_by_file` 가 `in_hunk` 를 추적한다.
"""diff 의 위험 신호를 카테고리 단위로 판정한다 — auto-tier 승격 입력.

왜 스크립트인가: 판정이 결정론적이고 binary 다 (guides/skill-authoring.md §11).
인라인 `grep -cE` 로는 아래 셋을 동시에 지킬 수 없었다.

  ① 추가된 코드만 본다   — hunk 헤더(`@@`)·context·삭제 라인은 이 PR 이 만든 위험이 아니다
  ② 토큰 경계를 지킨다   — `actor ` 가 `Interactor ` 에 매칭돼 오탐이 났다
  ③ 카테고리로 센다      — 같은 위험이 20줄에 걸쳐 있어도 위험은 하나다

실측 사례: 한 리뷰에서 4건이 매칭됐는데 전부 오탐이었다 — `Interactor` substring
+ 전부 `@@` 헤더. Lead 가 수동으로 0 으로 낮췄으니 망정이지 자동 판정 그대로면
작은 PR 이 상위 Tier 로 올라가 3~6 agent call 을 유발했다.

usage:
  risk_scan.py DIFF_PATH [--json]

exit: 0 = 판정 성공 / 2 = 사용법·입력 오류
  ⛔ exit 0 은 "위험 없음"이 아니다. 위험 수는 stdout 으로 읽는다.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent   # 플러그인 루트 — modules/plugin-refs.md 표를 읽는다

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diff_anchors import unquote_path  # noqa: E402 — 같은 폴더 · git C 스타일 인용 경로 해독(F-412)

# 카테고리별 패턴. 값은 (정규식, 설명).
# ⛔ 토큰 경계가 필요한 것과 리터럴로 둬야 하는 것을 구분한다 —
#    `@MainActor` 앞의 `@` 는 단어 문자가 아니라 `\b` 가 의도대로 걸리지 않는다.
# ⛔ 경계 정책은 카테고리마다 다르다 — 일괄 `\b` 는 정탐을 죽인다.
#   오탐 축과 정탐 축이 **다른 단어에 있다**:
#     · `actor` 는 `Interactor` 안에 나타나면 오탐 → 경계 필요
#     · `auth` 는 `authManager` 안에 나타나면 **정탐** → 경계를 걸면 놓친다
#   그래서 도메인 어휘(auth·token·session…)는 substring 을, 문법 토큰(actor·async…)은
#   경계를 쓴다. 단 substring 쪽도 흔한 오탐어는 개별 배제한다.
CATEGORIES = {
    "auth": (
        # substring — 식별자 내부 등장이 신호다 (authManager · tokenProvider · sessionStore)
        r"(?i)(?:auth|token|secret|credential|permission|keychain|crypto|certificate|privacy)"
        # 경계 필요 — 짧고 일반 어휘라 substring 이면 오탐이 폭발한다
        r"|\b(?:role|admin|session)\b",
        "인증·권한·비밀",
    ),
    "payment": (
        r"(?i)(?:payment|billing|refund|InAppPurchase|StoreKit)|\bIAP\b",
        "결제",
    ),
    "data": (
        r"(?:CoreData|(?i:migration|schema|database))|\bsql\b",
        "데이터 저장·마이그레이션",
    ),
    "public_api": (
        r"\bpublic\s+(?:func|class|protocol|struct|enum|var|let)\b",
        "공개 API 표면",
    ),
    "lifecycle": (
        r"\b(?:deinit|removeFromSuperview|deleteAll)\b",
        "생명주기·일괄 삭제",
    ),
    "concurrency": (
        r"(?:@MainActor|\bactor\b|\basync\b|\bawait\b|\bTask\s*\{"
        r"|\bwithCheckedContinuation\b|\bDispatchQueue\b)",
        "동시성",
    ),
    "build_config": (
        r"(?:\bxcconfig\b|Package\.swift|\bci_scripts\b)",
        "빌드 설정",
    ),
}

# 관점 카테고리 (round 2 S10) — 위험(Tier 승격)이 아니라 **리뷰 관점 신호**다. categories · detail 에 남고(axis_only) risk 합계에서 빠진다 —
#   UI · 로그 PR 마다 Tier 가 오르면 승격 신호가 묽어진다. 판정 근거가 아니라 '이 축을 따로 보라' 는 표지다.
#   analytics(F-515): 새 분기 술어의 입력 클래스(nil · 빈 값 · 스킴)마다 나가는 클릭 · 노출 로그 · 이동. 프로젝트 고유 트래커 이름은
#     플러그인에 박지 않고 env FZ_RISK_ANALYTICS_TOKENS(정규식 갈래)로 더한다.
#   animation(F-134): 가역 전환이면 정 · 역재생 두 시간 프로파일이 생긴다 — 코드를 읽어서는 둘째가 보이지 않는다.
#   content_access(F-083): 등급 · 연령 · 성인 · 보호자 — 미성년 보호 게이팅을 뒤집은 diff 가 risk 0 · 카테고리 0 이었다(`gradeCode` · `isGrade19`
#     가 어느 패턴에도 안 걸렸다). Tier 를 올릴 근거는 없어(엔트리 — 과승격 억제 압력) 표지만 붙인다. ⛔ 게이팅을 **지우는** 것이 반전이라
#     이 축은 양방향(TWO_WAY_AXES)으로 센다. 낱말 시작에만 건다(_camel_word) — `upgrade` · `usage` · `generating` 안의 grade · age · rating 은
#     낱말 중간이다. 프로젝트 고유 토큰(블러 · 블라인드 처리 이름 등)은 env FZ_RISK_CONTENT_ACCESS_TOKENS(정규식 갈래)로 더한다.


def _camel_word(w):
    """식별자 안 낱말 시작에만 걸리는 갈래 — 앞이 글자가 아니거나(gradeCode · CONTENT_GRADE) 소문자 · 숫자 뒤 대문자 시작(isGrade19)."""
    return r"(?:(?<![A-Za-z])(?i:%s)|(?<=[a-z0-9])%s(?i:%s))" % (w, w[0].upper(), w[1:])


# age 는 짧아 끝 경계도 건다 — 소문자 age/Age 뒤 소문자(agent · ages)와 대문자 AGE 뒤 글자(AGENT_ID)는 다른 낱말이다
_AGE = r"(?:(?<![A-Za-z])[aA]ge(?![a-z])|(?<=[a-z0-9])Age(?![a-z])|(?<![A-Za-z])AGE(?![A-Za-z]))"

AXIS_CATEGORIES = {
    "analytics": (
        r"(?i)(?:analytics|logEvent|trackEvent|sendEvent|tracker|impression|clickLog|logClick)",
        "분석 이벤트 — 새 분기 술어의 입력 클래스(nil · 빈 값 · 스킴)마다 나가는 로그 · 이동을 따로 본다",
    ),
    "animation": (
        r"(?:\.animation\(|\bwithAnimation\b|\bAnimatable\b|\banimatableData\b|\bUIView\.animate\b|\bCABasicAnimation\b|\btimingFunction\b)",
        "애니메이션 곡선 — 가역 전환이면 정 · 역재생 시간 프로파일을 둘 다 인쇄해 본다",
    ),
    "content_access": (
        "|".join([_camel_word("grade"), _camel_word("rating"), _AGE, _camel_word("adult"), _camel_word("parental"), _camel_word("guardian")]),
        "콘텐츠 접근 제한(등급 · 연령 · 성인 · 보호자) — 누가 무엇을 볼 수 있는지 바뀌는지 따로 본다(지운 게이팅 포함)",
    ),
}
# 관점 축의 프로젝트 고유 토큰 env — 값은 정규식 갈래로 그 축 패턴 뒤에 `|(?i:…)` 로 붙는다(대소문자 무시)
AXIS_ENV = {"analytics": "FZ_RISK_ANALYTICS_TOKENS", "content_access": "FZ_RISK_CONTENT_ACCESS_TOKENS"}
# 순감도 신호인 관점 축 — 토큰별 추가 ≠ 삭제면 성립한다(같은 수 짝 = 개명 · 이동은 조용하다). 나머지 축 · 카테고리는 순증만 센다
TWO_WAY_AXES = frozenset({"content_access"})

# 실행 필요 축 (F-258) — 렌즈가 읽기만으로 판정할 수 없는 축. 있으면 Lead 가 격리 프로브를 돌리거나 GPT 에 명시 질문으로 넘긴다.
#   ⛔ 위험이 아니다 — risk 에 넣지 않는다. 추가 행 순증 토큰만 센다(개명 · 이동 짝은 지운다).
RUNTIME_AXES = {
    "on_change": re.compile(r"\.onChange\s*\(|\.onReceive\s*\(|\.task\s*\(\s*id:"),
    "state_capture": re.compile(r"@State\b|@Binding\b"),
    "gesture": re.compile(r"\bGesture\b|\w+Gesture\b|\.gesture\s*\(|GestureRecognizer\b"),
    "state_transition": re.compile(r"\.transition\s*\(|matchedGeometryEffect|\.sheet\s*\(|\.fullScreenCover\s*\(|navigationDestination"),
}

# 형제 관례 대조 (F-516) — `--head DIR` 를 줄 때만. 바뀐 클로저 · 분기마다 같은 파일의 같은 역할 형제(같은 콜백 이름)가
#   **모두** 가진 guard 조건 중 이번 것에 없는 것을 원재료로 낸다. 판정은 렌즈 · Lead(Gate 4.9 [관례 이탈]).
#   형제 2곳 이상일 때만 · 고차 함수(map · filter …)는 역할이 아니라 뺀다.
ROLE_RE = re.compile(r"(?:\.(\w+)\s*(?:\([^)]*\))?\s*\{|\b(\w+)\s*=\s*\{|\b(\w+)\s*:\s*\{)")
GUARD_RE = re.compile(r"\bguard\s+(.*?)\s+else\b")
NOT_ROLES = frozenset("map filter compactMap flatMap forEach reduce sorted sort first contains allSatisfy sink receive "
                      "then catch async sync main if else switch case default do".split())
SIBLING_MIN = 2
# 술어 관례 (F-516 오라클 ②) — 같은 주어(마지막 식별자 — `url.scheme?.lowercased()` → scheme)를 문자열 리터럴과 견주는 판정식마다 줄 단위
#   리터럴 집합을 `--head` 아래 **바뀌지 않은** 줄에서 센다. 이번 판정식의 집합이 형제 관례 집합(2곳 이상 · 이번 형보다 많다)의
#   진부분 · 진상위 집합이면(https 단독 ↔ http · https 허용) 그 차를 N:M 으로 낸다. 서로소 집합(kind == "movie" ↔ "live")은 다른 분기라 뺀다.
#   판정은 렌즈 · Lead(Gate 4.9 [관례 이탈]). ⚠️ 범위는 --head 가 담은 파일이다 — gather 의 head/ 는 바뀐 파일만 담아 앱 전체 관례는
#   그 안의 형제만큼만 보인다(0건 = '관례 이탈 없음' 이 아니다).
_PRED_SUBJ = r"([A-Za-z_][\w?!]*(?:\(\))?(?:\.[A-Za-z_][\w?!]*(?:\(\))?)*)"
PRED_EQ = re.compile(_PRED_SUBJ + r'\s*===?\s*"([^"\\\n]*)"|"([^"\\\n]*)"\s*===?\s*' + _PRED_SUBJ)
PRED_IN = re.compile(r'\[\s*("[^"\\\n]*"(?:\s*,\s*"[^"\\\n]*")*)\s*\]\s*\.contains\(\s*' + _PRED_SUBJ)

# 역방향 신호 — 키워드가 없어도 위험한 것.
# 공유 가변 상태는 `actor`·`@MainActor` 없이도 data race 를 만든다.
# ⛔ 한 줄로 판정할 수 없다: 싱글톤 선언과 가변 프로퍼티가 같은 파일에 있어야 한다.
SINGLETON = re.compile(r"\bstatic\s+(?:let|var)\s+shared\b")
# 저장 프로퍼티만 — 메서드 로컬 `var` 를 배제한다.
#   · 타입 본문 깊이(들여쓰기 1~4칸)를 요구해 함수 내부(8칸+)를 거른다
#   · `private(set)` 같은 괄호 modifier 를 허용한다
# ⛔ 한계: 들여쓰기는 근사다. 한 줄에 몰아쓴 코드나 비표준 포매팅은 놓친다 —
#    정확히 하려면 파싱이 필요하고, 이 스크립트의 목적(승격 신호)에는 과하다.
MUTABLE = re.compile(
    r"^[ \t]{1,4}(?:(?:private|internal|public|fileprivate|open)(?:\(set\))?[ \t]+)*"
    r"(?:static[ \t]+|class[ \t]+)?var[ \t]+\w"
)


# 위험 판정에서 제외할 파일 — 문서 변경은 런타임 위험이 아니다.
#   README 에 "auth token" 이라 쓴 것이 Tier 를 올리면 안 된다.
DOC_SUFFIXES = (".md", ".markdown", ".txt", ".rst", ".adoc")

# 실행 필요 표면(launch_surface) — 앱이 뜨는 경로를 바꾼 변경은 정적 리뷰만으로 놓친다(F-366: 루트 화면 교체 PR 의
#   검은 화면은 신규 설치 1회 실행이면 보였다). ⛔ 위험(risk)과 다른 축이다 — Tier 를 올리지 않고 launch_smoke.py 가
#   smoke 를 돌릴지 정하는 입력이다. 그래서 risk 합계에 넣지 않는다.
# 범용 진입점만 둔다(플랫폼별 실행 방법은 project-rules 의 launchSmoke 레코드가 준다). 추가 · 삭제 양쪽을 본다 —
#   루트 화면 설정을 지우는 것도 실행 경로 변경이다. ⛔ 바뀐 hunk 의 문맥 줄 · hunk 머리도 본다 — 진입점 안에서 루트만
#   바꾸는 변경(`root.render(<New/>)` 옆의 바뀌지 않은 `createRoot(…)` · `WindowGroup { NewRoot() }`)은 바뀐 줄에 토큰이 없다.
LAUNCH_TOKENS = re.compile(
    r"rootViewController\s*=|setRootViewController|makeKeyAndVisible|UIApplicationMain|didFinishLaunching"
    r"|willConnectTo|@main\b|WindowGroup\b|setContentView\s*\(|createRoot\s*\(|ReactDOM\.render"
    r"|__name__\s*==\s*['\"]__main__['\"]|^\s*(?:func|fn)\s+main\s*\(",
    re.M)
LAUNCH_FILES = re.compile(
    r"(?:^|/)(?:(?:App|Scene)Delegate\.(?:swift|mm?)|main\.(?:swift|mm?|c|cc|cpp|go|rs|py|tsx|jsx)|__main__\.py"
    r"|Info\.plist|AndroidManifest\.xml|MainActivity\.(?:kt|java))$")

# PR 테스트(pr_tests · F-580) — diff 가 더하거나 고친 테스트 파일. 작성자가 고정하려는 동작의 신호인데 아무도 돌리지 않았다(새 테스트 17건 중
#   1건이 결정적으로 실패했는데 정적 렌즈 · GPT 독립 패스 · Curate 가 모두 통과시켰다). ⛔ 위험(risk)이 아니다 — Tier 를 올리지 않고
#   PR 테스트 실행 단계(modules/peer-review-tiers.md)가 무엇을 돌릴지 정하는 입력이다. 지운 테스트 파일은 돌릴 것이 없어 뺀다(추가 행 1줄 이상).
TEST_PATH = re.compile(
    r"(?:^|/)(?:[^/]*Tests?|tests?|__tests__|specs?)/"                     # 테스트 폴더 — Tests/ · FooTests/ · test/ · __tests__/ · spec/
    r"|(?:Tests?|Spec)\.(?:swift|kt|java|m|mm)$|(?:^|/)test_[^/]*\.py$|_test\.(?:py|go)$|\.(?:test|spec)\.[jt]sx?$")
TEST_NAME = re.compile(r"(?:Tests?|Spec)\.(?:swift|kt|java|m|mm)$|(?:^|/)test_[^/]*\.py$|_test\.(?:py|go)$|\.(?:test|spec)\.[jt]sx?$")
XCTEST_CLASS = re.compile(r"\b(?:class|struct)\s+(\w+)\s*:\s*(?:XCTest\.)?XCTestCase\b")


LOW_CONFIDENCE = {
    # ⛔ 카테고리에 속하지만 **단독으로는 그 카테고리를 성립시키지 못하는** 토큰.
    #    실측(F-165): 어떤 UI PR 이 `session` 을 지역 변수명으로 수십 번 써서
    #    auth 적중이 그만큼 쌓여 tier_delta +2 가 났다. 인증과 무관한 PR 이다.
    #    ⛔ 경계(`\bsession\b`)를 더 조여도 못 막는다 — 이미 경계이고 변수명이 정확히 그 단어다.
    #    처방은 경계 강화가 아니라 **신뢰도 분리**: samples 에는 남겨 사람이 보되,
    #    같은 hunk 에 고신뢰 토큰이 없으면 risk 계수에서 뺀다.
    "auth": {"session"},
}

# 저신뢰 토큰과 동반해야 그 카테고리를 성립시키는 고신뢰 토큰 (카테고리 패턴의 substring 갈래)
HIGH_CONFIDENCE = {
    "auth": re.compile(r"(?i)auth|token|secret|credential|permission|keychain|crypto|certificate|privacy"),
}


def _tally(matches):
    """매치를 토큰별로 센다. 대소문자는 무시한다 — `(?i)` 패턴이 `Auth`/`auth` 를
    서로 다른 토큰으로 만들면 net 비교가 어긋난다.
    ⚠️ 캡처 그룹이 있는 패턴은 findall 이 tuple 을 준다 — 첫 비어있지 않은 요소를 쓴다.
    """
    out = {}
    for m in matches:
        token = m if isinstance(m, str) else next((x for x in m if x), "")
        token = token.lower()
        if token:
            out[token] = out.get(token, 0) + 1
    return out


def _header_path(line):
    """`diff --git a/X b/X` 의 b 쪽 토큰(`+++ ` 줄과 같은 꼴)을 돌려준다. 양쪽 이름이 다르면 None.

    삭제 파일은 개명이 없어 양쪽 이름이 같다 — 가운데 공백으로 가르므로 공백이 든 경로도 풀린다.
    """
    rest = line[len("diff --git "):]
    mid = len(rest) // 2
    if len(rest) % 2 == 0 or rest[mid] != " ":
        return None
    a, b = rest[:mid], rest[mid + 1:]
    return b if a == b or a.replace("a/", "b/", 1) == b else None


def added_lines_by_file(diff_text):
    """추가된 **코드** 행만 파일별로 모은다.

    ⛔ hunk 상태를 추적한다. `+++ ` 는 hunk **밖**에서만 파일 헤더다 —
       hunk 안의 `+++ actor` 는 `++ actor` 를 추가한 소스 행이지 헤더가 아니다.
       상태 없이 접두사만 보면 그 행을 잃고 뒤따르는 추가 행도 엉뚱한 파일에 붙는다.
    ⛔ 삭제 파일은 `+++ /dev/null` 이라 경로가 `diff --git` 헤더에만 남는다(F-381). `+++` 를 그대로 쓰면
       삭제 행이 전부 '/dev/null' 한 키로 모이고, 지운 문서가 문서 제외를 피해 추가 코드의 순증을 상쇄한다.
       헤더를 못 풀면(대칭 아님) 예전처럼 '/dev/null' 로 모은다 — 행을 잃지는 않는다.
    """
    files, removed, current, in_hunk = {}, {}, None, False
    hunks, cur_hunk, header = [], None, None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current, in_hunk, cur_hunk = None, False, None
            header = _header_path(line)
        elif not in_hunk and line.startswith("+++ "):
            # ⛔ 인용 경로(core.quotePath — 비ASCII · 탭 · 따옴표)를 먼저 푼다 — 끝 글자 `"` 때문에 b/ 제거와 문서 접미사
            #    검사가 빗나가 지운 비ASCII 이름 문서의 auth 행이 추가 auth 순증을 상쇄했다(F-412)
            path = unquote_path(line[4:])
            if path == "/dev/null" and header:
                path = unquote_path(header)
            current = path[2:] if path.startswith("b/") else path
            if current.lower().endswith(DOC_SUFFIXES):
                current = None          # 문서는 수집하지 않는다
            else:
                files.setdefault(current, [])
                removed.setdefault(current, [])
        elif not in_hunk and line.startswith("--- "):
            continue
        elif line.startswith("@@"):
            in_hunk = True
            # ⛔ hunk 단위 묶음 — 저신뢰 토큰의 **동반 판정**에 쓴다. 파일 단위로 보면
            #    파일 어딘가에 auth 가 있다는 이유로 무관한 hunk 의 session 이 성립한다.
            cur_hunk = {"path": current, "added": [], "text": [line], "changed": False}   # text · changed — launch_surface 의 문맥 판정
            hunks.append(cur_hunk)
        elif in_hunk and current is not None:
            if cur_hunk is not None:
                cur_hunk["text"].append(line[1:])
                cur_hunk["changed"] = cur_hunk["changed"] or line[:1] in "+-"
            if line.startswith("+"):
                files[current].append(line[1:])
                if cur_hunk is not None:
                    cur_hunk["added"].append(line[1:])
            elif line.startswith("-"):
                removed[current].append(line[1:])
    return files, removed, hunks


def scan(diff_text):
    by_file, removed_by_file, hunks = added_lines_by_file(diff_text)
    all_added = [ln for lines in by_file.values() for ln in lines]
    all_removed = [ln for lines in removed_by_file.values() for ln in lines]
    blob = "\n".join(all_added)
    removed_blob = "\n".join(all_removed)

    # ⛔ **net-new** 만 위험으로 센다. 삭제 라인에 같은 신호가 같은 수만큼 있으면
    #    이 PR 이 만든 위험이 아니다 — 개명·이동에서 신호가 양쪽에 똑같이 나타난다.
    #    실측(한 개명 PR): `-@MainActor var isGiftWrapped` / `+@MainActor var includesGiftWrap`
    #    같은 쌍이 여럿. 추가 라인만 보면 concurrency 위험 1건으로 세어 Tier 1 크기의 PR 이 Tier 2 로 올라간다
    #    (agent 0콜 → 3콜). `risk_scan.py` 가 만들어진 이유(`Interactor` 오탐)와 같은 실패 클래스다.
    # ⚠️ **증분 가치 미증명 (2026-08-26 실측)**: 토큰 단위가 카테고리 단위와 판정이 갈린 실제 PR 은
#    **0/7** 이다. 구멍(`await`→`Task {`)은 합성 patch 로 찾았다(관측 N=0). 유지하는 이유는
#    엄격히 더 정확하고 측정된 downside 가 없어서다 — **필요했다는 주장이 아니다.**
# ⚠️ 한계: 위험한 신호를 5개 지우고 1개를 **더 위험한 자리**에 추가하면 net 이 음수여서
    #    승격하지 않는다. Tier 승격은 휴리스틱이고 cap 이 Tier 2 이므로 감수한다 —
    #    동시성 표면을 줄이는 변경이 실제로 더 안전하다는 판단이다.
    hits = {}
    axis = {}
    for k, (p, lab) in AXIS_CATEGORIES.items():
        extra = os.environ.get(AXIS_ENV[k], "").strip() if k in AXIS_ENV else ""
        axis[k] = ((p + "|(?i:%s)" % extra) if extra else p, lab)
    for name, (pattern, label) in list(CATEGORIES.items()) + list(axis.items()):
        two_way = name in TWO_WAY_AXES
        added_tokens = _tally(re.findall(pattern, blob))
        removed_tokens = _tally(re.findall(pattern, removed_blob)) if added_tokens or two_way else {}
        if not added_tokens and not removed_tokens:
            continue
        # ⛔ **토큰별로** 센다. 카테고리 합계로 세면 같은 카테고리 안의 **치환**을 놓친다 —
        #    실측: `-await other()` / `+Task { detached() }` 는 concurrency 합계 1:1 이라
        #    net 0 이 되어 미발화했다. 구조적 동시성에서 비구조적으로 바뀐 **새 위험**인데도.
        #    토큰별이면 `task {` 가 1>0 이라 발화하고, 개명 짝(`@mainactor` 5:5)은 그대로 미발화다.
        # 양방향 축(TWO_WAY_AXES)은 순감도 센다 — 등급 게이팅을 지운 diff(F-083)는 추가 행에 토큰이 없다
        if two_way:
            exceeded = {t: (added_tokens.get(t, 0), removed_tokens.get(t, 0)) for t in set(added_tokens) | set(removed_tokens)
                        if added_tokens.get(t, 0) != removed_tokens.get(t, 0)}
        else:
            exceeded = {t: (c, removed_tokens.get(t, 0))
                        for t, c in added_tokens.items() if c > removed_tokens.get(t, 0)}
        if not exceeded:
            continue          # 순증한 토큰이 없다 — 이 PR 이 만든 위험이 아니다
        hit = {
            "label": label,
            "samples": sorted(exceeded)[:3],
            "added": sum(added_tokens.values()),
            "removed": sum(removed_tokens.values()),
            "net_tokens": {t: v[0] - v[1] for t, v in exceeded.items()},
        }
        # ⛔ 저신뢰 토큰만으로 성립한 카테고리는 **같은 hunk** 의 고신뢰 토큰 동반을 요구한다.
        #    samples 는 그대로 둔다 — 사람이 보고 판정할 근거는 남기고, 자동 승격만 막는다.
        lo = LOW_CONFIDENCE.get(name)
        if lo and set(exceeded) <= lo:
            hi = HIGH_CONFIDENCE[name]
            lo_re = re.compile(r"(?i)\b(?:%s)\b" % "|".join(sorted(lo)))
            companion = any(lo_re.search(t) and hi.search(t)
                            for t in ("\n".join(h["added"]) for h in hunks))
            if not companion:
                hit["low_confidence_only"] = True
        if name in AXIS_CATEGORIES:
            hit["axis_only"] = True
        hits[name] = hit

    # 역방향: 싱글톤 선언과 가변 프로퍼티가 같은 파일에 있으면 동시성 위험
    for path, lines in by_file.items():
        gone_lines = removed_by_file.get(path, [])
        if (any(SINGLETON.search(ln) for ln in gone_lines)
                and any(MUTABLE.match(ln) for ln in gone_lines)):
            continue          # 삭제 쪽에도 같은 조합이 있었다 — 개명·이동
        if any(SINGLETON.search(ln) for ln in lines) and any(MUTABLE.match(ln) for ln in lines):
            entry = hits.setdefault("concurrency", {"label": "동시성", "samples": []})
            entry.setdefault("samples", []).append("reverse:shared+var")
            entry["reverse_signal"] = path
            break

    return {
        "launch_surface": launch_surface(by_file, removed_by_file, hunks),
        "pr_tests": pr_tests(by_file, hunks),
        "categories": sorted(hits),
        # ⛔ 저신뢰 단독 카테고리 · 관점 카테고리(axis_only)는 risk 에서 뺀다 — detail/categories 에는 남아 사람이 본다.
        "risk": sum(1 for h in hits.values() if not h.get("low_confidence_only") and not h.get("axis_only")),
        "detail": hits,
        "added_lines": len(all_added),
        "files": len(by_file),
        "runtime_axes": runtime_axes(blob, removed_blob),
        "doc_contract_deleted": doc_contract_deleted(diff_text),
        "plugin_refs": plugin_refs(by_file),
    }


def runtime_axes(blob, removed_blob):
    """실행 필요 축 — 추가 행에서 순증한 축 이름(정렬)."""
    return sorted(k for k, rx in RUNTIME_AXES.items() if len(rx.findall(blob)) > len(rx.findall(removed_blob)))


def doc_contract_deleted(diff_text):
    """`///` 주석만 지운 hunk 의 문장(F-013) — 코드는 남고 계약 문장만 사라진 자리. 같은 hunk 에 같은 문장이 다시 들어왔으면 뺀다."""
    out, path, header, in_hunk, rem, add = [], None, None, False, [], []

    def flush():
        docs = [l.strip()[3:].strip() for l in rem if l.strip().startswith("///")]
        code = [l for l in rem if l.strip() and not l.strip().startswith("///")]
        kept = {l.strip()[3:].strip() for l in add if l.strip().startswith("///")}
        lost = [d for d in docs if d and d not in kept]
        if path and lost and not code:
            out.append({"path": path, "lines": lost})

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush()
            rem, add, path, in_hunk, header = [], [], None, False, _header_path(line)
        elif not in_hunk and line.startswith("+++ "):
            p = unquote_path(line[4:])
            p = unquote_path(header) if p == "/dev/null" and header else p
            path = p[2:] if p.startswith("b/") else p
        elif line.startswith("@@"):
            flush()
            rem, add, in_hunk = [], [], True
        elif in_hunk and line.startswith("-"):
            rem.append(line[1:])
        elif in_hunk and line.startswith("+"):
            add.append(line[1:])
    flush()
    return out


def plugin_table():
    """modules/plugin-refs.md `## 자동 감지 트리거` 표 — [(토큰들, 플러그인, 참조 항목들)]. 표가 단일 출처다(F-520 — 조건을 세 토큰만 박아 뒀다)."""
    p = ROOT / "modules" / "plugin-refs.md"
    if not p.is_file():
        return None
    rows, on = [], False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            on = line.strip() == "## 자동 감지 트리거"
            continue
        if not (on and line.startswith("|") and "`" in line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        toks = [re.sub(r'"[^"]*"\)?$', "", t).rstrip(")") or t for t in re.findall(r"`([^`]+)`", cells[0])]
        refs = [r.strip() for r in re.split(r"\s*\(", cells[2])[0].split(",") if r.strip()]
        rows.append((toks, cells[1], refs))
    return rows


def plugin_refs(by_file):
    """Swift(`.swift`) 파일 추가 행에 표의 토큰이 있으면 그 행의 플러그인 · 참조 항목 — {플러그인: [참조 항목]}. 표가 없으면 None.

    ⛔ 파일별로 잰다 — 표는 Swift 플러그인 표다. 모든 파일의 추가 행을 blob 하나로 합치면 .ts · .py 의 async/await 도
       Swift Concurrency 참조를 Read 하라는 의무(pluginRefsRead)가 된다. 혼합 diff 는 파일마다 가르고 결과는 합집합이다.
       일반 동시성 범주(CATEGORIES)와 runtime_axes 는 언어와 무관하게 blob 으로 그대로 잰다.
    """
    rows = plugin_table()
    if rows is None:
        return None
    out = {}
    for path, lines in by_file.items():
        if not path.lower().endswith(".swift"):
            continue
        text = "\n".join(lines)
        for toks, plugin, refs in rows:
            if any(t and t in text for t in toks):
                out.setdefault(plugin, set()).update(refs)
    return {k: sorted(v) for k, v in sorted(out.items())}


def added_new_lines(diff_text):
    """파일별 추가 행의 새 쪽 줄 번호 집합."""
    out, path, header, in_hunk, n = {}, None, None, False, 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            path, in_hunk, header = None, False, _header_path(line)
        elif not in_hunk and line.startswith("+++ "):
            p = unquote_path(line[4:])
            path = None if p == "/dev/null" else (p[2:] if p.startswith("b/") else p)
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            n, in_hunk = (int(m.group(1)) if m else 0), True
        elif in_hunk and path:
            if line.startswith("+"):
                out.setdefault(path, set()).add(n)
                n += 1
            elif not line.startswith("-") and not line.startswith("\\"):
                n += 1
    return out


def guard_atoms(cond):
    parts = [" ".join(x.split()) for x in re.split(r",|&&", cond)]
    return [x for x in parts if x and x not in ("let self", "let self = self", "var self = self")]


def convention_deviations(diff_text, head_root):
    """F-516 — 바뀐 역할 블록의 guard 조건이 형제(같은 파일 · 같은 역할 이름 · 2곳 이상)가 모두 가진 조건을 빠뜨렸으면 그 차."""
    out = []
    for path, added in sorted(added_new_lines(diff_text).items()):
        f = Path(head_root) / path
        if path.lower().endswith(DOC_SUFFIXES) or not f.is_file():
            continue
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        occ = []
        for i, ln in enumerate(lines):
            m = ROLE_RE.search(ln)
            role = next((g for g in m.groups() if g), None) if m else None
            if not role or role in NOT_ROLES:
                continue
            atoms, gline = None, None
            for j in range(i, min(i + 6, len(lines))):
                g = GUARD_RE.search(lines[j])
                if g:
                    atoms, gline = guard_atoms(g.group(1)), j + 1
                    break
            occ.append((role, i + 1, atoms, (i + 1) in added or (gline in added if gline else False)))
        for role, ln, atoms, changed in occ:
            sib = [a for r, l2, a, _c in occ if r == role and l2 != ln and a is not None]
            if not changed or len(sib) < SIBLING_MIN:
                continue
            missing = sorted(set.intersection(*[set(a) for a in sib]) - set(atoms or []))
            if missing:
                out.append({"path": path, "role": role, "line": ln, "missing": missing, "siblings": len(sib)})
    return out + predicate_deviations(diff_text, head_root)


def _pred_subject(expr):
    """`url.scheme?.lowercased()` → `scheme` — 호출 마디(`()`)를 빼고 마지막 식별자."""
    segs = [s.strip("?!") for s in expr.split(".") if s and not s.endswith("()")]
    return segs[-1] if segs and segs[-1] else None


def predicate_forms(line):
    """한 줄의 {주어: 리터럴 집합} — `scheme == "http" || scheme == "https"` → {scheme: {http, https}}."""
    out = {}
    for m in PRED_EQ.finditer(line):
        subj, lit = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        s = _pred_subject(subj)
        if s:
            out.setdefault(s, set()).add(lit)
    for m in PRED_IN.finditer(line):
        s = _pred_subject(m.group(2))
        if s:
            out.setdefault(s, set()).update(re.findall(r'"([^"\\\n]*)"', m.group(1)))
    return out


def predicate_deviations(diff_text, head_root):
    """F-516 ② — 바뀐 줄의 판정식이 형제 술어 관례(같은 주어 · 바뀌지 않은 줄)의 진부분 · 진상위 집합이면 그 차와 N:M."""
    added = added_new_lines(diff_text)
    occ = []                                    # (경로, 줄, 주어, 리터럴 집합, 바뀐 줄인가)
    for dp, dirs, fs in os.walk(head_root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(fs):
            full = os.path.join(dp, name)
            rel = os.path.relpath(full, head_root).replace(os.sep, "/")
            if rel.lower().endswith(DOC_SUFFIXES):
                continue
            try:
                text = Path(full).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, ln in enumerate(text.splitlines(), 1):
                for subj, lits in predicate_forms(ln).items():
                    occ.append((rel, i, subj, frozenset(lits), i in added.get(rel, ())))
    out = []
    for path, ln, subj, form, changed in occ:
        if not changed:
            continue
        tally = {}
        for _p, _l, s2, f2, c2 in occ:
            if s2 == subj and not c2:
                tally[f2] = tally.get(f2, 0) + 1
        same = tally.get(form, 0)
        conv = [(n, sorted(f2)) for f2, n in tally.items()
                if f2 != form and (f2 < form or f2 > form) and n >= SIBLING_MIN and n > same]
        if conv:
            n, best = max(conv)
            out.append({"path": path, "line": ln, "subject": subj, "form": sorted(form), "convention": best, "tally": [n, same]})
    return out


def convention_md(devs):
    lines = ["# 형제 관례 대조 — 결정론 수집(판정 아님 · F-516)", "",
             "> 바뀐 클로저 · 분기마다 같은 파일의 같은 역할 형제(2곳 이상)가 **모두** 가진 guard 조건 중 이번 것에 없는 것이다.",
             "> 술어 관례: 바뀐 판정식의 리터럴 집합이 같은 주어 형제 판정식(바뀌지 않은 줄 · head 범위) 관례의 진부분 · 진상위 집합인 자리다(N:M = 관례 형 : 이번과 같은 형).",
             "> 누락인지 의도인지는 렌즈 · Lead 가 정한다 — `modules/peer-review-gates.md` Gate 4.9 `[관례 이탈]`.", ""]
    guard = [d for d in devs if "role" in d]
    pred = [d for d in devs if "subject" in d]
    if not guard:
        lines.append("형제 대비 빠진 guard 조건 없음(대조 가능한 역할 블록 기준).")
    for d in guard:
        lines.append("- `%s:%d` `%s` — 형제 %d곳이 모두 가진 조건 없음: %s"
                     % (d["path"], d["line"], d["role"], d["siblings"], ", ".join("`%s`" % m for m in d["missing"])))
    if not pred:
        lines.append("형제 술어 관례와 다른 판정식 없음(같은 주어 문자열 비교 · head 범위 기준 — 범위 밖 형제는 세지 않았다).")
    for d in pred:
        lines.append("- `%s:%d` `%s` 판정식 {%s} — 형제 관례 {%s} %d : 이번과 같은 형 %d"
                     % (d["path"], d["line"], d["subject"], ", ".join(d["form"]), ", ".join(d["convention"]), d["tally"][0], d["tally"][1]))
    return "\n".join(lines) + "\n"


def launch_surface(by_file, removed_by_file, hunks):
    """진입점 파일 경로 · 바뀐 hunk(추가 · 삭제 · 문맥 줄 · 머리) 안의 진입점 토큰을 신호로 모은다. 신호가 하나라도 있으면 flag."""
    signals = []
    for path in sorted(set(by_file) | set(removed_by_file)):
        if (by_file.get(path) or removed_by_file.get(path)) and LAUNCH_FILES.search(path or ""):
            signals.append("path:" + path)
    for h in hunks:
        if h["path"] is None or not h.get("changed"):
            continue
        for tok in sorted(set(LAUNCH_TOKENS.findall("\n".join(h["text"])))):
            sig = "token:%s (%s)" % (tok.strip(), h["path"])
            if sig not in signals:
                signals.append(sig)
    return {"flag": bool(signals), "signals": signals[:10]}


def pr_tests(by_file, hunks):
    """추가 행이 있는 테스트 파일 — [{path, suites}]. suites = 바뀐 hunk(추가 · 문맥 · 머리)의 XCTestCase 클래스 이름,
    없으면 파일 이름이 테스트 꼴일 때 그 줄기(XCTest 관례상 클래스 이름 · pytest 모듈 이름), 그도 아니면 빈 목록(테스트 폴더의 보조 파일)."""
    out = []
    for path in sorted(p for p, lines in by_file.items() if p and lines and TEST_PATH.search(p)):
        names = sorted({n for h in hunks if h["path"] == path for n in XCTEST_CLASS.findall("\n".join(h["text"]))})
        if not names and TEST_NAME.search(path):
            names = [os.path.splitext(os.path.basename(path))[0]]
        out.append({"path": path, "suites": names})
    return out


def escalation(risk):
    """카테고리 수 → tier 증가분. 임계는 기존과 같고 세는 단위만 행에서 카테고리로 바뀐다."""
    if risk >= 2:
        return 2
    return 1 if risk == 1 else 0


def main(argv):
    args, opts, rest = [], {}, list(argv[1:])
    while rest:
        a = rest.pop(0)
        if a in ("--head", "--convention-md"):
            if not rest:
                sys.stderr.write("%s 에 값이 없다\n" % a)
                return 2
            opts[a] = rest.pop(0)
        elif not a.startswith("--"):
            args.append(a)
    if len(args) != 1:
        sys.stderr.write("usage: risk_scan.py DIFF_PATH [--json] [--head HEAD_DIR [--convention-md OUT]]\n")
        return 2
    try:
        with open(args[0], encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        sys.stderr.write("diff 를 읽을 수 없다: %s\n" % exc)
        return 2

    result = scan(text)
    result["tier_delta"] = escalation(result["risk"])
    if "--head" in opts and os.path.isdir(opts["--head"]):
        result["convention_deviations"] = convention_deviations(text, opts["--head"])
        if "--convention-md" in opts:
            with open(opts["--convention-md"], "w", encoding="utf-8") as fh:
                fh.write(convention_md(result["convention_deviations"]))

    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("risk=%d tier_delta=+%d (added %d lines / %d files)"
              % (result["risk"], result["tier_delta"], result["added_lines"], result["files"]))
        ls = result["launch_surface"]
        if ls["flag"]:
            print("  launch_surface 실행 필요 표면 — %s" % ", ".join(ls["signals"][:3]))
        for name in result["categories"]:
            d = result["detail"][name]
            note = " [역방향: %s]" % d["reverse_signal"] if "reverse_signal" in d else ""
            if "net_tokens" in d:
                net = " (추가 %d / 삭제 %d · 순증 %s)" % (
                    d["added"], d["removed"],
                    ", ".join("%s%+d" % (t, n) for t, n in sorted(d["net_tokens"].items())))   # 양방향 축은 음수(순감)도 있다
            else:
                net = ""
            print("  %-13s %s%s%s  %s" % (name, d["label"], note, net, ", ".join(d["samples"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
