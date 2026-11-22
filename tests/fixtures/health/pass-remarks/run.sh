#!/bin/bash
# gpt-cli: none — health-check.sh 는 함수 본문만 떼어 셀마다 따로 돌린다(전체 실행 · §4.5 에 닿지 않는다)
# health-check 통과 비고 fixture — 통과 행의 비고가 무엇을 셌는지 보이는가 · 남긴 SKIP 이 그대로 찍히는가를 동작으로 본다.
#
# health-check.sh 에서 record · classify · record3 · chk_contract_lint 함수와 4.9 레지스트리 도구 self-test 루프 본문을 떼어
# 셀마다 bash 로 돌린다. 4.9 셀은 루프의 도구 목록만 임시 폴더에 심은 도구로 바꾼다(본문 · 비고 grep · 가드는 원문 그대로).
# 셀:
#   c-harness-05-retired-skip-gone   계약 lint 의 `--list` 와 SKIP 구획에 판정 기록 없이 남아 있던 여섯(#8 · #9 · #10 · #11 · #13 · #17)이 없다
#   c-harness-05-kept-skip-fires     남긴 SKIP(#2)은 그대로 찍힌다 — 이 트리의 lint 를 health-check 의 계약 lint 함수로 돌리면 SKIP 구획에 #2 ·
#                                    SKIP 수 = `--list` 의 비결정 항목 수(1 이상) · 결정 항목 줄 수 = `--list` 의 ✅ 수 · 통과면 비고에 그 SKIP 수
#   c-harness-12-remark-forms        통과 요약 꼴 다섯 — `self-test N/M passed` · `N/M passed` · `X self-test: PASS (N/M)` · `… 전부 통과` ·
#                                    분모 줄 뒤에 `X self-test: PASS` 가 붙는 꼴 → 전부 통과(0) · 비고 = 그 요약 줄(마지막 꼴은 분모 줄)
#   c-harness-12-no-denominator      exit 0 인데 요약 줄이 없는 도구 → 실패(1) · 비고 '분모 없는 통과'
#   c-harness-12-fail-still-fires    exit 1 도구 → 실패(1) · 비고 = 그 FAIL 줄(통과 비고를 넓혀도 실패 판정은 그대로다)
#   c-harness-12-unrun-still-unrun   `UNRUN:` 표지 + exit 2 도구 → 미실행(UNRUN) · 미실행 수 +1(가드는 exit 0 에만 걸린다)
# 기준 트리(통과 비고 = `^self-test` 만 · 가드 없음 · SKIP 일곱)는 remark-forms · no-denominator · retired-skip-gone 이 실패해 exit 1 이다.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 함수 추출 · 임시 폴더 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 이 기능 부재 재현 없이 통과한다 — 그래서 3 이다(미처리 예외도 3).
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -f "$R/scripts/health-check.sh" ] || { echo "SETUP health-check.sh 없음: $R"; exit 3; }
[ -f "$R/scripts/lint_contracts.py" ] || { echo "SETUP lint_contracts.py 없음: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" <<'PY'
import os, pathlib, re, shlex, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

TREE = pathlib.Path(sys.argv[1])
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON_COLORS="0")
FAIL = []
RETIRED = ("8", "9", "10", "11", "13", "17")


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def pieces(text):
    """health-check 본문 → 셀이 부를 조각. 하나라도 못 찾으면 Setup(함수 이름 · 루프 머리가 바뀌었다)."""
    got = {}
    m = re.search(r"^record\(\) \{[^\n]*\}$", text, re.M)
    if not m:
        raise Setup("record 함수(한 줄)를 찾지 못했다")
    got["record"] = m.group(0)
    for name in ("classify", "record3", "chk_contract_lint"):
        m = re.search(r"^%s\(\) \{\n.*?^\}$" % name, text, re.M | re.S)
        if not m:
            raise Setup(f"{name} 함수를 찾지 못했다")
        got[name] = m.group(0)
    m = re.search(r"^for FS in check_release_notes[^\n]*; do\n(.*?^done)$", text, re.M | re.S)
    if not m:
        raise Setup("4.9 레지스트리 도구 self-test 루프를 찾지 못했다")
    got["loop_body"] = m.group(1)
    return got


