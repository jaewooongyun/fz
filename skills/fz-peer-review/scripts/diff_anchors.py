#!/usr/bin/env python3
# diff-parse: hunk-state — `header_done` 로 헤더 구간을 닫고, 내용 라인 `-- x` 가
#   `--- x` 로 보이는 것을 `startswith("---- ")` 로 배제한다.
"""diff_anchors.py — 지적 구간이 GitHub 인라인 코멘트로 앵커 가능한지 판정한다.

계약·테스트 케이스: skills/fz-peer-review/references/test-spec.md "인라인 앵커 계산"

GitHub는 diff에 포함된 줄에만 인라인 코멘트를 달 수 있고, start_line~line은
같은 hunk 안이어야 한다. 이 판정은 binary라 언어 지시가 아닌 스크립트가 맡는다
(guides/skill-authoring.md 11).

어느 hunk가 논지인지는 의미 판단이므로 스크립트는 고르지 않는다 —
겹치는 hunk를 모두 반환하고 선택은 Lead에게 남긴다.

side 지원: RIGHT(신규 측)는 hunk의 + 범위, LEFT(변경 전 측)는 - 범위로 계산한다.
삭제된 코드를 지적하려면 LEFT가 필요하므로 두 좌표계를 모두 보존한다.

파싱은 `diff --git` 경계 기반 상태 머신이다. 헤더 판정만으로 파일을 바꾸면
diff 본문에 들어 있는 `+++ b/...` 추가 라인(패치 파일을 리뷰할 때 발생)이
파일 경계를 오염시켜 hunk가 엉뚱한 경로에 귀속된다.

의존성: Python 표준 라이브러리만. 외부 패키지/CLI 호출 금지
(같은 레포 ac8-link-check.sh가 rg 하드 의존으로 미설치 환경에서 exit 127).
"""

import argparse
import json
import re
import sys

HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)
DIFF_GIT_RE = re.compile(r"^diff --git ")
OLD_HDR_RE = re.compile(r"^--- (.+)$")
NEW_HDR_RE = re.compile(r"^\+\+\+ (.+)$")
VALID_SIDES = ("RIGHT", "LEFT")


def unquote_path(raw):
    """Git은 특수문자가 있는 경로를 C 스타일로 인용한다: "b/dir/file name.txt".

    비ASCII는 UTF-8 **바이트**를 octal escape로 쓴다("b/\\355\\225\\234.txt" = 한글).
    그래서 escape를 문자로 바로 풀면 mojibake가 된다 — 바이트로 되돌린 뒤
    UTF-8로 디코드해야 한다.
    """
    raw = raw.strip()
    # 후행 탭 + 타임스탬프 (git diff --no-index 등)
    raw = raw.split("\t", 1)[0].strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        inner = raw[1:-1]
        try:
            as_bytes = (
                inner.encode("latin-1", "backslashreplace")
                .decode("unicode_escape")
                .encode("latin-1")
            )
            raw = as_bytes.decode("utf-8", "replace")
        except (UnicodeDecodeError, UnicodeEncodeError):
            raw = inner
    return raw


def strip_prefix(path):
    """a/ · b/ prefix 제거. /dev/null은 그대로 둔다."""
    if path == "/dev/null":
        return path
    if len(path) > 2 and path[1] == "/" and path[0] in "ab":
        return path[2:]
    return path


def parse_hunks(diff_text):
    """diff 텍스트 → {경로: {'old': [(s,e)], 'new': [(s,e)]}}

    `diff --git` 경계로 파일 블록을 나누고, 각 블록 안에서 **첫 ---/+++ 쌍만**
    헤더로 인정한다. 이후 등장하는 +++ 는 본문(추가 라인)이므로 무시한다.
    """
    files = {}
    old_path = new_path = None
    header_done = False

    def register(path):
        if path and path != "/dev/null":
            files.setdefault(path, {"old": [], "new": []})

    for line in diff_text.splitlines():
        if DIFF_GIT_RE.match(line):
            old_path = new_path = None
            header_done = False
            continue

        if not header_done:
            m = OLD_HDR_RE.match(line)
            if m and not line.startswith("---- "):
                old_path = strip_prefix(unquote_path(m.group(1)))
                continue
            m = NEW_HDR_RE.match(line)
            if m:
                new_path = strip_prefix(unquote_path(m.group(1)))
                header_done = True
                register(new_path)
                register(old_path)
                continue

        m = HUNK_RE.match(line)
        if not m:
            continue
        o_start = int(m.group(1))
        o_count = int(m.group(2)) if m.group(2) is not None else 1
        n_start = int(m.group(3))
        n_count = int(m.group(4)) if m.group(4) is not None else 1
        if new_path and new_path != "/dev/null" and n_count > 0:
            files[new_path]["new"].append((n_start, n_start + n_count - 1))
        if old_path and old_path != "/dev/null" and o_count > 0:
            files[old_path]["old"].append((o_start, o_start + o_count - 1))

    return files


