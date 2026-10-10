#!/bin/bash
# A/B 계측기 구조 셀 (F-335 묶음 d ①~⑧·⑫) — 대상 트리의 scripts/ab_ledger*.py · fz_wf_metrics.py 를 합성 입력으로 돌려 셀마다 판정한다.
#   health-check 글롭(tests/fixtures/*/*/run.sh)에서 인자 없이 돈다(이 트리). 기준 트리 대조는 `--tree <기준>` 으로 부른다.
# 입력: 이 트리의 tests/fixtures/ab/mini-ledger(run 8개 — 읽기만, 임시 폴더에 복원) · 같은 폴더 frozen.json(기준 트리에서 얼린 값).
# 셀(F = 고친 동작 — 기준 트리에서 실패해야 한다 · C = 호환 — 기준 · 후보 모두 통과):
#   ① split-size F                  ab_ledger.py · ab_ledger*.py · INSTRUMENTS 파일이 각각 1500줄 이하
#     entrypoint C                  `ab_ledger.py --help` 하위 명령이 기준 집합을 포함 · `--self-test` 가 진입점으로 돈다
#   ② selftest-outside-fingerprint F  self_test 를 정의한 파일이 INSTRUMENTS 밖 · 사본에서 그 파일을 고쳐도 instrument_sha 불변 · 사본 self-test 통과
#     fingerprint-coverage C        사본에서 collect · recollect · judge · show 뒤 sys.modules 의 scripts/ 파일이 전부 INSTRUMENTS ·
#                                   self-test 모듈(진입점 밖이면) 미적재 · INSTRUMENTS 파일 하나하나를 고치면 instrument_sha 가 바뀐다
#   ③ criteria-table F              CRITERIA 가 mapping · 키 = IMPLEMENTED · 값 callable
#     criteria-dispatch F           CRITERIA 항목을 표지 줄을 내는 가짜로 바꾸면 judge_rows 출력에 그 줄이 나오고 exit 가 따라간다(두 방향)
#   ④ collect-spec-keys F           collect 행의 collect_args 키 = COLLECT_SPEC 필드 ∪ {spec} · self_test · case · func · cmd 0
#     collect-spec-legacy C         옛 형식 collect_args(self_test · case · 버전 없음) 행을 recollect → exit 0 · complete.ok 그대로
#   ⑤ single-parse F                wf_summary · --sweep-row 한 번에 journal.jsonl · agent-*.jsonl 을 파일마다 1회 연다(감사 훅 open 이벤트)
#     single-parse-equal C          mini-ledger wf 폴더 8개의 wf_summary 가 기준에서 얼린 값과 같다(기준 키 범위)
#   ⑥ stage-key-rename F            review-live run 을 --workflow 만 바꿔 collect 해도 complete 가 같고 stage 사유가 없다
#     stage-key-compat C            세 (스킬, 스크립트) 쌍 × stage2 × tier 의 필수 stage · stagesCompleted 기대 · 스킬 이름 보기가 기준과 같다
#   ⑦ history-kinds F               collect → recollect → collect 를 쌓으면 show --history 가 collect#1 · recollect · collect#2 순, judge 는 마지막 행
#     history-legacy-winner C       origin 없는 옛 행 원장에서 load() 승자가 마지막 행 · show 가 돈다
#   ⑧ formal-requires-sources F     judge --formal 에서 --verify-sources · --plugin-sha 결손이 각각 UNRUN exit 2 + 태그
#     formal-with-sources F         둘이 있으면 --formal 없는 호출과 exit · 판정 줄이 같고 머리 줄(formal:) 하나만 더한다
#     legacy-argv-unchanged C       mini-ledger judge argv 11종의 stdout · exit 가 기준에서 얼린 바이트와 같다(임시 폴더 접두만 토큰)
#   ⑫ clock-endpoint F              파서가 모르는 쓰기(make)로 끝난 run 에 시계를 주면 complete=True · wall.end = 시계 시각
#     clock-overrides-stale-parser F  파서가 앞선 쓰기를 잡고 진짜 마지막 쓰기는 시계에만 있을 때 끝점 = 시계 · mtime 교차 통과
#     clock-mtime-mismatch F        시계의 mtime 이 파일 mtime 과 허용 밖이면 미완주 · 사유
#     clock-spec-stored F           collect_args 에 spec=collect/1 · endpoint_clock(증거 사본) · endpoint_clock_source(원본)
#     clock-evidence-copy F         증거 사본 바이트 = 원본 시계 · sources.endpoint_clock 이 사본 경로 · sha256 을 적는다
#     clock-recollect-reproduce F   원본 시계를 변조 · 삭제한 뒤 recollect 해도 끝점 · 완주가 그대로다
#     clock-absent-unchanged C      시계 없이 같은 run 들을 collect 하면 complete · 끝점이 기준에서 얼린 값과 같다
# 출력: 셀마다 `CELL <이름> <F|C> PASS|FAIL [태그] — 상세` · 끝 줄 `CELLS ran=N pass=P fail=K failed=<정렬 목록|-> names=<정렬 목록>`.
#   기대 셀 집합과 실제로 돈 집합이 다르면 FAIL(F-408). 셀 안 예외는 그 셀 FAIL(태그 exception:<종류>) — 기준 트리에 없는 플래그 ·
#   속성은 예외가 아니라 그 셀의 단언 실패로 적는다(태그 no-…).
# 쓰기: 임시 폴더만 — 대상 트리 · 이 트리 · HOME 아래 0(바이트코드도 쓰지 않는다). 상태 스냅샷은 mini-ledger 방식(실 HOME 경로 이름)이다.
# exit: 0 전 셀 통과 · 1 단언 실패 · 2 UNRUN(python3 · git 부재) · 3 준비 실패(인자 · 트리 · 임시 폴더 · fixture 복원)
# usage: run.sh [--tree <플러그인 루트>] [--cells a,b]   (기본: 이 fixture 가 든 트리 · 전 셀)
#        run.sh --tree <기준 트리> --emit-frozen     호환 셀이 쓰는 얼린 값을 표준출력에만 낸다(frozen.json 재생성 — 기준 트리에서만)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$HERE/../../../.." && pwd)"
SELF="$R"
CELLS="" EMIT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    --cells) [ $# -ge 2 ] || { echo "SETUP --cells 에 값이 없다"; exit 3; }; CELLS="$2"; shift 2 ;;
    --emit-frozen) EMIT=1; shift ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 없음"; exit 2; }
