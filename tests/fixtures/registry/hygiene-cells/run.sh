#!/bin/bash
# 위생 검사 손상 셀 fixture (F-373 · SC-3) — check_findings_hygiene.py --strict 가 사각지대 6종을 위반으로 내는지 동작으로 본다.
#
# 정상 대조 레지스트리(실 레지스트리 형식: 대기열 절 · 재번호 이력 절의 백틱 표 · 펜스 안 덤프·행 · 배출 4열 행 ·
# 레거시 날짜 우선 행 · archive)를 임시 폴더에 만들고, 셀마다 사본 하나에 손상 하나를 넣어 --strict 를 돌린다.
#   control         정상 대조 — exit 0 · `OK:`
#   orphan          대기열 행이 가리키는 엔트리가 없다(고아)
#   out-of-queue    live 행이 대기열 절 밖에 있다 · `## 대기열` 제목이 바뀌었다
#   applied-conflict APPLIED 레거시 날짜 우선 번호 행 · 배출 4열 slug 행이 live 와 번호가 겹친다(EC-14)
#   dup-title       두 엔트리의 frontmatter title 이 같다
#   dup-h1-body     H1 이 같다 · 본문이 남의 것(archive 짝)이다
#   index-dump      엔트리·APPLIED 의 펜스 밖에 INDEX 덤프 잔재(`=== ` · `NN:| F-NNN`)
#   unrun           entries 부재 · 빈 분모 · archive 디코딩 실패 · APPLIED 부재 → exit 2 + 줄 맨 앞 `UNRUN:`
#   consumer        실 레지스트리 소비자(SC-3 · G27) — manifest↔APPLIED↔archive 가 맞는 레지스트리에 고아 행만 넣으면
#                   기본 모드(--strict 없이)와 `eject_findings.py --audit ROOT` 가 같은 `VIOLATION:` 줄로 exit 1(대장 대조는 누락 0)
# 손상 셀은 exit 1 + `VIOLATION:` 줄 + 그 축의 보고 줄을 함께 단언한다 — exit 만 보면 검사기가 죽은 것(traceback,
# 기본 exit 1)을 탐지로 읽는다. 기준 트리는 --strict 에 이 축들이 없어 orphan·control 외 셀이 놓친다 → exit 1.
# consumer 는 기준 기본 모드가 고아를 통과시키고 기준 --audit 이 위생 검사를 부르지 않아 놓친다 → exit 1.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 임시 레지스트리 · 검사기 traceback · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 게이트가 기능 부재 재현 없이 통과한다 — 그래서 3 이다.
#      python 의 미처리 예외(기본 exit 1)도 excepthook 으로 3 으로 바꾼다.
#   ⛔ F-343(선존 결함): Python 3.14 argparse 는 add_argument 에서 help 문자열을 검사해, `--strict` help 의 단독 `%`
#      때문에 위생 검사기가 모든 호출에서 traceback 으로 죽는다. 이 fixture 는 그것을 탐지 실패로 세지 않고
#      `SETUP … F-343` 으로 따로 표시해 3 으로 끝낸다. `--help` 상태는 판정 밖 `NOTE F-343` 줄로 찍는다.
# ⛔ 임시 레지스트리만 쓴다 — 실제 레지스트리 경로는 받지 않는다. 트리에 바이트코드를 남기지 않는다.
# usage: run.sh [--tree <플러그인 루트>] [--cells <셀>,…]   (기본: 이 fixture 가 든 트리 · 전체 셀)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
CELLS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    --cells) [ $# -ge 2 ] || { echo "SETUP --cells 에 값이 없다"; exit 3; }
             CELLS="$2"; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -f "$R/scripts/check_findings_hygiene.py" ] || { echo "SETUP check_findings_hygiene.py 없음: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" "$CELLS" <<'PY'
import json, os, pathlib, subprocess, sys, tempfile, time, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

TREE, CELLS_ARG = pathlib.Path(sys.argv[1]), sys.argv[2]
HYG = TREE / "scripts" / "check_findings_hygiene.py"
EJ = TREE / "scripts" / "eject_findings.py"
PY = sys.executable
FAIL, TALLY = [], {}
F343 = ("badly formed help string", "unsupported format character")


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    t = TALLY.setdefault(cell, [0, 0])
    t[0 if ok else 1] += 1
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def _run(argv, what):
    """대상 트리 스크립트 실행 → (rc, stdout+stderr). ⛔ traceback 은 탐지가 아니라 검사기 고장이다 → Setup."""
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON_COLORS="0")      # 색 코드 없이 — traceback 표지를 그대로 읽는다
    try:
        p = subprocess.run([PY, "-B", *[str(a) for a in argv]], capture_output=True,
                           text=True, env=e, stdin=subprocess.DEVNULL, timeout=120)
    except subprocess.TimeoutExpired as x:
        raise Setup(f"{what}가 120s 안에 끝나지 않았다 — {x}")
    out = p.stdout + p.stderr
    if "Traceback (most recent call last)" in out:
        tag = " — F-343 선존 결함(argparse help 의 단독 %) · 기능 판정 불가" if any(s in out for s in F343) else ""
        raise Setup(f"{what}가 traceback 으로 죽었다 rc={p.returncode}{tag} · {out.strip().splitlines()[-1][:200]}")
    return p.returncode, out


