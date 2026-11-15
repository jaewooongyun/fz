#!/bin/bash
# gpt-cli: real — 사본에서 health-check 전체를 돈다(§4.5 check-gpt-flags 가 실제 GPT CLI 의 --help 를 부른다)
# health-check 3분 판정 fixture (F-335 ⑬) — 판정 불가를 동작으로 본다.
#
# 트리 사본 한 벌에 판정 지점마다 검사기 하나씩 심고 health-check 전체를 한 번 돌린다.
#   최상위   check_single_source       → `UNRUN:` 표지 + exit 2          ⏸ 미실행
#            check_failure_table       → 표지 없는 exit 2                ⛔ 실패
#            plan_integrity_check      → `UNRUN:` 표지 + traceback + exit 2 ⛔ 실패 (세탁 금지)
#   :도구 루프 check_symptom_anchor --self-test → `UNRUN:` 표지 + exit 2      ⏸ 미실행
#   회귀 러너 fixture 표지 exit 2(⏸) · fixture 표지 없는 exit 2(⛔) · tests/workflows 표지 exit 2(⏸)
#            fixture SETUP 표지 exit 3(⏸ 준비 실패 · F-575) · 표지 없는 exit 3(⛔) · SETUP 표지 + traceback exit 3(⛔)
#   종합     실패와 미실행을 둘 다 보고하고 exit 2(미실행 우선 — 기존 규약)
# 같은 사본에서 부분 실행(--changed docs/zz-planted-f575.md)을 한 번 더 돈다 — 그 문서 경로를 적은 SETUP exit 3 러너만 골라
#   회귀 오라클이 미실행만 남은 경우를 본다. 실패가 섞이면 '전건 통과' 행이 원래 안 생겨 "미실행이 남으면 통과 아님" 이 보이지 않는다.
# 기준 트리(이분 판정)는 같은 plant 에서 표지 있는 exit 2 를 ⛔ 로 적어 이 fixture 가 exit 1 이다.
# exit: 0 전건 통과 · 1 판정 단언 실패(표 구조는 정상) · 3 준비 실패(인자 · 사본 · plant · 표 없음 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 게이트가 오분류 재현 없이 통과한다. 그래서 3 이다 — 바깥 health-check 는
#      SETUP 표지가 붙은 3 을 미실행으로 센다(F-575 · 통과 아님). 단언기 고장은 traceback 이 붙어 실패다.
# ⛔ 사본의 다른 회귀 러너는 지운다 — 판정 지점만 보며, 남기면 health-check 회귀 구간 전체가 한 번 더 돈다.
# ⛔ 중첩 재귀 가드: 사본의 health-check 는 FZ_HEALTH_UNRUN_FIXTURE=1 로 돈다. 그 안에서 이 fixture 가 다시
#    불리면 `UNRUN:` 을 내고 exit 2 로 끝낸다 — 돌지 않았으니 통과가 아니다(러너를 지워도 가드를 둔다 —
#    지우기가 빠지면 사본이 사본을 무한히 부른다. 그때는 미실행 행에 이 fixture 가 섞여 단언이 깨진다).
# ⛔ 사본에서 `.git` 을 뺀다 — 워크트리의 `.git` 파일을 복사하면 사본 안 git 명령이 원 저장소를 가리킨다.
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
if [ -n "${FZ_HEALTH_UNRUN_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 unrun-classification 이 이 사본을 판정하는 중"
  exit 2
fi
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
[ -f "$R/scripts/health-check.sh" ] || { echo "SETUP health-check 없음: $R"; exit 3; }
command -v rsync >/dev/null 2>&1 || { echo "SETUP rsync 부재 — 사본을 만들 수 없다"; exit 3; }
X="$(mktemp -d)"; trap 'rm -rf "$X"' EXIT
C="$X/copy"
rsync -a --exclude .git "$R/" "$C/" || { echo "SETUP 사본 생성 실패"; exit 3; }

python3 - "$C" <<'PY' || { echo "SETUP plant 실패"; exit 3; }
import pathlib, sys
c = pathlib.Path(sys.argv[1])
for p in list(c.glob("tests/fixtures/*/*/run.sh")) + list(c.glob("tests/workflows/*.js")) + list(c.glob("tests/lib/*.test.js")):
    p.unlink()

def stub(rel, body):
    p = c / "scripts" / rel
    assert p.is_file(), rel
    p.write_text("import sys, traceback\n" + body, encoding="utf-8")

stub("check_single_source.py",
     "if '--self-test' in sys.argv:\n    print('self-test planted-stub'); sys.exit(0)\n"
     "print('UNRUN: planted-ss 측정 불가'); sys.exit(2)\n")
stub("check_failure_table.py",
     "if '--self-test' in sys.argv:\n    print('self-test planted-stub'); sys.exit(0)\n"
     "print('planted-ft 표지 없음'); sys.exit(2)\n")
stub("plan_integrity_check.py",
     "print('UNRUN: planted-pi 측정 불가')\n"
     "try:\n    raise RuntimeError('planted-pi')\nexcept RuntimeError:\n    traceback.print_exc()\nsys.exit(2)\n")
stub("check_symptom_anchor.py",
     "print('UNRUN: planted-sa self-test 측정 불가'); sys.exit(2)\n")

def runner(rel, text):
    p = c / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
runner("tests/fixtures/zz-planted/unrun-marked/run.sh", "#!/bin/bash\necho 'UNRUN: planted 러너 측정 불가'\nexit 2\n")
runner("tests/fixtures/zz-planted/unmarked-exit2/run.sh", "#!/bin/bash\necho 'planted 러너 표지 없음'\nexit 2\n")
runner("tests/workflows/zz-planted-unrun.js", "console.log('UNRUN: planted 워크플로 시험 측정 불가')\nprocess.exit(2)\n")
runner("tests/fixtures/zz-planted/setup-exit3/run.sh",
       "#!/bin/bash\n# docs/zz-planted-f575.md — 부분 실행이 이 러너만 고르게 하는 문서 경로(실재하지 않아도 된다)\n"
       "echo 'SETUP planted 준비 실패'\nexit 3\n")
runner("tests/fixtures/zz-planted/unmarked-exit3/run.sh", "#!/bin/bash\necho 'planted 러너 표지 없음'\nexit 3\n")
runner("tests/fixtures/zz-planted/traceback-exit3/run.sh",
       "#!/bin/bash\necho 'SETUP planted'\necho 'Traceback (most recent call last):'\nexit 3\n")
PY

out="$(cd "$X" && FZ_HEALTH_UNRUN_FIXTURE=1 bash "$C/scripts/health-check.sh" 2>&1)"; rc=$?
printf '%s\n' "$out" > "$X/health.out"
out2="$(cd "$X" && FZ_HEALTH_UNRUN_FIXTURE=1 bash "$C/scripts/health-check.sh" --changed docs/zz-planted-f575.md 2>&1)"; rc2=$?
printf '%s\n' "$out2" > "$X/subset.out"

python3 - "$X/health.out" "$rc" "$X/subset.out" "$rc2" <<'PY'
import os, sys, traceback
def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '판정 단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc); sys.stdout.flush(); os._exit(3)
sys.excepthook = _crash
out = open(sys.argv[1], encoding="utf-8").read()
rc = int(sys.argv[2])
lines = out.split("\n")
fail = 0
# ⛔ 표 구조가 없으면 준비 실패(3)다 — 사전조건에서 멈춘 health-check 는 행이 0 이라 모든 단언이 '행 없음' 으로 1 이 된다.
#    두 트리 모두에 있어야 하는 행(표지와 무관하게 이름만)이 하나라도 없으면 3 으로 끝낸다.
ROWS = [l for l in lines if l[:1] in "✅⛔⏸"]
NEED = ["단일 출처 계약", "실패 처방 표 계약", "plan 계약 왕복", "레지스트리 도구 self-test (check_symptom_anchor)", "회귀 오라클"]
missing = [n for n in NEED if not any(l.split(" ", 1)[1].startswith(n + " ") for l in ROWS if " " in l)]
if len(ROWS) < 30 or missing:
    print(f"SETUP 표 구조 이상 — 행 {len(ROWS)}개 · 없는 행 {missing}")
    sys.exit(3)
def check(name, mark, code, has, hasnt=()):
    """표 행 '<표지> <이름> <exit> <비고>' — 이름 뒤 첫 토큰이 exit 다(printf 폭은 바이트라 한글 이름은 패딩이 없을 수 있다)"""
    global fail
    hit = [l for l in lines if l.startswith(f"{mark} {name} ") and l[len(mark) + len(name) + 2:].split()[:1] == [code]]
    ok = len(hit) == 1 and all(h in hit[0] for h in has) and not any(h in hit[0] for h in hasnt)
    seen = [l for l in lines if l[:1] in "✅⛔⏸" and f" {name} " in l]
    print(("PASS  " if ok else "FAIL  ") + f"{mark} {name} {code}" + (f" ← {' · '.join(has)}" if has else "") + ("" if ok else f" · 실제: {seen or '행 없음'}"))
    fail |= not ok
check("단일 출처 계약", "⏸", "UNRUN", ["UNRUN: planted-ss"])
check("실패 처방 표 계약", "⛔", "1", ["UNRUN 표지 없는 exit 2"])
check("plan 계약 왕복", "⛔", "1", ["exit 2 + traceback"], ["미실행"])
check("레지스트리 도구 self-test (check_symptom_anchor)", "⏸", "UNRUN", ["UNRUN: planted-sa"])
check("회귀 오라클", "⛔", "1", ["unmarked-exit2"], ["unrun-marked", "zz-planted-unrun.js"])
check("회귀 오라클 미실행", "⏸", "UNRUN", ["unrun-marked", "zz-planted-unrun.js", "3/6"], ["unmarked-exit2"])
def row(text, name, mark, code):
    hit = [l for l in text.split("\n") if l.startswith(f"{mark} {name} ") and l[len(mark) + len(name) + 2:].split()[:1] == [code]]
    return hit[0] if len(hit) == 1 else ""
def cell(name, ok, got):
    global fail
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f" — 실제: {got}"))
    fail |= not ok