command -v git >/dev/null 2>&1 || { echo "UNRUN: git 없음"; exit 2; }
[ -f "$R/scripts/ab_ledger.py" ] || { echo "SETUP 대상 계측기 없음 $R/scripts/ab_ledger.py"; exit 3; }
[ -d "$SELF/tests/fixtures/ab/mini-ledger" ] || { echo "SETUP mini-ledger fixture 없음"; exit 3; }
[ "$EMIT" = 1 ] || [ -f "$HERE/frozen.json" ] || { echo "SETUP 얼린 값 없음 $HERE/frozen.json"; exit 3; }
# ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 실패해도 `cd ""` 가 성공한다(F-355)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-structure-d.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
TD="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -I -B - "$R" "$SELF" "$TD" "$CELLS" "$EMIT" <<'PY'
import ast
import calendar
import datetime
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
TREE, SELF, TD, ONLY, EMIT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "1"
SCRIPTS = os.path.join(TREE, "scripts")
AB = os.path.join(SCRIPTS, "ab_ledger.py")
MINI = os.path.join(SELF, "tests", "fixtures", "ab", "mini-ledger")
BUILD = os.path.join(SELF, "tests", "fixtures", "quality", "_lib", "build_repo.sh")
FROZEN = os.path.join(SELF, "tests", "fixtures", "ab", "structure-d", "frozen.json")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
PY = [sys.executable, "-I", "-B"]
LIMIT = 1500
BASE_SUBCOMMANDS = ["blind-pack", "blind-unpack", "collect", "collect-gpt", "input", "judge", "recollect", "score", "show",
                    "verify-evidence", "snapshot"]
LEGACY_KEYS = ("self_test", "case", "ledger", "workflow", "arm", "run", "order", "phase", "release", "run_id", "fixture",
               "transcript", "artifact", "input_root", "input_json", "state_pristine", "state_start", "state_end", "gpt_log",
               "gpt_log_dir", "evidence_dir", "tasks_dir")
GIT_ENV = {"GIT_AUTHOR_NAME": "fixture", "GIT_COMMITTER_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_EMAIL": "fixture@example.invalid", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
EXPECTED = {"split-size": "F", "entrypoint": "C", "selftest-outside-fingerprint": "F", "fingerprint-coverage": "C",
            "criteria-table": "F", "criteria-dispatch": "F", "collect-spec-keys": "F", "collect-spec-legacy": "C",
            "single-parse": "F", "single-parse-equal": "C", "stage-key-rename": "F", "stage-key-compat": "C",
            "history-kinds": "F", "history-legacy-winner": "C", "formal-requires-sources": "F", "formal-with-sources": "F",
            "legacy-argv-unchanged": "C", "clock-endpoint": "F", "clock-overrides-stale-parser": "F",
            "clock-mtime-mismatch": "F", "clock-spec-stored": "F", "clock-evidence-copy": "F",
            "clock-recollect-reproduce": "F", "clock-absent-unchanged": "C"}


class Setup(Exception):
    """fixture 복원 실패 — 대상 트리의 결함이 아니다(exit 3)."""


class Cell(Exception):
    """셀 단언 실패 — 태그와 상세를 싣는다."""

    def __init__(self, tag, detail):
        super().__init__(detail)
        self.tag = tag


def sh(args, timeout=300, **kw):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=kw.pop("env", ENV), **kw)


def ab(*args, timeout=300):
    return sh(PY + [AB] + [str(a) for a in args], timeout=timeout)


def child(code, *args, scripts=SCRIPTS):
    """대상 트리(또는 사본) 모듈을 새 프로세스에서 싣고 code 를 돈다 → 마지막 줄 JSON. ⛔ 두 트리를 한 프로세스에 싣지 않는다."""
    pre = ("import sys, json, os, io, contextlib\nsys.dont_write_bytecode = True\nSC = sys.argv[1]\nsys.path.insert(0, SC)\n"
           "ARGS = sys.argv[2:]\n")
    r = sh(PY + ["-c", pre + code, scripts] + [str(a) for a in args])
    lines = r.stdout.strip().splitlines()
    if r.returncode != 0 or not lines:
        raise RuntimeError(f"child exit {r.returncode}: {(r.stderr or r.stdout).strip().splitlines()[-1:]}")
    return json.loads(lines[-1])


def tok(s):
    return s.replace(TD, "@W@") if isinstance(s, str) else s


def tokj(o):
    return json.loads(tok(json.dumps(o, ensure_ascii=False, sort_keys=True)))


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def epoch(iso):
    return calendar.timegm(time.strptime(iso.split(".")[0].replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))


def rows_of(ledger):
    return [json.loads(x) for x in open(ledger, encoding="utf-8") if x.strip()]


def last_run(ledger, run_id=None):
    rs = [r for r in rows_of(ledger) if r.get("type") == "run" and (run_id is None or r.get("run_id") == run_id)]
    if not rs:
        raise Cell("no-row", f"원장에 run 행이 없다 {tok(ledger)}")
    return rs[-1]


# ── mini-ledger 복원 · 수집(한 번) ─────────────────────────────────────────
_MEMO = {}


def memo(fn):
    def wrap():
        if fn.__name__ not in _MEMO:
            try:
                _MEMO[fn.__name__] = ("ok", fn())
            except Exception as e:  # noqa: BLE001 — 준비 실패 · 대상 결함을 셀마다 다시 던진다
                _MEMO[fn.__name__] = ("err", e)
        st, v = _MEMO[fn.__name__]
        if st == "err":
            raise v
        return v
    wrap.__name__ = fn.__name__
    return wrap