def hyg(root, *extra):
    return _run([HYG, *extra, "--root", root], "위생 검사기")


def audit(root):
    """배출 감사 `eject_findings.py --audit ROOT` — 실 레지스트리를 받는 검증 진입점(SC-3 소비자)."""
    if not EJ.is_file():
        raise Setup(f"eject_findings.py 없음: {EJ}")
    return _run([EJ, "--audit", root], "배출 감사")


def strict(root):
    return hyg(root, "--strict")


def has_line(out, prefix):
    return any(line.startswith(prefix) for line in out.splitlines())


# ── 정상 대조 레지스트리 ─────────────────────────────────────────────────────────
LIVE = {
    "F-001-artifact-state-assumed": "존재하는 산출물을 미처리 입력으로 가정",
    "F-002-detector-direction-one-sided": "판별자가 식별 규약을 가정해 오탐",
    "F-003-pattern-grep-syntax-variants": "문법 규칙을 패턴 grep 으로 검사",
    "F-004-shared-arg-array-divergent": "공용 인자 배열을 갈라진 하위 명령이 거부",
    "F-005-counter-idiom-double-output": "카운터 관용구가 0매치에서 두 줄",
    "F-006-subagent-cwd-write-leak": "외부 도구가 워크트리에 산출물을 남김",
}
ARCHIVED = {"F-090-archived-release-closed": "릴리즈가 닫아 배출된 엔트리"}


def body(slug):
    """엔트리마다 고유한 본문 — 4-gram 40 개를 넘고 서로 겹치지 않는다."""
    n = slug[2:5]
    lines = [f"- 관측 {k}: 사례{n}번 단서{n}가{k} 근거{n}나{k} 판정{n}다{k}" for k in range(24)]
    return "## 관측\n\n" + "\n".join(lines) + "\n"


def entry(slug, title, h1=None, text=None):
    num = slug[:5]
    return (f"---\nid: {num}\ntitle: {title}\ndate: 2026-10-01\nclass: hole\nfailure_class: {slug[6:]}\n"
            f"status: open\ndetector: self\n---\n\n# {num} — {h1 or title}\n\n{text if text is not None else body(slug)}")


def row(slug, one):
    num = slug[:5]
    return f"| {num} | 2026-10-01 | `hole` | {slug[6:]} | {one} | self | open | [{num}](entries/{slug}.md) |\n"


INDEX_HEAD = ("# INDEX — 시험 레지스트리 (미반영 대기열)\n\n> 반영·기각되면 행을 지우고 APPLIED.md 로 옮긴다.\n\n## 대기열\n\n"
              "| ID | 날짜 | class | failure_class | 한 줄 | 탐지자 | status | 문서 |\n"
              "|----|------|:-----:|---------------|-------|:------:|:------:|------|\n")
