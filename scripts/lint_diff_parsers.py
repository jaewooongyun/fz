#!/usr/bin/env python3
"""diff 라인 접두사로 판정하는 파일이 hunk 상태를 선언했는지 검사한다.

⛔ 신설 근거 (2026-08-25): 같은 결함이 **한 세션에 4번** 나왔다.
  · `risk_scan.py`   hunk 안의 `+++ actor` 를 파일 헤더로 오인 → 추가 행 유실
  · `gather.sh`      base 목록을 `+++ b/` 로 뽑아 **삭제 파일 통째 누락**
  · numstat 폴백     `for(k in a)` → 삭제만 있는 파일 누락
  · numstat 폴백     `/^\\+[^+]/` → **빈 추가 행**과 `++ …` 유실 (같은 함수의 2차 결함)
  정답은 같은 디렉터리의 `diff_anchors.py`(`header_done`)와 `verify-rebase.sh`(`inhdr`)에
  **이미 있었다.** 산문 규칙으로는 옆 파일을 안 본다 — 그래서 게이트로 만든다.

왜 hunk 상태가 필수인가: `+`·`-`·`+++`·`---` 는 hunk **안팎에서 뜻이 다르다.**
hunk 밖의 `+++ b/x` 는 파일 헤더지만, hunk 안의 `+++ x` 는 `++ x` 를 추가한 소스 행이다.
상태 없이 접두사만 보면 그 행을 잃고, 뒤따르는 행의 파일 귀속까지 엉킨다.
⛔ 변경 규모는 auto-tier 입력이라 유실은 **낮은 Tier 로 기울게** 만든다 — 실패가 아니라
   "작은 PR 이라 경량 경로가 맞다"처럼 보이는 형태다.

## 계약

diff 라인 접두사를 판정에 쓰는 파일은 첫 40행 안에 선언 1줄을 둔다:

    # diff-parse: hunk-state   — hunk/헤더 상태를 추적한다 (`@@` 참조 필수)
    # diff-parse: not-a-diff   — 접두사가 diff 가 아니다 (CLI 인자·git cherry 등). 사유 필수
    # diff-parse: waived       — 알면서 안 한다. 사유 + 영향 필수

⚠️ 한계 1 — **범위**: `.py`·`.sh`·`.awk`·`.js` 파일만 본다. **`.md` 안의 인라인 bash 는 대상이 아니다.**
   이 레포는 절차를 문서 안 bash 로 적는 관용구가 있고(`risk_scan.py` 가 대체한 것이 바로 그것),
   실측 결과 지금은 접두사 판정이 0건이지만(`tiers.md § 자동 선택` 은 `--numstat` **컬럼**을 본다)
   **"위반 0건"을 전수로 읽지 말 것.**
   ⛔ 판정 로직이 문서에서 스크립트로 옮겨가는 것이 이 레포의 방향이므로 범위를 넓히기보다
      새 판정 로직을 스크립트로 쓰게 하는 쪽이 맞다.

⚠️ 한계 2 — **입도**: `.sh` 안 heredoc 은 래퍼 파일의 선언 1개로 판정된다. 한 파일에
   파서가 여럿이면 선언 1줄이 전부를 대표한다.

⚠️ 한계 3: 선언은 **주장**이다. `hunk-state` 인데 실제로 안 하는 것을 완전히 막지는 못한다
(`@@` 참조 유무만 교차 확인한다). 그래도 산문 규칙보다 강하다 — 새 파서를 쓰는 사람이
선언을 쓰려면 세 갈래 중 하나를 **고르게** 되고, 고르려면 함정을 읽게 된다.

usage:
  lint_diff_parsers.py [--json] [--self-test]

exit: 0 위반 0건 / 1 위반 있음 / 2 검사기 고장 · 읽기 실패(UNKNOWN)
  ⛔ UNKNOWN 을 통과로 읽지 않는다 — 도구 실패가 "안전"이 되면 게이트가 사라진다.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MODES = ("hunk-state", "not-a-diff", "waived")
# 선언은 **줄 전체가 주석인 한 줄**이어야 한다.
DECL = re.compile(r"^\s*(?:#|//)\s*diff-parse:\s*(" + "|".join(MODES) + r")\b([^\n]*)", re.M)
DECL_HEAD_LINES = 40

# ⛔ 검사기는 자기를 검사하지 못한다. 이 파일은 계약 **문구**를 담고 있어서
#    선언 정규식이 자기 문서에 매칭된다 — 계약을 설명하면 계약을 만족하는 셈이다.
#    실제로 첫 실행에서 이 파일이 `hunk-state` 로 통과했다. 자기참조는 제외로 끊는다.
SELF = "scripts/lint_diff_parsers.py"

# diff 라인 접두사를 **판정에 쓰는** 표현.
# ⛔ `-` 는 한 글자만 본다. `startswith("--")` 는 CLI 인자 파싱이고 diff 가 아니다
#    (`measure_constraint_load.py` 에서 실제 오탐이었다).
SIGNALS = (
    (re.compile(r"""startswith\(\s*['"]\+"""), "py:startswith('+"),
    (re.compile(r"""startswith\(\s*['"]-(?:['"]|--\s)"""), "py:startswith('-"),
    (re.compile(r"""startsWith\(\s*['"]\+"""), "js:startsWith('+"),
    (re.compile(r"""startsWith\(\s*['"]-(?:['"]|--\s)"""), "js:startsWith('-"),
    (re.compile(r"/\^\\?\+"), "awk:/^+"),
    (re.compile(r"/\^-(?!\w)"), "awk:/^-"),
    (re.compile(r"""grep\s[^|;]*['"]\^\\?\+"""), "bash:grep '^+"),
    (re.compile(r"""grep\s[^|;]*['"]\^-"""), "bash:grep '^-"),
    (re.compile(r'r?["\']\^\\\+'), 're:"^\\\\+"'),
    # ⛔ 정규식 형태의 `-` 쪽 헤더. `diff_anchors.py:35` 의 `^--- ` 가 이 형태인데
    #    첫 판이 못 봤다(다른 신호로 **우연히** 잡혔다).
    # ⛔ 3-dash 뒤 **공백을 요구**한다. diff 헤더는 언제나 `--- <경로>` 지만
    #    YAML frontmatter 는 `---` 만 있다 — 요구하지 않으면 frontmatter 파서가
    #    전부 걸린다 (`parse_memory.py:48` 이 실제 오탐이었다).
    #    ⚠️ 그래서 공백 없는 `---` 판정은 **놓친다.** 비용은 낮다 — 실제 diff 파서는
    #       `+` 쪽도 반드시 읽으므로 위의 plus 신호가 이미 잡는다. 이 신호는 여분의 그물이다.
    #    ⛔ **리터럴 공백만** 요구한다. `\\s` 까지 허용하면 frontmatter(`^---\\s*\\n`)가
    #       다시 걸린다 — 관대하게 만들려던 첫 시도가 정확히 그 오탐을 되살렸다.
    (re.compile(r'r?["\']\^-{3} '), 're:"^--- "'),
    (re.compile(r"""startswith\(\s*['"]--- """), "py:startswith('--- "),
    (re.compile(r"""startsWith\(\s*['"]--- """), "js:startsWith('--- "),
)

AT_MARK = re.compile(r"@@")
EXTS = (".py", ".sh", ".awk", ".js")
SKIP_DIRS = {"node_modules", ".git", ".claude"}

# ⛔ 주석 안의 예시를 코드로 세지 않는다. `test-gates.sh` 의 `# grep '^+' 0매치가…` 가
#    실제 오탐이었다. 문자열 리터럴까지 파싱하지 않고 **줄 전체 주석만** 걷는다 —
#    인라인 주석을 걷으려면 리터럴 인식이 필요하고 그쪽이 오히려 위험하다.
LINE_COMMENT = {".py": "#", ".sh": "#", ".awk": "#", ".js": "//"}


def code_only(text, ext):
    marker = LINE_COMMENT.get(ext, "#")
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(marker) or stripped.startswith("*"):
            continue
        out.append(line)
    return "\n".join(out)


def classify(path, text, ext):
    """(verdict, signals, mode) — verdict ∈ ok | violation | not-parser"""
    code = code_only(text, ext)
    signals = [name for rx, name in SIGNALS if rx.search(code)]
    if not signals:
        return "not-parser", [], None
    head = "\n".join(text.splitlines()[:DECL_HEAD_LINES])
    pairs = DECL.findall(head)
    found = [m[0] for m in pairs]
    if not found:
        return "violation", signals, None
    # ⛔ 세 갈래를 **나열**하면 선언이 아니라 문서다. 선언은 하나를 **고르는** 행위다 —
    #    나열을 통과시키면 계약을 설명한 파일이 계약을 만족한다.
    if len(set(found)) > 1:
        return "violation", signals, "선언 아님(모드 %d종 나열)" % len(set(found))
    mode = found[0]
    # 사유 텍스트를 붙여 리포트에 싣는다 — `✅` 만 보이면 "선언했다"가 "옳다"로 읽힌다.
    reason = pairs[0][1].strip(" —-").strip()
    if reason:
        mode = "%s — %s" % (mode, reason)
    if found[0] == "hunk-state" and not AT_MARK.search(code):
        # 선언은 상태 추적이라는데 `@@` 를 안 본다 — 선언과 코드가 어긋난다
        return "violation", signals, "hunk-state(@@ 참조 없음)"
    return "ok", signals, mode


def scan(root, roots=("scripts", "skills", "workflows", "agents", "tests")):
    results, unknown = [], []
    for r in roots:
        base = os.path.join(root, r)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in sorted(filenames):
                ext = os.path.splitext(fn)[1]
                if ext not in EXTS:
                    continue
                p = os.path.join(dirpath, fn)
                if os.path.relpath(p, root) == SELF:
                    continue
                try:
                    with open(p, encoding="utf-8", errors="strict") as fh:
                        text = fh.read()
                except (OSError, UnicodeDecodeError) as exc:
                    unknown.append((os.path.relpath(p, root), str(exc)))
                    continue
                verdict, signals, mode = classify(p, text, ext)
                if verdict == "not-parser":
                    continue
                results.append({
                    "file": os.path.relpath(p, root),
                    "verdict": verdict, "signals": signals, "mode": mode,
                })
    return results, unknown


SELF_TESTS = (
    # (이름, 확장자, 본문, 기대 verdict)
    ("선언 없는 파서 → 위반", ".py",
     'for line in d:\n    if line.startswith("+++ "):\n        pass\n', "violation"),
    ("hunk-state 선언 + @@ → 통과", ".py",
     '# diff-parse: hunk-state\nfor line in d:\n    if line.startswith("@@"):\n'
     '        h = True\n    elif line.startswith("+"):\n        pass\n', "ok"),
    ("hunk-state 선언인데 @@ 없음 → 위반", ".py",
     '# diff-parse: hunk-state\nif line.startswith("+"):\n    pass\n', "violation"),
    ("not-a-diff 선언 → 통과", ".sh",
     '# diff-parse: not-a-diff — git cherry 출력의 +/- 는 upstream 여부다\n'
     "x=$(printf '%s' \"$o\" | grep '^+')\n", "ok"),
    # ⛔ 실제 오탐 2건을 못박는다 — 이것들이 위반으로 잡히면 게이트가 노이즈가 된다
    ("CLI 인자 파싱은 파서 아님", ".py",
     'args = [a for a in sys.argv[1:] if not a.startswith("--")]\n', "not-parser"),
    ("줄 전체 주석 안의 grep 은 파서 아님", ".sh",
     "# grep '^+' 는 0매치에서 exit 1 이다\necho hi\n", "not-parser"),
    ("diff 무관 파일 → 파서 아님", ".py", 'print("hello")\n', "not-parser"),
    # ⛔ 검사기가 자기 문서에 통과했던 실제 사례를 못박는다
    ("모드 나열은 선언이 아니다", ".py",
     '# diff-parse: hunk-state | not-a-diff | waived\nif line.startswith("+"):\n    pass\n',
     "violation"),
    # 실측 0건이지만 형태로 존재 가능 — 미탐지를 미리 닫는다
    ("정규식 ^--- 헤더 파서 (선언 없음) → 위반", ".py",
     'OLD = re.compile(r"^--- (.+)$")\n', "violation"),
    ("startswith(\'--- \') → 파서로 인식", ".py",
     "if line.startswith('--- '):\n    pass\n", "violation"),
    # ⛔ markdown 체크박스는 diff 가 아니다 (gate_check.py:73 실제 사례)
    # ⛔ YAML frontmatter 는 diff 가 아니다 (parse_memory.py:48 실제 오탐)
    ("YAML frontmatter 정규식은 파서 아님", ".py",
     'FM = re.compile(r"^---\\s*\\n(.*?)\\n---\\s*\\n", re.DOTALL)\n', "not-parser"),
    ("markdown 체크박스 정규식은 파서 아님", ".py",
     'GATE_RE = re.compile(r"^- \\[( |x)\\] (.+)$")\n', "not-parser"),
    ("문장 안의 diff-parse: 는 선언 아님", ".py",
     'x = "diff-parse: hunk-state"\nif line.startswith("@@"):\n    h=1\nif line.startswith("+"):\n    pass\n',
     "violation"),
)


def self_test():
    fail = 0
    for name, ext, body, want in SELF_TESTS:
        got, signals, mode = classify("<mem>" + ext, body, ext)
        ok = got == want
        print("%s  %-40s got=%-11s want=%s %s"
              % ("PASS" if ok else "FAIL", name, got, want,
                 ",".join(signals) if signals else ""))
        if not ok:
            fail += 1
    print("\n%d/%d 통과" % (len(SELF_TESTS) - fail, len(SELF_TESTS)))
    return 1 if fail else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    results, unknown = scan(str(ROOT))
    violations = [r for r in results if r["verdict"] == "violation"]

    if "--json" in argv:
        print(json.dumps({"results": results, "unknown": unknown,
                          "violations": len(violations)}, ensure_ascii=False, indent=1))
    else:
        print("diff 파서 선언 검사 — 대상 %d 파일" % len(results))
        for r in sorted(results, key=lambda x: (x["verdict"] != "violation", x["file"])):
            mark = "⛔" if r["verdict"] == "violation" else "✅"
            print("  %s %-58s %s  [%s]"
                  % (mark, r["file"], r["mode"] or "선언 없음", ",".join(r["signals"])))
        for f, why in unknown:
            print("  ⚠️ UNKNOWN %-52s %s" % (f, why))
        if violations:
            print("\n⛔ 위반 %d건 — 첫 %d행에 선언 1줄을 둔다:" % (len(violations), DECL_HEAD_LINES))
            print("   # diff-parse: hunk-state | not-a-diff | waived   (사유 함께)")
        else:
            print("\n✅ 위반 0건")

    if unknown:
        return 2          # ⛔ 읽지 못한 파일을 통과로 읽지 않는다
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
