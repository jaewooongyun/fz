#!/usr/bin/env python3
# lint:no-root-anchor — 러너 경로와 작업 폴더를 인수로 받는다(플러그인 루트를 해석하지 않는다)
"""run_runners.py — health-check 회귀 러너(run.sh)를 묶음 병렬로 돌리고 결과를 **입력 순서대로** 파일에 남긴다.

왜: health-check 1,058초 중 94.7% 가 러너 106개를 한 줄로 도는 "회귀 오라클" 한 행이었다(2026-11-05 계측). 러너들은
자기 임시 공간에서만 쓰도록 이미 격리돼 있다(실측: 공유 HOME · 고정 임시 경로 · 대상 저장소 git 쓰기 0 — 프로세스 정리는 run 태그로만).
그래서 실행만 병렬로 하고, 판정 · 보고는 호출자(health-check `chk_runners`)가 지금처럼 순서대로 한다 — 표 형식은 그대로다.

계약
  --jobs N        동시 실행 수(1 이면 직렬 · 옛 동작과 같다). 기본 4
  --cwd DIR       러너를 돌릴 작업 폴더(health-check 는 플러그인 루트)
  --out-dir DIR   러너마다 `<i>.rc` · `<i>.out`(i = 입력 순서 0부터)를 쓴다. 러너가 아무것도 못 남기면 rc 2 + `UNRUN:` 표지
  -- RUNNER...    `bash RUNNER` 로 돈다
  ⛔ 결과 파일은 러너마다 반드시 하나씩 생긴다 — 실행기 예외 · 러너 부재도 rc 2 + `UNRUN:` 로 남긴다(조용히 빠지면 통과로 읽힌다)
exit: 0 = 전부 실행(결과는 rc 파일이 말한다) · 2 = 인자 오류(⛔ 통과 아님)

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
import sys
import tempfile

OK, UNRUN = 0, 2


def run_one(i: int, runner: str, cwd: str, out_dir: str) -> None:
    rc, out = UNRUN, ""
    try:
        if not os.path.isfile(runner):
            out = f"UNRUN: 러너 없음 — {runner}\n"
        else:
            p = subprocess.run(["bash", runner], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            rc, out = p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception as e:   # noqa: BLE001 — 실행기 예외도 결과로 남긴다 — 빠진 러너는 통과처럼 보인다
        rc, out = UNRUN, f"UNRUN: 실행기 예외 — {type(e).__name__}: {e}\n"
    with open(os.path.join(out_dir, f"{i}.out"), "w", encoding="utf-8") as fh:
        fh.write(out)
    with open(os.path.join(out_dir, f"{i}.rc"), "w", encoding="utf-8") as fh:
        fh.write(str(rc))


def run_all(runners, jobs: int, cwd: str, out_dir: str) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        list(ex.map(lambda a: run_one(a[0], a[1], cwd, out_dir), enumerate(runners)))


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