@memo
def mini():
    """mini-ledger 를 임시 폴더에 복원한다(입력 저장소 · 플러그인 스텁 커밋 · 경로 치환 · mtime) — 대상 트리 코드는 쓰지 않는다."""
    work = os.path.join(TD, "mini")
    fx = os.path.join(work, "fx")
    shutil.copytree(MINI, fx)
    spec0 = json.load(open(os.path.join(fx, "runs.json"), encoding="utf-8"))
    table = {}
    for run in spec0["runs"]:
        d = os.path.join(work, "inputs", run["run_id"], "repo")
        os.makedirs(os.path.dirname(d))
        r = sh(["bash", BUILD, os.path.join(fx, "input"), d])
        if r.returncode != 0:
            raise Setup(f"입력 저장소 복원 실패 {r.stderr.strip()[:200]}")
        table[run["input"]] = d
    genv = dict(ENV, **GIT_ENV)
    for stub in ("plugin", "plugin-c"):
        d = os.path.join(fx, stub)
        for cmd in (["git", "-C", d, "init", "-q"], ["git", "-C", d, "add", "-A"],
                    ["git", "-C", d, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "stub"]):
            if sh(cmd, env=genv).returncode != 0:
                raise Setup(f"플러그인 스텁 git 실패 {' '.join(cmd)}")
    psha = sh(["git", "-C", os.path.join(fx, "plugin"), "rev-parse", "HEAD"]).stdout.strip()
    ledger = os.path.join(work, "ab", "ledger.jsonl")
    table.update({"@FIX@": fx, "@PLUGIN_C@": os.path.join(fx, "plugin-c"), "@PLUGIN@": os.path.join(fx, "plugin"),
                  "@WORK@": work, "@LEDGER@": ledger, "@PLUGIN_SHA@": psha})

    def subst(t):
        for k, v in table.items():
            t = t.replace(k, v)
        return t
    for root, _, files in os.walk(os.path.join(fx, "raw")):
        for f in files:
            p = os.path.join(root, f)
            t = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(subst(t))
    spec = json.loads(subst(open(os.path.join(fx, "runs.json"), encoding="utf-8").read()))
    for path, iso in spec["mtimes"].items():
        os.utime(path, (epoch(iso), epoch(iso)))
    exp = json.loads(subst(open(os.path.join(fx, "expected.json"), encoding="utf-8").read()))
    runs = {r["run_id"]: r for r in spec["runs"]}
    for run in spec["runs"]:
        run["input_json"] = os.path.join(work, "inputs", run["run_id"], "input.json")
    return {"work": work, "fx": fx, "ledger": ledger, "psha": psha, "spec": spec, "runs": runs, "exp": exp, "subst": subst}


def collect_args(run, **over):
    """runs.json 항목 → collect 인자. over: ledger · run_id · workflow · transcript · artifact · endpoint_clock."""
    a = ["collect", "--ledger", over.get("ledger"), "--run-id", over.get("run_id", run["run_id"])]
    for k in ("workflow", "arm", "run", "order", "phase", "release", "fixture", "transcript", "input_json",
              "state_pristine", "state_start", "state_end", "evidence_dir"):
        v = over.get(k, run.get(k))
        if v is not None:
            a += ["--" + k.replace("_", "-"), str(v)]
    for x in over.get("artifact", run["artifact"]):
        a += ["--artifact", x]
    if over.get("endpoint_clock"):
        a += ["--endpoint-clock", over["endpoint_clock"]]
    return a


@memo
def mini_ledger():
    """대상 트리 코드로 mini-ledger 8 run 을 input · collect · 가린 채점까지 — integration.py 와 같은 순서."""
    m = mini()
    for run in m["spec"]["runs"]:
        r = ab("input", "--root", run["input"], "--fixture", run["fixture"], "--plugin-root", run["plugin"],
               "--plugin-source", run["plugin"], "--out", run["input_json"])
        if not os.path.isfile(run["input_json"]):
            raise Cell("prep-input", f"input {run['run_id']} exit {r.returncode} {(r.stdout + r.stderr)[-200:]}")
        r = ab(*collect_args(run, ledger=m["ledger"]))
        if r.returncode != 0:
            raise Cell("prep-collect", f"collect {run['run_id']} exit {r.returncode} {(r.stdout + r.stderr)[-200:]}")
    pack, froot = os.path.join(m["work"], "blind"), os.path.join(m["fx"], "fixtures")
    r = ab("blind-pack", "--ledger", m["ledger"], "--fixtures-root", froot, "--out", pack, "--salt", "integration")
    if r.returncode != 0:
        raise Cell("prep-score", f"blind-pack exit {r.returncode}")
    pk = json.load(open(os.path.join(pack, "pack.json"), encoding="utf-8"))
    rules = json.load(open(os.path.join(m["fx"], "verdict-rules.json"), encoding="utf-8"))
    va = {it["anon"]: {c["cid"]: rules[c["cid"]] for c in it.get("candidates", []) if c["cid"] in rules} for it in pk["items"]}
    vf, vo = os.path.join(m["work"], "verdicts-anon.json"), os.path.join(m["work"], "verdicts.json")
    json.dump(va, open(vf, "w", encoding="utf-8"), ensure_ascii=False)
    for args in (("blind-unpack", "--pack", pack, "--verdicts", vf, "--out", vo),
                 ("score", "--ledger", m["ledger"], "--fixtures-root", froot, "--verdicts", vo)):
        r = ab(*args)
        if r.returncode != 0:
            raise Cell("prep-score", f"{args[0]} exit {r.returncode}")
    return m