INDEX_TAIL = ("\n## 재번호 이력 (2026-09-21, A4)\n\n옛 번호는 아래 표로 판별한다.\n\n| 옛 번호 | 유지 | 이동 |\n|---|---|---|\n"
              "| `F-032` | F-032-registry-number | `F-273` ← F-032-rule-scope |\n\n---\n## 다음 ID\n\n쓰기 직전에 잰다.\n\n"
              "```bash\n# 최대 번호 + 1\n| F-001 | 펜스 안 표 행은 등재가 아니다 |\n=== 펜스 안 덤프 표지 ===\n```\n\n---\n\n"
              "## failure_class 목록\n\n| failure_class | 대기 엔트리 |\n|---|---|\n| `artifact-state-assumed` | F-001 |\n")
APPLIED_TEXT = ("# APPLIED — 반영·기각으로 레지스트리를 떠난 항목\n\n> F-001 이 지적한 홀 같은 산문 언급은 배출 기록이 아니다.\n\n## 대장\n\n"
                "| 날짜 | ID | failure_class | 한 줄 | 처리 | 반영처 |\n|------|----|---------------|-------|:----:|--------|\n"
                "| 2026-08-24 | F-080 | `legacy-date-first` | 레거시 날짜 우선 행 | `applied` | `x.md` §1, v4.24.0 |\n\n"
                "### 처리 값\n\n| 값 | 의미 |\n|---|---|\n| `applied` | 반영 |\n\n"
                "| v9.9.8 | F-090-archived-release-closed | `v9.9.8.md` | 릴리즈 `Closes:` 로 배출 |\n")


def build(base):
    root = base / "reg"
    (root / "entries").mkdir(parents=True)
    (root / ".archive").mkdir()
    for s, one in LIVE.items():
        (root / "entries" / f"{s}.md").write_text(entry(s, one), encoding="utf-8")
    first = next(iter(LIVE))
    # 펜스 안 덤프 잔재는 위반이 아니다 — 정상 대조가 통과시켜야 한다
    (root / "entries" / f"{first}.md").write_text(
        entry(first, LIVE[first], text=body(first) + "\n```\n=== INDEX 구조 ===\n12:| F-003 | 2026-08-12 | 펜스 안 |\n```\n"),
        encoding="utf-8")
    for s, one in ARCHIVED.items():
        (root / ".archive" / f"{s}.md").write_text(entry(s, one), encoding="utf-8")
    (root / "INDEX.md").write_text(INDEX_HEAD + "".join(row(s, one) for s, one in LIVE.items()) + INDEX_TAIL, encoding="utf-8")
    (root / "APPLIED.md").write_text(APPLIED_TEXT, encoding="utf-8")
    return root


def edit(p, old, new):
    t = p.read_text(encoding="utf-8")
    if t.count(old) != 1:
        raise Setup(f"편집 대상이 정확히 1회가 아니다 ({t.count(old)}회) — {p.name}: {old[:60]!r}")
    p.write_text(t.replace(old, new), encoding="utf-8")


def slug_of(num):
    return next(s for s in LIVE if s.startswith(num))


def expect_violation(cell, out, rc, axis_text, what):
    check(cell, rc == 1, f"{what}: exit 1 (실제 {rc})", out)
    check(cell, has_line(out, "VIOLATION:"), f"{what}: 줄 맨 앞 `VIOLATION:`", out)
    check(cell, axis_text in out, f"{what}: 축 보고 `{axis_text}`", out)


# ── 셀 ─────────────────────────────────────────────────────────────────────────
def c_control(b):
    rc, out = strict(build(b))
    check("control", rc == 0, f"정상 대조 --strict exit 0 (실제 {rc})", out)
    check("control", has_line(out, "OK: 불변식 충족"), "정상 대조 `OK:` — 펜스 안 덤프·행 · 백틱 표 · 산문 언급 · 배출 4열·레거시 행을 오탐하지 않는다", out)


def c_orphan(b):
    root = build(b)
    edit(root / "INDEX.md", row(slug_of("F-006"), LIVE[slug_of("F-006")]),
         row(slug_of("F-006"), LIVE[slug_of("F-006")]) + row("F-777-entry-file-gone", "엔트리가 사라진 행"))
    rc, out = strict(root)
    expect_violation("orphan", out, rc, "INDEX 고아 행(live 엔트리 없음)      : 1", "대기열의 고아 행")
    check("orphan", "      F-777" in out, "고아 ID F-777 를 이름으로 보고", out)


