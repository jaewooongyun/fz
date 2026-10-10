#!/bin/bash
# Workflow 준비 계약 fixture — `guides/skill-authoring.md` §12 우회 계약의 **0단계 준비** 블록과 소비자 9곳의 준비 줄을
# 문서에서 꺼내 **실제로 실행**한다. 문구 존재가 아니라 행동(종료 코드 · 복사본 바이트 · 만들지 말아야 할 파일)을 본다.
#   --cells prep   0단계 블록(placeholder 를 임시 폴더로 치환)을 셀마다 돌린다
#     없음         복사본이 없다 → exit 0 · 원본과 바이트 일치
#     stale        다른 내용의 복사본이 있다 → exit 0 · 덮어써져 일치
#     정상         같은 복사본이 있다 → exit 0 · 일치
#     형제 접두사  WORK_DIR=<세션>-x (문자열 접두사만 같다) → 비0 · 복사본 0 / 대조: WORK_DIR=<세션> 자신 → exit 0
#     symlink      WORK_DIR=<세션>/link → 범위 밖 → 비0 · 밖에 복사본 0 / 대조: 세션 안을 가리키는 link → exit 0
#     import       원본에 require( 가 있다 → 비0 · 복사본 0 (self-contained 확인)
#     실워크플로   이 트리 workflows/*.js 전부를 원본으로 → exit 0 · 바이트 일치 (import 가 생기면 그 스킬은 운영에서 매 호출 L4)
#     cp 실패      쓰기 불가 WORK_DIR → 비0 · cmp 로 넘어가 통과하지 않는다 (종료 코드 확인)
#   --cells sites  소비자 9곳(skills 7 · modules 2 — 목록 고정)의 실제 준비 줄마다: scriptPath 가 같은 basename 의
#                  `{WORK_DIR}` 복사본 · 준비 줄이 호출 줄보다 앞 · §12 0단계(경로 판정) 참조 · 준비 명령을 꺼내
#                  없음/stale 로 돌려 exit 0 + 바이트 일치 · 없는 WORK_DIR 에서 비0 → `SITE-OK <파일>` 한 줄
#   --cells all    둘 다 (기본 — 인자 없이 도는 회귀 글롭 경로)
# --variant contract (기본): 블록 · 사이트 준비 줄에 `cmp -s` · 소비자 allowed-tools 에 `Bash(cmp *)` · tool-inventory 에 cmp
# --variant plan: cmp 는 이 fixture 안에서만 쓴다 — 문서에는 cp 와 종료 코드 확인만 요구한다
# 바이트 일치는 문서가 아니라 이 fixture 가 따로 잰다(filecmp) — 블록이 스스로 내린 판정을 믿지 않는다.
# 기준 트리(0단계 · 준비 줄 없음, 플러그인 루트 직접 호출)는 셀이 블록을 못 찾아 exit 1.
# ⛔ 셀 집합 대조(F-408): prep 을 돌렸으면 판정한 셀 이름이 위 8셀(`PREP_CELLS`)과 정확히 같아야 한다 — root 권한으로 cp 실패 셀을
#    만들 수 없으면 그 셀은 `skipped` 로 따로 센다. 끝 줄 `CELLS n=<수> ran=<…> skipped=<…>`(sites 를 돌렸으면 `sites=<OK>/9` 도).
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 임시 폴더 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 이 결함 재현 없이 통과한다 — 그래서 3 이다.
# usage: run.sh [--tree <플러그인 루트>] [--variant contract|plan] [--cells prep|sites|all]
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
VARIANT=contract CELLS=all
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    --variant) [ $# -ge 2 ] || { echo "SETUP --variant 에 값이 없다"; exit 3; }; VARIANT=$2; shift 2 ;;
    --cells) [ $# -ge 2 ] || { echo "SETUP --cells 에 값이 없다"; exit 3; }; CELLS=$2; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
case "$VARIANT" in contract|plan) ;; *) echo "SETUP --variant 는 contract|plan: $VARIANT"; exit 3 ;; esac
case "$CELLS" in prep|sites|all) ;; *) echo "SETUP --cells 는 prep|sites|all: $CELLS"; exit 3 ;; esac
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -f "$R/guides/skill-authoring.md" ] && [ -d "$R/workflows" ] || { echo "SETUP 플러그인 트리가 아니다: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" "$VARIANT" "$CELLS" <<'PY'
import filecmp, json, os, re, shutil, stat, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
TREE, VARIANT, CELLS = sys.argv[1], sys.argv[2], sys.argv[3]
CONTRACT = VARIANT == "contract"
GUIDE = os.path.join(TREE, "guides", "skill-authoring.md")
FAIL = []
PREP_CELLS = ("없음", "stale", "정상", "형제 접두사", "symlink", "import", "실워크플로", "cp 실패")   # 셀 이름 고정(F-408)
RAN, SKIPPED = [], []             # 판정한 prep 셀(첫 단언 순) · root 로 건너뛴 셀
# 소비자 9곳 — (파일, 부르는 워크플로 basename, allowed-tools 를 가진 SKILL). 목록을 고정한다: 사이트가 줄면 SITE-OK 가 9 에 못 미친다
SITES = [
    ("skills/fz-code/SKILL.md", "code-pair.js", "skills/fz-code/SKILL.md"),
    ("skills/fz-discover/SKILL.md", "discover-adversarial.js", "skills/fz-discover/SKILL.md"),
    ("skills/fz-fix/SKILL.md", "code-pair.js", "skills/fz-fix/SKILL.md"),
    ("skills/fz-pr-digest/SKILL.md", "search-cross-verify.js", "skills/fz-pr-digest/SKILL.md"),
    ("skills/fz-review/SKILL.md", "review-live.js", "skills/fz-review/SKILL.md"),
    ("skills/fz-search/SKILL.md", "search-cross-verify.js", "skills/fz-search/SKILL.md"),
    ("skills/fz/SKILL.md", "{skill}-{pattern}.js", "skills/fz/SKILL.md"),
    ("modules/peer-review-workflow.md", "peer-review.js", "skills/fz-peer-review/SKILL.md"),
    ("modules/peer-review-tiers.md", "peer-review.js", "skills/fz-peer-review/SKILL.md"),
]
SAFE_PATH = re.compile(r"[A-Za-z0-9_./-]+")
TMP_ROOT = os.path.realpath(tempfile.mkdtemp(prefix="fz-copy-cmp-"))
if not SAFE_PATH.fullmatch(TMP_ROOT):
    print(f"SETUP 임시 경로에 셸 특수문자가 있다: {TMP_ROOT}")
    sys.exit(3)


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-300:]
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if cell.startswith("CELL ") and cell[5:] not in RAN:
        RAN.append(cell[5:])
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def read(rel):
    with open(os.path.join(TREE, rel), encoding="utf-8") as fh:
        return fh.read()


