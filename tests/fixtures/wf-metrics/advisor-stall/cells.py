# advisor-stall · attempts 셀 (F-382 · F-387) — run.sh 가 부른다. 사용: python3 -B cells.py <트리> <stall|attempts|all>
# 셀을 임시 폴더에 합성하고, 정답은 이 파일이 **셀 정의에서 직접** 센다(대상 계측기 코드를 쓰지 않는다).
# 대상 트리의 scripts/fz_wf_metrics.py 를 모듈(read_wf)과 CLI(--wf 상세 · --row) 둘 다로 판독해 정답과 대조한다.
# 블록 꼴은 실제 기록에서 옮겼다: advisor 호출 = server_tool_use(name=advisor, id=srvtoolu_…) · 결과 = 별도 줄
# advisor_tool_result(tool_use_id) / journal = launched · started(key·agentId·label·phase) · failed(key·agentId) ·
# result(key·agentId·result) — 시각 필드 없음(순서만이 시도 경계의 근거다)
# exit: 0 전건 통과 · 1 METRICS-FAIL 태그 1건 이상 · 2 준비 실패(UNRUN: 표지) 또는 traceback
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

SESS = "sess-advisor-stall"
# 셀 이름 고정(F-408) — 판정한 셀이 이 집합과 다르면 METRICS-FAIL:cell-set-mismatch(셀을 지워도 통과하지 않게)
EXPECTED = {"stall": ("two_calls_one_result", "dup_result", "no_result", "no_advisor", "control_one_one"),
            "attempts": ("same_key_resume", "partial_reuse", "single_attempt", "ambiguous_not_restart", "ambiguous_no_resume",
                         "ambiguous_restart_after_boundary", "ambiguous_unplaced")}
RAN = []
TOL = 1.0
T0 = datetime.datetime(2026, 10, 1, 0, 0, 0)


