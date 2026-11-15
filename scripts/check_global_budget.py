#!/usr/bin/env python3
"""check_global_budget.py — 워크플로의 **동시 스폰이 모델 비용 상한을 넘는가** (B5 / v7 G-1).

왜: `guides/model-guide.md` §5 가 *"opus 동시 ≤3 · fable 동시 1 · 총 ≤4"* 를 불변으로 규정하는데,
그것을 어기는지 보는 기계 검사가 없었다. 워크플로가 `parallel([...])` 안에 opus 4개를 넣어도
문서는 초록으로 남는다.

⛔ **상한 수치를 여기 적지 않는다.** 정본은 `model-guide.md` §5 한 곳이고, 이 스크립트는
그 문장을 **파싱해서 읽는다**. 수치를 복사해 두면 정본이 바뀔 때 조용히 어긋난다
(`modules/governance.md` § Truth-of-Source 가 지정한 단일 출처 규약).

⛔ **변수로 넘긴 병렬은 세지 않는다** — `parallel(lensThunks)`·`parallel(costThunks.slice(…))` 처럼 배열이 리터럴이 아니면
블록을 못 잘라 분모에서 빠진다(discover-adversarial 이 이 형태다). 데이터 흐름 추적은 이 검사의 범위 밖이다 — 통과는 "리터럴 병렬이 상한 이내" 까지만 뜻한다.
그 수는 `unmeasured_parallel=N` 한 줄과 위치로 찍는다(F-335 ⑮) — 안 찍으면 "블록 11개 이내" 가 전수처럼 읽힌다.
재시도 래퍼 본문의 `parallel(thunks)` 도 여기 든다(호출부의 리터럴 배열은 따로 잰다). 함수 정의 줄 · 주석은 호출이 아니다.

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
import contextlib
import io
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
# ⛔ `parallel\w*` — 재시도 래퍼(`parallelWithRetry([…])`)도 동시 스폰이다. 이전 판은 `parallel(` 만 잡아
#    peer-review Stage 1 · plan-collaborative Stage 2 의 opus 병렬을 분모에서 뺐다(A5-03 실측: 블록 9 → 11).
# ⛔ `(` 와 `[` 사이의 블록 주석도 허용한다 — `parallelWithRetry(/* x */ [` 가 블록 탐색을 빠져나갔다(2라운드 003)
PARALLEL = re.compile(r"\bparallel\w*\s*\(\s*(?:/\*.*?\*/\s*)*\[", re.S)
MODEL = re.compile(r"model:\s*'([a-z0-9.-]+)'")
# 병렬 호출 전부(리터럴 여부 무관) — `(` 뒤 첫 비공백(블록 주석 건너뜀)이 `[` 가 아니면 미측정이다
PARALLEL_CALL = re.compile(r"\bparallel\w*\s*\(\s*(?:/\*.*?\*/\s*)*(.)", re.S)
FUNC_DEF = re.compile(r"\bfunction\s*\*?\s*$")


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


def unmeasured_calls(src: str):
    """리터럴 배열이 아닌 병렬 호출의 줄 번호들 — 이 검사가 모델 수를 세지 못하는 동시 스폰 후보.

    ⛔ 주석 안의 호출은 뺀다(블록 주석은 줄 수를 지켜 지운다 · `//` 줄 주석은 공백 뒤 또는 줄머리만 — URL 의 `://` 는 남긴다).
    ⛔ `function parallelWithRetry(thunks)` 같은 정의는 호출이 아니다.
    """
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    src = "\n".join(re.sub(r"(^|\s)//.*$", r"\1", l) for l in src.split("\n"))
    out = []
    for m in PARALLEL_CALL.finditer(src):
        if m.group(1) == "[" or FUNC_DEF.search(src[:m.start()]):
            continue
        out.append(src[:m.start()].count("\n") + 1)
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
    bad, nblocks, unmeasured = [], 0, []
    for q in wf:
        src = q.read_text(encoding="utf-8")
        unmeasured += [f"{q.name}:{n}" for n in unmeasured_calls(src)]
        for pos, body in parallel_blocks(src):
            # ⛔ 주석 줄은 호출이 아니다 — 세면 `// model:'opus'` 한 줄이 거짓 초과를 만든다(GPT R-A 검토 004)
            body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)   # 블록 주석도 호출이 아니다(2라운드 004)
            body = "\n".join(l for l in body.split("\n") if not l.lstrip().startswith("//"))
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
    # ⛔ 미측정 수는 판정을 바꾸지 않는다(데이터 흐름 추적은 범위 밖) — 대신 숫자로 드러낸다
    print(f"  unmeasured_parallel={len(unmeasured)} (리터럴 배열이 아닌 병렬 — 모델 수를 세지 못했다)")
    for u in unmeasured:
        print(f"      {u}")
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

    def c_parallel_with_retry_counted(tmp):
        """재시도 래퍼 안의 병렬도 동시다 — 래퍼 이름이 `parallel` 로 시작하면 센다."""
        r = mk(tmp / "r", "await parallelWithRetry([\n" + " a({model:'opus'}),\n"*4 + "])\n")
        assert check(r) == VIOLATION, "⛔ parallelWithRetry 안의 opus 4 동시를 놓쳤다"

    def c_comment_line_not_counted(tmp):
        r = mk(tmp / "r", "await parallel([\n a({model:'opus'}),\n // a({model:'opus'}),\n a({model:'opus'}), a({model:'opus'})\n])\n")
        assert check(r) == OK, "주석 줄의 model 을 세어 opus 4 로 오판했다"

    def c_block_comment_forms(tmp):
        r = mk(tmp / "r", "await parallelWithRetry(/* audit */ [\n" + " a({model:'opus'}),\n"*4 + "])\n")
        assert check(r) == VIOLATION, "⛔ ( 와 [ 사이 주석 뒤의 opus 4 동시를 놓쳤다"
        r2 = mk(tmp / "r2", "await parallel([ a({model:'opus'}), /* a({model:'opus'}) */ a({model:'opus'}), a({model:'opus'}) ])\n")
        assert check(r2) == OK, "블록 주석 안의 model 을 세어 거짓 초과를 냈다"

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

    def c_unmeasured_nonliteral_counted(tmp):
        """⛔ 변수로 넘긴 병렬은 모델 수를 못 센다 — 세지 못한 수를 숫자로 낸다(F-335 ⑮)."""
        js = ("const a = (await parallel(lensThunks)).filter(Boolean)\n"
              "  const chunk = await parallel(costThunks.slice(c, c + 4))\n"
              "async function parallelWithRetry(thunks) {\n  const out = await parallel(thunks)\n}\n"
              "await parallel([ a({model:'opus'}) ])\n")
        assert unmeasured_calls(js) == [1, 2, 4], f"비리터럴 병렬 줄 {unmeasured_calls(js)} (기대 [1, 2, 4])"
        r = mk(tmp / "r", js)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check(r)
        assert rc == OK, f"미측정은 판정을 바꾸지 않는다 — rc={rc}"
        assert "unmeasured_parallel=3 " in buf.getvalue(), "⛔ 출력에 unmeasured_parallel=3 이 없다"
        assert "w.js:4" in buf.getvalue(), "미측정 위치(w.js:4)를 찍지 않았다"

    def c_unmeasured_literal_and_defs_not_counted(tmp):
        """리터럴 배열 · 정의 줄 · 주석은 미측정이 아니다 — 세면 수가 부풀어 표면화가 소음이 된다."""
        js = ("async function parallelWithRetry(thunks) {\n}\n"
              "await parallelWithRetry(/* audit */ [ a({model:'opus'}) ])\n"
              "await parallel(\n  [ a({model:'opus'}) ])\n"
              "// parallel(thunks) 는 주석이다\n"
              "/* parallel(lensThunks)\n   parallel(more) */\n"
              "const u = 'https://x/parallel' // parallel(tail)\n")
        assert unmeasured_calls(js) == [], f"⛔ 리터럴 · 정의 · 주석을 미측정으로 셌다: {unmeasured_calls(js)}"
        r = mk(tmp / "r", js)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check(r)
        assert rc == OK and "unmeasured_parallel=0 " in buf.getvalue(), f"rc={rc} · unmeasured_parallel=0 이 아니다"

    def c_no_model_blocks_unrun(tmp):
        r = mk(tmp / "r", "await parallel(thunks)\n")
        assert check(r) == UNRUN, "⛔ 모델 명시 블록 0건이 통과했다 — 스캔 실패를 먼저 의심"

    for n, f in [("within-limit-passes", c_within_passes),
                 ("opus-over-detected", c_opus_over),
                 ("fable-over-detected", c_fable_over),
                 ("total-over-detected", c_total_over),
                 ("limits-read-from-canon", c_limits_read_from_canon),
                 ("parallel-with-retry-counted", c_parallel_with_retry_counted),
                 ("comment-line-not-counted", c_comment_line_not_counted),
                 ("block-comment-forms", c_block_comment_forms),
                 ("canon-unparseable-unrun", c_canon_unparseable_unrun),
                 ("sequential-not-counted", c_sequential_not_counted),
                 ("no-workflows-unrun", c_no_workflows_unrun),
                 ("no-model-blocks-unrun", c_no_model_blocks_unrun),
                 ("unmeasured-nonliteral-counted", c_unmeasured_nonliteral_counted),
                 ("unmeasured-literal-and-defs-not-counted", c_unmeasured_literal_and_defs_not_counted)]:
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