def run(cmd, cwd):
    p = subprocess.run(["bash", "-c", cmd], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def fresh(name):
    d = os.path.join(TMP_ROOT, name)
    os.makedirs(d)
    return d


def real_workflow():
    """원본 내용 — 이 트리의 실제 워크플로(self-contained 여야 한다)."""
    with open(os.path.join(TREE, "workflows", "code-pair.js"), "rb") as fh:
        return fh.read()


# ── 0단계 블록 추출 ─────────────────────────────────────────────────────────
def prep_block():
    """§12 우회 계약 절 안 '0단계' 표지 뒤 첫 ```bash 블록. 없으면 None."""
    text = read("guides/skill-authoring.md")
    m = re.search(r"^#### ⛔ scriptPath 거부 우회 계약.*$", text, re.M)
    if not m:
        return None, "§12 우회 계약 절이 없다"
    sec = text[m.end():]
    nxt = re.search(r"^#{2,4} ", sec, re.M)
    sec = sec[: nxt.start()] if nxt else sec
    k = sec.find("0단계")
    if k < 0:
        return None, "§12 우회 계약 절에 '0단계' 준비가 없다"
    b = re.search(r"```bash\n(.*?)```", sec[k:], re.S)
    if not b:
        return None, "0단계 뒤에 ```bash 블록이 없다"
    return b.group(1), ""


def fill(block, sess, work, plug, name):
    out = (block.replace("{세션 디렉터리}", sess).replace("{WORK_DIR}", work)
           .replace("{플러그인 루트}", plug).replace("{파일}", name))
    left = re.findall(r"(?<!\$)\{[^{}\s$]+\}", out)   # ${…} 는 셸 확장이다 — placeholder 가 아니다
    return out, left


def plugin_root(tag, body=None, name="wf"):
    p = fresh(tag)
    os.makedirs(os.path.join(p, "workflows"))
    with open(os.path.join(p, "workflows", name + ".js"), "wb") as fh:
        fh.write(real_workflow() if body is None else body)
    return p


def cells_prep():
    block, why = prep_block()
    if not check("prep", block is not None, "§12 0단계 준비 블록이 있다", why):
        return
    if CONTRACT:
        check("prep", "cmp -s" in block, "contract: 블록이 원본 ↔ 복사본 `cmp -s` 를 한다")
    check("prep", re.search(r"(?m)^\s*cp\s", block) is not None or " cp " in block, "블록이 cp 로 덮어쓴다")
    _, left = fill(block, "/s", "/w", "/p", "f")
    if not check("prep", not left, "블록의 placeholder 가 넷({세션 디렉터리}·{WORK_DIR}·{플러그인 루트}·{파일})뿐이다", f"남은 것: {left}"):
        return
    src_of = lambda plug: os.path.join(plug, "workflows", "wf.js")

    def go(cell, sess, work, plug):
        cmd, _ = fill(block, sess, work, plug, "wf")
        return run(cmd, TMP_ROOT)

    # 없음
    sess = fresh("c1/sess"); work = os.path.join(sess, "wd"); os.makedirs(work); plug = plugin_root("c1/plug")
    rc, out = go("없음", sess, work, plug)
    dst = os.path.join(work, "wf.js")
    check("CELL 없음", rc == 0 and os.path.isfile(dst) and filecmp.cmp(src_of(plug), dst, shallow=False),
          f"복사본 없음 → exit 0 · 바이트 일치 (exit {rc})", out)
    # stale
    sess = fresh("c2/sess"); work = os.path.join(sess, "wd"); os.makedirs(work); plug = plugin_root("c2/plug")
    dst = os.path.join(work, "wf.js")
    with open(dst, "wb") as fh:
        fh.write(b"// stale copy\n")
    rc, out = go("stale", sess, work, plug)
    check("CELL stale", rc == 0 and filecmp.cmp(src_of(plug), dst, shallow=False),
          f"stale 복사본 → exit 0 · 덮어써져 바이트 일치 (exit {rc})", out)
    # 정상
    sess = fresh("c3/sess"); work = os.path.join(sess, "wd"); os.makedirs(work); plug = plugin_root("c3/plug")
    dst = os.path.join(work, "wf.js")
    shutil.copyfile(src_of(plug), dst)
    rc, out = go("정상", sess, work, plug)
    check("CELL 정상", rc == 0 and filecmp.cmp(src_of(plug), dst, shallow=False), f"같은 복사본 → exit 0 · 일치 (exit {rc})", out)
    # 형제 접두사 — 문자열 접두사는 같지만 세그먼트 경계 밖
    base = fresh("c4"); sess = os.path.join(base, "work"); sib = os.path.join(base, "work-x")
    os.makedirs(sess); os.makedirs(sib); plug = plugin_root("c4/plug")
    rc, out = go("형제 접두사", sess, sib, plug)
    check("CELL 형제 접두사", rc != 0 and not os.path.exists(os.path.join(sib, "wf.js")),
          f"WORK_DIR=<세션>-x → 비0 · 복사본 0 (exit {rc})", out)
    rc, out = go("형제 접두사 대조", sess, sess, plug)
    check("CELL 형제 접두사", rc == 0 and filecmp.cmp(src_of(plug), os.path.join(sess, "wf.js"), shallow=False),
          f"대조 — WORK_DIR=<세션> 자신 → exit 0 (경계는 '항상 거부' 가 아니다) (exit {rc})", out)
    # symlink — 범위 밖을 가리키는 링크는 실제 경로로 판정한다
    base = fresh("c5"); sess = os.path.join(base, "sess"); outside = os.path.join(base, "outside"); inner = os.path.join(sess, "real")
    os.makedirs(sess); os.makedirs(outside); os.makedirs(inner); plug = plugin_root("c5/plug")
    os.symlink(outside, os.path.join(sess, "link-out")); os.symlink(inner, os.path.join(sess, "link-in"))
    rc, out = go("symlink", sess, os.path.join(sess, "link-out"), plug)
    check("CELL symlink", rc != 0 and not os.path.exists(os.path.join(outside, "wf.js")),
          f"WORK_DIR=<세션>/link → 범위 밖 → 비0 · 밖에 복사본 0 (exit {rc})", out)
    rc, out = go("symlink 대조", sess, os.path.join(sess, "link-in"), plug)
    check("CELL symlink", rc == 0 and filecmp.cmp(src_of(plug), os.path.join(inner, "wf.js"), shallow=False),
          f"대조 — 세션 안을 가리키는 link → exit 0 · 일치 (exit {rc})", out)
    # import — self-contained 아님
    sess = fresh("c6/sess"); work = os.path.join(sess, "wd"); os.makedirs(work)
    plug = plugin_root("c6/plug", body=b"const x = require('./lib')\nexport default 1\n")
    rc, out = go("import", sess, work, plug)
    check("CELL import", rc != 0 and not os.path.exists(os.path.join(work, "wf.js")),
          f"원본에 require( → 비0 · 복사본 0 (exit {rc})", out)
    # 실워크플로 — 이 트리의 workflows/*.js 전부가 0단계를 통과하는가(하나라도 import 가 생기면 운영에서 그 스킬은 매 호출 L4 다)
    sess = fresh("c8/sess"); work = os.path.join(sess, "wd"); os.makedirs(work)
    names = sorted(f[:-3] for f in os.listdir(os.path.join(TREE, "workflows")) if f.endswith(".js"))
    bad = []
    for n in names:
        cmd, _ = fill(block, sess, work, TREE, n)
        rc, out = run(cmd, TMP_ROOT)
        if rc != 0 or not filecmp.cmp(os.path.join(TREE, "workflows", n + ".js"), os.path.join(work, n + ".js"), shallow=False):
            bad.append(f"{n}.js(exit {rc})")
    check("CELL 실워크플로", bool(names) and not bad, f"트리 워크플로 {len(names)}개 전부 0단계 exit 0 · 바이트 일치", " · ".join(bad))
    # cp 실패 — 쓰기 불가 WORK_DIR (종료 코드를 보지 않으면 cmp 단계가 낡은 파일과 비교하거나 호출로 넘어간다)
    sess = fresh("c7/sess"); work = os.path.join(sess, "wd"); os.makedirs(work); plug = plugin_root("c7/plug")
    os.chmod(work, stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(work, os.W_OK):
            print("SKIP  CELL cp 실패: 쓰기 불가 폴더를 만들 수 없다(root?) — 이 셀만 건너뛴다")
            SKIPPED.append("cp 실패")
        else:
            rc, out = go("cp 실패", sess, work, plug)
            check("CELL cp 실패", rc != 0 and not os.path.exists(os.path.join(work, "wf.js")),
                  f"쓰기 불가 WORK_DIR → 비0 (exit {rc})", out)
    finally:
        os.chmod(work, stat.S_IRWXU)


# ── 사이트 ──────────────────────────────────────────────────────────────────
CP_RE = r"cp (\{플러그인 루트\}/workflows/(\S+?\.js)) (\{WORK_DIR\}/\2)"


def allowed_tools(rel):
    text = read(rel)
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    fm = text[4:end] if end > 0 else ""
    m = re.search(r"^allowed-tools:(.*?)(?=^\S)", fm + "\nz:", re.M | re.S)
    return m.group(1) if m else ""


def inventory_has_cmp():
    try:
        with open(os.path.join(TREE, "schemas", "tool-inventory.json"), encoding="utf-8") as fh:
            return "cmp" in (json.load(fh).get("external_commands") or {})
    except (OSError, ValueError):
        return False


def one_site(rel, base, consumer):
    why = []
    try:
        lines = read(rel).split("\n")
    except OSError as e:
        return [f"읽기 실패 {e}"]
    calls = [i for i, l in enumerate(lines) if "Workflow({ scriptPath:" in l and base in l]
    if len(calls) != 1:
        return [f"'{base}' 를 부르는 호출 줄이 {len(calls)}개 (기대 1)"]
    c = calls[0]
    sp = re.search(r"scriptPath:\s*'([^']+)'", lines[c])
    if not sp or sp.group(1) != "{WORK_DIR}/" + base:
        why.append(f"scriptPath 가 준비한 복사본(`{{WORK_DIR}}/{base}`)이 아니다: {sp.group(1) if sp else '없음'}")
    preps = [i for i in range(max(0, c - 6), c) if re.search(CP_RE, lines[i])]
    if not preps:
        return why + ["호출 줄 앞 6줄 안에 준비 줄(cp {플러그인 루트}/workflows/… {WORK_DIR}/…)이 없다"]
    p = preps[-1]
    pl = lines[p]
    arg = r"((?:\{[^{}]*\}|[^\s`{])+)"   # placeholder 는 공백을 품는다({플러그인 루트}) · 인라인 코드의 닫는 백틱은 인자가 아니다
    m = re.search(CP_RE + r"(\s*&&\s*cmp -s " + arg + " " + arg + ")?", pl)
    if m.group(2) != base:
        why.append(f"준비 줄의 basename '{m.group(2)}' ≠ 호출 '{base}'")
    if "0단계" not in pl or "경로 판정" not in pl:
        why.append("준비 줄이 §12 0단계 경로 판정을 가리키지 않는다")
    if "exit 0" not in pl:
        why.append("준비 줄에 종료 코드 확인(exit 0 일 때만)이 없다")
    if CONTRACT:
        if not m.group(4) or m.group(5) != m.group(1) or m.group(6) != m.group(3):
            why.append("contract: 준비 줄이 `cp 원본 복사본 && cmp -s 원본 복사본` 꼴이 아니다")
        if "Bash(cmp *)" not in allowed_tools(consumer):
            why.append(f"contract: {consumer} allowed-tools 에 Bash(cmp *) 가 없다")
        if not inventory_has_cmp():
            why.append("contract: schemas/tool-inventory.json 에 cmp 선언이 없다")
    if "{" not in base and not os.path.isfile(os.path.join(TREE, "workflows", base)):
        why.append(f"workflows/{base} 가 트리에 없다")
    # 실제 실행 — 준비 명령을 꺼내 없음 · stale · 없는 WORK_DIR 로 돌린다
    cmd = m.group(0)
    name = re.sub(r"\{[^{}]*\}", "x", base)
    tag = re.sub(r"[^A-Za-z0-9]", "_", rel)
    plug = fresh(f"site-{tag}/plug"); os.makedirs(os.path.join(plug, "workflows"))
    src = os.path.join(plug, "workflows", name)
    with open(src, "wb") as fh:
        fh.write(real_workflow())
    work = fresh(f"site-{tag}/wd")

    def go(wd):
        c2 = cmd.replace("{플러그인 루트}", plug).replace("{WORK_DIR}", wd).replace(base, name)
        return run(c2, TMP_ROOT)

    dst = os.path.join(work, name)
    rc, out = go(work)
    if rc != 0 or not os.path.isfile(dst) or not filecmp.cmp(src, dst, shallow=False):
        why.append(f"준비 명령 실행(복사본 없음) → exit {rc} · 일치 {os.path.isfile(dst) and filecmp.cmp(src, dst, shallow=False)} · {out.strip()[:120]}")
    with open(dst, "wb") as fh:
        fh.write(b"// stale\n")
    rc, out = go(work)
    if rc != 0 or not filecmp.cmp(src, dst, shallow=False):
        why.append(f"준비 명령 실행(stale) → exit {rc} · 덮어쓰기 안 됨")
    rc, out = go(os.path.join(work, "no-such-dir"))
    if rc == 0:
        why.append("없는 WORK_DIR 에서 준비 명령이 exit 0 — 종료 코드가 실패를 알리지 않는다")
    return why


def cells_sites():
    ok = 0
    for rel, base, consumer in SITES:
        why = one_site(rel, base, consumer)
        if why:
            print(f"SITE-FAIL {rel} — " + " · ".join(why))
            FAIL.append(f"site {rel}")
        else:
            print(f"SITE-OK {rel}")
            ok += 1
    return ok


tail = []
try:
    if CELLS in ("prep", "all"):
        cells_prep()
        got = RAN + SKIPPED
        check("prep cell-set", sorted(got) == sorted(PREP_CELLS) and len(got) == len(set(got)),
              "판정한 prep 셀 이름 = 고정 8셀(없음 · stale · 정상 · 형제 접두사 · symlink · import · 실워크플로 · cp 실패 — root SKIP 은 따로)",
              f"없음={sorted(set(PREP_CELLS) - set(got))} · 뜻밖={sorted(set(got) - set(PREP_CELLS))}")
        tail.append(f"n={len(RAN)} ran={','.join(RAN) or '-'} skipped={','.join(SKIPPED) or '-'}")
    if CELLS in ("sites", "all"):
        tail.append(f"sites={cells_sites()}/{len(SITES)}")
finally:
    for dp, dn, fn in os.walk(TMP_ROOT):
        os.chmod(dp, stat.S_IRWXU)
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
print(f"workflow-prep copy-cmp (variant={VARIANT} · cells={CELLS}): " + ("전건 통과" if not FAIL else f"실패 {len(FAIL)}건"))
print("CELLS " + " ".join(tail))
sys.exit(1 if FAIL else 0)
PY
