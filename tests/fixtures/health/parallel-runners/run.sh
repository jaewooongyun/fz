#!/bin/bash
# gpt-cli: real — 사본에서 health-check 전체를 돈다(§4.5 check-gpt-flags 가 실제 GPT CLI 의 --help 를 부른다)
# 회귀 러너 병렬 실행 fixture — health-check `chk_runners` 가 병렬(FZ_HEALTH_JOBS)로 돌아도 직렬과 판정이 같은가를 동작으로 본다.
#
# 트리 사본 한 벌에서 기존 러너를 모두 지우고 합성 러너만 심어 health-check 를 세 번 돌린다.
#   jobs=1 · jobs=4      "회귀 오라클" 행(실패 목록 · 미실행 목록 · 통과 수)과 최종 exit 이 같다
#   결과 누락           scripts/run_runners.py 를 첫 결과만 빼먹는 가짜로 바꾼 사본 — 빠진 러너가 미실행(UNRUN)으로 보고된다(통과 아님)
# 합성 러너: pass(exit 0) · fail(exit 1) · unrun(`UNRUN:` 표지 + exit 2) · crash(kill -9 — 비정상 종료는 실패)
# exit: 0 전건 통과 · 1 단언 실패 · 2 실행 불가(`UNRUN:` 표지) — ⛔ 준비 실패를 1 로 내지 않는다
# ⛔ 중첩 가드: 사본의 health-check 는 FZ_HEALTH_PARALLEL_FIXTURE=1 로 돈다 — 그 안에서 다시 불리면 UNRUN 으로 끝낸다.
#    사본에서는 이 러너를 포함한 기존 러너를 모두 지우므로 정상 경로에서는 불리지 않는다
set -u
if [ -n "${FZ_HEALTH_PARALLEL_FIXTURE:-}" ] || [ -n "${FZ_HEALTH_UNRUN_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 fixture 가 이 사본을 판정하는 중"; exit 2
fi
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
command -v rsync >/dev/null 2>&1 || { echo "UNRUN: rsync 부재 — 사본을 만들 수 없다"; exit 2; }
X="$(mktemp -d)"; trap 'rm -rf "$X"' EXIT
C="$X/copy"
rsync -a --exclude .git "$R/" "$C/" || { echo "UNRUN: 사본 생성 실패"; exit 2; }
python3 - "$C" <<'PY' || { echo "UNRUN: plant 실패"; exit 2; }
import pathlib, sys
c = pathlib.Path(sys.argv[1])
for p in list(c.glob("tests/fixtures/*/*/run.sh")) + list(c.glob("tests/workflows/*.js")) + list(c.glob("tests/lib/*.test.js")):
    p.unlink()
body = {"a-pass": "echo ok; exit 0", "b-fail": "echo 'planted 실패'; exit 1",
        "c-unrun": "echo 'UNRUN: planted 측정 불가'; exit 2", "d-crash": "kill -9 $$"}
for k, b in body.items():
    p = c / "tests/fixtures/zz-par" / k / "run.sh"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/bash\n" + b + "\n", encoding="utf-8")
PY
row() { grep -E '^(✅|⛔|⏸) 회귀 오라클' "$1" | sed -E 's/[[:space:]]+/ /g'; }
for j in 1 4; do
  (cd "$X" && FZ_HEALTH_PARALLEL_FIXTURE=1 FZ_HEALTH_JOBS=$j bash "$C/scripts/health-check.sh" > "$X/j$j.out" 2>&1); echo $? > "$X/j$j.rc"
done
# 결과 누락 사본 — 첫 러너(정렬상 a-pass)의 결과 파일만 쓰지 않는 가짜 실행기
python3 - "$C/scripts/run_runners.py" <<'PY' || { echo "UNRUN: 가짜 실행기 준비 실패"; exit 2; }
import sys, re
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
s = s.replace("def run_one(i: int, runner: str, cwd: str, out_dir: str) -> None:\n", "def run_one(i: int, runner: str, cwd: str, out_dir: str) -> None:\n    if i == 0:\n        return\n", 1)
assert "if i == 0:" in s
open(p, "w", encoding="utf-8").write(s)
PY
(cd "$X" && FZ_HEALTH_PARALLEL_FIXTURE=1 FZ_HEALTH_JOBS=4 bash "$C/scripts/health-check.sh" > "$X/drop.out" 2>&1); echo $? > "$X/drop.rc"
fail=0
chk() { if [ "$2" = "1" ]; then echo "PASS  $1"; else echo "FAIL  $1 — $3"; fail=1; fi; }
r1="$(row "$X/j1.out")"; r4="$(row "$X/j4.out")"
[ -n "$r1" ] || { echo "UNRUN: 직렬 실행에 회귀 오라클 행이 없다 — 표 구조 이상"; exit 2; }
chk "jobs=1 과 jobs=4 의 회귀 오라클 행이 같다" "$([ "$r1" = "$r4" ] && echo 1)" "$(printf '%s ⟂ %s' "$r1" "$r4")"
chk "최종 exit 이 같다" "$([ "$(cat "$X/j1.rc")" = "$(cat "$X/j4.rc")" ] && echo 1)" "$(cat "$X/j1.rc") ⟂ $(cat "$X/j4.rc")"
chk "실패 목록에 fail · crash, 통과 목록 밖" "$(printf '%s\n' "$r4" | grep -q 'b-fail' && printf '%s\n' "$r4" | grep -q 'd-crash' && echo 1)" "$r4"
chk "미실행 목록에 unrun" "$(printf '%s\n' "$r4" | grep -q 'c-unrun' && echo 1)" "$r4"
chk "결과 누락 러너는 미실행으로 보고된다(통과 아님)" "$(row "$X/drop.out" | grep -E '미실행' | grep -q 'a-pass' && echo 1)" "$(row "$X/drop.out")"
[ $fail -eq 0 ] && echo "병렬 러너 fixture 전건 통과" && exit 0
exit 1
