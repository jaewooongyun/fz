#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. fz_wf_metrics 가 만든 집계 dict 만 받는다.
"""fz_wf_view.py — fz_wf_metrics 집계(wf dict)의 사람용 출력(상세 · §5.7 행). fz_wf_metrics 가 import 한다(단독 실행 없음).

계측기 파일 상한(1500줄 · tests/fixtures/ab/structure-d split-size)으로 fz_wf_metrics.py 에서 떼어 냈다 — 판정 코드가 아니라 출력이지만
fz_wf_metrics 가 머리에서 import 하므로 계측기 지문(ab_ledger_base.INSTRUMENTS)에 든다.
"""
from __future__ import annotations


def fmt(v, unit=""):
    return "unavailable" if v is None else f"{v}{unit}"


def _secs(wf: dict, key: str, nd=None) -> str:
    """wall · critical_path 칸. 시도 경계가 모호하면 unavailable 이 아니라 UNRUN(미판정)으로 적는다."""
    if wf.get("attempt_ambiguous"):
        return "UNRUN"
    v = wf[key]
    return fmt(None if v is None else (round(v) if nd is None else round(v, nd)), "s")


def _attempt_note(wf: dict) -> str:
    """실패 시도 · 재사용 구간 — wall 과 섞지 않고 따로 적는다. 단일 시도면 빈 문자열."""
    if wf.get("attempt_ambiguous"):
        return f"attempts=UNRUN — 시도 경계 모호: {wf['attempt_ambiguous']}"
    if not wf.get("failed_attempts"):
        return ""
    sp = lambda v: fmt(None if v is None else round(v, 1), "s")
    note = (f"failed_attempts={wf['failed_attempts']}  failed_span={sp(wf['failed_span'])}"
            f"  last_attempt_agents={wf['last_attempt_agents']}/{wf['n_agents']}")
    if wf["reused_agents"]:
        note += f"  reused_agents={','.join(wf['reused_agents'])}  reused_span={sp(wf['reused_span'])}"
    return note + "  (wall · critical_path = 마지막 시도)"


def print_detail(wf: dict) -> None:
    print(f"wf {wf['wf']}  agents={wf['n_agents']}  wall={_secs(wf, 'wall', 1)}"
          f"  critical_path={_secs(wf, 'critical_path', 1)}")
    lb = "≥" if wf["tokens_partial"] else ""
    print(f"  advisor={wf['advisor']}  advisor_calls={wf['advisor_calls']}  advisor_stalled={fmt(wf['advisor_stalled'])}"
          f"  out_tok={lb}{wf['out_tok']:,}  thinking={lb}{wf['thinking']:,}"
          f"  cache_r={wf['cache_read']:,}  cache_w={wf['cache_write']:,}  so_retries={wf['so_retries']}  so_errors={wf['so_errors']}"
          f"  journal_results={wf['journal_results']}")
    if _attempt_note(wf):
        print(f"  {_attempt_note(wf)}")
    order = {s: i for i, s in enumerate(["S0", "S0-reb", "S0-fin", "S1", "S2-impact", "S2-edge", "S2-arch",
                                         "S3-imp", "S3-edge", "S4", "S5",
                                         "L1-full", "L1-edge", "L1-impact", "L2-merge",
                                         "R1-arch", "R1-quality", "R1-correct", "R2-arch", "R2-quality",
                                         "R3-counter", "?"])}
    for a in sorted(wf["agents"], key=lambda x: (order.get(x["stage"], 99), x["file"])):
        ot = "unavail" if a["out_tok"] is None else f"{a['out_tok']:,}"
        th = "unavail" if a["thinking"] is None else f"{a['thinking']:,}"
        rc = f" ret={a['result_chars']:,}자" if a.get("result_chars") else ""
        st = f" stall={fmt(a['advisor_stalled'])}" if a["advisor_stalled"] != 0 else ""
        at = {"earlier": " [failed-attempt]", "reused": " [reused]"}.get(a.get("attempt"), "")
        print(f"    {a['stage']:9} {a['model']:8} dur={fmt(round(a['dur'], 1) if a['dur'] is not None else None, 's'):>9}"
              f" turns={a['turns']:>3} tools={a['tools']:>3} out={ot:>9} think={th:>9}"
              f" adv={a['advisor']}{st} so={a['so_calls']}/{a['so_errors']}{rc}{at}")
        if a.get("forwarded"):
            print(f"      전달 요청: {a['forwarded']!r} — 워커가 본 사용자 글이다 · 재는 대상을 말하면 대조군이 아니다(F-660)")
    for e in wf["errors"]:
        print(f"  ⚠️ {e}")


def print_row(wf: dict) -> None:
    """experiment-log §5.7 fz-plan 테이블 행 형식 (agentCalls·nullCount·stages·fallback·wall-clock)."""
    stages = len([s for s in wf["stages_seen"] if s != "?"])
    lb = "≥" if wf["tokens_partial"] else ""
    # ⛔ 열은 늘리지 않는다 — 스톨 · 실패 시도는 마지막 비고 칸에 덧붙인다(wall 칸은 마지막 시도 값)
    sec = lambda v: fmt(None if v is None else round(v), "s")
    att = ""
    if wf.get("attempt_ambiguous"):
        att = " · 시도 경계 모호(wall UNRUN)"
    elif wf.get("failed_attempts"):
        att = f" · failed_attempts {wf['failed_attempts']} (실패 구간 {sec(wf['failed_span'])})"
        if wf["reused_agents"]:
            att += f" · reused {len(wf['reused_agents'])} ({sec(wf['reused_span'])})"
    print(f"| N | DATE | {wf['n_agents']} | {max(0, wf['n_agents'] - wf['journal_results'])} | "
          f"{stages} | 0 | {_secs(wf, 'wall')} | "
          f"advisor {wf['advisor']} · advisor_stalled {fmt(wf['advisor_stalled'])} · so_retries {wf['so_retries']} · out_tok {lb}{wf['out_tok']:,} "
          f"(thinking {wf['thinking']:,}) · critical_path {_secs(wf, 'critical_path')}{att} |")