def judge_argvs(m):
    """expected.json 의 judge argv(위조 행 포함) → [(이름, argv)]."""
    out = []
    for j in m["exp"]["judges"]:
        args = list(j["args"])
        if j.get("mutate"):
            forged = m["ledger"] + f".{j['name']}"
            shutil.copyfile(m["ledger"], forged)
            row = [x for x in rows_of(m["ledger"]) if x.get("type") == "run" and x["run_id"] == j["mutate"]["run_id"]][-1]
            for dotted, val in j["mutate"]["set"].items():
                cur = row
                *head, last = dotted.split(".")
                for h in head:
                    cur = cur[h]
                cur[last] = val
            with open(forged, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            args = [forged if x == m["ledger"] else x for x in args]
        out.append((j["name"], args))
    return out


# ── 시계 변형(F-335 ⑫) — B1 transcript 의 마지막 쓰기를 파서가 모르는 꼴(make)로 바꾼 사본 ─────────────────────
def z(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


T00 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def at(mm, ss=0):
    return T00 + datetime.timedelta(minutes=mm, seconds=ss)


def clock_line(t, path, mtime=None):
    st = os.stat(path)
    return json.dumps({"t": z(t), "path": path, "size": st.st_size, "mtime": st.st_mtime if mtime is None else mtime,
                       "sha256": sha256(path)}) + "\n"


@memo
def variants():
    m = mini()
    b1 = m["runs"]["B1"]
    evs = [json.loads(x) for x in open(b1["transcript"], encoding="utf-8") if x.strip()]
    d = os.path.join(TD, "clock")
    os.makedirs(d)
    art = b1["artifact"][0]

    def write_transcript(name, events):
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in events)
        return p

    def make_call(tid, ts_call, ts_res, target_dir):
        return [{"type": "assistant", "timestamp": z(ts_call), "effort": "xhigh", "cwd": evs[1]["cwd"],
                 "message": {"id": f"m-{tid}", "model": "claude-opus-5-5", "stop_reason": "tool_use", "usage": {"output_tokens": 5},
                             "content": [{"type": "tool_use", "id": tid, "name": "Bash",
                                          "input": {"command": f"make -C {target_dir} report"}}]}},
                {"type": "user", "timestamp": z(ts_res),
                 "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": "make: report — ok"}]}}]

    def is_write(e, kind):   # 산출물 Write 호출(tool_use) · 그 결과(tool_result) 블록이 든 이벤트
        c = (e.get("message") or {}).get("content")
        return isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == kind and "b1-tu-w" in (b.get("id"), b.get("tool_use_id"))
                                           for b in c)
    # make: 산출물 Write 를 make 호출로 바꾼다(시각 그대로 — 결과 00:25:02 · 파일 mtime 00:25:02)
    mk = []
    for e in evs:
        if is_write(e, "tool_use"):
            continue
        if is_write(e, "tool_result"):
            mk += make_call("mk-1", at(25, 1), at(25, 2), os.path.dirname(art))
            continue
        mk.append(e)
    if len(mk) != len(evs):
        raise Setup("B1 transcript 의 산출물 Write 를 make 호출로 바꾸지 못했다 — mini-ledger 형식이 바뀌었다")
    t_make = write_transcript("make.jsonl", mk)
    # stale: 같은 Write(00:25:02) 뒤 00:40:05 에 make 가 산출물을 다시 쓴다 — 파서는 앞 쓰기만 본다
    sart = os.path.join(d, "stale", "review-report.md")
    os.makedirs(os.path.dirname(sart))
    open(sart, "w", encoding="utf-8").write("(리포트 v1)\n")
    os.utime(sart, (at(25, 2).timestamp(),) * 2)
    st_v1 = clock_line(at(25, 2), sart)
    st = [json.loads(json.dumps(e).replace(json.dumps(art)[1:-1], json.dumps(sart)[1:-1])) for e in evs]
    if not any(is_write(e, "tool_result") for e in st):
        raise Setup("B1 transcript 에 산출물 Write 결과가 없다 — mini-ledger 형식이 바뀌었다")
    st += make_call("mk-2", at(40, 0), at(40, 5), os.path.dirname(sart))
    t_stale = write_transcript("stale.jsonl", st)
    open(sart, "w", encoding="utf-8").write("(리포트 v2)\n")
    os.utime(sart, (at(40, 5).timestamp(),) * 2)
    # 시계 — make: 앞선 관측(다른 내용 · 더 이른 t) + 마지막 관측 / stale: v1 관측 + v2 관측 / mismatch: 마지막 관측 mtime −100s
    c_make = os.path.join(d, "clock-make.jsonl")
    early = json.dumps({"t": z(at(20)), "path": art, "size": 1, "mtime": at(20).timestamp(), "sha256": "0" * 64}) + "\n"
    open(c_make, "w", encoding="utf-8").write(early + clock_line(at(25, 2), art))
    c_stale = os.path.join(d, "clock-stale.jsonl")
    open(c_stale, "w", encoding="utf-8").write(st_v1 + clock_line(at(40, 5), sart))
    c_bad = os.path.join(d, "clock-mismatch.jsonl")
    open(c_bad, "w", encoding="utf-8").write(clock_line(at(25, 2), art, mtime=os.stat(art).st_mtime - 100))
    return {"b1": b1, "art": art, "sart": sart, "t_make": t_make, "t_stale": t_stale, "c_make": c_make, "c_stale": c_stale,
            "c_bad": c_bad}


def collect_into(name, run, **over):
    led = os.path.join(TD, "led", name, "ledger.jsonl")
    os.makedirs(os.path.dirname(led), exist_ok=True)
    r = ab(*collect_args(run, ledger=led, **over))
    return led, r


@memo
def clock_run():
    """make 변형 + 시계 collect — 시계 셀 넷이 이 행을 본다. 기준 트리는 --endpoint-clock 을 모른다(argparse 거부)."""
    mini_ledger()
    v = variants()
    led, r = collect_into("clock-endpoint", v["b1"], run_id="CLK", transcript=v["t_make"], endpoint_clock=v["c_make"])
    if r.returncode != 0:
        raise Cell("no-clock-flag", f"collect --endpoint-clock exit {r.returncode} {(r.stderr or r.stdout).strip()[-160:]}")
    return led, last_run(led, "CLK")


# ── 셀 ────────────────────────────────────────────────────────────────────
def instruments():
    return child("import ab_ledger as m\nprint(json.dumps(list(m.INSTRUMENTS)))")


def selftest_files(scripts=SCRIPTS):
    out = []
    for p in sorted(glob.glob(os.path.join(scripts, "ab_ledger*.py"))):
        t = ast.parse(open(p, encoding="utf-8").read())
        if any(isinstance(n, ast.FunctionDef) and n.name == "self_test" for n in t.body):
            out.append(os.path.basename(p))
    return out


def cell_split_size():
    files = sorted(set(instruments()) | {os.path.basename(p) for p in glob.glob(os.path.join(SCRIPTS, "ab_ledger*.py"))})
    sizes = {f: open(os.path.join(SCRIPTS, f), encoding="utf-8").read().count("\n") for f in files}
    over = {f: n for f, n in sizes.items() if n > LIMIT}
    return not over, f"{len(files)}개 파일 · 상한 {LIMIT}줄 초과 {over or '없음'} · 최대 {max(sizes.values())}"


def cell_entrypoint():
    r = ab("--help")
    usage = r.stdout.replace("\n", " ")
    import re
    m = re.search(r"\{([a-z,-]+)\}", usage)
    have = set(m.group(1).split(",")) if m else set()
    miss = sorted(set(BASE_SUBCOMMANDS) - have)
    st = ab("--self-test")
    tail = (st.stdout.strip().splitlines() or [""])[-1]
    ok_st = st.returncode == 0 and re.fullmatch(r"self-test (\d+)/\1 passed", tail) is not None
    return (r.returncode == 0 and not miss and ok_st), f"하위 명령 빠짐 {miss or '없음'} · self-test exit {st.returncode} '{tail}'"