def c_out_of_queue(b):
    s4 = slug_of("F-004")
    root = build(b / "a")
    edit(root / "INDEX.md", row(s4, LIVE[s4]), "")
    edit(root / "INDEX.md", "| `F-032` | F-032-registry-number | `F-273` ← F-032-rule-scope |\n",
         "| `F-032` | F-032-registry-number | `F-273` ← F-032-rule-scope |\n\n" + row(s4, LIVE[s4]))
    rc, out = strict(root)
    expect_violation("out-of-queue", out, rc, "[--strict] INDEX 대기열 밖 행(## 대기열 절 밖 표 행): 1", "재번호 이력 절 아래로 옮긴 live 행")
    check("out-of-queue", "F-004 (INDEX.md:" in out, "대기열 밖 행을 ID·줄 번호로 보고", out)
    check("out-of-queue", "INDEX 미등재 엔트리                 : 1\n      F-004" in out,
          "등재는 대기열 절 행만 — 절 밖에만 행이 있는 live 엔트리는 미등재다", out)
    root = build(b / "b")
    edit(root / "INDEX.md", "## 대기열\n", "## 아무거나\n")
    rc, out = strict(root)
    expect_violation("out-of-queue", out, rc, f"[--strict] INDEX 대기열 밖 행(## 대기열 절 밖 표 행): {len(LIVE)}",
                     "`## 대기열` 제목이 바뀐 INDEX(M1 exp-b1)")


def c_applied_conflict(b):
    root = build(b / "legacy")
    edit(root / "APPLIED.md", "| 2026-08-24 | F-080 |", "| 2026-08-24 | F-002 |")
    rc, out = strict(root)
    expect_violation("applied-conflict", out, rc, "F-002: APPLIED 번호 행(레거시)", "레거시 날짜 우선 번호 행 ∩ live 번호")
    s5 = slug_of("F-005")
    root = build(b / "eject4")
    edit(root / "APPLIED.md", "| v9.9.8 | F-090-archived-release-closed |", f"| v9.9.8 | {s5} |")
    rc, out = strict(root)
    expect_violation("applied-conflict", out, rc, f"F-005: APPLIED slug 행 {s5}", "배출 4열 slug 행이 아직 live")


def c_dup_title(b):
    s1, s6 = slug_of("F-001"), slug_of("F-006")
    root = build(b)
    edit(root / "entries" / f"{s6}.md", f"title: {LIVE[s6]}\n", f"title: {LIVE[s1]}\n")
    rc, out = strict(root)
    expect_violation("dup-title", out, rc, "[--strict] title 중복(frontmatter): 1", "두 엔트리의 같은 title")
    check("dup-title", f"entries/{s1} ⇄ entries/{s6}" in out, "중복 쌍을 경로로 보고", out)


def c_dup_h1_body(b):
    s3, s6 = slug_of("F-003"), slug_of("F-006")
    root = build(b / "h1")
    edit(root / "entries" / f"{s6}.md", f"# F-006 — {LIVE[s6]}\n", f"# F-006 · {LIVE[s3]}\n")
    rc, out = strict(root)
    expect_violation("dup-h1-body", out, rc, "[--strict] H1 중복(번호 접두 제거): 1", "번호 접두만 다른 같은 H1")
    arc = next(iter(ARCHIVED))
    root = build(b / "body")
    (root / "entries" / f"{s6}.md").write_text(entry(s6, LIVE[s6], text=body(arc)), encoding="utf-8")
    rc, out = strict(root)
    expect_violation("dup-h1-body", out, rc, "본문 근접 중복(4-gram 포함도 ≥0.8): 1", "본문이 archive 짝의 것(제목·H1 은 다름)")
    check("dup-h1-body", f".archive/{arc} ⇄ entries/{s6}" in out, "archive 짝까지 포함해 쌍을 보고", out)


