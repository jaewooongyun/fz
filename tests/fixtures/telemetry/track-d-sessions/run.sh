#!/bin/bash
# 트랙 D 후보 보고 fixture (F-454 · F-071 부분) — fz_telemetry_report.py §4 가 같은 failure_class 묶음의
# 서로 다른 관측일을 세고, recurs_of · 본문 '재발' 언급은 묶지 않는지 동작으로 본다.
#
# 합성 레지스트리(entries + .archive)를 임시 폴더에 만들고 리포트를 렌더한다(셀 대부분은 한 레지스트리 · archive 실패 셀만 따로 · 기간 고정 · 빈 projects-root ·
# 임시 --out · --telemetry-dir · 없는 --plugin-root). 셀마다 렌더 결과의 한 축을 단언한다.
#   two-session-class                  archive F-001(10-01) · live F-002 · F-003(10-02) → 관측일 2 · 구성원 셋
#   same-day-one-session               live 둘이 같은 날 → 나열 안 됨
#   cross-midnight-no-session-claim    10-01 · 10-02 → '관측일 2' 로 나열 · '세션 충족' · '세션 N' 주장 없음
#   phrase-not-linked                  본문 `F-001 재발 …` 만 있고 클래스 다름 → 묶음 밖 · `미계수 1`
#   recurs-different-class-not-counted recurs_of: F-001 · 클래스 다름 → '관련' 줄에만 · F-001 묶음은 관측일 2 그대로
#   archived-only-hidden               구성원 전부 archive → 나열 안 됨
#   ledger-rule-line                   modules/promotion-ledger.md 에 인용 규칙 줄
#   archive-unreadable-flagged         .archive 열거 실패(권한 0) → '일부 미측정' 줄(빈 결과로 보이지 않는다)
#   archive-file-unreadable-flagged    archive 파일 하나 읽기 실패(권한 0) → 같은 줄에 그 파일 이름
# '나열 안 됨' 셀은 섹션 머리와 two-session 줄이 함께 있어야 PASS 다 — 기능이 없어 아무것도 안 찍힌 것을 통과로 읽지 않는다.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 리포트 traceback · 단언기 고장)
# ⛔ 실제 레지스트리 · 텔레메트리 경로는 받지 않는다. 트리에 바이트코드를 남기지 않는다.
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
[ -f "$R/scripts/fz_telemetry_report.py" ] || { echo "SETUP fz_telemetry_report.py 없음: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" <<'PY'
import os, pathlib, re, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
TREE = pathlib.Path(sys.argv[1])
FAIL = []


def check(cell, ok, what):
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}")
    if not ok:
        FAIL.append(cell)


ENTRIES = {   # (폴더, ID, date, failure_class, 추가 frontmatter, 본문)
    ("entries", "F-002", "2026-10-02", "two-session", "", ""),
    ("entries", "F-003", "2026-10-02", "two-session", "", ""),
    (".archive", "F-001", "2026-10-01", "two-session", "", ""),
    ("entries", "F-040", "2026-10-04", "same-day", "", ""),
    ("entries", "F-041", "2026-10-04", "same-day", "", ""),
    ("entries", "F-050", "2026-10-01", "cross-midnight", "", ""),
    ("entries", "F-051", "2026-10-02", "cross-midnight", "", ""),
    ("entries", "F-010", "2026-10-06", "phrase-other", "", "- F-001 재발 기록의 처방과 같다\n"),
    ("entries", "F-020", "2026-10-05", "recurs-other", "recurs_of: F-001\n", ""),
    (".archive", "F-030", "2026-10-01", "archived-only", "", ""),
    (".archive", "F-031", "2026-10-03", "archived-only", "", ""),
}

