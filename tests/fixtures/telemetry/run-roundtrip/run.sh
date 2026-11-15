#!/bin/bash
# 실행 기록 왕복 fixture (F-475 · F-505) — run_metrics.py 가 쓴 행을 fz_telemetry_report.py 가 그대로 집계하는지 동작으로 본다.
#
# 임시 FZ_RUN_STATE 와 가짜 세션 트랜스크립트(assistant 1건 — message.model · effort)를 만들고
# CLAUDE_CODE_SESSION_ID + run_metrics.py --projects-root 로 잇는다. 실제 ~/.fz · ~/.claude 는 읽지도 쓰지도 않는다.
#   record-to-report       start → end → `fz_telemetry_report.py --runs-root … --runs-json` 에 그 run_id 가 가짜 트랜스크립트의 model · effort 로 있다
#   resume-attempt-2       end 없이 다시 start → 같은 run_id 에 attempt 1(interrupted) · 2(completed) 가 둘 다 리포터에 보인다
#   schema-version         schema 99 행을 섞으면 리포트 JSON runs.unreadable 1 · --runs-json 에는 없다 · 나머지 행 집계는 그대로
#   run_metrics-self-test  run_metrics.py --self-test(동시 실행 · 중복 end · 중단 · 쓰기 실패 · 본문 복제 · 재개 · Harness 칸)가 exit 0 · PASS —
#                          health-check 글롭이 도는 것은 이 러너뿐이라 기록기 self-test 를 여기서 회귀 감시한다
#   harness-metrics-judgement  별도 임시 FZ_RUN_STATE 에 `end --gate-issues · --findings` 로 11회 기록 → 리포트 JSON harness 가
#                          10회 이슈 0 Gate = neutral-candidate · 10회 이슈 있음 = load-bearing · 9회 = preliminary ·
#                          findings 합 · 플래그 없는 행은 두 키가 없다(0 이 아니다) — experiment-log.md §5.4 손 기록을 대신하는 판정
# 출력: case 마다 `<case>: PASS` · `<case>: FAIL <why>`, 끝에 `run-roundtrip: PASS|FAIL`.
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(`UNRUN:` — python3 · 스크립트 부재 · 단언기 고장)
set -u
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 부재"; exit 2; }
for f in scripts/run_metrics.py scripts/fz_telemetry_report.py scripts/mode_gate.py; do
  [ -f "$ROOT/$f" ] || { echo "UNRUN: $f 없음: $ROOT"; exit 2; }
done
PYTHONDONTWRITEBYTECODE=1 exec python3 -B - "$ROOT" <<'PY'
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


def _crash(*exc):   # 단언기 고장은 2 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    print("UNRUN: run-roundtrip 단언기 고장")
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(2)


sys.excepthook = _crash
ROOT = Path(sys.argv[1])
RM = ROOT / "scripts" / "run_metrics.py"
REPORT = ROOT / "scripts" / "fz_telemetry_report.py"
SID = "roundtrip-session-0001"
MODEL = "claude-roundtrip-model"
ALIEN = "a1b2c3d4e5f6"
FAILED = []


def case(name, ok, why):
    print("%s: PASS" % name if ok else "%s: FAIL %s" % (name, why))
    if not ok:
        FAILED.append(name)


def run_id_at(out, attempt):
    m = re.search(r"^RUN ([0-9a-f]{12}) attempt %d$" % attempt, out, re.M)
    return m.group(1) if m else None