def c_index_dump(b):
    s2 = slug_of("F-002")
    root = build(b / "entry")
    p = root / "entries" / f"{s2}.md"
    p.write_text(p.read_text(encoding="utf-8") + "=== INDEX 구조 ===\n46:| F-003 | 2026-08-12 | `hole` | 잔재 |\n", encoding="utf-8")
    rc, out = strict(root)
    expect_violation("index-dump", out, rc, "펜스 밖 INDEX 덤프(^=== · ^NN:| F-NNN): 1", "엔트리 본문 끝의 펜스 밖 덤프(F-022 형)")
    check("index-dump", f"entries/{s2}: 2줄" in out, "덤프 파일·줄 수를 보고", out)
    root = build(b / "applied")
    edit(root / "APPLIED.md", "### 처리 값\n", "=== INDEX lines 1-8 ===\n# INDEX — 덤프\n\n### 처리 값\n")
    rc, out = strict(root)
    expect_violation("index-dump", out, rc, "APPLIED.md: 1줄", "APPLIED 대장 안의 펜스 밖 덤프(APPLIED:47-74 형)")


def c_unrun(b):
    gone = b / "absent"
    gone.mkdir()
    rc, out = strict(gone)
    check("unrun", rc == 2 and has_line(out, "UNRUN:"), f"entries 부재 → exit 2 + 줄 맨 앞 `UNRUN:` (실제 {rc})", out)
    root = build(b / "empty")
    for q in (root / "entries").iterdir():
        q.unlink()
    rc, out = strict(root)
    check("unrun", rc == 2 and has_line(out, "UNRUN:"), f"빈 분모(entries 0건) → exit 2 + `UNRUN:` (실제 {rc})", out)
    root = build(b / "decode")
    (root / ".archive" / f"{next(iter(ARCHIVED))}.md").write_bytes(b"---\nstatus: open\n---\n\xff\xfe")
    rc, out = strict(root)
    check("unrun", rc == 2 and has_line(out, "UNRUN:"), f"--strict 가 읽는 archive 본문 디코딩 실패 → exit 2 + `UNRUN:` (실제 {rc})", out)
    root = build(b / "no-applied")
    (root / "APPLIED.md").unlink()
    rc, out = strict(root)
    check("unrun", rc == 2 and has_line(out, "UNRUN:") and "APPLIED.md 가 없다" in out,
          f"APPLIED 부재(위반 0) → exit 2 + `UNRUN:` — 충돌 0 으로 읽지 않는다 (실제 {rc})", out)


def c_consumer(b):
    """SC-3 소비자: `--audit ROOT` 가 같은 ROOT 에 위생 검사 기본 모드를 부르는가 — 위반은 위생 검사만 보는 고아 행 하나."""
    root = build(b)
    arc = next(iter(ARCHIVED))
    (root / ".eject-manifest.json").write_text(
        json.dumps([{"version": "9.9.8", "note": "v9.9.8.md", "planned": [arc], "state": "done", "ejected": [arc]}],
                   ensure_ascii=False), encoding="utf-8")
    ledger_ok = "APPLIED 누락 0 · archive 누락 0"
    # 주입 전 — 대장 대조와 위생 검사가 모두 깨끗해야 뒤의 비0 을 고아 행 탓으로 가를 수 있다
    rc, out = hyg(root)
    check("consumer", rc == 0 and has_line(out, "OK: 불변식 충족"), f"주입 전: 기본 위생 검사 exit 0 · `OK:` (실제 {rc})", out)
    rc, out = audit(root)
    check("consumer", rc == 0 and ledger_ok in out, f"주입 전: --audit exit 0 · 대장 대조 `{ledger_ok}` (실제 {rc})", out)
    # 고아 행만 주입 — 배출분이 아니라서 대장 대조(`INDEX 잔존`)는 보지 않고 위생 검사만 본다
    s6 = slug_of("F-006")
    edit(root / "INDEX.md", row(s6, LIVE[s6]), row(s6, LIVE[s6]) + row("F-777-entry-file-gone", "엔트리가 사라진 행"))
    axis = "INDEX 고아 행(live 엔트리 없음)      : 1"
    rc_h, out_h = hyg(root)
    vio = [line for line in out_h.splitlines() if line.startswith("VIOLATION:")]
    check("consumer", rc_h == 1 and len(vio) == 1 and axis in out_h and "      F-777" in out_h,
          f"기본 위생 검사(--strict 없이)가 고아 행으로 exit 1 · `VIOLATION:` 1줄 · 축 `{axis}` · F-777 (실제 {rc_h})", out_h)
    rc_a, out_a = audit(root)
    check("consumer", rc_a == 1, f"--audit exit 1 (실제 {rc_a})", out_a)
    check("consumer", ledger_ok in out_a and "미완료" not in out_a and "INDEX 잔존 0" in out_a,
          "--audit 의 비0 은 대장 대조 탓이 아니다(누락 0 · pending 0 · 배출분 잔존 0)", out_a)
    check("consumer", len(vio) == 1 and vio[0] in out_a.splitlines() and axis in out_a and "      F-777" in out_a,
          "--audit 이 기본 위생 검사와 같은 위반 태그(`VIOLATION:` 줄 그대로 · 고아 축 · F-777)를 낸다", out_a)
    # exit 합치기(위반 우선) — 새 소비자의 판정 규칙. INDEX 를 지우면 위생 검사가 미판정(UNRUN)이다
    (root / "INDEX.md").unlink()
    rc_u, out_u = audit(root)
    check("consumer", rc_u == 2 and has_line(out_u, "UNRUN:") and "→ exit 2" in out_u,
          f"INDEX 를 지운 사본: --audit exit 2 · 줄 맨 앞 `UNRUN:` · `AUDIT: … → exit 2` (실제 {rc_u})", out_u)
    # 같은 사본에 위생 핵심 위반(같은 번호 엔트리 = 중복 ID)을 더하면 미판정보다 위반이 이긴다
    (root / "entries" / "F-006-dup-copy.md").write_bytes((root / "entries" / f"{s6}.md").read_bytes())
    rc_v, out_v = audit(root)
    check("consumer", rc_v == 1 and "→ exit 1" in out_v,
          f"INDEX 부재 + 중복 ID: --audit exit 1(위반 우선) · `AUDIT: … → exit 1` (실제 {rc_v})", out_v)