def resolve_path(requested, known_paths):
    """리뷰는 basename으로 파일을 부르고 diff는 전체 경로를 쓴다.

    정확 일치 우선, 없으면 유일한 suffix 일치를 채택한다.
    복수 일치는 임의로 고르지 않고 호출자에게 되돌린다.
    """
    needle = strip_prefix(unquote_path(requested)).lstrip("./")
    if needle in known_paths:
        return needle, None
    matches = [p for p in known_paths if p == needle or p.endswith("/" + needle)]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "ambiguous_path"
    return None, "path_not_in_diff"


def compute(files, targets):
    anchorable, non_anchorable = [], []
    for t in targets:
        req, start, end = t["path"], t["start"], t["end"]
        side = t.get("side", "RIGHT")
        resolved, reason = resolve_path(req, files.keys())
        if resolved is None:
            non_anchorable.append(
                {"path": req, "start": start, "end": end, "side": side, "reason": reason}
            )
            continue

        key = "new" if side == "RIGHT" else "old"
        hunks = files[resolved][key]
        if not hunks:
            # diff에는 있으나 해당 side에 앵커할 hunk가 없다 (바이너리 · 순수
            # 추가 파일의 LEFT · 순수 삭제 hunk의 RIGHT). path_not_in_diff와 구분한다.
            non_anchorable.append(
                {"path": resolved, "start": start, "end": end, "side": side,
                 "reason": "no_hunks_on_side"}
            )
            continue

        overlaps = [(a, b) for a, b in hunks if not (b < start or a > end)]
        if not overlaps:
            non_anchorable.append(
                {"path": resolved, "start": start, "end": end, "side": side,
                 "reason": "outside_diff"}
            )
            continue

        # 겹치는 hunk마다 교집합 구간을 하나씩. 잘라내기는 해도 고르지는 않는다.
        for a, b in overlaps:
            anchorable.append(
                {
                    "path": resolved,
                    "side": side,
                    "start_line": max(a, start),
                    "line": min(b, end),
                    "hunk_start": a,
                    "hunk_end": b,
                }
            )
    return {"anchorable": anchorable, "non_anchorable": non_anchorable}


def load_targets(raw):
    targets = json.loads(raw)
    if not isinstance(targets, list):
        raise ValueError("targets는 배열이어야 한다")
    for t in targets:
        for key in ("path", "start", "end"):
            if key not in t:
                raise ValueError(f"target에 '{key}' 누락: {t}")
        if not isinstance(t["start"], int) or not isinstance(t["end"], int):
            raise ValueError(f"start/end는 정수여야 한다: {t}")
        if t["start"] > t["end"]:
            raise ValueError(f"start > end: {t}")
        if t.get("side", "RIGHT") not in VALID_SIDES:
            raise ValueError(f"side는 RIGHT 또는 LEFT여야 한다: {t}")
    return targets


def main():
    ap = argparse.ArgumentParser(description="지적 구간의 인라인 앵커 가능 여부 판정")
    ap.add_argument("--diff", required=True, help="diff.patch 경로")
    ap.add_argument(
        "--targets",
        required=True,
        help='JSON 배열: [{"path":"...","start":N,"end":M,"side":"RIGHT|LEFT"}, ...]',
    )
    args = ap.parse_args()

    # 입력 오류는 부분 출력 없이 exit 1로 끊는다 — 반쪽 결과가 payload로 흘러가면
    # 엉뚱한 줄에 코멘트가 달린다.
    try:
        targets = load_targets(args.targets)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"targets 파싱 실패: {e}", file=sys.stderr)
        return 1
    try:
        with open(args.diff, encoding="utf-8", errors="replace") as f:
            diff_text = f.read()
    except OSError as e:
        print(f"diff 읽기 실패: {e}", file=sys.stderr)
        return 1

    result = compute(parse_hunks(diff_text), targets)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
