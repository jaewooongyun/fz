#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff 를 판정하지 않는다. 접두사 정규식 표본을 문자열로 임시 트리에 쓰고 트리의 lint 를 돌려 exit · JSON · 출력만 본다
# diff 파서 lint 신호 · 외부 명령 lint 2글자 셀 (F-357 · F-379 · SC-17).
#   diff 셀 (임시 트리 = 트리의 lint_diff_parsers.py 사본 + 셀 파일. 셀마다 확장자가 있다 — 판정은 파일별로 찾는다):
#     inline-flag-m      r"(?m)^\+\+\+ b/…" 수집기(F-357 원형 · .py)           → 위반 — 기준 lint 는 파서로 못 본다
#     inline-flag-ms     r'(?ms)^\+\+\+ b/…' 작은따옴표(.py)                    → 위반 — 기준은 놓친다
#     nonraw-escape      비-raw "^\\+\\+\\+ b/…" (.py)                          → 위반 — 기준은 놓친다
#     js-regexp-ctor     new RegExp("^\\+\\+\\+ b/…", "gm") (.js)               → 위반 — 기준은 놓친다
#     ctl-frontmatter · ctl-checkbox · ctl-comment-only(.py 주석) · ctl-js-comment-only(.js // 주석) · ctl-escape-nonplus("^\\s")
#                        → 정상 대조 — 파서 아님
#     mixed-diff         hunk 밖 헤더 `+++ b/a.ts` · hunk 안 소스 줄 `+++ b/phantom.ts`(= `++ b/phantom.ts` 를 더한 줄)가 섞인 diff 를
#                        셀에 실제로 먹인다. 위 .py 양성 셀 셋은 phantom.ts 를 파일로 세고(행동 결함), hunk 상태를 고르는
#                        mixed-hunk-state 셀(선언 hunk-state · `@@` 로 헤더 구간을 닫는다)은 a.ts · c.ts 만 센다 →
#                        lint 판정이 행동과 같다: 세는 셀 = 위반 · 고르는 셀 = ok
#     mini-good          정상 대조 + mixed-hunk-state 만 둔 임시 트리 → lint exit 0
#   명령 셀 (셀마다 임시 루트 skills/x/SKILL.md 의 bash 블록 · 선언은 트리의 schemas/tool-inventory.json):
#     undeclared-fd · undeclared-ag  미선언 2글자 명령 → VIOLATION · 미선언 = 그 이름 하나 — 기준(3글자 이상만)은 놓친다
#     undeclared-rg                  미선언 2글자 rg → 탐지 · VIOLATION(F-379 — 문서 bash 블록의 rg 재유입) — 기준은 탐지 0
#     declared-gh                    선언(required=false) 2글자 명령 → 탐지(문서 등장 1종) · 위반 아님 — 기준은 탐지 0
#     posix-utils                    cd · ls · cp · mv · rm · wc · tr · sh → 위반 아님(허용 목록)
#     shell-keywords                 for · do · done · if · then · fi 줄 → 위반 아님(셸 키워드)
#     kubectl-ctl                    3글자 이상 미선언 → VIOLATION (두 트리 공통 양성 대조 — 스캐너가 살아 있다)
#     mixed-cmd                      rg · gh · fd · ag · cd · ls · do · python3 한 블록 → 미선언 = {ag, fd, rg} 정확히
#     no-which-ec33                  cd · ls · cp · mv · rm · tr · sh · rg · gh 가 실행 파일로 없는 환경(shutil.which → None)을 흉내 내도
#                                    위반 아님 — 셸 내장을 which 로 확인하는 필수 항목이 없다(EC-33)
#   live-diff-lint · live-cmd-lint   트리 자신에 두 lint → exit 0 (라이브 오탐 0)
# 기준 트리는 2글자 명령 · 따옴표 뒤가 아닌 `^\+` 를 못 봐 양성 셀을 놓친다 → exit 1.
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 도구 · 임시 폴더 · lint traceback ·
#       예기치 않은 lint exit · 셀 자신의 행동 이상 · 판정 줄 없이 끝난 실행)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 이 기능 부재 재현 없이 통과한다 — 그래서 3 이다(미처리 예외 · 신호 종료도 3).
# ⛔ 중첩 가드: 도는 동안 FZ_DIFF_CMD_CELLS_FIXTURE=1. 안에서 다시 불리면 `UNRUN:` 을 내고 exit 2.
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 fixture 가 든 트리 — health-check 는 인자 없이 부른다)
set -u
if [ -n "${FZ_DIFF_CMD_CELLS_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 diff-and-cmd-cells 가 도는 중"
  exit 2
fi
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
[ -n "$TREE" ] || { echo "SETUP 트리 경로를 정하지 못했다"; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
for f in scripts/lint_diff_parsers.py scripts/check_external_commands.py schemas/tool-inventory.json; do
  [ -f "$TREE/$f" ] || { echo "SETUP $f 없음: $TREE"; exit 3; }
done
LOG="$(mktemp "${TMPDIR:-/tmp}/fz-diff-cmd-cells.XXXXXX")" || { echo "SETUP 임시 파일 실패"; exit 3; }
trap 'rm -f "${LOG:?}"' EXIT
export FZ_DIFF_CMD_CELLS_FIXTURE=1 PYTHONDONTWRITEBYTECODE=1

python3 -B - "$TREE" > "$LOG" 2>&1 <<'PY'
import json, os, pathlib, re, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

TREE = pathlib.Path(sys.argv[1])
PY = sys.executable
LINT = TREE / "scripts" / "lint_diff_parsers.py"
CMDS = TREE / "scripts" / "check_external_commands.py"
FAIL, PASSED = [], [0]


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if ok:
        PASSED[0] += 1
    else:
        FAIL.append(f"{cell}: {what}")
    return ok


def run(args, stdin=None, allowed=(0, 1)):
    """→ (rc, stdout). ⛔ traceback · 허용 밖 exit 는 탐지가 아니라 검사기(또는 셀) 고장이다 → Setup."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON_COLORS="0")
    r = subprocess.run([PY, "-B", *map(str, args)], input=stdin, capture_output=True, text=True, env=env)
    out = r.stdout + r.stderr
    if "Traceback (most recent call last)" in out:
        raise Setup(f"{pathlib.Path(str(args[0])).name} traceback ⏎ {out[-300:]}")
    if r.returncode not in allowed:
        raise Setup(f"{pathlib.Path(str(args[0])).name} 예기치 않은 exit {r.returncode} ⏎ {out[-300:]}")
    return r.returncode, r.stdout


def write(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


# ── diff 셀 본문 ─────────────────────────────────────────────────────
POS = {   # 이름: (경로, 본문) — 선언 없는 접두사 판정. 후보 lint 는 위반, 기준 lint 는 파서로 못 본다
    "inline-flag-m": ("scripts/cells/inline_flag_m.py", r'''import re, sys
d = sys.stdin.read()
print("\n".join(m.group(1) for m in re.finditer(r"(?m)^\+\+\+ b/([^\t\n]+)", d)))
'''),
    "inline-flag-ms": ("scripts/cells/inline_flag_ms.py", r'''import re, sys
HDR = re.compile(r'(?ms)^\+\+\+ b/(\S+)')
print("\n".join(HDR.findall(sys.stdin.read())))
'''),
    "nonraw-escape": ("scripts/cells/nonraw_escape.py", r'''import re, sys
HDR = re.compile("^\\+\\+\\+ b/(\\S+)", re.M)
print("\n".join(HDR.findall(sys.stdin.read())))
'''),
    "js-regexp-ctor": ("scripts/cells/js_regexp_ctor.js", r'''const HDR = new RegExp("^\\+\\+\\+ b/(\\S+)", "gm");
const d = require("fs").readFileSync(0, "utf8");
for (const m of d.matchAll(HDR)) console.log(m[1]);
'''),
}
CTL = {   # 정상 대조 — 두 트리 모두 파서 아님(결과에 없다)
    "ctl-frontmatter": ("scripts/cells/ctl_frontmatter.py", r'''import re
FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
'''),
    "ctl-checkbox": ("scripts/cells/ctl_checkbox.py", r'''import re
GATE_RE = re.compile(r"^- \[( |x)\] (.+)$")
'''),
    "ctl-comment-only": ("scripts/cells/ctl_comment_only.py", r'''# re.finditer(r"(?m)^\+\+\+ b/", d) 처럼 쓰면 hunk 안 줄을 헤더로 센다 — 예시일 뿐 이 파일은 diff 를 읽지 않는다
print("ok")
'''),
    "ctl-js-comment-only": ("scripts/cells/ctl_js_comment_only.js", r'''// new RegExp("^\\+\\+\\+ b/", "gm") 는 예시다 — 이 도구는 diff 를 읽지 않는다
console.log("ok");
'''),
    "ctl-escape-nonplus": ("scripts/cells/ctl_escape_nonplus.py", r'''import re
IND = re.compile("^\\s*#")
'''),
}
HUNK = ("mixed-hunk-state", "scripts/cells/mixed_hunk_state.py", r'''# diff-parse: hunk-state — `diff --git` 에서 헤더 구간을 열고 첫 `@@` 에서 닫는다. hunk 안의 `+++ …` 는 추가된 소스 줄이다
import re, sys
HDR = re.compile(r"(?m)^\+\+\+ b/(\S+)")
out, in_header = [], False
for line in sys.stdin.read().splitlines():
    if line.startswith("diff --git "):
        in_header = True
        continue
    if line.startswith("@@"):
        in_header = False
        continue
    m = HDR.match(line) if in_header else None
    if m:
        out.append(m.group(1))
print("\n".join(out))
''')
MIXED = ("diff --git a/a.ts b/a.ts\nindex 1111111..2222222 100644\n--- a/a.ts\n+++ b/a.ts\n"
         "@@ -1 +1,2 @@\n x\n+++ b/phantom.ts\n"
         "diff --git a/c.ts b/c.ts\nnew file mode 100644\n--- /dev/null\n+++ b/c.ts\n@@ -0,0 +1 @@\n+y\n")
NAIVE_OUT, HUNK_OUT = ["a.ts", "phantom.ts", "c.ts"], ["a.ts", "c.ts"]


def lint_mini(root, cells):
    """root 에 트리의 lint 사본 + 셀 → (rc, {파일: (verdict, mode)}). ⛔ 사본 경로는 정확히 scripts/lint_diff_parsers.py —
    lint 의 ROOT 는 스크립트 기준이고 자기 제외(SELF)는 상대경로 비교다."""
    write(root, "scripts/lint_diff_parsers.py", LINT.read_text(encoding="utf-8"))
    for rel, body in cells:
        write(root, rel, body)
    rc, out = run([root / "scripts" / "lint_diff_parsers.py", "--json"])
    try:
        d = json.loads(out)
        res = {r["file"]: (r["verdict"], r.get("mode") or "") for r in d["results"]}
        unknown = d["unknown"]
    except (ValueError, KeyError, TypeError) as e:
        raise Setup(f"lint --json 파싱 실패 {type(e).__name__}: {e}")
    if unknown:
        raise Setup(f"lint UNKNOWN {unknown}")
    return rc, res


def cmd_cell(base, name, block):
    """셀 루트에 bash 블록 하나 → (rc, 문서 등장 수, 미선언 집합)."""
    root = base / name
    write(root, "skills/x/SKILL.md", "# x\n\n```bash\n" + block + "```\n")
    rc, out = run([CMDS, "--root", root])
    m = re.search(r"문서 등장 (\d+)종", out)
    if not m:
        raise Setup(f"{name}: '문서 등장 N종' 줄 없음 ⏎ {out[-200:]}")
    undeclared = set(re.findall(r"^ {6}(\S+) — DECLARED", out, re.M))
    return rc, int(m.group(1)), undeclared


NO_WHICH = r'''
import importlib.util, io, contextlib, pathlib, shutil, sys
tree, root = sys.argv[1:3]
real = shutil.which
GONE = {"cd", "ls", "cp", "mv", "rm", "tr", "sh", "rg", "gh"}
shutil.which = lambda c, *a, **k: None if c in GONE else real(c, *a, **k)
s = importlib.util.spec_from_file_location("cmds_under_test", tree + "/scripts/check_external_commands.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    rc = m.check(pathlib.Path(root))
print(buf.getvalue())
print("RC=%d" % rc)
'''

try:
    with tempfile.TemporaryDirectory(prefix="fz-diff-cmd-cells-") as tmp:
        tmp = pathlib.Path(tmp)

        # ── diff 셀 ─────────────────────────────────────────────────
        cells = [v for v in POS.values()] + [v for v in CTL.values()] + [HUNK[1:]]
        rc, res = lint_mini(tmp / "mini-bad", cells)
        check("mini-bad", rc == 1, "양성 셀이 있는 임시 트리 → lint exit 1", f"exit {rc}")
        for name, (rel, _) in POS.items():
            got = res.get(rel, ("absent", ""))[0]
            check(name, got == "violation", f"{rel} → 위반", f"got={got}")
        for name, (rel, _) in CTL.items():
            got = res.get(rel, ("absent", ""))[0]
            check(name, got == "absent", f"{rel} → 파서 아님(정상 대조)", f"got={got}")

        # 혼합 diff — 셀의 실제 행동(행동이 기대와 다르면 셀 자신의 고장 → Setup)
        root = tmp / "mini-bad"
        counted = {}
        for name, (rel, _) in POS.items():
            if rel.endswith(".py"):
                _, out = run([root / rel], stdin=MIXED, allowed=(0,))
                counted[name] = out.split()
        _, hout = run([root / HUNK[1]], stdin=MIXED, allowed=(0,))
        if any(v != NAIVE_OUT for v in counted.values()) or hout.split() != HUNK_OUT:
            raise Setup(f"혼합 diff 셀 행동 이상 — 접두사 셀 {counted} · hunk 셀 {hout.split()}")
        miscount = sorted(n for n, v in counted.items() if "phantom.ts" in v)
        flagged = sorted(n for n in counted if res.get(POS[n][0], ("absent", ""))[0] == "violation")
        hv, hm = res.get(HUNK[1], ("absent", ""))
        check("mixed-diff", miscount == flagged,
              "hunk 안 `+++ b/phantom.ts` 를 파일로 세는 셀 = lint 위반 셀", f"센 셀={miscount} · 위반={flagged}")
        check("mixed-diff", hv == "ok" and hm.startswith("hunk-state"),
              "`@@` 로 헤더 구간을 닫아 a.ts · c.ts 만 세는 셀은 hunk-state 선언으로 ok", f"got={hv} {hm}")

        rc, res2 = lint_mini(tmp / "mini-good", [v for v in CTL.values()] + [HUNK[1:]])
        check("mini-good", rc == 0, "정상 대조 + hunk-state 셀만 둔 임시 트리 → lint exit 0",
              f"exit {rc} · 위반 {sorted(f for f, v in res2.items() if v[0] == 'violation')}")

        # ── 명령 셀 ─────────────────────────────────────────────────
        cb = tmp / "cmd"
        for name, block, want in (("undeclared-fd", "fd -e md .\n", "fd"), ("undeclared-ag", "ag TODO src\n", "ag")):
            rc, n, und = cmd_cell(cb, name, block)
            check(name, rc == 1 and und == {want}, f"미선언 2글자 명령 {want} → VIOLATION · 미선언 = {{{want}}}",
                  f"exit {rc} · 미선언 {sorted(und)}")
        rc, n, und = cmd_cell(cb, "undeclared-rg", "rg -n TODO .\n")
        check("undeclared-rg", n == 1, "미선언 2글자 명령 rg 가 탐지된다(문서 등장 1종)", f"문서 등장 {n}종")
        check("undeclared-rg", rc == 1 and und == {"rg"}, "미선언 rg → VIOLATION(재유입 방어 — F-379)", f"exit {rc} · 미선언 {sorted(und)}")
        for name, block, cmd in (("declared-gh", "gh pr view 1 --json title\n", "gh"),):
            rc, n, und = cmd_cell(cb, name, block)
            check(name, n == 1, f"선언 2글자 명령 {cmd} 이 탐지된다(문서 등장 1종)", f"문서 등장 {n}종")
            check(name, rc == 0 and not und, f"선언(required=false)된 {cmd} 는 위반 아님", f"exit {rc} · 미선언 {sorted(und)}")
        rc, n, und = cmd_cell(cb, "posix-utils", "cd /tmp\nls -l\ncp a b\nmv a b\nrm -f a\nwc -l a\ntr a b < a\nsh -c true\n")
        check("posix-utils", rc == 0 and not und, "POSIX 유틸 cd · ls · cp · mv · rm · wc · tr · sh → 위반 아님",
              f"exit {rc} · 미선언 {sorted(und)}")
        rc, n, und = cmd_cell(cb, "shell-keywords", "for f in a b\ndo\n  printf '%s\\n' \"$f\"\ndone\nif true\nthen\n  :\nfi\n")
        check("shell-keywords", rc == 0 and not und, "셸 키워드 for · do · done · if · then · fi → 위반 아님",
              f"exit {rc} · 미선언 {sorted(und)}")
        rc, n, und = cmd_cell(cb, "kubectl-ctl", "kubectl get pods\n")
        check("kubectl-ctl", rc == 1 and und == {"kubectl"}, "3글자 이상 미선언 명령 → VIOLATION (양성 대조)",
              f"exit {rc} · 미선언 {sorted(und)}")
        rc, n, und = cmd_cell(cb, "mixed-cmd", "rg -n x .\ngh pr list\nfd x\nag x\ncd /tmp\nls\nfor f in a\ndo\n  :\ndone\n"
                                               "python3 -c 'print(1)'\n")
        check("mixed-cmd", rc == 1 and und == {"ag", "fd", "rg"}, "선언 gh · POSIX · 키워드 · 미선언 fd · ag · rg 혼합 → 미선언 = {ag, fd, rg}",
              f"exit {rc} · 미선언 {sorted(und)}")
        nw = cb / "no-which-ec33"
        write(nw, "skills/x/SKILL.md", "# x\n\n```bash\ncd /tmp\nls -l\ncp a b\ngh pr view 1\n```\n")
        _, out = run(["-c", NO_WHICH, TREE, nw], allowed=(0,))
        m = re.search(r"^RC=(\d+)$", out, re.M)
        if not m:
            raise Setup(f"no-which-ec33: RC 줄 없음 ⏎ {out[-200:]}")
        check("no-which-ec33", m.group(1) == "0",
              "cd · ls · cp · gh 가 실행 파일로 없는 환경을 흉내 내도 위반 아님 — GONE 집합의 명령을 which 로 확인하는 필수 항목 없음",
              out)

        # ── 라이브 트리 ─────────────────────────────────────────────
        rc, out = run([LINT])
        check("live-diff-lint", rc == 0, "트리 자신의 diff 파서 lint → exit 0", out.strip().splitlines()[-1:] if rc == 0 else out)
        rc, out = run([CMDS, "--root", TREE])
        check("live-cmd-lint", rc == 0, "트리 자신의 외부 명령 lint → exit 0", out)
except Setup as e:
    print(f"SETUP {e}")
    sys.stdout.flush()
    os._exit(3)

print()
print(f"CELLS pass={PASSED[0]} fail={len(FAIL)}")
for f in FAIL:
    print(f"  FAIL {f}")
if not FAIL:
    print("DIFF_AND_CMD_CELLS_OK")
sys.stdout.flush()
os._exit(1 if FAIL else 0)
PY
rc=$?
cat "$LOG"
last="$(grep -E '^CELLS pass=[0-9]+ fail=[0-9]+$' "$LOG" | tail -1)"
case "$rc" in
  0) [ "$last" != "${last%fail=0}" ] && grep -qx 'DIFF_AND_CMD_CELLS_OK' "$LOG" && exit 0 ;;
  1) [ -n "$last" ] && [ "$last" = "${last%fail=0}" ] && exit 1 ;;
  3) exit 3 ;;
esac
echo "SETUP 판정 줄 없이 끝났다 — 단언기 exit $rc (신호 · 비정상 종료). 단언 실패(1)로 읽지 않는다"
exit 3