CELLS = {"control": c_control, "orphan": c_orphan, "out-of-queue": c_out_of_queue, "applied-conflict": c_applied_conflict,
         "dup-title": c_dup_title, "dup-h1-body": c_dup_h1_body, "index-dump": c_index_dump, "unrun": c_unrun,
         "consumer": c_consumer}
picked = []
for tok in [t for t in CELLS_ARG.replace(" ", ",").split(",") if t] or list(CELLS):
    if tok not in CELLS:
        print(f"SETUP 알 수 없는 셀: {tok} (셀: {', '.join(CELLS)})")
        sys.exit(3)
    if tok not in picked:
        picked.append(tok)

# F-343 — 판정 밖 표시. 실패로도 통과로도 세지 않는다.
hp = subprocess.run([PY, "-B", str(HYG), "--help"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON_COLORS="0"))
crash = "Traceback (most recent call last)" in hp.stdout + hp.stderr
print(f"NOTE F-343(선존 결함 · 이 fixture 판정 밖): --help exit {hp.returncode}"
      + (" · traceback(argparse help 의 단독 %)" if crash else " · 정상") + f" · python {sys.version.split()[0]}")

t0 = time.monotonic()
for name in picked:
    with tempfile.TemporaryDirectory(prefix=f"hygiene-cells-{name}-") as d:
        try:
            CELLS[name](pathlib.Path(d))
        except Setup as e:
            print(f"SETUP {name}: {e}")
            sys.exit(3)
print()
for name in picked:
    ok, bad = TALLY.get(name, [0, 0])
    print(f"CELL {name}: {'PASS' if not bad else 'FAIL'} ({ok}/{ok + bad})")
print(f"hygiene-cells: {'전건 통과' if not FAIL else f'실패 {len(FAIL)}건'} — 셀 {len(picked)}개 · {time.monotonic() - t0:.1f}s · tree {TREE.name}")
sys.exit(1 if FAIL else 0)
PY
a=$?
# ⛔ 단언기 자체의 고장(0 · 1 · 3 밖)은 준비 실패로 바꾼다 — 그대로 두면 기능 부재 재현처럼 읽힌다
[ "$a" -eq 0 ] || [ "$a" -eq 1 ] || [ "$a" -eq 3 ] || { echo "SETUP 단언기 비정상 종료 $a"; exit 3; }
exit "$a"