def run_block(P, root, block):
    """조각을 이어 bash 로 돈다 → (기록 행 [(이름, 코드, 비고)], 추가 출력 줄 dict). traceback · 셸 오류는 Setup."""
    script = "\n".join([
        "set -u",
        "ROOT=" + shlex.quote(str(root)),
        'NAMES=() CODES=() NOTES=()',
        'UNRUN=0 LINT_OUT="" SKIP_N=0',
        P["record"], P["classify"], P["record3"], P["chk_contract_lint"],
        block,
        'for i in "${!NAMES[@]}"; do printf \'ROW\\t%s\\t%s\\t%s\\n\' "${NAMES[$i]}" "${CODES[$i]}" "${NOTES[$i]}"; done',
        "printf 'SKIPN\\t%s\\n' \"$SKIP_N\"",
        "printf 'UNRUNN\\t%s\\n' \"$UNRUN\"",
        "printf '%s\\n' \"$LINT_OUT\" | sed 's/^/LINT\\t/'",
    ])
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=ENV)
    if r.returncode != 0 or "Traceback (most recent call last)" in r.stdout + r.stderr:
        raise Setup(f"조각 실행 실패(exit {r.returncode}): {(r.stderr or r.stdout)[-300:]}")
    rows, extra = [], {"SKIPN": [], "UNRUNN": [], "LINT": []}
    for ln in r.stdout.splitlines():
        tag, _, rest = ln.partition("\t")
        if tag == "ROW":
            rows.append(tuple(rest.split("\t", 2)))
        elif tag in extra:
            extra[tag].append(rest)
    return rows, extra


# 심는 도구 — 이름 → (출력, exit). 출력 꼴은 이 트리 도구들의 실제 요약 줄 꼴을 따른다
#   (`self-test N/M passed` · fz_snapshot 의 `N/M passed` · run_metrics 의 `… self-test: PASS (N/M)` · lint_contracts 의 `… 전부 통과` ·
#    counter_adapter 의 분모 줄 + `… self-test: PASS`)
PLANT = {
    "shape_selftest": ("case-a: PASS\nself-test 3/3 passed\n", 0),
    "shape_passed": ("PASS 스냅숏 기록\nPASS 플러그인 루트 아님 → exit 2\n26/26 passed\n", 0),
    "shape_paren": ("unknown-skill: PASS\nshape_paren self-test: PASS (16/16)\n", 0),
    "shape_all_pass": ("양성 대조 78건 + 통합 fixture 12검사(46 위치) 전부 통과\n", 0),
    "shape_trailing_pass": ("cli-missing-or-junk: PASS\nself-test 11/11 passed\nshape_trailing_pass self-test: PASS\n", 0),
    "shape_no_denominator": ("케이스를 돌렸다\n", 0),
    "shape_fail": ("self-test 2/3 passed\nFAIL case-b: 기대 1 · 실제 0\n", 1),
    "shape_unrun": ("UNRUN: 입력 원장 없음 — 판정 불가\n", 2),
}
WANT_NOTE = {
    "shape_selftest": "self-test 3/3 passed",
    "shape_passed": "26/26 passed",
    "shape_paren": "shape_paren self-test: PASS (16/16)",
    "shape_all_pass": "양성 대조 78건 + 통합 fixture 12검사(46 위치) 전부 통과",
    "shape_trailing_pass": "self-test 11/11 passed",
}

