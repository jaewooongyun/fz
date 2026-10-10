#!/bin/bash
# Workflow journal.jsonl 실표본 재생 (F-358 · F-387) — health-check 글롭(tests/fixtures/*/*/run.sh)에서 인자 없이 돈다.
#
# 표본: plan-lean2 Workflow run 1개를 스크럽한 것(provenance.json · samples/wf/). 1단 병렬 agent 3개가 실패하고 다음 날 같은
#   runId 로 재개됐다 — journal launched 1 · started 7 · failed 3 · result 4, 시각 필드 없음(순서만이 시도 경계의 근거).
#   대상 트리의 scripts/fz_wf_metrics.py 공개 함수 `read_wf` 로 읽는다. 기대값 = 마지막 시도 wall 2214.4s · 크리티컬 패스
#   2212.7s · failed_attempts 1 · 마지막 시도 agent 4/7 · 실패 구간 6870.6s · journal_results 4 · 오류 0. 시도를 합치는
#   파서는 wall 을 57766.9s(실패 시도 시작 ~ 재개 끝)로 읽는다 — 같은 표본으로 FAIL 한다.
# 셀(순서 고정 · F-408 — 돈 셀 이름이 다르면 FAIL)
#   provenance     필수 키 · samples 모양 · 해시 재계산. 표본 부재는 UNRUN(exit 2)
#   scrub          표본 스크럽 감사(홈 경로 · 비밀값 · journal result 본문 · 허용 키 밖 · 자유 문장) 위반 0
#   contamination  사본에 오염을 넣으면 감사 · 해시가 잡는다 — 홈 경로 · 비밀값 · result 본문 · 원문 이벤트 키 · meta 키 ·
#                  표본 삭제(UNRUN)
#   replay         read_wf → wall · critical_path · failed_attempts · last_attempt_agents · failed_span · n_agents ·
#                  journal_results · out_tok · errors = 기대값
#   parser-guard   journal 을 마지막 failed 에서 자르면(재개 기록 없음) wall · 크리티컬 패스를 숫자가 아니라 UNRUN(no-resume)으로 둔다
# 출력: 셀마다 `PASS|FAIL|SETUP <셀>: …` · 요약 `JOURNAL-REPLAY-OK 5/5` | `-FAIL` | `-UNRUN` | `-SETUP` · 끝 줄 `CELLS n=<수> ran=<…>`
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
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-journal-replay.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
TD="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -I -B - "$TREE" "$HERE" "$TD" "$LIB" <<'PY'
import importlib.util
import os
import shutil
import sys

sys.dont_write_bytecode = True   # ⛔ 대상 트리(기준 clone 포함) · 이 트리의 tests/lib 에 __pycache__ 를 쓰지 않는다
TREE, HERE, TD, LIB = sys.argv[1:5]


def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


R = load("sample_replay", LIB)
WF = os.path.join(HERE, "samples", "wf")
JOURNAL = "samples/wf/journal.jsonl"
EXPECTED = ("provenance", "scrub", "contamination", "replay", "parser-guard")
WANT = {"failed_attempts": 1, "last_attempt_agents": 4, "n_agents": 7, "journal_results": 4, "attempt_ambiguous": None,
        "out_tok": 503752, "errors": []}
WANT_S, TOL = {"wall": 2214.418, "critical_path": 2212.712, "failed_span": 6870.552}, 1.0


def metrics():
    return load("fz_wf_metrics_target", os.path.join(TREE, "scripts", "fz_wf_metrics.py"))


def cell_contamination(prov):
    meta = sorted(x["file"] for x in prov["samples"] if x["file"].endswith(".meta.json"))[0]
    agent = sorted(x["file"] for x in prov["samples"] if x["file"].endswith(".jsonl") and "/agent-" in x["file"])[0]
    result = lambda t: t.replace('"result":{"', '"result":{"원문":"계획 본문","', 1)
    raw_key = lambda t: t.replace('{"type": "user", ', '{"type": "user", "sessionId": "s", ', 1)
    meta_key = lambda t: t.replace("{", '{"prompt":"원문 프롬프트",', 1)
    return R.contamination_cell(HERE, TD, JOURNAL, [
        ("result-body", JOURNAL, result, "structure"), ("raw-event-key", agent, raw_key, "structure"),
        ("meta-key", meta, meta_key, "structure")])


def cell_replay(prov):
    r = metrics().read_wf(WF)
    got = {k: r.get(k, "(없음)") for k in WANT}
    sec = {k: r.get(k, "(없음)") for k in WANT_S}
    ok = got == WANT and all(isinstance(sec[k], (int, float)) and abs(sec[k] - v) <= TOL for k, v in WANT_S.items())
    return ok, f"read_wf {sec} {got} (기대 {WANT_S}±{TOL} {WANT})"


def cell_parser_guard(prov):
    d = os.path.join(TD, "wf-cut")
    shutil.copytree(WF, d)
    p = os.path.join(d, "journal.jsonl")
    with open(p, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    cut = max(i for i, x in enumerate(lines) if '"type":"failed"' in x) + 1
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines[:cut]) + "\n")
    r = metrics().read_wf(d)
    amb = r.get("attempt_ambiguous", "(없음)")
    ok = (r.get("wall", 0) is None and r.get("critical_path", 0) is None and "failed_attempts" in r and r["failed_attempts"] is None
          and isinstance(amb, str) and amb.startswith("no-resume")
          and any(e.startswith("UNRUN: 시도 경계 모호") for e in r.get("errors") or []))
    return ok, (f"journal 을 마지막 failed({cut}줄)에서 자름 → wall={r.get('wall')} critical_path={r.get('critical_path')} "
                f"failed_attempts={r.get('failed_attempts', '(없음)')} ambiguous={str(amb)[:40]} (기대 None · None · None · no-resume)")


sys.exit(R.run("journal-replay", HERE, EXPECTED,
               [("contamination", cell_contamination), ("replay", cell_replay), ("parser-guard", cell_parser_guard)], TD))
PY
