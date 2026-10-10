#!/bin/bash
# 역할 본문 주입 사이트 재생 fixture (F-335 ㉒) — 호출부가 `cat "$…SKILL_PATH"` 로 본문을 넣던 사이트가 래퍼 `--inject-skill` 로
# 바뀌었는지 문서 문자열이 아니라 **실제 argv** 로 본다.
#   ① 사이트 목록: 기준 문서(--base) 의 ```bash 블록에서 `cat "$…SKILL_PATH"` 줄을 찾고, 같은 블록의 `get_gpt_skill_path "<역할>"` 로
#      (문서 · 제목 · 역할) 고유 사이트를 만든다. --base 가 없으면 이 폴더의 sites.tsv(f500bc9 에서 뽑은 동결본)를 쓴다
#   ② 사이트마다 대상 트리(--tree)의 같은 문서 · 같은 제목 · 같은 역할 Bash 블록을 가짜 래퍼(scripts/gpt-exec.sh 대역 — argv 기록)로
#      돌려, exec argv 에 `--inject-skill <그 역할 본문 경로>` 가 있고 프롬프트 파일에 본문이 없음(호출부 cat 없음)을 단언한다
#   ③ 대조 셀 — 셋 다 판정기가 **거부**해야 통과다: 설명/주석만 추가(argv 는 --gpt-skill-path) · 잘못된 경로 · 호출 삭제
#   ④ harness — 합성 블록 양성(통과해야)·음성(거부해야). 둘 중 하나라도 어긋나면 판정기 고장이라 준비 실패(3)다
#   ⑤ floor — 통과한 고유 사이트가 7 이상(원장 하한)
# 기준 트리는 cat + --gpt-skill-path 그대로라 ② 가 전부 실패한다 → exit 1.
# 기대 셀 집합(F-408): harness · 사이트마다 1셀 · 대조 3셀 · floor — 판정한 셀과 정확히 같아야 하고, 끝 줄에 돈 셀 목록 · 수를 찍는다.
# ⛔ 실제 GPT CLI · 래퍼를 부르지 않는다(FZ_PLUGIN_ROOT 를 임시 대역으로) · HOME 은 임시 폴더 · 블록의 /tmp/ 는 임시 폴더로 바꿔 돌린다.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 문서 읽기 · 사이트 7 미만 · harness 고장 · 미처리 예외)
# usage: run.sh [--tree <플러그인 루트>] [--base <기준 루트>] [--emit-sites]
#   --emit-sites  --base 에서 뽑은 사이트 목록을 TSV 로 찍고 끝낸다(sites.tsv 재생성용)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="" EMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    --base) [ $# -ge 2 ] || { echo "SETUP --base 에 경로가 없다"; exit 3; }
            BASE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --base 경로 없음: $2"; exit 3; }; shift 2 ;;
    --emit-sites) EMIT=1; shift ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다
T0="$(mktemp -d)" || { echo "SETUP mktemp 실패"; exit 3; }; T="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 해석 실패"; exit 3; }
trap 'rm -rf "${T:?}"' EXIT

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" "$BASE" "$HERE/sites.tsv" "$T" "$EMIT" <<'PY'
import json, os, pathlib, re, subprocess, sys, traceback


def _crash(*exc):   # 판정기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
TREE, BASE, FROZEN, TMP, EMIT = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3]), pathlib.Path(sys.argv[4]), sys.argv[5]
DOCS = ("skills/fz-modernize/SKILL.md", "modules/cross-validation.md", "modules/fz-gpt-subcommands-aux.md",
        "modules/fz-gpt-subcommands-core.md", "modules/peer-review-tiers.md")
FLOOR = 7
CAT = re.compile(r'cat "\$\{?([A-Z_]*SKILL_PATH)')
ROLE = re.compile(r'\b([A-Z_]*SKILL_PATH)=\$\(get_gpt_skill_path "([a-z-]+)"')
EXEC_LINE = re.compile(r'/scripts/gpt-exec\.sh"')
WRONG = '"$FZ_PLUGIN_ROOT/gpt-skills/fz-wrong/SKILL.md"'


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def read(root, rel):
    p = pathlib.Path(root) / rel
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        raise Setup(f"문서를 읽지 못했다 {p}: {type(e).__name__}")