try:
    P = pieces((TREE / "scripts" / "health-check.sh").read_text(encoding="utf-8"))

    # ── 4.9 루프 — 심은 도구로 목록만 바꾼다 ─────────────────────────────
    with tempfile.TemporaryDirectory(prefix="fz-pass-remarks.") as td:
        root = pathlib.Path(td)
        (root / "scripts").mkdir()
        for name, (out, code) in PLANT.items():
            (root / "scripts" / f"{name}.py").write_text(
                "import sys\nsys.stdout.write(%r)\nsys.exit(%d)\n" % (out, code), encoding="utf-8")
        rows, loop_extra = run_block(P, root, "for FS in %s; do\n%s" % (" ".join(PLANT), P["loop_body"]))
    got = {n[n.find("(") + 1:-1]: (c, note) for n, c, note in rows if n.startswith("레지스트리 도구 self-test (")}
    if set(got) != set(PLANT):
        raise Setup(f"루프가 심은 도구를 다 기록하지 않았다: {sorted(got)}")
    bad = {k: got[k] for k in WANT_NOTE if got[k] != ("0", WANT_NOTE[k])}
    check("c-harness-12-remark-forms", not bad, "통과 요약 꼴 다섯 → 통과(0) · 비고 = 요약 줄(분모 줄 뒤 PASS 꼴은 분모 줄)", bad)
    c, note = got["shape_no_denominator"]
    check("c-harness-12-no-denominator", c == "1" and "분모 없는 통과" in note, "exit 0 · 요약 줄 없음 → 실패(1) · 비고 '분모 없는 통과'",
          f"code={c} note={note}")
    c, note = got["shape_fail"]
    check("c-harness-12-fail-still-fires", c == "1" and note == "⛔ FAIL case-b: 기대 1 · 실제 0", "exit 1 → 실패(1) · 비고 = FAIL 줄",
          f"code={c} note={note}")
    c, note = got["shape_unrun"]
    check("c-harness-12-unrun-still-unrun", c == "UNRUN" and note.startswith("미실행 — UNRUN: 입력 원장 없음") and loop_extra["UNRUNN"] == ["1"],
          "UNRUN 표지 + exit 2 → 미실행(UNRUN) · 미실행 수 1", f"code={c} note={note} UNRUN={loop_extra['UNRUNN']}")

    # ── 계약 lint — 이 트리의 lint 를 health-check 의 계약 lint 함수로 ──────────
    lst = subprocess.run([sys.executable, "-B", str(TREE / "scripts" / "lint_contracts.py"), "--list"],
                         capture_output=True, text=True, env=ENV, cwd=str(TREE))
    if lst.returncode != 0 or "Traceback (most recent call last)" in lst.stdout + lst.stderr:
        raise Setup(f"lint --list 실패(exit {lst.returncode}): {(lst.stderr or lst.stdout)[-300:]}")
    nondet = re.findall(r"^(?:⏸|👤) #(\S+) ", lst.stdout, re.M)
    det_n = len(re.findall(r"^✅ #", lst.stdout, re.M))
    rows, extra = run_block(P, TREE, "chk_contract_lint")
    lint_rows = [(c, note) for n, c, note in rows if n == "계약 lint"]
    if len(lint_rows) != 1 or not extra["SKIPN"]:
        raise Setup(f"계약 lint 함수가 한 행을 기록하지 않았다: {rows}")
    code, note = lint_rows[0]
    lint_out = extra["LINT"]
    skip_lines = [ln for ln in lint_out if re.match(r"^   ⏸ #", ln)]
    gone = [i for i in RETIRED if i in nondet or any(re.match(r"^   ⏸ #%s " % i, ln) for ln in skip_lines)]
    check("c-harness-05-retired-skip-gone", not gone, "--list · SKIP 구획에 #8 · #9 · #10 · #11 · #13 · #17 이 없다", f"남음={gone}")
    skip_n = extra["SKIPN"][0]
    det_lines = [ln for ln in lint_out if re.match(r"^(?:OK  |FAIL\(\d+\)) #", ln)]
    ok = (code in ("0", "1") and "2" in nondet and any(re.match(r"^   ⏸ #2 ", ln) for ln in skip_lines)
          and skip_n == str(len(nondet)) and len(det_lines) == det_n and det_n > 0
          and (code != "0" or note == f"위반 0건 · SKIP {len(nondet)}항목"))
    check("c-harness-05-kept-skip-fires", ok, "남긴 SKIP #2 가 SKIP 구획에 찍히고 SKIP 수 = --list 비결정 항목 수 · 결정 항목은 전부 돈다",
          f"code={code} note={note} SKIP_N={skip_n} nondet={nondet} det_lines={len(det_lines)} det_list={det_n}")
except Setup as e:
    print(f"SETUP {e}")
    sys.exit(3)

print()
print(f"SUMMARY fail={len(FAIL)}")
for f in FAIL:
    print(f"  FAIL {f}")
sys.exit(1 if FAIL else 0)
PY