bad, un = row(out, "회귀 오라클", "⛔", "1"), row(out, "회귀 오라클 미실행", "⏸", "UNRUN")
cell("r3-f575-setup-exit3-unrun — SETUP 표지가 있는 러너 exit 3 은 실패가 아니라 미실행", " setup-exit3" in un and " setup-exit3" not in bad, [bad, un])
cell("r3-f575-unmarked-exit3-fail — 표지 없는 exit 3 · traceback 이 붙은 exit 3 은 실패",
     all(f" {n}" in bad and f" {n}" not in un for n in ("unmarked-exit3", "traceback-exit3")), [bad, un])
load = out.split("[회귀 오라클]\n", 1)[1].split("\n", 1)[0] if "[회귀 오라클]\n" in out else ""
cell("f575-load-in-detail — 실패 · 미실행 러너의 실행 시작 · 끝 부하가 상세에 남는다",
     all(f"{n} " in load for n in ("setup-exit3", "unmarked-exit3", "unrun-marked")) and "→" in load, load or "상세 줄 없음")
# 부분 실행 — 문서 경로를 적은 SETUP exit 3 러너 하나만 고른다. 선택이 다르면 이 셀을 잴 수 없다(준비 실패 3)
out2, rc2 = open(sys.argv[3], encoding="utf-8").read(), int(sys.argv[4])
picked = [l.split()[1] for l in out2.split("\n") if l.startswith("HEALTH-SELECT check=tests/")]
if not any(l.startswith("HEALTH-SELECT mode=subset") for l in out2.split("\n")) or picked != ["check=tests/fixtures/zz-planted/setup-exit3/run.sh"]:
    print(f"SETUP 부분 실행이 SETUP exit 3 러너 하나를 고르지 않았다 — {[l for l in out2.splitlines() if l.startswith('HEALTH-SELECT')][:6]}")
    sys.exit(3)
