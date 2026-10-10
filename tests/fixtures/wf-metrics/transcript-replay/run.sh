#!/bin/bash
# Claude Code agent transcript 실표본 재생 (F-358 · F-382) — health-check 글롭(tests/fixtures/*/*/run.sh)에서 인자 없이 돈다.
#
# 표본: code-pair Workflow 워커 트랜스크립트 1개를 스크럽한 것(provenance.json · samples/). advisor 호출 블록
#   (`server_tool_use` name=advisor, id=srvtoolu_…)이 결과(`advisor_tool_result`) 없이 34분 42초 뒤 사용자 중단까지 멈췄다.
#   대상 트리의 scripts/fz_wf_metrics.py 공개 함수 `read_agent` 로 읽는다. 기대값 = advisor 0(결과 기준) · advisor_calls 1 ·
#   advisor_stalled 1 · 턴 1 · 도구 13 · 출력 토큰 193 · dur 2250.1s. 호출 블록을 세지 않는 파서는 스톨이 0 으로 사라진다 —
#   같은 표본으로 FAIL 한다.
# 셀(순서 고정 · F-408 — 돈 셀 이름이 다르면 FAIL)
#   provenance     필수 키 · samples 모양 · 해시 재계산. 표본 부재는 UNRUN(exit 2)
#   scrub          표본 스크럽 감사(홈 경로 · 비밀값 · 허용 키 밖 · 자유 문장 · thinking 본문) 위반 0
#   contamination  사본에 오염을 넣으면 감사 · 해시가 잡는다 — 홈 경로 · 비밀값 · 원문 이벤트 키 · text 본문 · thinking 본문 ·
#                  표본 삭제(UNRUN)
#   replay         read_agent → advisor · advisor_calls · advisor_stalled · turns · tools · out_tok · dur = 기대값
#   parser-guard   호출 블록 없는 advisor 결과(호출 기록 누락)를 덧붙이면 스톨 수를 0 이 아니라 None(unavailable)으로 둔다
# 출력: 셀마다 `PASS|FAIL|SETUP <셀>: …` · 요약 `TRANSCRIPT-REPLAY-OK 5/5` | `-FAIL` | `-UNRUN` | `-SETUP` · 끝 줄 `CELLS n=<수> ran=<…>`
# exit: 0 전 셀 통과 · 1 단언 실패(형식 · 해시 · 스크럽 위반 · 읽기 오류 포함) · 2 UNRUN(표본 부재 · python3 · 대상 계측기 부재) ·
#       3 준비 실패(인자 · 임시 폴더 · 셀 안 예외)
# ⛔ 대상 트리에는 쓰지 않는다(python -B). 변형 사본은 기본 TMPDIR 의 임시 폴더에 만들고 지운다.
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
[ -f "$TREE/scripts/fz_wf_metrics.py" ] || { echo "UNRUN: 대상 계측기 없음 $TREE/scripts/fz_wf_metrics.py"; exit 2; }
LIB="$HERE/../../../lib/sample_replay.py"
[ -f "$LIB" ] || { echo "SETUP 공통 러너 없음: $LIB"; exit 3; }
# ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 실패해도 `cd ""` 가 성공한다(F-355)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-transcript-replay.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
TD="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -I -B - "$TREE" "$HERE" "$TD" "$LIB" <<'PY'
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True   # ⛔ 대상 트리(기준 clone 포함) · 이 트리의 tests/lib 에 __pycache__ 를 쓰지 않는다
TREE, HERE, TD, LIB = sys.argv[1:5]


def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


R = load("sample_replay", LIB)
SAMPLE = "samples/agent-stall.jsonl"
EXPECTED = ("provenance", "scrub", "contamination", "replay", "parser-guard")
WANT = {"advisor": 0, "advisor_calls": 1, "advisor_stalled": 1, "turns": 1, "tools": 13, "out_tok": 193}
WANT_DUR, TOL = 2250.103, 0.5


def metrics():
    return load("fz_wf_metrics_target", os.path.join(TREE, "scripts", "fz_wf_metrics.py"))


def cell_contamination(prov):
    raw_key = lambda t: t.replace('{"type": "user", ', '{"type": "user", "sessionId": "s", ', 1)
    text = lambda t: t.replace('{"type": "text", "text": ""}', '{"type": "text", "text": "구현 단계 설명 원문"}', 1)
    think = lambda t: t.replace('{"type": "thinking", "thinking": ""}', '{"type": "thinking", "thinking": "추론 원문"}', 1)
    return R.contamination_cell(HERE, TD, SAMPLE, [
        ("raw-event-key", SAMPLE, raw_key, "structure"), ("text-body", SAMPLE, text, "structure"),
        ("thinking-body", SAMPLE, think, "structure")])


def cell_replay(prov):
    a = metrics().read_agent(os.path.join(HERE, SAMPLE))
    got = {k: a.get(k, "(없음)") for k in WANT}
    dur = a.get("dur")
    ok = got == WANT and dur is not None and abs(dur - WANT_DUR) <= TOL
    return ok, f"read_agent {got} · dur={dur} (기대 {WANT} · dur={WANT_DUR}±{TOL})"


def cell_parser_guard(prov):
    with open(os.path.join(HERE, SAMPLE), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    last = json.loads(lines[-1])
    orphan = {"type": "assistant", "timestamp": last["timestamp"], "message": {"role": "assistant", "id": "msg_guard", "content": [
        {"type": "advisor_tool_result", "tool_use_id": "srvtoolu_guard", "content": {"type": "advisor_result"}}]}}
    p = os.path.join(TD, "agent-guard.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines + [json.dumps(orphan, ensure_ascii=False)]) + "\n")
    a = metrics().read_agent(p)
    ok = "advisor_stalled" in a and a["advisor_stalled"] is None and a.get("advisor") == 1 and a.get("advisor_calls") == 1
    return ok, (f"호출 없는 결과 주입 → advisor={a.get('advisor')} advisor_calls={a.get('advisor_calls', '(없음)')} "
                f"advisor_stalled={a.get('advisor_stalled', '(없음)')} (기대 1 · 1 · None — 보이는 호출만으로 0 을 내지 않는다)")


sys.exit(R.run("transcript-replay", HERE, EXPECTED,
               [("contamination", cell_contamination), ("replay", cell_replay), ("parser-guard", cell_parser_guard)], TD))
PY
