#!/usr/bin/env python3
"""check_health_wiring.py — health-check 의 검사 등록이 실제 스크립트와 맞는가 (F-529).

왜: health-check 의 등록 목록(존재 확인 · self-test 루프)은 손으로 따로 관리돼 어긋났다 — `--self-test` 를 가진
스크립트 10개가 어디서도 자동으로 돌지 않았고(텔레메트리 리포터 · Stop 훅 · 실행 기록 포함), 존재 목록은
self-test 루프가 부르는 스크립트(`gpt_merge` · `gpt_ab_decide`)를 빠뜨렸다(2026-11-05 실측).

판정 (플러그인 루트 하나):
  ① 처리기 집합 = `scripts/*.{py,sh,js}` 중 `--self-test` 를 **실제로 처리하는** 것 — 문서 · 사용법 문구가 아니라
     코드의 리터럴로 본다(py: `__main__` 진입점이 있고 리터럴이 `add_argument` 호출 · 비교식 안에 있다 · js: 주석 밖 따옴표 리터럴 ·
     sh: 주석 밖 `--self-test)` case 갈래 또는 `$1` 비교)
  ② 실행 집합 = health-check 가 `--self-test` 로 부르는 스크립트(직접 호출 ∪ `for X in …; do … scripts/$X.<ext> … --self-test` 루프)
     ∪ 회귀 러너(`tests/fixtures/*/*/run.sh`)가 주석 밖 줄에서 `<이름>.<ext> … --self-test` 로 부르는 것
  ③ ① ⊆ ② ∪ 제외표(`tests/fixtures/health/wiring-exempt.tsv` — `<이름>\\t<사유 10자+>`) — 아니면 위반.
     제외표의 이름이 처리기가 아니거나 이미 실행되면 낡은 제외(위반)
  ④ 존재 목록(health-check 의 `for f in …; do` 사전조건) ⊇ health-check 가 self-test 로 부르는 스크립트 — 루프가 부르는데
     목록에 없으면 부재가 "명령 없음" 오류로 묻힌다
  ⑤ 러너 모드 계약(F-354): 러너가 받는 모드 플래그(경로 · 셀 부분집합 선택 제외)마다 `# modes:` 선언 — caller=health · release 면
     그 진입점에 러너 경로 + 플래그 호출이 있고, manual 이면 last-pass=<sha|none> + result. 호출 한 줄을 지우면 여기서 걸린다
  ⑥ GPT CLI 의존 선언(F-411): 실제 GPT CLI 에 닿을 수 있는 러너(주석 밖에 health-check.sh · check-gpt-flags.sh · GPT CLI 실행 파일 직접 호출 류 ·
     가짜 CLI `_shim` 없음)는 머리말 `# gpt-cli: real|none — <사유 10자+>` 한 줄을 단다. 오프라인 워커 · 리뷰어에게 돌리게 할지
     이 줄로 가린다. 닿지 않는 러너의 선언은 낡은 선언(위반)

exit code: 0 PASS · 1 VIOLATION · 2 UNRUN(health-check 부재 · 존재 목록 · 루프 파싱 실패 — ⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import ast
import os
import pathlib
import re
import sys
import tempfile

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXTS = (".py", ".sh", ".js")
LIT = re.compile(r"""(["'`])--self-test\1""")
SH_CASE = re.compile(r"""^\s*(?:[\w"'*.-]+\|)*["']?--self-test["']?(?:\|[\w"'*.-]+)*\)""")   # case 갈래는 줄 앞에만 — `… --self-test) 2>&1` 서브셸 닫힘은 아니다
SH_CMP = re.compile(r"""\$\{?1[^}\s"]*\}?"?\s*={1,2}\s*["']?--self-test""")
EXIST = re.compile(r"^for f in ([^;\n]+); do", re.M)
# ── 러너 모드 계약(F-354) — 러너가 받는 모드 플래그마다 머리말 `# modes: <flag|default> caller=health|release|manual[ last-pass=<sha|none> result=<요약>]`
# 경로 · 셀 부분집합 선택 플래그는 기본 실행이 상위집합이라 계약 밖이다(2026-11-05 배선 감사 Task 2 — 그 밖 13개가 모드 변경 플래그였다)
SUBSET_FLAGS = {"--tree", "--scripts", "--skills", "--cells"}
MODE_CASE = re.compile(r"^\s*((?:--[a-z][a-z0-9-]*)(?:\|--[a-z][a-z0-9-]*)*)\)")
MODE_CMP = re.compile(r"""(?:\$\{?1[^}\s"]*\}?|\bmode|\barg|\ba|\bflag)"?\s*={1,2}\s*["']?(--[a-z][a-z0-9-]*)""")
MODE_IN = re.compile(r"""["'](--[a-z][a-z0-9-]*)["']\s+in\s+(?:sys\.)?argv""")
MODES_DECL = re.compile(r"^# modes: (\S+) caller=(health|release|manual)(?: last-pass=(\S+))?(?: result=(.*\S))?\s*$")
SHA_OR_NONE = re.compile(r"^(?:[0-9a-f]{7,40}|none)$")
RELEASE_ENTRIES = ("scripts/check_release_sync.sh", "docs/completion-gates.md")
DEFAULT_GLOB = re.compile(r"^chk_runners .*tests/fixtures/\*/\*/run\.sh", re.M)
LOOP = re.compile(r"^for (\w+) in ([^;\n]+); do\n(.*?)^done", re.M | re.S)
GPT_CLI_TRIGGER = re.compile(r"health-check\.sh|check-gpt-flags\.sh|\bcodex\s+(?:exec|review|login|--version|--help)\b")
GPT_CLI_DECL = re.compile(r"^# gpt-cli: (real|none) — (.{10,})$")


def log(*a):
    print(*a, file=sys.stderr)


def handles(path: pathlib.Path) -> bool:
    t = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".py":
        # 리터럴이 **처리 문맥**에 있을 때만 — `add_argument("--self-test")` 호출 또는 비교식(`argv == ["--self-test"]` · `in argv`).
        # ⛔ 값 집합 · 정규식 같은 데이터 리터럴은 처리기가 아니다(실측: 라이브러리 모듈 ab_ledger_transcript 가 데이터로만 가진다 —
        #    `--self-test` 로 돌리면 아무것도 안 하고 exit 0 이라 배선하면 빈 시험이 통과로 찍힌다)
        try:
            tree = ast.parse(t)
        except SyntaxError:
            return False
        # 진입점(`if __name__ == "__main__":`)이 없는 모듈은 명령줄을 받지 않는다 — 라이브러리의 비교식은 처리기가 아니다
        if not any(isinstance(x, ast.Compare) and isinstance(x.left, ast.Name) and x.left.id == "__name__" for x in ast.walk(tree)):
            return False
        parent = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "--self-test":
                up = parent.get(node)
                while isinstance(up, (ast.List, ast.Tuple, ast.Set)):
                    up = parent.get(up)
                if isinstance(up, ast.Compare):
                    return True
                if isinstance(up, ast.Call) and getattr(up.func, "attr", getattr(up.func, "id", "")) == "add_argument":
                    return True
        return False
    code = [ln for ln in t.splitlines() if not ln.lstrip().startswith("//" if path.suffix == ".js" else "#")]
    if path.suffix == ".js":
        return any(LIT.search(ln) for ln in code)
    return any(SH_CASE.search(ln) or SH_CMP.search(ln) for ln in code)


def runner_modes(text: str) -> set:
    """러너가 실제로 받는 모드 플래그(부분집합 플래그 제외). 주석 줄 · 따옴표로 시작하는 줄(다른 파일에 심을 코드 문자열)은 보지 않는다."""
    got = set()
    for ln in text.splitlines():
        st = ln.lstrip()
        if st.startswith("#") or st[:1] in ("\"", "'"):
            continue
        m = MODE_CASE.match(ln)
        if m:
            got |= set(m.group(1).split("|"))
        got |= set(MODE_CMP.findall(ln)) | set(MODE_IN.findall(ln))
    return got - SUBSET_FLAGS


def mode_violations(root: pathlib.Path, hc_text: str):
    """(a) 받는 모드 ⊆ 선언 · 선언 ⊆ 받는 모드 ∪ {default} (b) caller=health · release 는 그 진입점에 러너 경로 + 플래그가 한 줄에 있다
    (c) manual 은 last-pass(sha 7~40 · 아직 통과한 적 없으면 none) + result. 반환 (위반 목록, 선언 수)."""
    bad, n = [], 0
    rel_text = {e: (root / e).read_text(encoding="utf-8") if (root / e).is_file() else "" for e in RELEASE_ENTRIES}
    for r in sorted(root.glob("tests/fixtures/*/*/run.sh")):
        rel = r.parent.relative_to(root / "tests" / "fixtures").as_posix()
        text = r.read_text(encoding="utf-8", errors="replace")
        decl = {}
        for ln in text.splitlines():
            if not ln.startswith("# modes:"):
                continue
            m = MODES_DECL.match(ln)
            if not m:
                bad.append(f"{rel}: `# modes:` 형식 밖 — {ln[:90]!r}")
                continue
            decl[m.group(1)] = m.groups()[1:]
        n += len(decl)
        parsed = runner_modes(text)
        for f in sorted(parsed - set(decl)):
            bad.append(f"{rel}: `{f}` 를 받는데 `# modes:` 선언이 없다 — 호출처(health · release)나 수동 기록(last-pass · result)을 적는다")
        for f in sorted(set(decl) - parsed - {"default"}):
            bad.append(f"{rel}: `# modes: {f}` 를 선언했는데 러너가 그 플래그를 받지 않는다(낡은 선언)")
        for f, (caller, last, result) in sorted(decl.items()):
            if caller == "manual":
                if not (last and SHA_OR_NONE.match(last) and result):
                    bad.append(f"{rel}: `{f}` caller=manual 은 last-pass=<sha|none> 와 result=<요약> 이 필요하다")
                continue
            if f == "default":
                ok = caller == "health" and bool(DEFAULT_GLOB.search(hc_text))
            else:
                hay = hc_text if caller == "health" else "\n".join(rel_text.values())
                ok = any(rel in ln and f in ln for ln in hay.splitlines() if not ln.lstrip().startswith("#"))
            if not ok:
                where = "health-check.sh" if caller == "health" else " · ".join(RELEASE_ENTRIES)
                bad.append(f"{rel}: `{f}` caller={caller} 인데 {where} 에 그 러너 + 플래그 호출이 없다")
    return bad, n


def calls_in(text: str, direct_re: re.Pattern):
    """health-check 본문 → (직접 호출 이름 집합, 루프 구성원 {이름: 확장자})."""
    direct = {m.group(1) for ln in text.splitlines() if not ln.lstrip().startswith("#") for m in direct_re.finditer(ln)}
    loops = {}
    for m in LOOP.finditer(text):
        var, members, body = m.group(1), m.group(2).split(), m.group(3)
        e = re.search(r"scripts/\$\{?%s\}?\.(py|sh|js)" % var, body)
        if e and "--self-test" in body:
            loops.update({x: "." + e.group(1) for x in members})
    return direct, loops


def gpt_cli_violations(root: pathlib.Path):
    """⑥ 실제 GPT CLI 에 닿을 수 있는 러너의 의존 선언(F-411) → (위반 목록, 선언 수)."""
    bad, n = [], 0
    for r in sorted(root.glob("tests/fixtures/*/*/run.sh")):
        rel = r.parent.relative_to(root / "tests" / "fixtures").as_posix()
        lines = r.read_text(encoding="utf-8", errors="replace").splitlines()
        code = [ln for ln in lines if not ln.lstrip().startswith("#")]
        hit = any(GPT_CLI_TRIGGER.search(ln) for ln in code) and not any("_shim" in ln for ln in code)
        decl = [ln for ln in lines if ln.startswith("# gpt-cli:")]
        n += len(decl)
        if len(decl) > 1 or any(not GPT_CLI_DECL.match(ln) for ln in decl):
            bad.append(f"{rel}: `# gpt-cli:` 형식 밖 — `# gpt-cli: real|none — <사유 10자+>` 한 줄")
        elif hit and not decl:
            bad.append(f"{rel}: 실제 GPT CLI 에 닿을 수 있는데(health-check · check-gpt-flags · GPT CLI 실행 파일) `# gpt-cli:` 선언이 없다 — real|none 과 사유")
        elif decl and not hit:
            bad.append(f"{rel}: `# gpt-cli:` 를 선언했는데 GPT CLI 에 닿는 호출이 없다(낡은 선언)")
    return bad, n


def check(root: pathlib.Path):
    hc = root / "scripts" / "health-check.sh"
    if not hc.is_file():
        log(f"UNRUN: health-check 없음 — {hc}")
        return UNRUN
    text = hc.read_text(encoding="utf-8")
    ex = EXIST.search(text)
    if not ex:
        log("UNRUN: health-check 의 존재 목록(`for f in …; do`)을 찾지 못했다")
        return UNRUN
    exist = set(ex.group(1).split())
    files = {p.stem: p for p in sorted((root / "scripts").iterdir()) if p.suffix in EXTS and p.is_file()}
    hand = {s for s, p in files.items() if handles(p)}
    direct_re = re.compile(r"scripts/([\w.-]+?)\.(?:py|sh|js)\"?[^\n|;&]*?--self-test")
    direct, loops = calls_in(text, direct_re)
    if not direct and not loops:
        log("UNRUN: health-check 에서 self-test 호출을 하나도 찾지 못했다 — 파싱이 형식을 놓쳤을 수 있다")
        return UNRUN
    runner_re = re.compile(r"([\w.-]+?)\.(?:py|sh|js)\"?\s+(?:[^\n|;&#]*\s)?--self-test")
    by_runner = {}
    for r in sorted(root.glob("tests/fixtures/*/*/run.sh")):
        for ln in r.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.lstrip().startswith("#"):
                continue
            for m in runner_re.finditer(ln):
                by_runner.setdefault(m.group(1).rsplit("/", 1)[-1], r.relative_to(root).as_posix())
    hc_runs = direct | set(loops)
    # 양성 대조 — health-check 가 이미 self-test 로 부르는 스크립트는 처리기로 보여야 한다. 안 보이면 감지기가 그 형식을 놓친 것이다
    blind = sorted(s for s in hc_runs if s in files and s not in hand)
    if blind:
        log(f"UNRUN: health-check 가 --self-test 로 부르는데 처리기로 감지 못한 스크립트 {blind[:5]} — 감지 규칙이 그 형식을 놓쳤다")
        return UNRUN
    runs = hc_runs | set(by_runner)
    exempt, bad = {}, []
    ef = root / "tests" / "fixtures" / "health" / "wiring-exempt.tsv"
    if ef.is_file():
        for n, ln in enumerate(ef.read_text(encoding="utf-8").splitlines(), 1):
            if not ln.strip() or ln.startswith("#"):
                continue
            name, _, why = ln.partition("\t")
            if len(why.strip()) < 10:
                bad.append(f"wiring-exempt.tsv:{n} `{name}` — 사유가 없거나 짧다(10자+)")
            exempt[name.strip()] = why.strip()
    for s in sorted(hand - runs - set(exempt)):
        bad.append(f"`scripts/{files[s].name}` 의 --self-test 가 어디서도 자동으로 돌지 않는다 — health-check 에 배선하거나 wiring-exempt.tsv 에 사유")
    for s in sorted(exempt):
        if s not in hand:
            bad.append(f"wiring-exempt.tsv `{s}` — --self-test 처리기가 없다(낡은 제외)")
        elif s in runs:
            bad.append(f"wiring-exempt.tsv `{s}` — 이미 자동으로 돈다(낡은 제외)")
    for s in sorted(hc_runs):
        f = files.get(s)
        name = f.name if f else s + loops.get(s, "")
        if name not in exist:
            bad.append(f"존재 목록에 `{name}` 없음 — health-check 가 self-test 로 부르는데 사전조건이 부재를 잡지 못한다")
    mbad, mdecl = mode_violations(root, text)
    gbad, gdecl = gpt_cli_violations(root)
    bad += mbad + gbad
    print(f"health-check 배선 — 처리기 {len(hand)} · health-check 실행 {len(hc_runs)} · 러너 경유 {len(set(by_runner) - hc_runs)} · 제외 {len(exempt)} · 러너 모드 선언 {mdecl}"
          f" · GPT CLI 선언 {gdecl}")
    for b in bad:
        print(f"  ✗ {b}")
    return VIOLATION if bad else OK


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {detail}"))

    seq = [0]

    def tree(t, hc, scripts, runners=None, exempt=None):
        seq[0] += 1
        r = pathlib.Path(t) / f"r{seq[0]}"
        (r / "scripts").mkdir(parents=True)
        (r / "scripts" / "health-check.sh").write_text(hc)
        for n, body in scripts.items():
            (r / "scripts" / n).write_text(body)
        for rel, body in (runners or {}).items():
            p = r / "tests" / "fixtures" / rel / "run.sh"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        if exempt is not None:
            p = r / "tests" / "fixtures" / "health" / "wiring-exempt.tsv"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(exempt)
        return r

    PY = 'import sys\nif __name__ == "__main__" and sys.argv[1:] == ["--self-test"]:\n    print("self-test 1/1")\n'
    DOC = '"""usage: x.py --self-test"""\nprint(1)\n'
    HC = ('for f in a.py b.py; do [ -f "$ROOT/scripts/$f" ]; done\n'
          'python3 "$ROOT/scripts/a.py" --self-test\n'
          'for FS in b; do\n  python3 "scripts/$FS.py" --self-test\ndone\n')
    with tempfile.TemporaryDirectory() as t:
        quiet = open(os.devnull, "w")
        o, sys.stdout = sys.stdout, quiet
        try:
            r_ok = check(tree(t, HC, {"a.py": PY, "b.py": PY}))
            r_unwired = check(tree(t, HC, {"a.py": PY, "b.py": PY, "c.py": PY}))
            r_doc = check(tree(t, HC, {"a.py": PY, "b.py": PY, "d.py": DOC}))
            r_data = check(tree(t, HC, {"a.py": PY, "b.py": PY, "e.py": 'FLAGS = {"--self-test", "--tree"}\nprint(1)\n'}))
            r_lib = check(tree(t, HC, {"a.py": PY, "b.py": PY, "l.py": 'def f(x):\n    return [t for t in x if t in ("--self-test",)]\n'}))
            r_argp = check(tree(t, HC, {"a.py": PY, "b.py": PY, "g.py": 'import argparse\nap = argparse.ArgumentParser()\nap.add_argument("--self-test", action="store_true")\nif __name__ == "__main__":\n    ap.parse_args()\n'}))
            r_runner = check(tree(t, HC, {"a.py": PY, "b.py": PY, "c.py": PY}, {"x/c": 'python3 "$R/scripts/c.py" --self-test\n'}))
            r_runner_comment = check(tree(t, HC, {"a.py": PY, "b.py": PY, "c.py": PY}, {"x/c": '# c.py --self-test 를 돈다\n'}))
            r_exempt = check(tree(t, HC, {"a.py": PY, "b.py": PY, "c.py": PY}, exempt="c\t실행하면 실제 상태 폴더에 쓴다\n"))
            r_exempt_short = check(tree(t, HC, {"a.py": PY, "b.py": PY, "c.py": PY}, exempt="c\t짧음\n"))
            r_exempt_stale = check(tree(t, HC, {"a.py": PY, "b.py": PY}, exempt="a\t이미 health-check 가 직접 부른다\n"))
            r_exist = check(tree(t, HC.replace("a.py b.py", "a.py"), {"a.py": PY, "b.py": PY}))
            r_sh = check(tree(t, HC, {"a.py": PY, "b.py": PY, "s.sh": 'case "${1:-}" in\n  --self-test) echo ok ;;\nesac\n'}))
            r_sub = check(tree(t, HC, {"a.py": PY, "b.py": PY, "w.sh": 'X="$( (python3 a.py --self-test) 2>&1)"\n'}))
            r_js = check(tree(t, HC, {"a.py": PY, "b.py": PY, "j.js": "// --self-test 설명\nconsole.log(1)\n"}))
            HCD = HC + 'chk_runners "$ROOT"/tests/fixtures/*/*/run.sh\n'
            RUN_OK = '#!/bin/bash\n# modes: default caller=health\n# modes: --live caller=health\ncase "${1:-}" in\n  --live) : ;;\nesac\n'
            r_modes_ok = check(tree(t, HCD + 'bash "$ROOT/tests/fixtures/x/m/run.sh" --live\n', {"a.py": PY, "b.py": PY}, {"x/m": RUN_OK}))
            r_caller_missing = check(tree(t, HCD, {"a.py": PY, "b.py": PY}, {"x/m": RUN_OK}))
            r_undeclared = check(tree(t, HCD, {"a.py": PY, "b.py": PY}, {"x/m": '#!/bin/bash\ncase "${1:-}" in\n  --emit) : ;;\nesac\n'}))
            r_stale_decl = check(tree(t, HCD, {"a.py": PY, "b.py": PY}, {"x/m": '#!/bin/bash\n# modes: --gone caller=manual last-pass=abc1234 result=PASS\n'}))
            r_manual_bare = check(tree(t, HCD, {"a.py": PY, "b.py": PY}, {"x/m": '#!/bin/bash\n# modes: --emit caller=manual\ncase "${1:-}" in\n  --emit) : ;;\nesac\n'}))
            r_manual_ok = check(tree(t, HCD, {"a.py": PY, "b.py": PY}, {"x/m": '#!/bin/bash\n# modes: --emit caller=manual last-pass=none result=사람 호출 전용 — 네트워크\ncase "${1:-}" in\n  --emit) : ;;\nesac\n'}))
            r_subset = check(tree(t, HCD, {"a.py": PY, "b.py": PY}, {"x/m": '#!/bin/bash\ncase "${1:-}" in\n  --tree|--cells) : ;;\nesac\n'}))
            r_strline = check(tree(t, HCD, {"a.py": PY, "b.py": PY}, {"x/m": '#!/bin/bash\nX=(\n  "if \'--planted\' in sys.argv:"\n)\n'}))
            r_default_noglob = check(tree(t, HC, {"a.py": PY, "b.py": PY}, {"x/m": '#!/bin/bash\n# modes: default caller=health\n'}))
            gr = lambda body: check(tree(t, HC, {"a.py": PY, "b.py": PY}, {"x/h": "#!/bin/bash\n" + body}))   # noqa: E731
            r_gpt = (gr('bash "$C/scripts/health-check.sh"\n'),
                     gr('# gpt-cli: real — 사본에서 health-check 전체를 돈다\nbash "$C/scripts/health-check.sh"\n'),
                     gr('# gpt-cli: none — 부분 실행만 한다고 적었다\necho hi\n'),
                     gr('export PATH="$R/tests/fixtures/gpt/_shim:$PATH"\ncodex exec x\n'),
                     gr('# gpt-cli: real\nbash "$C/scripts/health-check.sh"\n'))
            r_nohc = check(pathlib.Path(t) / "absent")
            r_blind = check(tree(t, HC, {"a.py": DOC, "b.py": PY}))
            r_noloop = check(tree(t, "for f in a.py; do :; done\n", {"a.py": PY}))
        finally:
            sys.stdout = o
            quiet.close()
    case("wired-ok", r_ok == OK, r_ok)
    case("handler-unwired", r_unwired == VIOLATION, r_unwired)
    case("docstring-not-handler", r_doc == OK, r_doc)
    case("data-literal-not-handler", r_data == OK, r_data)
    case("argparse-handler", r_argp == VIOLATION, r_argp)
    case("library-compare-not-handler", r_lib == OK, r_lib)
    case("runner-counts", r_runner == OK, r_runner)
    case("runner-comment-not-call", r_runner_comment == VIOLATION, r_runner_comment)
    case("exempt-with-reason", r_exempt == OK, r_exempt)
    case("exempt-without-reason", r_exempt_short == VIOLATION, r_exempt_short)
    case("exempt-stale", r_exempt_stale == VIOLATION, r_exempt_stale)
    case("loop-member-not-in-existence", r_exist == VIOLATION, r_exist)
    case("sh-case-handler", r_sh == VIOLATION, r_sh)
    case("js-comment-not-handler", r_js == OK, r_js)
    case("subshell-paren-not-handler", r_sub == OK, r_sub)
    case("modes-declared-ok", r_modes_ok == OK, r_modes_ok)
    case("caller-missing-health-call", r_caller_missing == VIOLATION, r_caller_missing)
    case("mode-undeclared", r_undeclared == VIOLATION, r_undeclared)
    case("mode-stale-declaration", r_stale_decl == VIOLATION, r_stale_decl)
    case("manual-needs-last-pass", r_manual_bare == VIOLATION, r_manual_bare)
    case("manual-none-with-result", r_manual_ok == OK, r_manual_ok)
    case("subset-flags-exempt", r_subset == OK, r_subset)
    case("string-line-not-mode", r_strline == OK, r_strline)
    case("default-needs-runner-glob", r_default_noglob == VIOLATION, r_default_noglob)
    case("f411-runner-gpt-dependency", r_gpt == (VIOLATION, OK, VIOLATION, OK, VIOLATION),
         f"미선언 · 선언 · 낡은 선언 · shim · 사유 없음 → {r_gpt}")
    case("no-health-check-unrun", r_nohc == UNRUN, r_nohc)
    case("no-calls-unrun", r_noloop == UNRUN, r_noloop)
    case("detector-blind-unrun", r_blind == UNRUN, r_blind)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", default=os.path.join(SCRIPT_DIR, ".."))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return check(pathlib.Path(a.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
