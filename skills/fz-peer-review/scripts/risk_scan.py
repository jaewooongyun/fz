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
114줄 PR 이 상위 Tier 로 올라가 3~6 agent call 을 유발했다.

usage:
  risk_scan.py DIFF_PATH [--json]

exit: 0 = 판정 성공 / 2 = 사용법·입력 오류
  ⛔ exit 0 은 "위험 없음"이 아니다. 위험 수는 stdout 으로 읽는다.
"""
import json
import re
import sys

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


def added_lines_by_file(diff_text):
    """추가된 **코드** 행만 파일별로 모은다.

    ⛔ hunk 상태를 추적한다. `+++ ` 는 hunk **밖**에서만 파일 헤더다 —
       hunk 안의 `+++ actor` 는 `++ actor` 를 추가한 소스 행이지 헤더가 아니다.
       상태 없이 접두사만 보면 그 행을 잃고 뒤따르는 추가 행도 엉뚱한 파일에 붙는다.
    """
    files, removed, current, in_hunk = {}, {}, None, False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current, in_hunk = None, False
        elif not in_hunk and line.startswith("+++ "):
            path = line[4:].strip()
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
        elif in_hunk and current is not None:
            if line.startswith("+"):
                files[current].append(line[1:])
            elif line.startswith("-"):
                removed[current].append(line[1:])
    return files, removed


def scan(diff_text):
    by_file, removed_by_file = added_lines_by_file(diff_text)
    all_added = [ln for lines in by_file.values() for ln in lines]
    all_removed = [ln for lines in removed_by_file.values() for ln in lines]
    blob = "\n".join(all_added)
    removed_blob = "\n".join(all_removed)

    # ⛔ **net-new** 만 위험으로 센다. 삭제 라인에 같은 신호가 같은 수만큼 있으면
    #    이 PR 이 만든 위험이 아니다 — 개명·이동에서 신호가 양쪽에 똑같이 나타난다.
    #    실측(#4766): `-@MainActor var isExtendedLayout` / `+@MainActor var supportsSplitLayout`
    #    5쌍. 추가 라인만 보면 concurrency 위험 1건으로 세어 166줄 PR 이 Tier 1→2 로 올라간다
    #    (agent 0콜 → 3콜). `risk_scan.py` 가 만들어진 이유(`Interactor` 오탐)와 같은 실패 클래스다.
    # ⚠️ **증분 가치 미증명 (2026-08-26 실측)**: 토큰 단위가 카테고리 단위와 판정이 갈린 실제 PR 은
#    **0/7** 이다. 구멍(`await`→`Task {`)은 합성 patch 로 찾았다(관측 N=0). 유지하는 이유는
#    엄격히 더 정확하고 측정된 downside 가 없어서다 — **필요했다는 주장이 아니다.**
# ⚠️ 한계: 위험한 신호를 5개 지우고 1개를 **더 위험한 자리**에 추가하면 net 이 음수여서
    #    승격하지 않는다. Tier 승격은 휴리스틱이고 cap 이 Tier 2 이므로 감수한다 —
    #    동시성 표면을 줄이는 변경이 실제로 더 안전하다는 판단이다.
    hits = {}
    for name, (pattern, label) in CATEGORIES.items():
        added_tokens = _tally(re.findall(pattern, blob))
        if not added_tokens:
            continue
        removed_tokens = _tally(re.findall(pattern, removed_blob))
        # ⛔ **토큰별로** 센다. 카테고리 합계로 세면 같은 카테고리 안의 **치환**을 놓친다 —
        #    실측: `-await other()` / `+Task { detached() }` 는 concurrency 합계 1:1 이라
        #    net 0 이 되어 미발화했다. 구조적 동시성에서 비구조적으로 바뀐 **새 위험**인데도.
        #    토큰별이면 `task {` 가 1>0 이라 발화하고, 개명 짝(`@mainactor` 5:5)은 그대로 미발화다.
        exceeded = {t: (c, removed_tokens.get(t, 0))
                    for t, c in added_tokens.items() if c > removed_tokens.get(t, 0)}
        if not exceeded:
            continue          # 순증한 토큰이 없다 — 이 PR 이 만든 위험이 아니다
        hits[name] = {
            "label": label,
            "samples": sorted(exceeded)[:3],
            "added": sum(added_tokens.values()),
            "removed": sum(removed_tokens.values()),
            "net_tokens": {t: v[0] - v[1] for t, v in exceeded.items()},
        }

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
        "categories": sorted(hits),
        "risk": len(hits),
        "detail": hits,
        "added_lines": len(all_added),
        "files": len(by_file),
    }


def escalation(risk):
    """카테고리 수 → tier 증가분. 임계는 기존과 같고 세는 단위만 행에서 카테고리로 바뀐다."""
    if risk >= 2:
        return 2
    return 1 if risk == 1 else 0


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.stderr.write("usage: risk_scan.py DIFF_PATH [--json]\n")
        return 2
    try:
        with open(args[0], encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        sys.stderr.write("diff 를 읽을 수 없다: %s\n" % exc)
        return 2

    result = scan(text)
    result["tier_delta"] = escalation(result["risk"])

    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("risk=%d tier_delta=+%d (added %d lines / %d files)"
              % (result["risk"], result["tier_delta"], result["added_lines"], result["files"]))
        for name in result["categories"]:
            d = result["detail"][name]
            note = " [역방향: %s]" % d["reverse_signal"] if "reverse_signal" in d else ""
            if "net_tokens" in d:
                net = " (추가 %d / 삭제 %d · 순증 %s)" % (
                    d["added"], d["removed"],
                    ", ".join("%s+%d" % (t, n) for t, n in sorted(d["net_tokens"].items())))
            else:
                net = ""
            print("  %-13s %s%s%s  %s" % (name, d["label"], note, net, ", ".join(d["samples"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