def blocks(text):
    """```bash 블록 → [(제목, 시작 줄, 본문)]. 제목은 펜스 밖의 가장 가까운 앞 `#` 줄이다."""
    out, head, cur, start = [], "", None, 0
    for i, line in enumerate(text.split("\n"), 1):
        if cur is None:
            if re.match(r"^```bash\s*$", line):
                cur, start = [], i + 1
            elif re.match(r"^#{1,6}\s", line):
                head = line.strip()
        elif re.match(r"^```\s*$", line):
            out.append((head, start, "\n".join(cur)))
            cur = None
        else:
            cur.append(line)
    return out


def sites_of(root):
    """기준 트리 → 고유 사이트 [(문서, 제목, 역할, 변수, 줄)]."""
    got, seen = [], set()
    for doc in DOCS:
        for head, start, body in blocks(read(root, doc)):
            roles = {v: r for v, r in ROLE.findall(body)}
            for off, line in enumerate(body.split("\n")):
                m = CAT.search(line)
                if not m:
                    continue
                var = m.group(1)
                if var not in roles:
                    raise Setup(f"{doc}:{start + off} — cat 하는 {var} 의 get_gpt_skill_path 역할을 같은 블록에서 찾지 못했다")
                key = (doc, head, roles[var])
                if key not in seen:
                    seen.add(key)
                    got.append((doc, head, roles[var], var, start + off))
    return got


def load_frozen():
    try:
        rows = [l.split("\t") for l in FROZEN.read_text(encoding="utf-8").split("\n") if l and not l.startswith("#")]
    except OSError as e:
        raise Setup(f"동결 사이트 목록을 읽지 못했다 {FROZEN}: {type(e).__name__}")
    if any(len(r) != 5 for r in rows):
        raise Setup("sites.tsv 형식 — 열 5개(문서 · 제목 · 역할 · 변수 · 기준 줄)")
    return [(a, b, c, d, int(e)) for a, b, c, d, e in rows]


# ── 대역 래퍼 · 재생 ───────────────────────────────────────────────
STUB = '''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
with open(os.environ["FZ_SITE_CAPTURE"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(a, ensure_ascii=False) + "\\n")
if "--out" in a and a.index("--out") + 1 < len(a):
    out = a[a.index("--out") + 1]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w").write("{}")
'''
FIXED = {"AFFECTED_SYMBOLS": "", "MAJOR_ISSUES_COUNT": "1", "HAS_FIXABLE_ISSUES": "true"}   # 호출 분기에 들어가는 전제
ENV_GIVEN = {"FZ_PLUGIN_ROOT", "HOME", "PATH"}
RUN_N = [0]