def copy_scripts(name):
    dst = os.path.join(TD, "copies", name, "scripts")
    shutil.copytree(SCRIPTS, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


SHA_EDIT = ("import ab_ledger as m\nf = os.path.join(SC, ARGS[0])\nb0 = m.instrument_sha()\norig = open(f, 'rb').read()\n"
            "open(f, 'ab').write(b'\\n# probe edit\\n')\nb1 = m.instrument_sha()\nopen(f, 'wb').write(orig)\n"
            "print(json.dumps([b0, b1, m.instrument_sha()]))")


def cell_selftest_outside_fingerprint():
    st = selftest_files()
    if len(st) != 1:
        raise Cell("selftest-file", f"self_test 정의 파일 {st} (정확히 1개여야 한다)")
    inst = instruments()
    if st[0] in inst:
        raise Cell("in-fingerprint", f"self_test 가 계측기 지문 안 파일 {st[0]} 에 있다 — self-test 만 고쳐도 지문이 바뀐다")
    cp = copy_scripts("sof")
    b0, b1, b2 = child(SHA_EDIT, st[0], scripts=cp)
    open(os.path.join(cp, st[0]), "a", encoding="utf-8").write("\n# probe edit\n")
    r = sh(PY + [os.path.join(cp, "ab_ledger.py"), "--self-test"])
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return (b0 == b1 == b2 and r.returncode == 0), f"{st[0]} 편집 전후 지문 {b0}·{b1} · 사본 self-test exit {r.returncode} '{tail}'"


COVER = """import ab_ledger as m
L, B1 = ARGS[0], json.loads(ARGS[1])
def run(argv):
    sys.argv = ["ab_ledger.py"] + argv
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return m.main()
        except SystemExit as e:
            return e.code
rc = [run(["collect", "--ledger", L, "--run-id", "COV"] + B1), run(["recollect", "--ledger", L]),
      run(["judge", "--ledger", L, "--phase", "baseline", "--workflows", "fz-review", "--min-runs", "1",
           "--verify-sources", "transcript,wf-metrics,start-state,input-hash,instrument-sha"]),
      run(["show", "--ledger", L])]
real = os.path.realpath(SC)
loaded = sorted({os.path.basename(x.__file__) for x in list(sys.modules.values())
                 if getattr(x, "__file__", None) and os.path.dirname(os.path.realpath(x.__file__)) == real})
changed = {}
for f in m.INSTRUMENTS:
    p = os.path.join(SC, f)
    orig = open(p, "rb").read()
    b0 = m.instrument_sha()
    open(p, "ab").write(b"\\n# probe edit\\n")
    changed[f] = m.instrument_sha() != b0
    open(p, "wb").write(orig)
print(json.dumps({"rc": rc, "loaded": loaded, "instruments": list(m.INSTRUMENTS), "changed": changed}))
"""


def b1_cli_args(m, **over):
    a = collect_args(m["runs"]["B1"], ledger="X", **over)
    return a[a.index("--run-id") + 2:]


def cell_fingerprint_coverage():
    m = mini_ledger()
    cp = copy_scripts("cov")
    led = os.path.join(TD, "led", "cov", "ledger.jsonl")
    os.makedirs(os.path.dirname(led))
    out = child(COVER, led, json.dumps(b1_cli_args(m)), scripts=cp)
    st = selftest_files(cp)
    outside = [f for f in out["loaded"] if f not in out["instruments"]]
    st_loaded = [f for f in st if f != "ab_ledger.py" and f in out["loaded"]]
    unchanged = sorted(f for f, c in out["changed"].items() if not c)
    ok = out["rc"][0] == 0 and out["rc"][1] in (0, 1) and not outside and not st_loaded and not unchanged
    return ok, (f"exit {out['rc']} · 적재 {out['loaded']} · 지문 밖 적재 {outside or '없음'} · self-test 모듈 적재 {st_loaded or '없음'} · "
                f"고쳐도 지문 불변 {unchanged or '없음'}")


CRIT_TABLE = """import ab_ledger as m, collections.abc
C = getattr(m, "CRITERIA", None)
print(json.dumps({"has": C is not None, "mapping": isinstance(C, collections.abc.Mapping),
                  "keys": list(C) if isinstance(C, collections.abc.Mapping) else None, "implemented": list(m.IMPLEMENTED),
                  "callable": all(callable(v) for v in C.values()) if isinstance(C, collections.abc.Mapping) else False}))
"""


def cell_criteria_table():
    o = child(CRIT_TABLE)
    if not o["has"]:
        raise Cell("no-criteria", "CRITERIA 표가 없다 — judge_rows 는 if 사슬로 분기한다")
    ok = o["mapping"] and o["keys"] == o["implemented"] and o["callable"]
    return ok, f"mapping={o['mapping']} · 키=IMPLEMENTED {o['keys'] == o['implemented']} · callable={o['callable']}"


DISPATCH = """import ab_ledger as m
runs, scores = m.load(ARGS[0])
def opts(phase, release, req):
    return {"model": m.DEFAULT_MODEL, "effort": m.DEFAULT_EFFORT, "phase": phase, "arm": "C", "release": release,
            "workflows": ["fz-review"], "min_runs": 2, "runs": 1, "plugin_sha": None, "require": req, "envs": None,
            "options_on": False, "require_passed": None}
o1, o2 = opts(None, None, ["SC-3"]), opts("release-smoke", "R-A", ["SC-3-smoke"])
real1, real2 = m.judge_rows(runs, scores, o1)[0], m.judge_rows(runs, scores, o2)[0]
if not hasattr(m, "CRITERIA"):
    print(json.dumps({"has": False}))
    raise SystemExit(0)
m.CRITERIA["SC-3"] = lambda *a, **k: (True, ["CRITERIA-DISPATCH-MARK-PASS"])
m.CRITERIA["SC-3-smoke"] = lambda *a, **k: (False, ["CRITERIA-DISPATCH-MARK-FAIL"])
f1, f2 = m.judge_rows(runs, scores, o1), m.judge_rows(runs, scores, o2)
print(json.dumps({"has": True, "real": [real1, real2], "fake": [f1[0], f2[0]],
                  "mark": ["CRITERIA-DISPATCH-MARK-PASS" in " ".join(f1[1]), "CRITERIA-DISPATCH-MARK-FAIL" in " ".join(f2[1])]}))
"""


def cell_criteria_dispatch():
    m = mini_ledger()
    o = child(DISPATCH, m["ledger"])
    if not o["has"]:
        raise Cell("no-criteria", "CRITERIA 표가 없다 — 가짜 판정 함수를 끼울 자리가 없다")
    ok = o["real"] == [1, 0] and o["fake"] == [0, 1] and all(o["mark"])
    return ok, f"실제 exit SC-3 · SC-3-smoke {o['real']}(기대 [1, 0]) · 가짜 {o['fake']}(기대 [0, 1]) · 표지 {o['mark']}"


SPEC = """import ab_ledger as m
S = getattr(m, "COLLECT_SPEC", None)
print(json.dumps({"fields": [k for k, _ in S] if S else None, "version": getattr(m, "COLLECT_SPEC_VERSION", None)}))
"""


def cell_collect_spec_keys():
    m = mini_ledger()
    ca = last_run(m["ledger"], "B1")["collect_args"]
    o = child(SPEC)
    leak = sorted(k for k in ("self_test", "case", "func", "cmd") if k in ca)
    if o["fields"] is None:
        raise Cell("no-spec", f"COLLECT_SPEC 이 없다 · collect_args 의 CLI 전역 키 {leak}")
    ok = set(ca) == set(o["fields"]) | {"spec"} and ca.get("spec") == o["version"] == "collect/1" and not leak
    return ok, (f"키 ≠ 필드∪spec: 더함 {sorted(set(ca) - set(o['fields']) - {'spec'})} · 빠짐 {sorted(set(o['fields']) - set(ca))} · "
                f"spec={ca.get('spec')} · 새는 키 {leak or '없음'}")


def cell_collect_spec_legacy():
    m = mini_ledger()
    row = last_run(m["ledger"], "B1")
    ca = row["collect_args"]
    old = dict(row, collect_args=dict({k: ca.get(k) for k in LEGACY_KEYS}, self_test=False, case=None))
    for k in ("origin", "measure_seq"):
        old.pop(k, None)
    led = os.path.join(TD, "led", "legacy", "ledger.jsonl")
    os.makedirs(os.path.dirname(led))
    open(led, "w", encoding="utf-8").write(json.dumps(old, ensure_ascii=False) + "\n")
    r = ab("recollect", "--ledger", led)
    new = last_run(led, "B1")
    ok = r.returncode == 0 and len([x for x in rows_of(led) if x.get("type") == "run"]) == 2 \
        and new["complete"]["ok"] == row["complete"]["ok"]
    return ok, f"recollect exit {r.returncode} · complete {row['complete']['ok']}→{new['complete']['ok']} · {tok(r.stdout.strip()[-160:])}"


AUDIT = """opens = []
def hook(ev, args):
    if ev == "open" and args and isinstance(args[0], str):
        opens.append(args[0])
import ab_ledger as m, fz_wf_metrics as w
sys.addaudithook(hook)
F = os.path.realpath(ARGS[0])
def count():
    c = {}
    for p in opens:
        q = os.path.realpath(p)
        if os.path.dirname(q) == F and (os.path.basename(q) == "journal.jsonl" or
                                        (os.path.basename(q).startswith("agent-") and q.endswith(".jsonl"))):
            c[os.path.basename(q)] = c.get(os.path.basename(q), 0) + 1
    return c
m.wf_summary(ARGS[0])
a = count()
del opens[:]
sys.argv = ["fz_wf_metrics.py", "--sweep-row", "--wf", ARGS[0]]
with contextlib.redirect_stdout(io.StringIO()):
    rc = w.main()
b = count()
print(json.dumps({"wf_summary": a, "sweep_row": b, "rc": rc}))
"""


def cell_single_parse():
    m = mini()
    folder = os.path.join(m["fx"], "raw", "wf", "wf_b1")
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "agent-*.jsonl"))) + ["journal.jsonl"]
    o = child(AUDIT, folder)
    bad = {k: {f: o[k].get(f, 0) for f in files if o[k].get(f, 0) != 1} for k in ("wf_summary", "sweep_row")}
    ok = o["rc"] == 0 and not bad["wf_summary"] and not bad["sweep_row"]
    return ok, f"파일 {len(files)}개 · 1회가 아닌 열기 wf_summary {bad['wf_summary'] or '없음'} · sweep-row {bad['sweep_row'] or '없음'}"


