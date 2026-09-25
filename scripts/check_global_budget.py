#!/usr/bin/env python3
"""check_global_budget.py — 워크플로의 **동시 스폰이 모델 비용 상한을 넘는가** (B5 / v7 G-1).

왜: `guides/model-guide.md` §5 가 *"opus 동시 ≤3 · fable 동시 1 · 총 ≤4"* 를 불변으로 규정하는데,
그것을 어기는지 보는 기계 검사가 없었다. 워크플로가 `parallel([...])` 안에 opus 4개를 넣어도
문서는 초록으로 남는다.

⛔ **상한 수치를 여기 적지 않는다.** 정본은 `model-guide.md` §5 한 곳이고, 이 스크립트는
그 문장을 **파싱해서 읽는다**. 수치를 복사해 두면 정본이 바뀔 때 조용히 어긋난다
(`modules/governance.md` § Truth-of-Source 가 지정한 단일 출처 규약).

⛔ **advisor 사각지대는 이 검사의 범위 밖이다** — `governance.md` 가 명시하듯 advisor 는
스폰된 에이전트가 아니라 서버사이드 tool call 이라 어떤 동시 상한도 bound 하지 못한다.
여기서 통과해도 그 지출은 재지지 않는다.

exit code:
  0  PASS — 모든 parallel 블록이 상한 이내
  1  VIOLATION — 상한 초과 블록이 있다
  2  UNRUN — 정본 수치 파싱 실패·워크플로 0건 등 판정 불가. ⛔ 통과로 읽지 않는다

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

GUIDE = "guides/model-guide.md"
# 정본 문장: "opus 동시 ≤3 · fable 에이전트 **동시 1개**(Lead 세션 제외) · 총 ≤4"
LIMIT_OPUS = re.compile(r"opus\s*동시\s*[≤<=]+\s*(\d+)")
LIMIT_FABLE = re.compile(r"fable[^·\n]*?동시\s*\*{0,2}(\d+)\s*개")
LIMIT_TOTAL = re.compile(r"총\s*[≤<=]+\s*(\d+)")
# parallel([...]) 블록 — 괄호 균형으로 끝을 찾는다
PARALLEL = re.compile(r"parallel\s*\(\s*\[")
MODEL = re.compile(r"model:\s*'([a-z0-9.-]+)'")


def log(*a):
    print(*a, file=sys.stderr)


def read_limits(root: pathlib.Path):
    """정본에서 상한을 **읽는다**. 못 읽으면 UNRUN — 기본값으로 때우지 않는다."""
    g = root / GUIDE
    if not g.is_file():
        return None, f"{GUIDE} 없음"
    t = g.read_text(encoding="utf-8")
    got = {}
    for key, pat in (("opus", LIMIT_OPUS), ("fable", LIMIT_FABLE), ("total", LIMIT_TOTAL)):
        m = pat.search(t)
        if not m:
            return None, f"{GUIDE} 에서 '{key}' 상한 문장을 찾지 못했다 — 정본 문면이 바뀌었는지 확인하라"
        got[key] = int(m.group(1))
    return got, None


def parallel_blocks(src: str):
    """`parallel([ … ])` 의 내용을 괄호 균형으로 잘라 돌려준다."""
    out = []
    for m in PARALLEL.finditer(src):
        i, depth = m.end() - 1, 0          # '[' 위치
        for j in range(i, len(src)):
            if src[j] == "[":
                depth += 1
            elif src[j] == "]":
                depth -= 1
                if depth == 0:
                    out.append((m.start(), src[i + 1:j]))
                    break
    return out


def check(root: pathlib.Path):
    lim, err = read_limits(root)
    if lim is None:
        log(f"UNRUN: 정본 상한을 읽을 수 없다 — {err}")
        return UNRUN

    wf = sorted((root / "workflows").glob("*.js")) if (root / "workflows").is_dir() else []
    if not wf:
        log(f"UNRUN: 워크플로가 0건 — {root/'workflows'} (측정 실패를 먼저 의심한다)")
        return UNRUN

    print(f"정본 상한 ({GUIDE}): opus ≤{lim['opus']} · fable ≤{lim['fable']} · 총 ≤{lim['total']}")
    bad, nblocks = [], 0
    for q in wf:
        src = q.read_text(encoding="utf-8")
        for pos, body in parallel_blocks(src):
            models = MODEL.findall(body)
            if not models:
                continue                   # 에이전트 스폰이 아닌 parallel (thunk 변수 등)
            nblocks += 1
            line = src[:pos].count("\n") + 1
            o = sum(1 for m in models if m.startswith("opus"))
            f = sum(1 for m in models if m.startswith("fable"))
            over = []
            if o > lim["opus"]:
                over.append(f"opus {o}>{lim['opus']}")
            if f > lim["fable"]:
                over.append(f"fable {f}>{lim['fable']}")
            if len(models) > lim["total"]:
                over.append(f"총 {len(models)}>{lim['total']}")
            if over:
                bad.append(f"{q.name}:{line} — {' · '.join(over)} (모델 {models})")

    print(f"분모: 워크플로 {len(wf)}개 · 모델 명시 parallel 블록 {nblocks}개")
    print(f"  상한 초과                          : {len(bad)}")
    for b in bad:
        print(f"      {b}")
    print("  ⛔ advisor 는 이 검사의 범위 밖이다 (서버사이드 tool call — governance.md § 사각지대)")

    if nblocks == 0:
        log("UNRUN: 모델을 명시한 parallel 블록이 0건 — 스캔이 실패했을 수 있다")
        return UNRUN
    if bad:
        log(f"VIOLATION: 동시 스폰 상한 초과 {len(bad)}건")
        return VIOLATION
    print("OK: 모든 parallel 블록이 정본 상한 이내")
    return OK


def self_test():
    """행동 fixture — 상한 초과에서 **실패**, 이내에서 **통과** (플랜 verify #5)."""
    import tempfile
    passed, failed, cases = [], [], 0

    def case(name, fn):
        nonlocal cases
        cases += 1
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(pathlib.Path(tmp)); passed.append(name)
            except AssertionError as e:
                failed.append(f"{name}: {e}")
            except Exception as e:
                failed.append(f"{name}: ⛔ 예외 {type(e).__name__}: {e}")

    GUIDE_OK = ("## 5. 적용\n- ⛔ **동시 실행 상한 (불변)**: opus 동시 ≤3 · "
                "fable 에이전트 **동시 1개**(Lead 세션 제외) · 총 ≤4.\n")

    def mk(root, js, guide=GUIDE_OK):
        (root / "guides").mkdir(parents=True, exist_ok=True)
        (root / "guides" / "model-guide.md").write_text(guide, encoding="utf-8")
        (root / "workflows").mkdir(parents=True, exist_ok=True)
        (root / "workflows" / "w.js").write_text(js, encoding="utf-8")
        return root

    def c_within_passes(tmp):
        r = mk(tmp / "r", "await parallel([\n a({model:'opus'}), a({model:'opus'}), a({model:'opus'})\n])\n")
        assert check(r) == OK, "opus 3 은 상한 이내인데 막혔다"

    def c_opus_over(tmp):
        r = mk(tmp / "r", "await parallel([\n" + " a({model:'opus'}),\n"*4 + "])\n")
        assert check(r) == VIOLATION, "⛔ opus 4 동시를 놓쳤다"

    def c_fable_over(tmp):
        r = mk(tmp / "r", "await parallel([ a({model:'fable'}), a({model:'fable'}) ])\n")
        assert check(r) == VIOLATION, "⛔ fable 2 동시를 놓쳤다"

    def c_total_over(tmp):
        r = mk(tmp / "r", "await parallel([ a({model:'opus'}), a({model:'opus'}), "
                          "a({model:'opus'}), a({model:'sonnet'}), a({model:'sonnet'}) ])\n")
        assert check(r) == VIOLATION, "⛔ 총 5 를 놓쳤다 (opus·fable 각각은 이내)"

    def c_limits_read_from_canon(tmp):
        """⛔ 상한을 하드코딩하지 않는다 — 정본을 바꾸면 판정이 따라와야 한다."""
        tight = ("- ⛔ **동시 실행 상한 (불변)**: opus 동시 ≤1 · "
                 "fable 에이전트 **동시 1개** · 총 ≤4.\n")
        r = mk(tmp / "r", "await parallel([ a({model:'opus'}), a({model:'opus'}) ])\n", guide=tight)
        assert check(r) == VIOLATION, "⛔ 정본을 ≤1 로 줄였는데 opus 2 가 통과했다 — 수치가 하드코딩됐다"

    def c_canon_unparseable_unrun(tmp):
        r = mk(tmp / "r", "await parallel([ a({model:'opus'}) ])\n", guide="# 상한 문장이 없다\n")
        rc = check(r)
        assert rc == UNRUN, f"⛔ 정본 파싱 실패인데 rc={rc} — 기본값으로 때우면 안 된다"

    def c_sequential_not_counted(tmp):
        """순차 스폰은 동시가 아니다 — parallel 밖은 세지 않는다."""
        r = mk(tmp / "r", "await a({model:'opus'})\nawait a({model:'opus'})\n"
                          "await a({model:'opus'})\nawait a({model:'opus'})\n"
                          "await parallel([ a({model:'opus'}) ])\n")
        assert check(r) == OK, "순차 4회를 동시로 오판했다"

    def c_no_workflows_unrun(tmp):
        r = tmp / "r"
        (r / "guides").mkdir(parents=True)
        (r / "guides" / "model-guide.md").write_text(GUIDE_OK, encoding="utf-8")
        assert check(r) == UNRUN, "워크플로 0건이 통과했다"

    def c_no_model_blocks_unrun(tmp):
        r = mk(tmp / "r", "await parallel(thunks)\n")
        assert check(r) == UNRUN, "⛔ 모델 명시 블록 0건이 통과했다 — 스캔 실패를 먼저 의심"

    for n, f in [("within-limit-passes", c_within_passes),
                 ("opus-over-detected", c_opus_over),
                 ("fable-over-detected", c_fable_over),
                 ("total-over-detected", c_total_over),
                 ("limits-read-from-canon", c_limits_read_from_canon),
                 ("canon-unparseable-unrun", c_canon_unparseable_unrun),
                 ("sequential-not-counted", c_sequential_not_counted),
                 ("no-workflows-unrun", c_no_workflows_unrun),
                 ("no-model-blocks-unrun", c_no_model_blocks_unrun)]:
        case(n, f)

    print(f"self-test {len(passed)}/{cases} 통과")
    for x in passed:
        print(f"  ok   {x}")
    for x in failed:
        print(f"  FAIL {x}")
    return OK if not failed else VIOLATION


def main():
    ap = argparse.ArgumentParser(description="모델 비용 상한 검사 (B5 / G-1)")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(SCRIPT_DIR).parent)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else check(a.root)


if __name__ == "__main__":
    sys.exit(main())