def replay(body):
    """블록 하나를 대역으로 돌린다 → (exec argv 목록, 샌드박스, rc, 출력 꼬리)."""
    RUN_N[0] += 1
    w = TMP / f"run{RUN_N[0]}"
    for d in ("plugin/scripts", "skills", "io", "dirs", "ph", "tmp", "home", "cwd"):
        (w / d).mkdir(parents=True, exist_ok=True)
    stub = w / "plugin/scripts/gpt-exec.sh"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    # 자리표시 `{NAME}` — 경로 · 파일은 내용 있는 파일, 폴더는 폴더, 나머지는 고정 토큰
    def ph(m):
        n = m.group(1)
        p = w / "ph" / n
        if n.endswith("_DIR"):
            p.mkdir(parents=True, exist_ok=True)
        elif n.endswith(("_PATH", "_FILE")):
            p.write_text(f"PH-{n}\n", encoding="utf-8")
        else:
            return "PH"
        return str(p)
    body = re.sub(r"(?<!\$)\{([A-Z][A-Z0-9_]*)\}", ph, body)
    body = re.sub(r"(?<=[\s\"'=>])/tmp/", str(w / "tmp") + "/", body)
    used = set(re.findall(r"\$\{?([A-Z][A-Z0-9_]*)", body))
    assigned = set(re.findall(r"(?:^|[\s;{(])([A-Z][A-Z0-9_]*)=", body))
    pre = []
    for n in sorted(used - assigned - ENV_GIVEN):
        if n in FIXED:
            v = FIXED[n]
        elif n in ("WORK_DIR", "GIT_ROOT", "ISO"):
            (w / "dirs" / n).mkdir(exist_ok=True)
            v = str(w / "dirs" / n)
        elif n.startswith("P_") or n in ("P", "OUT") or n.endswith("_FILE"):
            v = str(w / "io" / n)
        else:
            v = f"FIXED-{n}"
        pre.append(f"{n}={json.dumps(v, ensure_ascii=False)}")
    # 블록이 읽는 Lead 산출(`${WORK_DIR}/challenger-findings.md` 등)은 내용 있는 파일로 둔다 — 없으면 호출 전 채움 검사에서 멈춘다
    for d, f in set(re.findall(r"\$\{?(WORK_DIR|GIT_ROOT)\}?/([\w.-]+)", body)):
        (w / "dirs" / d).mkdir(exist_ok=True)
        q = w / "dirs" / d / f
        if not q.exists():
            q.write_text(f"FIXED-{f}\n", encoding="utf-8")
    script = "\n".join([
        'get_gpt_skill_path() { local d="$FZ_STUB_SKILLS/fz-$1"; mkdir -p "$d";'
        ' printf \'# fz-%s — 고정 본문(fixture)\\nSTUB-BODY-%s\\n\' "$1" "$1" > "$d/SKILL.md"; printf \'%s\' "$d/SKILL.md"; }',
        *pre, body, ""])
    (w / "block.sh").write_text(script, encoding="utf-8")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(w / "home"), "FZ_PLUGIN_ROOT": str(w / "plugin"),
           "FZ_STUB_SKILLS": str(w / "skills"), "FZ_SITE_CAPTURE": str(w / "cap.jsonl"), "LC_ALL": "C.UTF-8"}
    try:
        r = subprocess.run(["bash", "--noprofile", "--norc", str(w / "block.sh")], cwd=str(w / "cwd"), env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        rc, tail = r.returncode, (r.stdout + r.stderr)[-300:]
    except subprocess.TimeoutExpired:
        rc, tail = "timeout", "60s"
    cap = w / "cap.jsonl"
    argv = [json.loads(l) for l in cap.read_text(encoding="utf-8").split("\n") if l] if cap.is_file() else []
    return [a for a in argv if a and a[0] == "exec"], w, rc, tail


def judge(body, role):
    """→ (통과?, 사유). 통과 = exec argv 에 `--inject-skill <역할 본문>` 이 있고, 그 호출의 프롬프트에 본문이 없다."""
    execs, w, rc, tail = replay(body)
    want = str(w / "skills" / f"fz-{role}" / "SKILL.md")
    if not execs:
        return False, f"exec 호출 0 (rc={rc} · {tail.strip()[-160:]!r})"
    why = []
    for a in execs:
        pairs = list(zip(a, a[1:]))
        inj = [v for k, v in pairs if k == "--inject-skill"]
        gsp = [v for k, v in pairs if k == "--gpt-skill-path"]
        pf = [v for k, v in pairs if k == "--prompt-file"]
        if want not in inj:
            why.append(f"--inject-skill {[x.replace(str(w), '<W>') for x in inj] or '없음'} (기대 <W>/skills/fz-{role}/SKILL.md)")
            continue
        if any(g != want for g in gsp):
            why.append("--gpt-skill-path 가 다른 파일 — 래퍼 exit 10")
            continue
        body_in = any(f"STUB-BODY-{role}" in pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
                      for p in pf if pathlib.Path(p).is_file())
        if body_in:
            why.append("프롬프트 파일에 본문이 이미 있다 — 호출부 cat 이 남았다(이중 책임)")
            continue
        return True, f"exec argv 에 --inject-skill <W>/skills/fz-{role}/SKILL.md · 프롬프트에 본문 없음"
    return False, " | ".join(why)


def is_code(line):
    return not line.lstrip().startswith("#")


def ctl_comment(body, var):
    """설명/주석만 — 코드의 --inject-skill 을 --gpt-skill-path 로 되돌리고 --inject-skill 은 주석에만 둔다."""
    lines = [l.replace("--inject-skill", "--gpt-skill-path") if is_code(l) else l for l in body.split("\n")]
    out = []
    for l in lines:
        if is_code(l) and EXEC_LINE.search(l):
            out.append(f'# 역할 본문은 래퍼가 --inject-skill "${var}" 로 넣는다(설명만)')
        out.append(l)
    out.append(f'# --inject-skill "${var}"')
    return "\n".join(out)


def ctl_wrong(body):
    """잘못된 경로 — --inject-skill 의 인자를 다른 스킬로(없으면 --gpt-skill-path 자리를 잘못된 --inject-skill 로)."""
    def fix(l):
        if not is_code(l):
            return l
        if "--inject-skill" in l:
            return re.sub(r'--inject-skill\s+("[^"]*"|\S+)', f"--inject-skill {WRONG}", l)
        return re.sub(r'--gpt-skill-path\s+("[^"]*"|\S+)', f"--inject-skill {WRONG}", l)
    return "\n".join(fix(l) for l in body.split("\n"))


def ctl_deleted(body):
    """호출 삭제 — gpt-exec.sh 호출 줄과 그 이어진 줄(`\\` 끝)을 지운다."""
    out, skip = [], False
    for l in body.split("\n"):
        if skip or (is_code(l) and EXEC_LINE.search(l)):
            skip = l.rstrip().endswith("\\")
            continue
        out.append(l)
    return "\n".join(out)


RAN, FAILS, N = [], [], [0]


def check(cell, ok, what, detail=""):
    N[0] += 1
    if cell not in RAN:
        RAN.append(cell)
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAILS.append(f"{cell}: {what}")


def cell_of(site):
    doc, _, role, _, line = site
    return f"site:{doc}:{role}:L{line}"


def main():
    if BASE:
        sites = sites_of(BASE)
        src = f"--base {BASE}"
    else:
        sites = load_frozen()
        src = f"동결 {FROZEN.name}"
    if EMIT:
        if not BASE:
            raise Setup("--emit-sites 는 --base 가 필요하다")
        print("# 문서\t제목\t역할\t변수\t기준 줄 — run.sh --base <기준> --emit-sites 로 만든다")
        for s in sites:
            print("\t".join(map(str, s)))
        return 0
    if len(sites) < FLOOR:
        raise Setup(f"사이트 {len(sites)}개 < {FLOOR} — 이 기준은 cat 사이트를 가진 판이 아니다({src})")
    if BASE and FROZEN.is_file():
        fz = {s[:3] for s in load_frozen()}
        if fz != {s[:3] for s in sites}:
            print(f"INFO  --base 사이트 집합이 동결 sites.tsv 와 다르다(이번 판정은 --base 기준) — 빠짐 {sorted(fz - {s[:3] for s in sites})}")
    tree_text = {doc: read(TREE, doc) for doc in DOCS}           # 다섯 문서 읽기 확인 — 못 읽으면 준비 실패
    print(f"사이트 {len(sites)}개 ({src}) · 대상 {TREE}")

    # ── harness — 판정기가 양성은 통과 · 음성은 거부하는가 ──────────────────
    pos = ('SKILL_PATH=$(get_gpt_skill_path "architect" "$FZ_PLUGIN_ROOT")\nprintf \'x\\n\' > "$P"\n'
           '"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$GIT_ROOT" --out "$OUT" --prompt-file "$P" \\\n'
           '  --gpt-skill architect --inject-skill "$SKILL_PATH"\n')
    neg = ('SKILL_PATH=$(get_gpt_skill_path "architect" "$FZ_PLUGIN_ROOT")\nSKILL_PROMPT="$(cat "$SKILL_PATH")"\n'
           'printf \'%s\\n\' "$SKILL_PROMPT" > "$P"\n'
           '"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$GIT_ROOT" --out "$OUT" --prompt-file "$P" \\\n'
           '  --gpt-skill architect --gpt-skill-path "$SKILL_PATH"\n')
    ok_p, why_p = judge(pos, "architect")
    ok_n, why_n = judge(neg, "architect")
    if not ok_p or ok_n:
        raise Setup(f"harness 고장 — 양성 {ok_p}({why_p}) · 음성 {ok_n}({why_n})")
    check("harness", True, "합성 블록 양성 통과 · 음성(cat + --gpt-skill-path) 거부")

    passed, ctl = 0, {"ctl-comment": [], "ctl-wrongpath": [], "ctl-deleted": []}
    skipped = {k: 0 for k in ctl}
    for doc, head, role, var, line in sites:
        cell = cell_of((doc, head, role, var, line))
        cands = [b for b in blocks(tree_text[doc]) if b[0] == head and f'get_gpt_skill_path "{role}"' in b[2]]
        if len(cands) != 1:
            check(cell, False, f"대응 Bash 블록 1개 ({doc} · {head} · {role})", f"{len(cands)}개 — 0 이면 블록 삭제 · 제목 변경")
            continue
        _, start, body = cands[0]
        ok, why = judge(body, role)
        check(cell, ok, f"{head.lstrip('#').strip()[:40]} → 후보 {doc}:{start} 재생", why)
        passed += ok
        cvar = (ROLE.search(body) or re.search(r"(SKILL_PATH)", "SKILL_PATH")).group(1)
        for name, mutated in (("ctl-comment", ctl_comment(body, cvar)), ("ctl-wrongpath", ctl_wrong(body)),
                              ("ctl-deleted", ctl_deleted(body))):
            if mutated == body:   # 걸 자리가 없다 = 그 블록에 exec · 플래그가 없다 — 사이트 셀이 이미 실패한다
                skipped[name] += 1
                continue
            c_ok, c_why = judge(mutated, role)
            ctl[name].append((f"{doc}:{start}", c_ok, c_why))
    for name, rows in ctl.items():
        leaked = [f"{where}({why})" for where, ok, why in rows if ok]
        check(name, bool(rows) and not leaked, f"변이 {len(rows)}개 전부 거부(걸 자리 없음 {skipped[name]})",
              f"통과해 버린 변이 {leaked or '— 변이 0개'}")
    check("floor", passed >= FLOOR, f"통과한 고유 사이트 {passed} ≥ {FLOOR}", f"{passed}")

    # F-408 — 판정한 셀 = 기대 셀. check 를 거치지 않는다(거치면 그 이름이 RAN 에 들어간다)
    exp = ["harness"] + [cell_of(s) for s in sites] + list(ctl) + ["floor"]
    if set(RAN) != set(exp) or len(RAN) != len(exp):
        what = f"기대 셀 집합 — 빠짐 {sorted(set(exp) - set(RAN))} · 더함 {sorted(set(RAN) - set(exp))} · 판정 {len(RAN)} · 기대 {len(exp)}"
        print(f"FAIL  {what}")
        FAILS.append(what)
    print()
    if FAILS:
        print(f"INJECT_SKILL_SITES_FAIL fail={len(FAILS)} sites_passed={passed}/{len(sites)} ran={len(RAN)}({' '.join(RAN)}) checks={N[0]}")
        return 1
    print(f"INJECT_SKILL_SITES_OK sites={passed}/{len(sites)} ran={len(RAN)}({' '.join(RAN)}) checks={N[0]}")
    return 0


try:
    sys.exit(main())
except Setup as ex:
    print(f"SETUP {ex}")
    sys.exit(3)
PY
rc=$?
case "$rc" in
  0|1|3) exit "$rc" ;;
  *) echo "SETUP python 이 0/1/3 밖으로 끝났다 (exit $rc)"; exit 3 ;;
esac