def render(entries, lock=None):
    """합성 레지스트리 → 리포트 본문. lock(레지스트리 상대 경로 — 폴더 · 파일)은 렌더 동안 권한 0 으로 둔다(읽기 실패)."""
    with tempfile.TemporaryDirectory() as tmp:
        reg = pathlib.Path(tmp) / "reg"
        for folder, fid, day, cls, extra, body in entries:
            (reg / folder).mkdir(parents=True, exist_ok=True)
            (reg / folder / f"{fid}-x.md").write_text(
                f"---\nid: {fid}\ntitle: {fid} 합성\ndate: {day}\nfailure_class: {cls}\nstatus: open\naxis: tool\n{extra}---\n\n# {fid}\n\n{body}",
                encoding="utf-8")
        for d in ("projects", "telemetry"):
            (pathlib.Path(tmp) / d).mkdir()
        out_md = pathlib.Path(tmp) / "report.md"
        target = reg / lock if lock else None
        mode = target.stat().st_mode if target else None
        if target:
            target.chmod(0)
        try:
            p = subprocess.run([sys.executable, "-B", str(TREE / "scripts" / "fz_telemetry_report.py"),
                                "--since", "2026-09-01", "--until", "2026-10-31", "--out", str(out_md),
                                "--projects-root", f"{tmp}/projects", "--findings-dir", str(reg / "entries"),
                                "--plugin-root", f"{tmp}/no-plugin", "--telemetry-dir", f"{tmp}/telemetry"],
                               capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", FZ_RUN_STATE=f"{tmp}/no-runs"),
                               stdin=subprocess.DEVNULL, timeout=120)
        finally:
            if target:
                target.chmod(mode)
        if p.returncode != 0 or "Traceback (most recent call last)" in p.stdout + p.stderr or not out_md.is_file():
            print(f"SETUP 리포트 렌더 실패 rc={p.returncode} · {(p.stdout + p.stderr).strip()[-300:]}")
            sys.exit(3)
        return out_md.read_text(encoding="utf-8")


text = render(ENTRIES)
lines = text.splitlines()


def cand(cls):
    return next((ln for ln in lines if ln.startswith(f"- `{cls}` — 트랙 D 후보(")), None)


two = cand("two-session")
alive = "### 트랙 D 후보" in text and two is not None     # 부재 단언의 양성 대조


def hidden(cell, cls):
    check(cell, alive and cand(cls) is None, f"`{cls}` 묶음이 나열되지 않는다(섹션 · two-session 줄은 있다)")


check("two-session-class", two is not None and "관측일 2 " in two
      and all(s in two for s in ("F-001 2026-10-01(archive)", "F-002 2026-10-02", "F-003 2026-10-02")),
      f"클래스 · 관측일 2 · 구성원 셋의 ID · 날짜 — {two!r}")
hidden("same-day-one-session", "same-day")
cm = cand("cross-midnight")
check("cross-midnight-no-session-claim", cm is not None and "관측일 2 " in cm and "별개 세션 미확인" in cm
      and "세션 충족" not in text and not re.search(r"세션 \d", text),
      f"관측일 2 로 나열 · 세션 충족 · 세션 N 주장 없음 — {cm!r}")
check("phrase-not-linked", alive and "F-010" not in two and cand("phrase-other") is None
      and "본문 '재발' 언급 미계수 1 " in text, "본문 언급은 묶음 밖 · 미계수 1")
rel = next((ln for ln in lines if ln.startswith("관련(`recurs_of`")), "")
check("recurs-different-class-not-counted", alive and "F-020 → F-001" in rel and "F-020" not in two
      and "관측일 2 " in two and cand("recurs-other") is None,
      f"관련 줄에만 · F-001 묶음 관측일 2 그대로 — {rel!r}")
hidden("archived-only-hidden", "archived-only")
ledger = (TREE / "modules" / "promotion-ledger.md").read_text(encoding="utf-8")
check("ledger-rule-line", any("관측일 수는 세션 수가 아니다" in ln and "failure_class" in ln and "인용" in ln
                              for ln in ledger.splitlines()), "promotion-ledger.md 트랙 D 인용 규칙 줄")

# archive 를 열거하지 못하면 live 1 + archive 1 묶음이 사라진다 — 빈 결과가 아니라 '일부 미측정' 으로 드러나야 한다(GPT check 후속 P2)
if os.geteuid() == 0:
    print("SETUP root 는 권한 0 폴더도 읽는다 — archive-unreadable-flagged 를 판정할 수 없다")
    sys.exit(3)
locked = render({("entries", "F-060", "2026-10-01", "split", "", ""), (".archive", "F-061", "2026-10-02", "split", "", "")},
                lock=".archive")
check("archive-unreadable-flagged", "### 트랙 D 후보" in locked and "일부 미측정" in locked and ".archive 열거" in locked,
      "archive 열거 실패는 '일부 미측정' 줄로 드러난다")
# 열거는 되는데 파일 하나를 못 읽으면 frontmatter 없음과 섞여 조용히 빠졌다(GPT check 후속 2 P2)
locked = render({("entries", "F-062", "2026-10-01", "split", "", ""), (".archive", "F-063", "2026-10-02", "split", "", "")},
                lock=".archive/F-063-x.md")
check("archive-file-unreadable-flagged", "### 트랙 D 후보" in locked and "일부 미측정" in locked and "F-063-x.md" in locked,
      "archive 파일 읽기 실패도 '일부 미측정' 줄에 그 파일 이름으로 드러난다")

print(f"{'OK' if not FAIL else 'FAIL'}: {9 - len(set(FAIL))}/9")
sys.exit(1 if FAIL else 0)
PY