WFS = """import ab_ledger as m
print(json.dumps({d: m.wf_summary(os.path.join(ARGS[0], d)) for d in sorted(os.listdir(ARGS[0]))}, default=str, sort_keys=True))
"""


def obs_wf_summary():
    m = mini()
    return tokj(child(WFS, os.path.join(m["fx"], "raw", "wf")))


def cell_single_parse_equal(frozen):
    got, want = obs_wf_summary(), frozen["wf_summary"]
    diff = {d: sorted(k for k in want[d] if (got.get(d) or {}).get(k) != want[d][k]) for d in want}
    diff = {d: ks for d, ks in diff.items() if ks}
    ok = sorted(got) == sorted(want) and not diff
    return ok, f"폴더 {len(want)}개 · 기준 키 중 다른 값 {diff or '없음'}"


def cell_stage_key_rename():
    m = mini_ledger()
    base = last_run(m["ledger"], "B1")["complete"]
    led, r = collect_into("rename", m["runs"]["B1"], run_id="RN", workflow="fz-peer-review")
    if r.returncode != 0:
        raise Cell("prep-collect", f"collect exit {r.returncode}")
    c = last_run(led, "RN")["complete"]
    stage = [w for w in c["why"] if "필수 stage" in w or "stagesCompleted" in w]
    ok = c["ok"] == base["ok"] and not stage
    return ok, f"--workflow fz-review→fz-peer-review: complete {base['ok']}→{c['ok']} · stage 사유 {tok(str(stage))[:200] or '없음'}"


STAGES = """import ab_ledger as m
PAIRS = [("fz-plan", "plan-lean2"), ("fz-review", "review-live"), ("fz-peer-review", "peer-review")]
new = hasattr(m, "STAGES_BY_SCRIPT") and hasattr(m, "required_stages")
out = {}
for sk, sc in PAIRS:
    for s2 in (None, True, False):
        for tier in (None, 2, 3):
            if new:
                v = [list(m.required_stages(sc, s2, tier)), m.expected_stages_completed(sc, s2, tier)]
            else:
                v = [list(m._required_stages(sk, s2, tier)), m._expected_stages_completed(sk, s2, tier)]
            out[f"{sk}|{s2}|{tier}"] = v
print(json.dumps({"api": "script" if new else "skill", "table": out,
                  "view": {k: list(v) for k, v in m.REQUIRED_STAGES.items()}}, sort_keys=True))
"""


def obs_stages():
    o = child(STAGES)
    return {"table": o["table"], "view": o["view"]}, o["api"]


def cell_stage_key_compat(frozen):
    got, api = obs_stages()
    want = frozen["stages"]
    diff = sorted(k for k in want["table"] if got["table"].get(k) != want["table"][k])
    ok = not diff and sorted(got["table"]) == sorted(want["table"]) and got["view"] == want["view"]
    return ok, f"API={api} · 27 조합 중 다른 값 {diff or '없음'} · 스킬 이름 보기 {'같다' if got['view'] == want['view'] else '다르다'}"


