#!/usr/bin/env python3
"""A/B 원장 통합 테스트 — 고정 fixture 를 collect → score → judge 로 끝까지 돌려 예상 판정과 대조한다 (S05).

⛔ 판정기의 self-test 는 순수 함수만 본다. 이 러너는 **CLI·원천 파서·증거 사본·원천 대조**까지 한 번에 본다 —
   transcript 형식이 바뀌면 여기서 먼저 깨져야 한다.

fixture (tests/fixtures/ab/mini-ledger/):
  runs.json      collect 인자 목록 + 파일 mtime(산출물 기록 시각과 맞춘다)
  expected.json  judge 호출 목록 — exit · stdout_has · stdout_lacks · (선택) mutate(원장 행 위조)
  input/         fixture 저장소 원본 → tests/fixtures/quality/_lib/build_repo.sh 로 복원
  plugin/ · plugin-c/  B·C 플러그인 스텁 → 고정 신원·시각으로 git 커밋(결정적 SHA)
  raw/           transcript · Workflow 폴더 · 하네스 output · 상태 스냅샷 · 산출물 · GPT 로그

usage: integration.py --fixture DIR --expect-verdicts FILE
exit: 0=전건 일치 · 1=불일치 · 2=실행 불가(⛔ 통과 아님)
"""
import argparse
import calendar
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(HERE))
LEDGER_PY = os.path.join(PLUGIN, "scripts", "ab_ledger.py")
BUILD = os.path.join(PLUGIN, "tests", "fixtures", "quality", "_lib", "build_repo.sh")
GIT_ENV = {"GIT_AUTHOR_NAME": "fixture", "GIT_COMMITTER_NAME": "fixture",
           "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, timeout=300, **kw)


def subst(text, table):
    for k, v in table.items():
        text = text.replace(k, v)
    return text


def epoch(iso):
    return calendar.timegm(time.strptime(iso.split(".")[0].replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--expect-verdicts", required=True)
    a = ap.parse_args()
    for need in (LEDGER_PY, BUILD, os.path.join(a.fixture, "runs.json"), a.expect_verdicts):
        if not os.path.isfile(need):
            print(f"UNRUN: {need} 없음")
            return 2
    if shutil.which("git") is None:
        print("UNRUN: git 없음")
        return 2
    work = tempfile.mkdtemp(prefix="ab-int-")
    try:
        fx = os.path.join(work, "fx")
        shutil.copytree(a.fixture, fx)
        spec0 = json.load(open(os.path.join(fx, "runs.json"), encoding="utf-8"))
        inputs = {}
        for run in spec0["runs"]:   # ⛔ run 마다 새 저장소 — 공유하면 판정기가 '재사용' 으로 무효 처리한다
            d = os.path.join(work, "inputs", run["run_id"], "repo")
            os.makedirs(os.path.dirname(d))
            r = sh(["bash", BUILD, os.path.join(fx, "input"), d])
            if r.returncode != 0:
                print(f"UNRUN: 입력 저장소 복원 실패 — {r.stderr.strip()[:200]}")
                return 2
            inputs[run["input"]] = d
        env = dict(os.environ, **GIT_ENV)
        for stub in ("plugin", "plugin-c"):
            d = os.path.join(fx, stub)
            for cmd in (["git", "-C", d, "init", "-q"], ["git", "-C", d, "add", "-A"],
                        ["git", "-C", d, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "stub"]):
                if sh(cmd, env=env).returncode != 0:
                    print(f"UNRUN: 플러그인 스텁 git 실패 — {' '.join(cmd)}")
                    return 2
        plugin_sha = sh(["git", "-C", os.path.join(fx, "plugin"), "rev-parse", "HEAD"]).stdout.strip()
        ledger = os.path.join(work, "ab", "ledger.jsonl")
        table = dict(inputs)
        table.update({"@FIX@": fx, "@PLUGIN_C@": os.path.join(fx, "plugin-c"),
                 "@PLUGIN@": os.path.join(fx, "plugin"), "@WORK@": work, "@LEDGER@": ledger, "@PLUGIN_SHA@": plugin_sha})
        for root, _, files in os.walk(os.path.join(fx, "raw")):
            for f in files:
                p = os.path.join(root, f)
                with open(p, encoding="utf-8") as fh:
                    t = fh.read()
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(subst(t, table))
        spec = json.loads(subst(open(os.path.join(fx, "runs.json"), encoding="utf-8").read(), table))
        for path, iso in spec["mtimes"].items():
            os.utime(path, (epoch(iso), epoch(iso)))
        fails, passed = [], 0
        # ① run 전 입력 신원(저장소·플러그인) → collect
        for run in spec["runs"]:
            ij = os.path.join(work, "inputs", run["run_id"], "input.json")
            r = sh([sys.executable, LEDGER_PY, "input", "--root", run["input"], "--fixture", run["fixture"],
                    "--plugin-root", run["plugin"], "--plugin-source", run["plugin"], "--out", ij])
            if r.returncode != 0:
                fails.append(f"input {run['run_id']}: exit {r.returncode} — {(r.stdout + r.stderr).strip()[:300]}")
            run["input_json"] = ij
            args = [sys.executable, LEDGER_PY, "collect", "--ledger", ledger, "--run-id", run["run_id"]]
            for k in ("workflow", "arm", "run", "order", "phase", "release", "fixture", "transcript", "input_json",
                      "state_pristine", "state_start", "state_end", "evidence_dir"):
                if run.get(k) is not None:
                    args += ["--" + k.replace("_", "-"), str(run[k])]
            for x in run["artifact"]:
                args += ["--artifact", x]
            r = sh(args)
            if r.returncode != 0:
                fails.append(f"collect {run['run_id']}: exit {r.returncode} — {(r.stdout + r.stderr).strip()[:300]}")
        # ② 가린 검증자 — pack → (가짜 검증자: 후보 **내용** 규칙표, 열쇠를 보지 않는다) → unpack → score
        pack = os.path.join(work, "blind")
        froot = os.path.join(fx, "fixtures")
        r = sh([sys.executable, LEDGER_PY, "blind-pack", "--ledger", ledger, "--fixtures-root", froot, "--out", pack,
                "--salt", "integration"])
        if r.returncode != 0:
            fails.append(f"blind-pack: exit {r.returncode} — {(r.stdout + r.stderr).strip()[:300]}")
        else:
            pk = json.load(open(os.path.join(pack, "pack.json"), encoding="utf-8"))
            leaked = [rid for rid in (x["run_id"] for x in spec["runs"]) if f'"{rid}"' in json.dumps(pk, ensure_ascii=False)]
            if leaked:
                fails.append(f"blind-pack: run_id 가 꾸러미에 샌다 {leaked}")
            src = ((pk.get("fixtures") or {}).get("review-mini") or {}).get("source") or {}
            if not src.get("diff") or "App/Foo.swift" not in (src.get("files") or {}):
                fails.append("blind-pack: 검증자 꾸러미에 코드(diff·파일)가 없다 — 주장만으로 판정하게 된다")
            rules = json.load(open(os.path.join(fx, "verdict-rules.json"), encoding="utf-8"))
            va = {it["anon"]: {c["cid"]: rules[c["cid"]] for c in it.get("candidates", []) if c["cid"] in rules}
                  for it in pk["items"]}
            vf = os.path.join(work, "verdicts-anon.json")
            json.dump(va, open(vf, "w", encoding="utf-8"), ensure_ascii=False)
            out = os.path.join(work, "verdicts.json")
            r = sh([sys.executable, LEDGER_PY, "blind-unpack", "--pack", pack, "--verdicts", vf, "--out", out])
            if r.returncode != 0:
                fails.append(f"blind-unpack: exit {r.returncode} — {(r.stdout + r.stderr).strip()[:300]}")
            r = sh([sys.executable, LEDGER_PY, "score", "--ledger", ledger, "--fixtures-root", froot, "--verdicts", out])
            if r.returncode != 0:
                fails.append(f"score: exit {r.returncode} — {(r.stdout + r.stderr).strip()[:300]}")
        # ③ judge — 예상 판정과 대조
        exp = json.loads(subst(open(a.expect_verdicts, encoding="utf-8").read(), table))
        if not exp.get("judges"):
            print("UNRUN: expected.json 에 judges 가 없다 (0/0 통과 금지)")
            return 2
        for j in exp["judges"]:
            args = list(j["args"])
            if j.get("mutate"):
                # 원장 행 위조 — 같은 run_id 의 마지막 행이 이긴다. 원천 대조가 잡아야 한다
                forged = ledger + f".{j['name']}"
                shutil.copyfile(ledger, forged)
                rows = [json.loads(l) for l in open(ledger, encoding="utf-8")]
                row = [x for x in rows if x.get("type") == "run" and x["run_id"] == j["mutate"]["run_id"]][-1]
                for dotted, val in j["mutate"]["set"].items():
                    cur = row
                    *head, last = dotted.split(".")
                    for h in head:
                        cur = cur[h]
                    cur[last] = val
                with open(forged, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                args = [forged if x == ledger else x for x in args]
            r = sh([sys.executable, LEDGER_PY] + args)
            out = r.stdout
            why = []
            if r.returncode != j["exit"]:
                why.append(f"exit {r.returncode} (기대 {j['exit']})")
            why += [f"출력에 없음: {s!r}" for s in j.get("stdout_has", []) if s not in out]
            why += [f"출력에 있으면 안 됨: {s!r}" for s in j.get("stdout_lacks", []) if s in out]
            if why:
                fails.append(f"judge {j['name']}: " + " · ".join(why) + f"\n      ── stdout ──\n      "
                             + "\n      ".join(out.strip().splitlines()[:14]))
            else:
                passed += 1
        for f in fails:
            print(f"  FAIL {f}")
        total = len(exp["judges"])
        print(f"ab integration: judges {passed}/{total} 일치 · collect {len(spec['runs'])} run · "
              f"{'OK' if not fails else f'실패 {len(fails)}'}")
        return 0 if not fails else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
