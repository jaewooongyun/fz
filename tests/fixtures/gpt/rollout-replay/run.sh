#!/bin/bash
# GPT 스트림 로그(rollout) 실표본 재생 (F-358 · F-361) — health-check 글롭(tests/fixtures/*/*/run.sh)에서 인자 없이 돈다.
#
# 표본: 2-run 묶음 run 1 의 GPT 검증 2라운드 기록을 스크럽한 것(provenance.json · samples/). 1라운드 스트림 로그 둘을
#   2라운드 전에 `mv … .r1.json.stream.log` 로 옮겼다. 대상 트리의 scripts/ab_ledger.py `collect`(CLI 진입점)로 Lead
#   transcript 의 GPT 호출 4개와 스트림 로그 배너(ANSI 섞인 실제 머리 · model · reasoning effort · CLI 버전)를 1:1 로 잇는다.
#   기대값 = 채취 당시 원장 행의 gpt 칸(calls 4 · ok 4 · 배너 4 · 미연결 0). 옮긴 로그를 따라가지 않는 파서는 직접 경로에
#   남은 2라운드 로그가 1라운드 시간창 밖이라 배너 2 · 미연결 2 로 읽는다 — 같은 표본으로 FAIL 한다.
# 셀(순서 고정 · F-408 — 돈 셀 이름이 다르면 FAIL)
#   provenance     필수 키 · samples 모양 · 해시 재계산. 표본 부재는 UNRUN(exit 2)
#   scrub          표본 스크럽 감사(홈 경로 · 비밀값 · 배너 밖 본문 · transcript 허용 키 밖 · 자유 문장) 위반 0
#   contamination  사본에 오염을 넣으면 감사 · 해시가 잡는다 — 홈 경로 · 비밀값 · 배너 뒤 본문 · 원문 이벤트 키 · 자유 문장 ·
#                  표본 삭제(UNRUN)
#   replay         collect → gpt calls · ok · failed · banners · unlinked · models · efforts · versions = 기대값
#   parser-guard   이동 기록(mv)을 transcript 에서 지우면 빈자리를 다른 라운드 로그로 채우지 않는다(배너 2 · 미연결 2)
# 출력: 셀마다 `PASS|FAIL|SETUP <셀>: …` · 요약 `ROLLOUT-REPLAY-OK 5/5` | `-FAIL` | `-UNRUN` | `-SETUP` · 끝 줄 `CELLS n=<수> ran=<…>`
# exit: 0 전 셀 통과 · 1 단언 실패(형식 · 해시 · 스크럽 위반 · 읽기 오류 포함) · 2 UNRUN(표본 부재 · python3 · 대상 계측기 부재) ·
#       3 준비 실패(인자 · 임시 폴더 · 셀 안 예외 · collect 비정상 종료)
# ⛔ 대상 트리에는 쓰지 않는다(python -B). 재구성 · 원장은 기본 TMPDIR 의 임시 폴더에 만들고 지운다. HOME 은 바꾸지 않는다.
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 파일이 든 트리)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
TREE="$(cd "$HERE/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 없음"; exit 2; }
[ -f "$TREE/scripts/ab_ledger.py" ] || { echo "UNRUN: 대상 계측기 없음 $TREE/scripts/ab_ledger.py"; exit 2; }
LIB="$HERE/../../../lib/sample_replay.py"
[ -f "$LIB" ] || { echo "SETUP 공통 러너 없음: $LIB"; exit 3; }
# ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 실패해도 `cd ""` 가 성공한다(F-355)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-rollout-replay.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
TD="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }

GIT_OPTIONAL_LOCKS=0 PYTHONDONTWRITEBYTECODE=1 python3 -I -B - "$TREE" "$HERE" "$TD" "$LIB" <<'PY'
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True   # ⛔ 대상 트리(기준 clone 포함) · 이 트리의 tests/lib 에 __pycache__ 를 쓰지 않는다
TREE, HERE, TD, LIB = sys.argv[1:5]
sp = importlib.util.spec_from_file_location("sample_replay", LIB)
R = importlib.util.module_from_spec(sp)
sp.loader.exec_module(R)
AB = os.path.join(TREE, "scripts", "ab_ledger.py")
EXPECTED = ("provenance", "scrub", "contamination", "replay", "parser-guard")
# 채취 당시 원장 행(옮긴 로그를 따라간 계측기로 수집)의 gpt 칸
WANT = {"calls": 4, "ok": 4, "failed": 0, "banners": 4, "unlinked": 0,
        "models": ["gpt-6.1-sol"], "efforts": ["high"], "versions": ["0.159.2"]}