def ts(sec):
    return (T0 + datetime.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ── stall 셀 (F-382) ─────────────────────────────────────────────────────────
ROLE = "[Workflow harness — computed task]\n[역할] 설계자 — 이 과제의 계획을 **혼자** 끝낸다."
INTERRUPT = [{"type": "text", "text": "[Request interrupted by user]"}]


def srv(i):
    return {"type": "server_tool_use", "id": "srvtoolu_%s" % i, "name": "advisor", "input": {}}


def res(i):
    return {"type": "advisor_tool_result", "tool_use_id": "srvtoolu_%s" % i,
            "content": {"type": "advisor_result", "text": "advice"}}


def asst(sec, mid, blocks, stop=None, out=0):
    m = {"id": mid, "role": "assistant", "content": blocks}
    if stop:
        m["stop_reason"] = stop
        m["usage"] = {"output_tokens": out}
    return {"type": "assistant", "timestamp": ts(sec), "message": m}


def user(sec, content):
    return {"type": "user", "timestamp": ts(sec), "message": {"role": "user", "content": content}}


def so_turn(sec, mid):
    return [asst(sec, mid, [{"type": "tool_use", "id": "so_" + mid, "name": "StructuredOutput", "input": {}}], "tool_use", 50),
            user(sec + 1, [{"type": "tool_result", "tool_use_id": "so_" + mid, "content": "ok"}])]


def stall_cells():
    """셀 → (트랜스크립트 줄, 반환 여부). 스톨은 실 사례(server_tool_use 1 · 결과 0 · 34분 뒤 사용자 중단) 꼴."""
    c = {}
    c["two_calls_one_result"] = ([user(0, ROLE),
                                   asst(10, "msg_1", [{"type": "thinking", "thinking": "t", "signature": "s"}]),
                                   asst(11, "msg_1", [srv("A1")]),
                                   asst(100, "msg_1", [res("A1")]),
                                   asst(101, "msg_1", [{"type": "text", "text": "go"}], "tool_use", 40),
                                   asst(200, "msg_2", [srv("A2")]),
                                   user(2283, INTERRUPT)], False)
    c["dup_result"] = ([user(0, ROLE),
                        asst(11, "msg_1", [srv("B1")]),
                        asst(100, "msg_1", [res("B1")]),
                        asst(100, "msg_1", [res("B1")]),
                        asst(101, "msg_1", [{"type": "text", "text": "go"}], "end_turn", 40)] + so_turn(200, "msg_2"), True)
    c["no_result"] = ([user(0, ROLE),
                       asst(10, "msg_1", [{"type": "thinking", "thinking": "t", "signature": "s"}]),
                       asst(11, "msg_1", [srv("C1")]),
                       user(2094, INTERRUPT)], False)
    c["no_advisor"] = ([user(0, ROLE),
                        asst(101, "msg_1", [{"type": "text", "text": "go"}], "end_turn", 40)] + so_turn(200, "msg_2"), True)
    c["control_one_one"] = ([user(0, ROLE),
                             asst(11, "msg_1", [srv("E1")]),
                             asst(100, "msg_1", [res("E1")]),
                             asst(101, "msg_1", [{"type": "text", "text": "go"}], "end_turn", 40)] + so_turn(200, "msg_2"), True)
    return c


def stall_truth(rows):
    calls, results = set(), set()
    for r in rows:
        for b in (r.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "server_tool_use" and b.get("name") == "advisor":
                calls.add(b["id"])
            if isinstance(b, dict) and b.get("type") == "advisor_tool_result":
                results.add(b["tool_use_id"])
    return {"calls": len(calls), "results": len(results), "stalled": len(calls - results)}


def build_stall(base):
    truth = {}
    for name, (rows, returned) in stall_cells().items():
        f = os.path.join(base, "proj", SESS, "subagents", "workflows", "wf_stall_" + name)
        os.makedirs(f)
        with open(os.path.join(f, "agent-a1.jsonl"), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(os.path.join(f, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:plan-structure", "model": "opus"}, fh)
        with open(os.path.join(f, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "launched"}) + "\n")
            fh.write(json.dumps({"type": "started", "key": "v2:k1", "agentId": "a1", "label": "stall-" + name}) + "\n")
            if returned:
                fh.write(json.dumps({"type": "result", "key": "v2:k1", "agentId": "a1", "result": {"ok": True}}) + "\n")
        truth[name] = (f, stall_truth(rows))
    return truth


# ── attempts 셀 (F-387) ──────────────────────────────────────────────────────
R = 55000  # 재개 시도 시작(초) — 1차 시도 뒤 약 15시간 공백(노트북 수면 · 다음 날 재개 꼴)
ROLES = {
    "L1-full": "설계자 — 이 과제의 계획을 **혼자** 끝낸다. 방향 판정·영향 범위·",
    "L1-edge": "경계 케이스 적대자 — 이 접근이 **어디서 깨지는가**만 판다.",
    "L1-impact": "영향 범위 + 아키텍처 검증자 — **이 변경이 어디까지 퍼지는가**와",
    "L2-merge": "통합자 — 적대 렌즈와 영향·아키 렌즈의 발견을 기존 계획에",
}
PARALLEL = ("L1-full", "L1-edge", "L1-impact")
SERIAL = ("L2-merge",)
KEY = {s: "v2:k-" + s.lower() for s in ROLES}


def attempt_cells():
    """셀 → (agents{id: (stage, first_s, last_s, returned)}, journal 순서, 기대 모호 코드 또는 None).
    모호 셀은 각각 **한 조건만** 맞게 짰다(다른 조건은 구성상 성립하지 않는다)."""
    c = {}
    # 같은 key 실패 1 + 재개 1 (실 사례 꼴: 렌즈 3개가 결과 없이 실패 → 같은 runId 로 재개 → 병합)
    ag = {"a1": ("L1-full", 0, 6870, False), "a2": ("L1-edge", 0, 3810, False), "a3": ("L1-impact", 0, 6869, False),
          "a4": ("L1-full", R, R + 1482, True), "a5": ("L1-impact", R, R + 1214, True), "a6": ("L1-edge", R, R + 1122, True),
          "a7": ("L2-merge", R + 1485, R + 2215, True)}
    j = [("started", "a1"), ("started", "a2"), ("started", "a3"),
         ("failed", "a2"), ("failed", "a3"), ("failed", "a1"),
         ("started", "a4"), ("started", "a5"), ("started", "a6"),
         ("result", "a6"), ("result", "a5"), ("result", "a4"),
         ("started", "a7"), ("result", "a7")]
    c["same_key_resume"] = (ag, j, None)
    # 여러 key — 일부 성공(L1-full 결과) · 일부 실패 뒤 재개(성공 key 는 다시 시작하지 않고 결과 재사용)
    ag2 = {"a1": ("L1-full", 0, 1800, True), "a2": ("L1-edge", 0, 3600, False), "a3": ("L1-impact", 0, 6000, False),
           "a4": ("L1-edge", R, R + 1200, True), "a5": ("L1-impact", R, R + 1500, True),
           "a6": ("L2-merge", R + 1510, R + 2110, True)}
    j2 = [("started", "a1"), ("started", "a2"), ("started", "a3"),
          ("result", "a1"), ("failed", "a2"), ("failed", "a3"),
          ("started", "a4"), ("started", "a5"), ("result", "a4"), ("result", "a5"),
          ("started", "a6"), ("result", "a6")]
    c["partial_reuse"] = (ag2, j2, None)
    # 대조 — failed 없는 단일 시도: wall 은 전 agent min~max(기존 정의 그대로)
    ag3 = {"a1": ("L1-full", 0, 1500, True), "a2": ("L1-edge", 0, 1100, True), "a3": ("L1-impact", 0, 1300, True),
           "a4": ("L2-merge", 1510, 2200, True)}
    j3 = [("started", "a1"), ("started", "a2"), ("started", "a3"), ("result", "a2"), ("result", "a3"), ("result", "a1"),
          ("started", "a4"), ("result", "a4")]
    c["single_attempt"] = (ag3, j3, None)
    # 모호 ① — failed 뒤 첫 started 가 실패 key 재기동이 아니다(실패를 넘기고 다음 stage 로 간 것과 재개를 못 가른다)
    ag4 = {"a1": ("L1-full", 0, 1500, True), "a2": ("L1-edge", 0, 900, False), "a3": ("L2-merge", R, R + 700, True)}
    j4 = [("started", "a1"), ("started", "a2"), ("result", "a1"), ("failed", "a2"), ("started", "a3"), ("result", "a3")]
    c["ambiguous_not_restart"] = (ag4, j4, "resume-unproven")
    # 모호 ② — 마지막 failed 뒤 started 가 없다(재개 없이 실패로 끝남)
    ag5 = {"a1": ("L1-full", 0, 6870, False), "a2": ("L1-edge", 0, 3810, False), "a3": ("L1-impact", 0, 6869, False)}
    j5 = [("started", "a1"), ("started", "a2"), ("started", "a3"), ("failed", "a2"), ("failed", "a3"), ("failed", "a1")]
    c["ambiguous_no_resume"] = (ag5, j5, "no-resume")
    # 모호 ③ — 경계 뒤에 같은 key 가 두 번 시작한다(failed 없는 재기동)
    ag6 = {"a1": ("L1-full", 0, 3000, False), "a2": ("L1-full", R, R + 1000, False), "a3": ("L1-full", R + 1000, R + 2000, True)}
    j6 = [("started", "a1"), ("failed", "a1"), ("started", "a2"), ("started", "a3"), ("result", "a3")]
    c["ambiguous_restart_after_boundary"] = (ag6, j6, "restart-after-boundary")
    # 모호 ④ — journal 에 없는 트랜스크립트(a9)가 있다(시도에 배치할 수 없다)
    c["ambiguous_unplaced"] = (dict(ag, a9=("L1-edge", 100, 200, False)), j, "unplaced")
    return c


def transcript(stage, first, last, returned):
    rows = [{"type": "user", "timestamp": ts(first),
             "message": {"role": "user", "content": "[Workflow harness — computed task]\n[역할] " + ROLES[stage]}},
            {"type": "assistant", "timestamp": ts(first + 5),
             "message": {"id": "msg_1", "stop_reason": "tool_use", "usage": {"output_tokens": 30},
                         "content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {}}]}},
            {"type": "user", "timestamp": ts(first + 6),
             "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "r1", "content": "x"}]}}]
    if returned:
        rows.append({"type": "assistant", "timestamp": ts(last - 1),
                     "message": {"id": "msg_2", "stop_reason": "tool_use", "usage": {"output_tokens": 60},
                                 "content": [{"type": "tool_use", "id": "so1", "name": "StructuredOutput", "input": {}}]}})
        rows.append({"type": "user", "timestamp": ts(last),
                     "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "so1", "content": "ok"}]}})
    else:
        rows.append({"type": "assistant", "timestamp": ts(last),
                     "message": {"id": "msg_2", "content": [{"type": "text", "text": "working"}]}})
    return rows


def attempt_truth(ag, j, amb):
    """정답 — 경계 = 마지막 failed 뒤 첫 started · 경계 앞 결과를 재사용한 key 는 wall · 크리티컬 패스 밖."""
    span = lambda ids: (max(ag[a][2] for a in ids) - min(ag[a][1] for a in ids)) if ids else None
    if amb:
        return {"ambiguous": amb, "n_agents": len(ag)}
    if not any(e[0] == "failed" for e in j):
        after, boundary = list(ag), 0
    else:
        last_failed = max(i for i, e in enumerate(j) if e[0] == "failed")
        boundary = next(i for i, e in enumerate(j) if i > last_failed and e[0] == "started")
        after = [e[1] for e in j[boundary:] if e[0] == "started"]
    # 재개 경계 수 = failed 뒤에 처음 오는 started 의 수(실패 시도 수 — 이 셀들에서는 1)
    failed_attempts, flag = 0, False
    for e in j:
        if e[0] == "started":
            failed_attempts += flag
            flag = False
        elif e[0] == "failed":
            flag = True
    keys_after = {KEY[ag[a][0]] for a in after}
    reused = sorted(e[1] for e in j[:boundary] if e[0] == "result" and KEY[ag[e[1]][0]] not in keys_after)
    before = sorted({e[1] for e in j[:boundary] if e[0] == "started"})
    crit = sum(ag[a][2] - ag[a][1] for a in after if ag[a][0] in SERIAL)
    par = [ag[a][2] - ag[a][1] for a in after if ag[a][0] in PARALLEL]
    crit += max(par) if par else 0
    return {"ambiguous": None, "wall": float(span(after)), "critical_path": float(crit), "failed_attempts": failed_attempts,
            "reused_agents": reused, "reused_span": span(reused), "failed_span": span(before), "n_agents": len(ag)}


def build_attempts(base):
    truth = {}
    for name, (ag, j, amb) in attempt_cells().items():
        f = os.path.join(base, "proj", SESS, "subagents", "workflows", "wf_att_" + name)
        os.makedirs(f)
        for a, (stage, first, last, returned) in ag.items():
            with open(os.path.join(f, "agent-%s.jsonl" % a), "w", encoding="utf-8") as fh:
                for r in transcript(stage, first, last, returned):
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            with open(os.path.join(f, "agent-%s.meta.json" % a), "w", encoding="utf-8") as fh:
                json.dump({"agentType": "fz:plan-structure", "model": "opus"}, fh)
        with open(os.path.join(f, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "launched"}) + "\n")
            for t, a in j:
                ev = {"type": t, "key": KEY[ag[a][0]], "agentId": a}
                if t == "started":
                    ev.update(label="lean2-" + ag[a][0].split("-")[1],
                              phase="생산+적대+영향 (동시 3)" if ag[a][0] in PARALLEL else "델타 병합")
                if t == "result":
                    ev["result"] = {"plan": "x" * 40}
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        truth[name] = (f, attempt_truth(ag, j, amb))
    return truth


# ── 판독 · 대조 ──────────────────────────────────────────────────────────────
def cli(script, *args):
    p = subprocess.run([sys.executable, "-B", script] + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=120)
    out = (p.stdout or b"").decode("utf-8", "replace")
    if "Traceback (most recent call last)" in out:
        raise RuntimeError("대상 CLI traceback:\n" + out)
    return out


def near(a, b):
    return a is not None and b is not None and abs(a - b) <= TOL


def check_stall(m, script, truth, tags):
    for name, (folder, t) in truth.items():
        wf = m.read_wf(folder)
        bad = []
        if wf.get("advisor") != t["results"]:
            bad.append("advisor-changed")   # 기존 열은 결과 기반 · tool_use_id 중복 제거 의미 그대로
        if "advisor_stalled" not in wf:
            bad.append("advisor_stalled-missing")
        elif wf["advisor_stalled"] != t["stalled"]:
            bad.append("advisor_stalled-mismatch")
        if "advisor_calls" not in wf:
            bad.append("advisor_calls-missing")
        elif wf["advisor_calls"] != t["calls"]:
            bad.append("advisor_calls-mismatch")
        det = cli(script, "--wf", folder)
        row = cli(script, "--wf", folder, "--row")
        if not re.search(r"\badvisor_stalled=%d\b" % t["stalled"], det) or not re.search(r"\badvisor_stalled %d\b" % t["stalled"], row):
            bad.append("advisor_stalled-missing" if "advisor_stalled" not in det + row else "advisor_stalled-mismatch")
        got = "advisor=%s calls=%s stalled=%s" % (wf.get("advisor"), wf.get("advisor_calls", "(없음)"), wf.get("advisor_stalled", "(없음)"))
        report(name, "truth(calls=%d results=%d stalled=%d)" % (t["calls"], t["results"], t["stalled"]), got, bad, tags)


def cell_wall(text, row):
    if row:
        mm = re.search(r"^\| N \| DATE \| \d+ \| \d+ \| \d+ \| 0 \| ([^|]+?) \|", text, re.M)
    else:
        mm = re.search(r"^wf \S+  agents=\d+  wall=(\S+)  critical_path=", text, re.M)
    return mm.group(1) if mm else None


def wall_text_ok(txt, want, row):
    if txt is None:
        return False
    if want is None:
        return txt == "UNRUN"
    try:
        return abs(float(txt.rstrip("s")) - want) <= TOL
    except ValueError:
        return False


def check_attempts(m, script, truth, tags):
    for name, (folder, t) in truth.items():
        wf = m.read_wf(folder)
        bad = []
        if wf.get("n_agents") != t["n_agents"]:
            bad.append("agents-changed")   # agent 수는 전 시도 그대로(완주 오라클 · ab 원장 대조가 이 수를 쓴다)
        det = cli(script, "--wf", folder)
        row = cli(script, "--wf", folder, "--row")
        if t["ambiguous"]:
            want_wall = None
            if wf.get("wall") is not None or wf.get("critical_path") is not None:
                bad.append("attempt-wall-mismatch")   # 모호 경계인데 값을 냈다 — UNRUN 이어야 한다
            amb = wf.get("attempt_ambiguous")
            if amb is None and "attempt_ambiguous" not in wf:
                bad.append("attempt-fields-missing")
            elif not (isinstance(amb, str) and amb.startswith(t["ambiguous"])):
                bad.append("attempt-unrun-reason-mismatch")
            if wf.get("failed_attempts") is not None:
                bad.append("attempt-failed-attempts-mismatch")
            want = "UNRUN(%s)" % t["ambiguous"]
        else:
            want_wall = t["wall"]
            if not near(wf.get("wall"), t["wall"]):
                bad.append("attempt-wall-mismatch")
            if not near(wf.get("critical_path"), t["critical_path"]):
                bad.append("attempt-critical-path-mismatch")
            if any(k not in wf for k in ("failed_attempts", "reused_agents", "reused_span", "failed_span", "attempt_ambiguous")):
                bad.append("attempt-fields-missing")
            else:
                if wf["failed_attempts"] != t["failed_attempts"] or wf["attempt_ambiguous"] is not None:
                    bad.append("attempt-failed-attempts-mismatch")
                if wf["reused_agents"] != t["reused_agents"] or not (
                        (wf["reused_span"] is None and t["reused_span"] is None) or near(wf["reused_span"], t["reused_span"])):
                    bad.append("attempt-reused-mismatch")
                if not ((wf["failed_span"] is None and t["failed_span"] is None) or near(wf["failed_span"], t["failed_span"])):
                    bad.append("attempt-failed-span-mismatch")
            if t["failed_attempts"] and "failed_attempts %d" % t["failed_attempts"] not in row:
                bad.append("attempt-fields-missing")   # --row 비고 칸에 실패 시도 표시
            want = "wall=%.1f crit=%.1f failed_attempts=%d reused=%s" % (
                t["wall"], t["critical_path"], t["failed_attempts"], ",".join(t["reused_agents"]) or "-")
        if not wall_text_ok(cell_wall(det, False), want_wall, False) or not wall_text_ok(cell_wall(row, True), want_wall, True):
            bad.append("attempt-wall-mismatch")       # 상세 · --row 의 wall 칸도 같은 값이어야 한다
        got = "wall=%s crit=%s failed_attempts=%s reused=%s ambiguous=%s | 상세 wall=%s · row wall=%s" % (
            wf.get("wall"), wf.get("critical_path"), wf.get("failed_attempts", "(없음)"),
            ",".join(wf.get("reused_agents") or []) or "-", wf.get("attempt_ambiguous", "(없음)"),
            cell_wall(det, False), cell_wall(row, True))
        report(name, want, got, bad, tags)


def report(name, want, got, bad, tags):
    RAN.append(name)
    bad = sorted(set(bad))
    print("CELL %-34s %s" % (name, "ok" if not bad else "FAIL"))
    print("     want %s" % want)
    print("     got  %s" % got)
    for b in bad:
        print("METRICS-FAIL:%s cell=%s" % (b, name))
    tags.extend(bad)


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ("stall", "attempts", "all"):
        print("UNRUN: usage — cells.py <트리> <stall|attempts|all>")
        return 2
    tree, which = sys.argv[1], sys.argv[2]
    script = os.path.join(tree, "scripts", "fz_wf_metrics.py")
    if not os.path.isfile(script):
        print("UNRUN: 대상 계측기 없음 — %s" % script)
        return 2
    sys.dont_write_bytecode = True   # 대상 트리에 __pycache__ 를 남기지 않는다
    spec = importlib.util.spec_from_file_location("fz_wf_metrics_target", script)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception:
        traceback.print_exc()
        print("UNRUN: 대상 계측기 import 실패 — %s" % script)
        return 2
    base = tempfile.mkdtemp(prefix="fz-advisor-stall-")
    tags = []
    try:
        print("tree=%s cells=%s" % (tree, which))
        if which in ("stall", "all"):
            check_stall(m, script, build_stall(base), tags)
        if which in ("attempts", "all"):
            check_attempts(m, script, build_attempts(base), tags)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    want = [n for k in ("stall", "attempts") if which in (k, "all") for n in EXPECTED[k]]
    if RAN != want:
        print("METRICS-FAIL:cell-set-mismatch 없음=%s 뜻밖=%s" % (sorted(set(want) - set(RAN)), sorted(set(RAN) - set(want))))
        tags.append("cell-set-mismatch")
    cells_line = "CELLS n=%d ran=%s" % (len(RAN), ",".join(RAN) or "-")
    if tags:
        print("SUMMARY METRICS-FAIL %d건 — %s" % (len(tags), " ".join(sorted(set(tags)))))
        print(cells_line)
        return 1
    print("ADVISOR-STALL-ATTEMPTS-OK" if which == "all" else "SUBSET-OK cells=%s (전 셀 통과 줄은 인자 없이 돌 때만)" % which)
    print(cells_line)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()   # 단언기 · 대상 고장은 2 — 단언 실패(1)와 섞지 않는다
        sys.stdout.flush()
        os._exit(2)
