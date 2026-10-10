# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import 와 계측기 해시에 이 파일의 디렉토리만 쓴다.
"""ab_ledger_base.py — A/B 원장 계측기의 한 부분: 공통 상수 · 원천 읽기 도구 · 계측기 지문(instrument_sha).

진입점 · 설계 · 측정 규약은 ab_ledger.py 머리말에 있다(이 파일은 그 실행 코드를 나눠 담는다).
"""
from __future__ import annotations

import hashlib
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PASS, FAIL, UNRUN = 0, 1, 2
SCHEMA = "ab-ledger/1"
STATE_SCHEMA = "ab-state/1"
SEVERITIES = ("critical", "major", "minor", "suggestion")
GATED = ("critical", "major")
AXES6 = ("idiom", "naming", "architecture", "ui_structure", "placement", "design_alternative")
AXES_ALLOWED = AXES6 + ("correctness",)
DEFAULT_MODEL, DEFAULT_EFFORT = "claude-opus-5-5", "xhigh"   # Sprint Contract 제약 — 워커는 Opus 5.5 xhigh
LINE_TOL = 3            # 인용 줄이 라벨 범위에서 이만큼 벗어나도 같은 지적으로 본다
WALL_XCHECK_PCT = 5.0   # wall_workflow 두 자의 허용 차이
MTIME_TOL_S = 5.0       # 최종 산출물 기록 이벤트 ↔ 파일 mtime 허용 차이
PHASES = ("baseline", "release-smoke", "change")
# 계측기 지문 = 실행 중 import 되는 형제 모듈 **전부**(F-335 ②). ⛔ self-test 모듈(ab_ledger_selftest.py)은 넣지 않는다 —
#    판정 코드가 아니고, 넣으면 self-test 만 고쳐도 지문이 바뀌어 채점 행이 낡는다. ⛔ 실행 모듈을 새로 나누면 여기에 더한다
#    (빠뜨리면 그 모듈을 고쳐도 지문이 그대로다 — fail-open). 형제 모듈은 정적 import 만 쓴다(문자열 동적 적재 금지).
INSTRUMENTS = ("ab_ledger.py", "ab_ledger_base.py", "ab_ledger_transcript.py", "ab_ledger_collect.py", "ab_ledger_judge.py",
               "ab_ledger_gpt.py", "fz_wf_metrics.py", "freeze_baseline.py")
# 구현한 run 기준 목록(IMPLEMENTED)은 판정 표 CRITERIA 의 키다 — ab_ledger_judge.py. S27 의 SC-1 · SC-2 · AC-2 · AC-3 은
#    run 행이 아니라 gpt-pass 행(런처 첫 패스)을 판정한다 — `GPT_PASS_CRIT` · judge_gpt(run 기준과 섞지 않는다).
SOURCE_KINDS = ("transcript", "wf-metrics", "start-state", "input-hash", "instrument-sha")
GPT_PASS_CRIT = ("SC-1", "SC-2", "AC-2", "AC-3")


# ── 공통 ────────────────────────────────────────────────────────────────
def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha_obj(o) -> str:
    return sha_text(json.dumps(o, ensure_ascii=False, sort_keys=True))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def iso(t):
    return t.isoformat() if t else None


def secs(a, b):
    return round((b - a).total_seconds(), 3) if a and b else None


def norm_model(m):
    """`claude-opus-5-5[1m]` 과 `claude-opus-5-5` 는 같은 모델이다(컨텍스트 창 표기만 다르다)."""
    return re.sub(r"\[[^\]]*\]$", "", m) if isinstance(m, str) else m


def iter_jsonl(path):
    evs, bad = [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(ev, dict):
                evs.append(ev)
            else:
                bad += 1
    return evs, bad


def instrument_sha() -> str:
    h = hashlib.sha256()
    for n in INSTRUMENTS:
        with open(os.path.join(SCRIPT_DIR, n), "rb") as fh:
            h.update(n.encode("utf-8") + b"\0" + fh.read())
    return h.hexdigest()[:16]