GUARD = {"calls": 4, "ok": 4, "banners": 2, "unlinked": 2}
MV = "for f in gpt-verify gpt-verify-gates; do mv $W/$f.json.stream.log $W/$f.r1.json.stream.log; done; "


def materialize(mutate=None):
    """표본 → 임시 run 폴더. 자리표시자 @RUN@ = 그 폴더 · @TMP@ = 없는 폴더(하네스 /tmp 원본이 사라진 상태 —
    작업 출력은 run 직후 복사한 tasks 폴더에서 같은 이름을 찾는다). mtime 은 layout.json 의 채취 값으로 되돌린다."""
    dst = tempfile.mkdtemp(dir=TD)
    with open(os.path.join(HERE, "samples", "layout.json"), encoding="utf-8") as fh:
        lay = json.load(fh)
    for f in lay["files"]:
        p = os.path.join(dst, f["path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if "text" in f:
            text = f["text"]
        else:
            with open(os.path.join(HERE, f["from"]), encoding="utf-8") as fh:
                text = fh.read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text.replace("@RUN@", dst))
        os.utime(p, (f["mtime"], f["mtime"]))
    with open(os.path.join(HERE, lay["transcript"]), encoding="utf-8") as fh:
        t = fh.read()
    if mutate:
        t2 = mutate(t)
        if t2 == t:
            raise RuntimeError("transcript 변형이 표본을 바꾸지 못했다 — 변형 자리 부재")
        t = t2
    tp = os.path.join(dst, "lead.jsonl")
    with open(tp, "w", encoding="utf-8") as fh:
        fh.write(t.replace("@RUN@", dst).replace("@TMP@", os.path.join(dst, "gone-tmp")))
    return dst, lay, tp


def collect(mutate=None):
    dst, lay, tp = materialize(mutate)
    led = os.path.join(dst, "ledger.jsonl")
    cmd = ["python3", "-B", AB, "collect", "--ledger", led, "--workflow", "fz-plan", "--arm", "C", "--run", "1", "--order", "1",
           "--phase", "change", "--run-id", "replay", "--fixture", "plan-feature", "--transcript", tp,
           "--input-json", os.path.join(dst, "input.json"), "--state-pristine", os.path.join(dst, "pristine.json"),
           "--state-start", os.path.join(dst, "start.json"), "--state-end", os.path.join(dst, "end.json"),
           "--gpt-log-dir", os.path.join(dst, lay["gpt_log_dir"]), "--tasks-dir", os.path.join(dst, lay["tasks_dir"])]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"collect exit {r.returncode}: {(r.stdout + r.stderr)[-300:]}")
    with open(led, encoding="utf-8") as fh:
        rows = [json.loads(x) for x in fh if x.strip()]
    return [x for x in rows if x.get("type") == "run"][-1].get("gpt") or {}


def cell_contamination(prov):
    body = lambda t: t + "\x1b[36muser\x1b[0m\n(원문 프롬프트)\n"
    raw_key = lambda t: t.replace('{"type": "user", ', '{"type": "user", "sessionId": "s", ', 1)
    free = lambda t: t.replace("<command-args>(scrubbed)</command-args>", "<command-args>요구사항 원문</command-args>", 1)
    return R.contamination_cell(HERE, TD, "samples/lead.jsonl", [
        ("banner-body", "samples/logs/gpt-verify.r1.json.stream.log", body, "banner-only"),
        ("raw-event-key", "samples/lead.jsonl", raw_key, "structure"),
        ("free-text", "samples/lead.jsonl", free, "structure")])


def cell_replay(prov):
    g = collect()
    got = {k: g.get(k) for k in WANT}
    return got == WANT, f"gpt {got} (기대 {WANT})"


def cell_parser_guard(prov):
    g = collect(lambda t: t.replace(MV, "", 1))
    got = {k: g.get(k) for k in GUARD}
    return got == GUARD, f"이동 기록 삭제 → gpt {got} (기대 {GUARD} — 옮긴 곳을 추측하지 않는다)"


sys.exit(R.run("rollout-replay", HERE, EXPECTED,
               [("contamination", cell_contamination), ("replay", cell_replay), ("parser-guard", cell_parser_guard)], TD))
PY