def cell_history_kinds():
    m = mini_ledger()
    b1 = m["runs"]["B1"]
    led = os.path.join(TD, "led", "history", "ledger.jsonl")
    os.makedirs(os.path.dirname(led))
    steps = [ab(*collect_args(b1, ledger=led, run_id="H1")), ab("recollect", "--ledger", led, "--run-id", "H1"),
             ab(*collect_args(b1, ledger=led, run_id="H1"))]
    if [s.returncode for s in steps] != [0, 0, 0]:
        raise Cell("prep-collect", f"collect · recollect · collect exit {[s.returncode for s in steps]}")
    r = ab("show", "--ledger", led, "--history", "H1")
    if r.returncode != 0:
        raise Cell("no-history", f"show --history exit {r.returncode} {(r.stderr or r.stdout).strip()[-140:]}")
    import re
    lines = [x for x in r.stdout.splitlines() if re.match(r"^\s+\d+ ", x)]
    kinds = [x.split()[1] for x in lines]
    win = child("import ab_ledger as m\nr = m.load(ARGS[0])[0]['H1']\nprint(json.dumps([r.get('origin'), r.get('measure_seq')]))", led)
    ok = (kinds[:1] == ["collect#1"] and len(kinds) == 3 and kinds[1].startswith("recollect") and kinds[2] == "collect#2"
          and lines[-1].endswith("← judge") and win == ["collect", 2])
    return ok, f"이력 {kinds} · 마지막 줄 judge 표시 {bool(lines) and lines[-1].endswith('← judge')} · load() 승자 {win}"


