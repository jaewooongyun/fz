#!/usr/bin/env python3
# lint:no-root-anchor — 러너 경로와 작업 폴더를 인수로 받는다(플러그인 루트를 해석하지 않는다)
"""run_runners.py — health-check 회귀 러너(run.sh)를 묶음 병렬로 돌리고 결과를 **입력 순서대로** 파일에 남긴다.

왜: health-check 1,058초 중 94.7% 가 러너 106개를 한 줄로 도는 "회귀 오라클" 한 행이었다(2026-11-05 계측). 러너들은
자기 임시 공간에서만 쓰도록 이미 격리돼 있다(실측: 공유 HOME · 고정 임시 경로 · 대상 저장소 git 쓰기 0 — 프로세스 정리는 run 태그로만).
그래서 실행만 병렬로 하고, 판정 · 보고는 호출자(health-check `chk_runners`)가 지금처럼 순서대로 한다 — 표 형식은 그대로다.

계약
  --jobs N        동시 실행 수(1 이면 직렬 · 옛 동작과 같다). 기본 4
  --cwd DIR       러너를 돌릴 작업 폴더(health-check 는 플러그인 루트)
  --out-dir DIR   러너마다 `<i>.rc` · `<i>.out` · `<i>.meta`(i = 입력 순서 0부터)를 쓴다. 러너가 아무것도 못 남기면 rc 2 + `UNRUN:` 표지
                  meta 한 줄 = `load_start=<1분 부하> load_end=<1분 부하> solo=0|1 retried=0|1 first_rc=<첫 시도 rc>`(못 재면 '?')
  -- RUNNER...    `bash RUNNER` 로 돈다
  ⛔ 결과 파일은 러너마다 반드시 하나씩 생긴다 — 실행기 예외 · 러너 부재도 rc 2 + `UNRUN:` 로 남긴다(조용히 빠지면 통과로 읽힌다)
  시간 민감 러너(머리 4KB 에 `# runner: timing-sensitive` 줄) — 병렬 묶음이 다 끝난 뒤 하나씩 돈다. 준비 실패(SETUP 표지 exit 3)면
  한 번만 다시 돌고 출력 첫 줄에 `RETRY:` 를 단다. 판정 실패(exit 1 등)는 다시 돌리지 않는다 — 실제 회귀를 재시도로 통과시키지 않는다(F-575:
  준비 창이 초 단위인 러너가 부하 평균 약 190 에서 준비를 놓쳐 릴리스 게이트를 실패시켰다 · 대상 단언은 직접 실행 3회 모두 맞았다)
exit: 0 = 전부 실행(결과는 rc 파일이 말한다) · 2 = 인자 오류(⛔ 통과 아님)

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import tempfile

OK, UNRUN = 0, 2
TIMING_MARK = re.compile(r"^# runner: timing-sensitive\b", re.M)
SETUP_MARK = re.compile(r"^SETUP( |:|$)", re.M)
TRACEBACK = "Traceback (most recent call last)"


def load_avg() -> str:
    """1분 부하 평균 — 못 재면 '?'. 실패가 코드 회귀인지 호스트 부하인지 가르는 근거다(F-575)."""
    try:
        return f"{os.getloadavg()[0]:.2f}"
    except (OSError, AttributeError):
        return "?"


def timing_sensitive(runner: str) -> bool:
    try:
        with open(runner, encoding="utf-8", errors="replace") as fh:
            return bool(TIMING_MARK.search(fh.read(4096)))
    except OSError:
        return False


def setup_failure(rc: int, out: str) -> bool:
    """준비 실패 = exit 3 + 줄 맨 앞 SETUP 표지 + traceback 없음.

    - Important: health-check `classify` 의 exit 3 규칙과 같은 술어다 — 한쪽만 고치면 재시도 대상과 미실행 분류가 갈린다.
    """
    return rc == 3 and bool(SETUP_MARK.search(out)) and TRACEBACK not in out


def _exec(runner: str, cwd: str):
    try:
        if not os.path.isfile(runner):
            return UNRUN, f"UNRUN: 러너 없음 — {runner}\n"
        p = subprocess.run(["bash", runner], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception as e:   # noqa: BLE001 — 실행기 예외도 결과로 남긴다 — 빠진 러너는 통과처럼 보인다
        return UNRUN, f"UNRUN: 실행기 예외 — {type(e).__name__}: {e}\n"


def run_one(i: int, runner: str, cwd: str, out_dir: str) -> None:
    solo = timing_sensitive(runner)
    l0 = load_avg()
    rc, out = _exec(runner, cwd)
    first, retried = rc, 0
    if solo and setup_failure(rc, out):
        why = next((ln.strip() for ln in out.splitlines() if SETUP_MARK.match(ln)), "")
        rc, out = _exec(runner, cwd)
        retried = 1
        out = f"RETRY: 첫 시도 준비 실패(exit 3 · {why}) — 단독으로 한 번 다시 돌렸다(F-575)\n" + out
    l1 = load_avg()
    with open(os.path.join(out_dir, f"{i}.out"), "w", encoding="utf-8") as fh:
        fh.write(out)
    with open(os.path.join(out_dir, f"{i}.meta"), "w", encoding="utf-8") as fh:
        fh.write(f"load_start={l0} load_end={l1} solo={int(solo)} retried={retried} first_rc={first}\n")
    with open(os.path.join(out_dir, f"{i}.rc"), "w", encoding="utf-8") as fh:
        fh.write(str(rc))


def run_all(runners, jobs: int, cwd: str, out_dir: str) -> None:
    todo = list(enumerate(runners))
    solo = [a for a in todo if timing_sensitive(a[1])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        list(ex.map(lambda a: run_one(a[0], a[1], cwd, out_dir), [a for a in todo if a not in solo]))
    for i, r in solo:   # 병렬 묶음이 다 끝난 뒤 하나씩 — 결과 파일 번호는 입력 순서 그대로다
        run_one(i, r, cwd, out_dir)


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {detail}"))

    with tempfile.TemporaryDirectory() as t:
        bodies = {"pass": "echo ok; exit 0", "fail": "echo bad; exit 1", "unrun": "echo 'UNRUN: 측정 불가'; exit 2",
                  "crash": "kill -9 $$"}
        rs = []
        for k, b in bodies.items():
            p = os.path.join(t, f"{k}.sh")
            open(p, "w").write("#!/bin/bash\n" + b + "\n")
            rs.append(p)
        rs.append(os.path.join(t, "absent.sh"))

        def read(d):
            return [(open(os.path.join(d, f"{i}.rc")).read(), open(os.path.join(d, f"{i}.out")).read()) for i in range(len(rs))]
        res = {}
        for j in (1, 4):
            d = os.path.join(t, f"o{j}")
            os.mkdir(d)
            run_all(rs, j, t, d)
            res[j] = read(d)
        case("same-results", res[1] == res[4], "jobs=1 과 jobs=4 의 (rc, 출력) 순서열이 다르다")
        rc = [int(x[0]) for x in res[4]]
        case("classification", rc[0] == 0 and rc[1] == 1 and rc[2] == 2 and rc[3] != 0 and rc[-1] == 2, rc)
        case("absent-is-unrun", res[4][-1][1].startswith("UNRUN:"), res[4][-1])
        # 동시 실행 장벽 — 세 러너가 각자 표지를 남기고 셋이 다 모일 때까지 기다린다(최대 10초). 동시에 떠 있어야만 exit 0 이다.
        # ⛔ 벽시계 비교(병렬 + 0.8초 < 직렬)는 health-check 가 러너를 병렬로 도는 부하 속에서 같은 트리에서도 흔들렸다(S21 GPT verify-gates)
        bar = os.path.join(t, "barrier")
        os.mkdir(bar)
        brs = []
        for k in ("b1", "b2", "b3"):
            p = os.path.join(t, f"{k}.sh")
            open(p, "w").write(f'#!/bin/bash\n: > "{bar}/{k}"\nfor i in $(seq 100); do [ "$(ls "{bar}" | wc -l)" -ge 3 ] && exit 0; sleep 0.1; done\nexit 1\n')
            brs.append(p)
        d = os.path.join(t, "ob")
        os.mkdir(d)
        run_all(brs, 3, t, d)
        brc = [open(os.path.join(d, f"{i}.rc")).read() for i in range(3)]
        case("parallel-concurrent", brc == ["0", "0", "0"], f"장벽 rc {brc} — 세 러너가 동시에 떠 있지 않았다")
        case("one-file-per-runner", all(os.path.isfile(os.path.join(t, "o4", f"{i}.rc")) for i in range(len(rs))))
        metas = [open(os.path.join(t, "o4", f"{i}.meta")).read() for i in range(len(rs))]
        case("r3-f575-load-per-runner", all(re.match(r"load_start=\d+\.\d+ load_end=\d+\.\d+ ", m) for m in metas), metas)
        # 시간 민감 러너 — 병렬 러너 둘이 다 끝난 뒤(끝 표지) 혼자(잠금 폴더) 돌아야 첫 단언을 넘는다. 넘으면 flaky 는 첫 시도만 준비 실패,
        # judge 는 판정 실패(exit 1 — 다시 돌리지 않는다). 표지 없는 러너의 준비 실패도 다시 돌리지 않는다
        sd = os.path.join(t, "solo")
        os.mkdir(sd)
        solo_chk = (f'[ -f "{sd}/done-p1" ] && [ -f "{sd}/done-p2" ] || {{ echo "병렬 묶음과 겹쳤다"; exit 1; }}\n'
                    f'mkdir "{sd}/lock" 2>/dev/null || {{ echo "다른 시간 민감 러너와 겹쳤다"; exit 1; }}\nsleep 0.3\nrmdir "{sd}/lock"\n')
        sbodies = {"p1": f'sleep 0.5\n: > "{sd}/done-p1"', "p2": f'sleep 0.5\n: > "{sd}/done-p2"',
                   "flaky": "# runner: timing-sensitive — 합성\n" + solo_chk
                            + f'[ -f "{sd}/cnt" ] && exit 0\n: > "{sd}/cnt"\necho "SETUP 준비 동기화 실패(합성)"\nexit 3',
                   "judge": "# runner: timing-sensitive — 합성\n" + solo_chk + "echo 판정 실패\nexit 1",
                   "plain-setup": 'echo "SETUP 합성 준비 실패"\nexit 3'}
        srs = []
        for k in ("flaky", "p1", "judge", "p2", "plain-setup"):
            p = os.path.join(t, f"s-{k}.sh")
            open(p, "w").write("#!/bin/bash\n" + sbodies[k] + "\n")
            srs.append(p)
        d = os.path.join(t, "os")
        os.mkdir(d)
        run_all(srs, 4, t, d)
        got = [(open(os.path.join(d, f"{i}.rc")).read(), open(os.path.join(d, f"{i}.meta")).read(), open(os.path.join(d, f"{i}.out")).read())
               for i in range(len(srs))]
        case("r3-f575-timing-solo-retry-noted",
             got[0][0] == "0" and " solo=1 retried=1 first_rc=3" in got[0][1] and got[0][2].startswith("RETRY: 첫 시도 준비 실패")
             and got[2][0] == "1" and " solo=1 retried=0 first_rc=1" in got[2][1]
             and got[4][0] == "3" and " solo=0 retried=0 first_rc=3" in got[4][1] and [got[1][0], got[3][0]] == ["0", "0"], got)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--cwd")
    ap.add_argument("--out-dir")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("runners", nargs="*")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.cwd and a.out_dir and os.path.isdir(a.cwd) and os.path.isdir(a.out_dir)) or a.jobs < 1:
        print("UNRUN: --cwd · --out-dir(있는 폴더) · --jobs ≥ 1 이 필요하다", file=sys.stderr)
        return UNRUN
    run_all(a.runners, a.jobs, a.cwd, a.out_dir)
    return OK


if __name__ == "__main__":
    sys.exit(main())