with tempfile.TemporaryDirectory(prefix="fz-run-roundtrip-") as td:
    tmp = Path(td)
    state, projects, empty = tmp / "state", tmp / "projects", tmp / "empty-projects"
    (projects / "-roundtrip").mkdir(parents=True)
    empty.mkdir()
    (projects / "-roundtrip" / ("%s.jsonl" % SID)).write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "roundtrip prompt"}}) + "\n"
        + json.dumps({"type": "assistant", "effort": "high",
                      "message": {"id": "m1", "model": MODEL, "content": [{"type": "text", "text": "roundtrip body"}]}}) + "\n",
        encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_EFFORT_LEVEL", "CLAUDE_EFFORT")}
    env.update({"FZ_RUN_STATE": str(state), "CLAUDE_CODE_SESSION_ID": SID, "PYTHONDONTWRITEBYTECODE": "1"})

    def run(cmd):
        proc = subprocess.run([sys.executable, "-B"] + [str(c) for c in cmd], env=env, capture_output=True, text=True,
                              timeout=180, stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout, proc.stderr

    def rm(*args):
        rc, out, err = run([RM, *args, "--projects-root", projects, "--strict"])
        return rc, out + err

    def runs_json():
        rc, out, err = run([REPORT, "--runs-root", state, "--runs-json"])
        try:
            rows = json.loads(out)
        except ValueError:
            rows = None
        return rc, rows if isinstance(rows, list) else None, (out + err).strip()[-300:]

    # record-to-report — start → end → 리포터 --runs-json 에 그 run_id 가 가짜 트랜스크립트의 model · effort 로
    wd1 = tmp / "wd1"
    c1, o1 = rm("start", "--skill", "fz-plan", "--mode", "light", "--recommended", "light", "--source", "gate", "--work-dir", wd1)
    rid1 = run_id_at(o1, 1)
    c2, o2 = rm("end", "--skill", "fz-plan", "--work-dir", wd1, "--status", "completed")
    rc, rows, tail = runs_json()
    mine = [r for r in rows or [] if isinstance(r, dict) and r.get("run_id") == rid1]
    got = [(r.get("model"), r.get("effort"), r.get("status"), r.get("mode")) for r in mine]
    case("record-to-report",
         c1 == 0 and c2 == 0 and rid1 is not None and rc == 0 and got == [(MODEL, "high", "completed", "light")],
         "start rc=%s end rc=%s run_id=%s report rc=%s rows=%s · %s" % (c1, c2, rid1, rc, got, tail if rc else (o1 + o2).strip()[-200:]))

    # resume-attempt-2 — end 없이 다시 start 하면 같은 run_id 의 attempt 1 은 interrupted, 2 는 completed
    wd2 = tmp / "wd2"
    same = ("--skill", "fz-code", "--work-dir", wd2)
    c1, o1 = rm("start", *same, "--mode", "full", "--recommended", "full", "--source", "gate")
    c2, o2 = rm("start", *same, "--mode", "full", "--recommended", "none", "--source", "arg")
    c3, o3 = rm("end", *same, "--status", "completed")
    rid_a, rid_b = run_id_at(o1, 1), run_id_at(o2, 2)
    rc, rows, tail = runs_json()
    mine = sorted(((r.get("attempt"), r.get("status")) for r in rows or [] if isinstance(r, dict) and r.get("run_id") == rid_a),
                  key=str)
    case("resume-attempt-2",
         (c1, c2, c3, rc) == (0, 0, 0, 0) and rid_a is not None and rid_a == rid_b and mine == [(1, "interrupted"), (2, "completed")],
         "rc=%s run_id %s -> %s rows=%s · %s" % ((c1, c2, c3, rc), rid_a, rid_b, mine, (o1 + o2 + o3).strip()[-200:]))

    # schema-version — 모르는 schema 행은 unreadable 로 센다(조용히 버리지 않는다) · --runs-json 에는 없다
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    alien = state / "zz-alien"
    alien.mkdir(parents=True)
    (alien / "runs.jsonl").write_text(json.dumps({
        "schema": 99, "run_id": ALIEN, "attempt": 1, "skill": "fz-review", "mode": "full", "recommended": "full",
        "status": "completed", "started_at": now, "ended_at": now, "model": MODEL, "effort": "high"}) + "\n", encoding="utf-8")
    out_json = tmp / "report.json"
    rc1, o1, e1 = run([REPORT, "--runs-root", state, "--projects-root", empty, "--findings-dir", tmp / "no-findings",
                       "--plugin-root", tmp / "no-plugin", "--telemetry-dir", tmp / "telemetry", "--json", "--out", out_json])
    try:
        payload = json.loads(out_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = None
    runs = payload.get("runs") if isinstance(payload, dict) else None
    runs = runs if isinstance(runs, dict) else {}
    rc2, rows, tail = runs_json()
    listed = sorted(str(r.get("run_id")) for r in rows or [] if isinstance(r, dict))
    groups = sorted((str(g.get("skill")), str(g.get("mode")), g.get("n")) for g in runs.get("by_skill_mode") or [] if isinstance(g, dict))
    case("schema-version",
         rc1 == 0 and rc2 == 0 and runs.get("unreadable") == 1 and ALIEN not in listed and len(listed) == 3
         and groups == [("fz-code", "full", 2), ("fz-plan", "light", 1)],
         "report rc=%s runs-json rc=%s unreadable=%s listed=%d groups=%s · %s"
         % (rc1, rc2, runs.get("unreadable"), len(listed), groups, (o1 + e1).strip()[-200:]))

    # run_metrics-self-test — 기록기 self-test 7 case 를 이 러너로 회귀 감시한다(내부 self-test 는 자기 임시 FZ_RUN_STATE 를 쓴다)
    rc, out, err = run([RM, "--self-test"])
    lines = out.strip().splitlines()
    case("run_metrics-self-test",
         rc == 0 and bool(lines) and lines[-1].startswith("run_metrics self-test: PASS"),
         "rc=%s · %s" % (rc, (out + err).strip()[-300:]))

    # harness-metrics-judgement — 위 case 들과 섞이지 않게 자기 FZ_RUN_STATE 를 쓴다(schema-version 이 state 의 행 수를 센다)
    h_state, h_wd = tmp / "state-harness", tmp / "wd-harness"
    h_env = dict(env, FZ_RUN_STATE=str(h_state))
    h_rcs = []

    def rmh(*args):
        proc = subprocess.run([sys.executable, "-B", str(RM)] + [str(a) for a in args] + ["--projects-root", str(projects), "--strict"],
                              env=h_env, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
        h_rcs.append(proc.returncode)
        return (proc.stdout + proc.stderr).strip()

    # 시도 11회(같은 스킬 · 같은 WORK_DIR — start/end 짝). 1~10: Gate A 이슈 0 · Gate B i%3 · findings 1/2/3. 1~9 만 Gate C. 11: 플래그 없음
    for i in range(11):
        rmh("start", "--skill", "fz-review", "--mode", "full", "--recommended", "full", "--source", "gate", "--work-dir", h_wd)
        flags = []
        if i < 10:
            flags = ["--gate-issues", "Gate A=0", "--gate-issues", "Gate B (cross-model)=%d" % (i % 3),
                     "--findings", "gpt=1,claude=2,convergent=3"]
        if i < 9:
            flags += ["--gate-issues", "Gate C=1"]
        last = rmh("end", "--skill", "fz-review", "--work-dir", h_wd, "--status", "completed", *flags)
    h_json = tmp / "report-harness.json"
    rc1, o1, e1 = run([REPORT, "--runs-root", h_state, "--projects-root", empty, "--findings-dir", tmp / "no-findings",
                       "--plugin-root", tmp / "no-plugin", "--telemetry-dir", tmp / "telemetry-harness", "--json", "--out", h_json])
    try:
        payload = json.loads(h_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = None
    harness = payload.get("harness") if isinstance(payload, dict) else None
    harness = harness if isinstance(harness, dict) else {}
    gates = sorted((str(g.get("gate")), g.get("runs"), g.get("issues"), g.get("verdict"))
                   for g in harness.get("gates") or [] if isinstance(g, dict) and g.get("skill") == "fz-review")
    want_gates = [("Gate A", 10, 0, "neutral-candidate"), ("Gate B (cross-model)", 10, 9, "load-bearing"), ("Gate C", 9, 9, "preliminary")]
    want_found = {"runs": 10, "gpt_unique_findings": 10, "claude_unique_findings": 20, "convergent_findings": 30, "total_findings": 60}
    h_runs = (payload.get("runs") or {}).get("n") if isinstance(payload, dict) else None
    proc = subprocess.run([sys.executable, "-B", str(REPORT), "--runs-root", str(h_state), "--runs-json"], env=h_env,
                          capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
    try:
        h_rows = json.loads(proc.stdout)
    except ValueError:
        h_rows = None
    h_rows = h_rows if isinstance(h_rows, list) else []
    plain = [r for r in h_rows if isinstance(r, dict) and r.get("attempt") == 11]
    flagged = [r for r in h_rows if isinstance(r, dict) and r.get("attempt") == 1]
    case("harness-metrics-judgement",
         h_rcs == [0] * 22 and rc1 == 0 and proc.returncode == 0 and gates == want_gates and harness.get("findings") == want_found
         and h_runs == 11 and len(h_rows) == 11 and len(plain) == 1 and "gate_issues" not in plain[0] and "findings" not in plain[0]
         and len(flagged) == 1 and flagged[0].get("gate_issues") == {"Gate A": 0, "Gate B (cross-model)": 0, "Gate C": 1},
         "rc=%s report rc=%s runs-json rc=%s gates=%s findings=%s runs.n=%s rows=%d plain keys=%s · %s"
         % (sorted(set(h_rcs)), rc1, proc.returncode, gates, harness.get("findings"), h_runs, len(h_rows),
            sorted(set(plain[0]) & {"gate_issues", "findings"}) if plain else None, (last + o1 + e1).strip()[-200:]))

print("run-roundtrip: %s" % ("FAIL" if FAILED else "PASS"))
sys.exit(1 if FAILED else 0)
PY