un2 = row(out2, "회귀 오라클 미실행", "⏸", "UNRUN")
cell("r3-f575-unrun-keeps-gate-unmet — 미실행만 남으면 회귀 오라클은 통과 행을 내지 않고 종합도 0 이 아니다",
     "setup-exit3" in un2 and "1/1" in un2 and not any(l.startswith("✅ 회귀 오라클 ") for l in out2.split("\n")) and rc2 != 0,
     [un2, rc2, [l for l in out2.split("\n") if "회귀 오라클" in l]])
for want in ("실행되지 못한 검사", "추가로 실패한 검사도 있다"):
    ok = want in out
    print(("PASS  " if ok else "FAIL  ") + f"종합 보고에 '{want}'")
    fail |= not ok
ok = rc == 2
print(("PASS  " if ok else "FAIL  ") + f"종합 exit {rc} (기대 2 — 실패·미실행이 함께면 미실행 우선)")
fail |= not ok
print()
print("unrun-classification: " + ("전건 통과" if not fail else "실패 있음"))
sys.exit(1 if fail else 0)
PY
a=$?
# ⛔ 단언기 자체의 고장(traceback 등 0 · 1 밖)은 준비 실패로 바꾼다 — python 의 미처리 예외도 1 이라 그대로 두면 오분류 재현처럼 읽힌다
[ "$a" -eq 0 ] || [ "$a" -eq 1 ] || [ "$a" -eq 3 ] || { echo "SETUP 단언기 비정상 종료 $a"; exit 3; }
exit "$a"