def cell_history_legacy_winner():
    m = mini_ledger()
    row = last_run(m["ledger"], "B1")
    for k in ("origin", "measure_seq"):
        row.pop(k, None)
    second = json.loads(json.dumps(row))
    second["wall"]["total_s"] = 12345.0
    led = os.path.join(TD, "led", "legacy-winner", "ledger.jsonl")
    os.makedirs(os.path.dirname(led))
    open(led, "w", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n" + json.dumps(second, ensure_ascii=False) + "\n")
    win = child("import ab_ledger as m\nprint(json.dumps(m.load(ARGS[0])[0]['B1']['wall']['total_s']))", led)
    r = ab("show", "--ledger", led)
    ok = win == 12345.0 and r.returncode == 0 and "wall=12345.0" in r.stdout
    return ok, f"load() 승자 wall {win}(기대 12345.0 — 마지막 행) · show exit {r.returncode}"


def judge_out(argv):
    r = ab(*argv)
    return r.returncode, tok(r.stdout)


def cell_formal_requires_sources():
    m = mini_ledger()
    base = ["judge", "--ledger", m["ledger"], "--phase", "baseline", "--workflows", "fz-review", "--min-runs", "2", "--formal"]
    c1, o1 = judge_out(base + ["--plugin-sha", m["psha"]])
    c2, o2 = judge_out(base + ["--verify-sources", "transcript"])
    ok = c1 == 2 and "FORMAL-SOURCES-MISSING" in o1 and c2 == 2 and "FORMAL-PLUGIN-SHA-MISSING" in o2
    if not ok and c1 == c2 == 2 and not o1.strip() and not o2.strip():
        raise Cell("no-formal-flag", "judge 가 --formal 을 모른다(argparse 거부 exit 2 · 태그 없음)")
    return ok, f"원천 없음 exit {c1} {o1.strip()[:80]!r} · SHA 없음 exit {c2} {o2.strip()[:80]!r}"


def cell_formal_with_sources():
    m = mini_ledger()
    argvs = dict(judge_argvs(m))
    pairs = []
    for name in ("baseline-valid-2-of-6", "baseline-min-3-fails"):
        plain, formal = judge_out(argvs[name]), judge_out(argvs[name] + ["--formal"])
        pairs.append((name, plain, formal))
    if all(f[0] == 2 and not f[1].strip() for _, _, f in pairs):
        raise Cell("no-formal-flag", "judge 가 --formal 을 모른다(argparse 거부 exit 2)")
    bad = [n for n, p, f in pairs if not (f[0] == p[0] and f[1].splitlines()[:1] and f[1].splitlines()[0].startswith("formal: ")
                                          and f[1].splitlines()[1:] == p[1].splitlines())]
    return not bad, f"exit (plain, formal) {[(p[0], f[0]) for _, p, f in pairs]} · 머리 줄 하나 외 다른 출력 {bad or '없음'}"


def obs_judges():
    m = mini_ledger()
    return [[n, *judge_out(a)] for n, a in judge_argvs(m)]


def cell_legacy_argv_unchanged(frozen):
    got, want = obs_judges(), frozen["judges"]
    diff = [w[0] for g, w in zip(got, want) if g != w] + (["count"] if len(got) != len(want) else [])
    return not diff, f"argv {len(want)}종 중 stdout · exit 이 다른 것 {diff or '없음'}"


def cell_clock_endpoint():
    led, row = clock_run()
    v = variants()
    w = row["wall"]
    ok = row["complete"]["ok"] is True and w["end"] == "2026-01-01T00:25:02+00:00" and w["total_s"] == 1502.0
    return ok, f"complete={row['complete']['ok']} {tok(str(row['complete']['why']))[:160]} · end {w['end']} · total {w['total_s']}"


def cell_clock_overrides_stale_parser():
    mini_ledger()
    v = variants()
    led, r = collect_into("clock-stale", v["b1"], run_id="STL", transcript=v["t_stale"], artifact=[v["sart"]],
                          endpoint_clock=v["c_stale"])
    if r.returncode != 0:
        raise Cell("no-clock-flag", f"collect --endpoint-clock exit {r.returncode}")
    row = last_run(led, "STL")
    w = row["wall"]
    md = w.get("mtime_delta_s")
    ok = (row["complete"]["ok"] is True and w["end"] == "2026-01-01T00:40:05+00:00" and md is not None and abs(md) <= 5
          and (w.get("clock") or {}).get("parser_end") == "2026-01-01T00:25:02+00:00")
    return ok, (f"complete={row['complete']['ok']} · end {w['end']}(기대 00:40:05) · mtimeΔ {md} · 파서 끝점 "
                f"{(w.get('clock') or {}).get('parser_end')}")


def cell_clock_mtime_mismatch():
    mini_ledger()
    v = variants()
    led, r = collect_into("clock-bad", v["b1"], run_id="BAD", transcript=v["t_make"], endpoint_clock=v["c_bad"])
    if r.returncode != 0:
        raise Cell("no-clock-flag", f"collect --endpoint-clock exit {r.returncode}")
    c = last_run(led, "BAD")["complete"]
    hit = [x for x in c["why"] if "끝점 시계 mtime 불일치" in x]
    return (c["ok"] is False and bool(hit)), f"complete={c['ok']} · 사유 {tok(str(hit))[:160] or '없음'}"


def cell_clock_spec_stored():
    led, row = clock_run()
    v = variants()
    ca = row["collect_args"]
    cp = ca.get("endpoint_clock")
    ok = (ca.get("spec") == "collect/1" and isinstance(cp, str) and os.path.isfile(cp) and cp != v["c_make"]
          and ca.get("endpoint_clock_source") == v["c_make"])
    return ok, f"spec={ca.get('spec')} · endpoint_clock={tok(cp)} · source={tok(ca.get('endpoint_clock_source'))}"


def cell_clock_evidence_copy():
    led, row = clock_run()
    v = variants()
    src = (row.get("sources") or {}).get("endpoint_clock") or {}
    cp = src.get("path")
    ok = (isinstance(cp, str) and os.path.isfile(cp) and sha256(cp) == sha256(v["c_make"]) == src.get("sha256")
          and src.get("original") == v["c_make"] and cp == row["collect_args"].get("endpoint_clock"))
    return ok, f"사본 {tok(cp)} · 바이트 일치 {isinstance(cp, str) and os.path.isfile(cp) and sha256(cp) == sha256(v['c_make'])}"


def cell_clock_recollect_reproduce():
    led, row = clock_run()
    v = variants()
    orig = open(v["c_make"], encoding="utf-8").read()
    try:
        open(v["c_make"], "w", encoding="utf-8").write(orig.replace("00:25:02", "00:10:00"))
        r1 = ab("recollect", "--ledger", led, "--run-id", "CLK")
        a = last_run(led, "CLK")
        os.unlink(v["c_make"])
        r2 = ab("recollect", "--ledger", led, "--run-id", "CLK")
        b = last_run(led, "CLK")
    finally:
        open(v["c_make"], "w", encoding="utf-8").write(orig)
    ok = (r1.returncode == r2.returncode == 0 and a["wall"]["end"] == b["wall"]["end"] == row["wall"]["end"]
          and a["complete"]["ok"] == b["complete"]["ok"] == row["complete"]["ok"])
    return ok, (f"변조 뒤 exit {r1.returncode} end {a['wall']['end']} · 삭제 뒤 exit {r2.returncode} end {b['wall']['end']} · "
                f"원래 {row['wall']['end']}")


def obs_clock_absent():
    mini_ledger()
    v = variants()
    out = {}
    for name, over in (("b1", {}), ("make", {"transcript": v["t_make"]}),
                       ("stale", {"transcript": v["t_stale"], "artifact": [v["sart"]]})):
        led, r = collect_into(f"absent-{name}", v["b1"], run_id=f"A-{name}", **over)
        row = last_run(led, f"A-{name}")
        out[name] = tokj({"exit": r.returncode, "complete": row["complete"],
                          "wall": {k: row["wall"].get(k) for k in ("end", "total_s", "mtime_delta_s")}})
    return out


def cell_clock_absent_unchanged(frozen):
    got, want = obs_clock_absent(), frozen["clock_absent"]
    diff = sorted(k for k in want if got.get(k) != want[k])
    return not diff, f"시계 없는 collect 3종 중 기준과 다른 것 {diff or '없음'}"


CELLS = {"split-size": cell_split_size, "entrypoint": cell_entrypoint,
         "selftest-outside-fingerprint": cell_selftest_outside_fingerprint, "fingerprint-coverage": cell_fingerprint_coverage,
         "criteria-table": cell_criteria_table, "criteria-dispatch": cell_criteria_dispatch,
         "collect-spec-keys": cell_collect_spec_keys, "collect-spec-legacy": cell_collect_spec_legacy,
         "single-parse": cell_single_parse, "single-parse-equal": cell_single_parse_equal,
         "stage-key-rename": cell_stage_key_rename, "stage-key-compat": cell_stage_key_compat,
         "history-kinds": cell_history_kinds, "history-legacy-winner": cell_history_legacy_winner,
         "formal-requires-sources": cell_formal_requires_sources, "formal-with-sources": cell_formal_with_sources,
         "legacy-argv-unchanged": cell_legacy_argv_unchanged, "clock-endpoint": cell_clock_endpoint,
         "clock-overrides-stale-parser": cell_clock_overrides_stale_parser, "clock-mtime-mismatch": cell_clock_mtime_mismatch,
         "clock-spec-stored": cell_clock_spec_stored, "clock-evidence-copy": cell_clock_evidence_copy,
         "clock-recollect-reproduce": cell_clock_recollect_reproduce, "clock-absent-unchanged": cell_clock_absent_unchanged}
NEEDS_FROZEN = {"single-parse-equal", "stage-key-compat", "legacy-argv-unchanged", "clock-absent-unchanged"}


def main():
    if EMIT:
        try:
            stages, _ = obs_stages()
            print(json.dumps({"wf_summary": obs_wf_summary(), "stages": stages, "judges": obs_judges(),
                              "clock_absent": obs_clock_absent()}, ensure_ascii=False, indent=1, sort_keys=True))
        except Exception as e:  # noqa: BLE001
            print(f"SETUP 얼린 값을 만들지 못했다 {type(e).__name__}: {e}")
            return 3
        return 0
    try:
        frozen = json.load(open(FROZEN, encoding="utf-8"))
        mini()
    except Setup as e:
        print(f"SETUP {e}")
        return 3
    except Exception as e:  # noqa: BLE001 — fixture 복원 · 얼린 값 읽기 실패는 준비 실패다
        print(f"SETUP 준비 실패 {type(e).__name__}: {e}")
        return 3
    want = [c for c in ONLY.split(",") if c] or sorted(EXPECTED)
    unknown = [c for c in want if c not in EXPECTED]
    if unknown:
        print(f"SETUP 모르는 셀 {unknown}")
        return 3
    ran, fails = [], []
    for name in want:
        tag, t0 = "", time.time()
        try:
            ok, detail = CELLS[name](frozen) if name in NEEDS_FROZEN else CELLS[name]()
        except Setup as e:
            print(f"SETUP {e}")
            return 3
        except Cell as e:
            ok, detail, tag = False, str(e), f" [{e.tag}]"
        except Exception as e:  # noqa: BLE001 — 셀 안 예외는 그 셀 FAIL
            ok, detail, tag = False, traceback.format_exc().strip().splitlines()[-1][:200], f" [exception:{type(e).__name__}]"
        ran.append(name)
        if not ok:
            fails.append(name)
        print(f"CELL {name} {EXPECTED[name]} {'PASS' if ok else 'FAIL'}{tag} — {tok(str(detail)).replace(chr(10), ' ⏎ ')[:400]} ({time.time() - t0:.1f}s)")
    bad_set = not ONLY and sorted(ran) != sorted(EXPECTED)
    if bad_set:
        print(f"FAIL 기대 셀 집합 — 빠짐 {sorted(set(EXPECTED) - set(ran))} · 더함 {sorted(set(ran) - set(EXPECTED))}")
    print(f"CELLS ran={len(ran)} pass={len(ran) - len(fails)} fail={len(fails)} failed={','.join(sorted(fails)) or '-'} "
          f"names={','.join(sorted(ran))}")
    return 1 if fails or bad_set else 0


sys.exit(main())
PY
